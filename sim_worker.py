# gui/sim_worker.py
from __future__ import annotations

import traceback
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QImage

from PyQt6.QtCore import pyqtSignal

from .pybullet_sim import PyBulletSim
import numpy as np

class SimWorker(QThread):
    frame_ready = pyqtSignal(QImage)
    zone_entered = pyqtSignal(str)

    def __init__(self, parent=None, fps: int = 30):
        super().__init__(parent)
        self.sim = PyBulletSim()
        self._running = True
        self._fps_ms = max(1, int(1000 / max(1, fps)))

        self._q = None
        self._joint_provider = None
        self._mtx = QMutex()
        self._zone_inside = {}  # dict[str,bool]


    # ---------- API UI ----------

    def load_robot(self, urdf_path: str):
        with QMutexLocker(self._mtx):
            self.sim.reset()
            self.sim.load_robot(urdf_path)

    def set_joints(self, q_rad):
        if q_rad is None:
            return
        with QMutexLocker(self._mtx):
            self._q = list(q_rad)

    def set_joint_provider(self, provider):
        """provider: callable -> list[float] | None"""
        self._joint_provider = provider

    # ---------- Thread ----------

    def run(self):
        while self._running:
            try:
                # 1) récupérer joints
                q = None
                if self._joint_provider:
                    try:
                        q = self._joint_provider()
                    except Exception:
                        q = None
                else:
                    with QMutexLocker(self._mtx):
                        q = None if self._q is None else list(self._q)

                # 2) appliquer joints si dispo
                if q is not None:
                    self.sim.set_joints(q)

                # 3) step + render
                self.sim.step()
                

                img = self.sim.render_rgb()
                img = np.ascontiguousarray(img, dtype=np.uint8)
                h, w, _ = img.shape
                qimg = QImage(
                    img.data, w, h, 3 * w, QImage.Format.Format_RGB888
                ).copy()
                self.frame_ready.emit(qimg)
                self._check_trigger_zones()
                img = self.sim.render_rgb()
            except Exception:
                traceback.print_exc()

            self.msleep(self._fps_ms)

    def _check_trigger_zones(self):
    # nécessite: self._zone_inside dict et self.sim.trigger_zones + self.sim.get_ee_pos()
        ee = self.sim.get_ee_pos()
        if ee is None:
            return

        x, y, z = ee
        for zone in getattr(self.sim, "trigger_zones", []):
            inside = (
                zone.aabb_min[0] <= x <= zone.aabb_max[0] and
                zone.aabb_min[1] <= y <= zone.aabb_max[1] and
                zone.aabb_min[2] <= z <= zone.aabb_max[2]
            )

            prev = self._zone_inside.get(zone.name, False)
            self._zone_inside[zone.name] = inside

            # Déclenchement uniquement à l'entrée
            if inside and not prev:
                self.zone_entered.emit(zone.name)



    def set_ee_link(self, link_index: int):
        with QMutexLocker(self._mtx):
            self.sim.set_ee_link(link_index)

    def add_trigger_zone(self, name: str, aabb_min, aabb_max, rgba=(0, 1, 0, 0.15)):
        with QMutexLocker(self._mtx):
            self.sim.add_trigger_zone(name, aabb_min, aabb_max, rgba=rgba)


    def stop(self):
        self._running = False
        self.wait(1500)
        try:
            self.sim.disconnect()
        except Exception:
            pass
