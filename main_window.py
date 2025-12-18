# gui/main_window.py
import math
import numpy as np
from PyQt6.QtWidgets import QSplitter, QTabWidget, QPushButton, QLabel, QVBoxLayout, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer   
from core.models import SpeedJointProfile, JointLimits
from core.motion import deg2rad_list, rad2deg_list 
from core.rtde_client import RTDEClient
from .widgets import JointGroup
from .sim_panel import SimPanel
from core.gamepad_teleop import XboxTeleop
import time
import pygame
from gui.gamepad_view import GamepadView
from gui.gamepad_poller import GamepadPoller
from gui.gamepad_info import GamepadInfoPanel

class MainWindow(QWidget):
    def __init__(self, rtde_client, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Robot Control Application")
        self.setGeometry(100, 100, 1280, 720)

        # Interface
        self.joint_limits = JointLimits(
            min_rad=[math.radians(-360)]*6,
            max_rad=[math.radians( 360)]*6,
        )

        self.rtde = rtde_client
        self.teleop_enabled = False
        self._teleop = None
        self._last_speedl_ts = 0.0

        # --- GAMEPAD VIEW + INFO (UNIQUE) ---
        self.gamepad_view = GamepadView()
        self.gamepad_info = GamepadInfoPanel()

        self.gamepad_poller = GamepadPoller(hz=60, parent=self)
        if self.gamepad_poller.is_ok():
            self.gamepad_poller.stateChanged.connect(self.gamepad_view.set_state)
            self.gamepad_poller.stateChanged.connect(self.gamepad_info.set_state)
            self.gamepad_poller.start()
        else:
            self.gamepad_view.setToolTip("Aucune manette détectée (pygame).")


        # JOINTS
        self.joint_group = JointGroup("Joints (deg)")
        # Connecter le signal jogJointRequested à la méthode de mise à jour des joints

        # Récupérer les positions actuelles du robot et initialiser les sliders
        if self.rtde:
            joint_state = self.rtde.get_q()
            current_values_deg = [q * (180 / np.pi) for q in joint_state.q]  # Convertir rad en deg
            self.joint_group.set_values_deg(current_values_deg)


       # --- SIMULATION (UNIQUE) ---
        self.sim_panel = SimPanel()
        # 1) Choisir le link TCP (à ajuster)
        self.sim_panel.worker.set_ee_link(6)

        # 2) Créer 2 zones (coordonnées à adapter)
        self.sim_panel.worker.add_trigger_zone(
            "ZONE_1",
            aabb_min=(0.30, -0.20, 0.05),
            aabb_max=(0.50,  0.00, 0.30),
            rgba=(0, 1, 0, 0.15)
        )
        self.sim_panel.worker.add_trigger_zone(
            "ZONE_2",
            aabb_min=(0.30, 0.10, 0.05),
            aabb_max=(0.50, 0.30, 0.30),
            rgba=(0, 0, 1, 0.15)
        )

        # 3) Callback entrée zone
        def _on_zone_enter(name: str):
            print(f"[TRIGGER] Enter {name}")
            if name == "ZONE_1":
                self.launch_program_zone1()
            elif name == "ZONE_2":
                self.launch_program_zone2()

        self.sim_panel.on_zone_enter = _on_zone_enter

        if self.rtde:
            self.sim_panel.set_joint_provider(self._safe_joint_provider)

        # ---- Colonne droite (manette + infos)
        right_panel = QWidget()
        right_lay = QVBoxLayout(right_panel)
        right_lay.addWidget(self.gamepad_view)
        right_lay.addWidget(self.gamepad_info)
        right_lay.addStretch(1)

        # ---- Splitter horizontal : PyBullet | Manette
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.sim_panel)
        split.addWidget(right_panel)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        # --- Boutons (sans le schéma manette)
        self.btn_moveJ = QPushButton("MoveJ to sliders")
        self.btn_read_q = QPushButton("Read Joints")
        self.btn_gamepad = QPushButton("Gamepad: OFF")
        self.btn_gamepad.setCheckable(True)
        self.lbl_q = QLabel("q: n/a")

        self.btn_moveJ.clicked.connect(self.on_moveJ)
        self.btn_read_q.clicked.connect(self.on_read_q)
        self.btn_gamepad.toggled.connect(self.on_gamepad_toggle)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_moveJ)
        buttons.addWidget(self.btn_read_q)
        buttons.addWidget(self.btn_gamepad)

         # --- Tabs ---
        tabs = QTabWidget()

        # Tab 1: Simulation (PyBullet + Manette)
        tab_sim = QWidget()
        tab_sim_lay = QVBoxLayout(tab_sim)
        tab_sim_lay.addWidget(split)
        tabs.addTab(tab_sim, "Simulation")

        # Tab 2: Joints (Sliders)
        tab_joints = QWidget()
        tab_joints_lay = QVBoxLayout(tab_joints)
        tab_joints_lay.addWidget(self.joint_group)
        tabs.addTab(tab_joints, "Joints")

        # --- Layout main ---
        lay = QVBoxLayout(self)
        lay.addLayout(buttons)
        lay.addWidget(self.lbl_q)
        lay.addWidget(tabs)


        # --- Gamepad teleop (polling) ---
        self._teleop: XboxTeleop | None = None
        self._teleop_timer = QTimer(self)
        self._teleop_timer.setInterval(20)  # 50 Hz
        self._teleop_timer.timeout.connect(self._teleop_tick)
        self._teleop_timer.start()

    def on_moveJ(self):
        qd = self.joint_group.values_deg()
        q = deg2rad_list(qd)
        prof = SpeedJointProfile(**self.speed_joint_group.values())
        self.rtde.move_j(q, prof, async_=True)
        print(f"Moving to joint positions (deg): {qd}")

    def on_read_q(self):
        joint_state = self.rtde.get_q()
        qd = rad2deg_list(joint_state.q)
        self.lbl_q.setText(f"q (deg): {', '.join(f'{v:.1f}' for v in qd)}")

    def on_gamepad_toggle(self, enabled: bool):
        self.teleop_enabled = enabled

        if not enabled:
            self.btn_gamepad.setText("Gamepad: OFF")
            self._teleop = None
            if self.rtde:
                try:
                    self.rtde.speed_stop(10.0)
                except Exception:
                    pass
            return

        # enabled
        self.btn_gamepad.setText("Gamepad: ON")
        if self._teleop is None:
            try:
                self._teleop = XboxTeleop(hz=50.0)
                self.lbl_q.setText("Gamepad ON — hold A (deadman)")
            except Exception as e:
                self.btn_gamepad.setChecked(False)
                self.btn_gamepad.setText("Gamepad: OFF")
                self.lbl_q.setText(f"Gamepad init failed: {e}")
                self._teleop = None
                self.teleop_enabled = False


    def _safe_joint_provider(self):
        if not self.rtde:
            return None
        try:
            return self.rtde.get_q().q
        except Exception:
            return None


    def _teleop_tick(self):
        
        try:
            pygame.event.pump()
        except Exception:
            pass

        if not self.teleop_enabled or not self.rtde or not self._teleop:
            return


        # Safety: si protective stop / e-stop -> coupe la téléop + stop
        try:
            if self.rtde.rtde_r and (
                self.rtde.rtde_r.isProtectiveStopped() or self.rtde.rtde_r.isEmergencyStopped()
            ):
                try:
                    self.rtde.speed_stop(10.0)
                except Exception:
                    pass
                self.teleop_enabled = False
                self.btn_gamepad.setChecked(False)
                self.lbl_q.setText("Protective/E-Stop: gamepad OFF")
                return
        except Exception:
            pass

        # Watchdog: si on n’a pas rafraîchi speedL récemment -> stop
        now = time.time()
        if (now - self._last_speedl_ts) > 0.10:
            try:
                self.rtde.speed_stop(10.0)
            except Exception:
                pass
            
        # Poll une seule fois
        try:
            cmd = self._teleop.poll()

        except Exception as e:
            print(f"[GAMEPAD] poll error: {e}")
            try:
                self.rtde.speed_stop(10.0)
            except Exception:
                pass
            self.teleop_enabled = False
            self.btn_gamepad.setChecked(False)
            return

        # Optionnel: afficher infos
        if cmd.kind == "speedL":
            if cmd.payload is None:
                try:
                    self.rtde.speed_stop(10.0)
                except Exception:
                    pass
                return

            try:
                self.rtde.speed_l(list(cmd.payload), a=0.2, t=0.02)
                self._last_speedl_ts = time.time()
            except Exception as e:
                print(f"[GAMEPAD] speedL failed: {e}")
                try:
                    self.rtde.speed_stop(10.0)
                except Exception:
                    pass
            return
        if cmd.kind == "stop":
            self.rtde.speed_stop(10.0)
            return

        if cmd.kind == "toggle_mode":
            # UI only (optionnel)
            return

        if cmd.kind == "gain":
            # UI only (optionnel)
            return

        if cmd.kind == "step_cart":
            dx, dy, dz = cmd.payload
            # -> moveL relatif (à toi selon ta méthode)
            return

        if cmd.kind == "step_joint":
            dq = cmd.payload
            # -> moveJ relatif
            return

        if cmd.kind == "speedL":
            self.rtde.speed_l(cmd.payload, 0.25, 0.03)
            return


    def on_fd_on(self):
        if self.rtde.freedrive_on():
            self._update_fd_status()

    def on_fd_off(self):
        if self.rtde.freedrive_off():
            self._update_fd_status()
    
    def update_joint(self, joint_index: int, delta_deg: float):
        current_values_deg = self.joint_group.values_deg()
        current_values_deg[joint_index] += delta_deg

        # Convertir les valeurs en radians et mettre à jour le robot
        current_values_rad = [deg * (np.pi / 180) for deg in current_values_deg]
        speed_profile = self.speed_joint_group.values()
        self.rtde.move_j(current_values_rad, SpeedJointProfile(**speed_profile))

    def closeEvent(self, e):

        try:
            self.gamepad_poller.stop()
        except Exception:
            pass

        try:
            # stop teleop
            if self.rtde:
                self.rtde.speed_stop(10.0)
            self.rtde.freedrive_off()
        except Exception:
            pass
        
        return super().closeEvent(e)