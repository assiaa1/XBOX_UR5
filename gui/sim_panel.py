# gui/sim_panel.py
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.sim_worker import SimWorker


class SimPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.lbl = QLabel("(simulation)")
        self.lbl.setMinimumSize(400, 300)

        self._zone_inside = {}
        self.on_zone_enter = None  # callable(name: str) -> None


        # Worker thread (PyBullet)
        self.worker = SimWorker(self, fps=30)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.zone_entered.connect(self._on_zone_entered)

        self.worker.start()

        # Timer: auto-sync RTDE → PyBullet
        self.timer = QTimer(self)
        self.timer.setInterval(33)  # ~30 Hz
        self.timer.timeout.connect(self._sync_from_rtde)
        self.timer.start()

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl)

        self._joint_provider = None  # () -> list[float] (rad)

        # Auto-load UR10
        self._autoload_default_ur10()

    def _on_zone_entered(self, name: str):
        if callable(self.on_zone_enter):
            self.on_zone_enter(name)


    def check_trigger_zones(self):
        ee = self.sim.get_ee_pos()
        if ee is None:
            return

        x, y, z = ee
        for zone in self.sim.trigger_zones:
            inside = (zone.aabb_min[0] <= x <= zone.aabb_max[0] and
                    zone.aabb_min[1] <= y <= zone.aabb_max[1] and
                    zone.aabb_min[2] <= z <= zone.aabb_max[2])

            prev = self._zone_inside.get(zone.name, False)
            self._zone_inside[zone.name] = inside

            if inside and not prev and callable(self.on_zone_enter):
                self.on_zone_enter(zone.name)


    def set_joint_provider(self, provider_callable):
        """provider_callable: () -> list[float] (rad)"""
        self._joint_provider = provider_callable

    def _autoload_default_ur10(self):
        here = Path(__file__).resolve()
        root = here.parent.parent
        ur10 = root / "ur_description" / "urdf" / "ur5.urdf"
        if ur10.exists():
            self.worker.load_robot(str(ur10))

    def _sync_from_rtde(self):
        if not self._joint_provider:
            return
        try:
            q = self._joint_provider()
            if q is not None and len(q) >= 6:
                self.worker.set_joints(q[:6])
        except Exception:
            pass

    def _on_frame(self, qimg):
        self.lbl.setPixmap(QPixmap.fromImage(qimg))

    def stop(self):
        try:
            self.timer.stop()
            self.worker.stop()
        except Exception:
            pass

    def closeEvent(self, e):
        self.stop()
        return super().closeEvent(e)
