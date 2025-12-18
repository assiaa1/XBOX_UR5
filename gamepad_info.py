# gui/gamepad_info.py
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QGroupBox
from PyQt6.QtCore import Qt

from .gamepad_view import GamepadState

DEADZONE = 0.12
DEADMAN_RT = 0.10

def dz(x: float, deadzone: float = DEADZONE) -> float:
    return 0.0 if abs(x) < deadzone else x


class GamepadInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.lbl_deadman = QLabel("DEADMAN (RT): NO")
        self.lbl_deadman.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_deadman.setStyleSheet("font-weight:800; padding:6px; border:2px solid black;")

        # --- Aide statique (TES COMBOS)
        help_box = QGroupBox("Combos / commandes")
        help_lay = QVBoxLayout(help_box)
        self.lbl_help = QLabel(
            "Deadman = RT (à maintenir)\n\n"
            "Mode JOINTS:\n"
            "• Maintenir A:\n"
            "  - Stick gauche → J1\n"
            "  - Stick droit  → J2\n"
            "  - D-pad        → J3\n"
            "• Maintenir B:\n"
            "  - Stick gauche → J4\n"
            "  - Stick droit  → J5\n"
            "  - D-pad        → J6\n\n"
            "Mode CARTÉSIEN:\n"
            "• Maintenir X + D-pad:\n"
            "  - ←/→ : X\n"
            "  - ↑/↓ : Y\n"
            "• Z : Maintenir LT + Stick gauche (↑ = +Z, ↓ = -Z)\n"
        )
        self.lbl_help.setWordWrap(True)
        help_lay.addWidget(self.lbl_help)

        # --- Live
        live_box = QGroupBox("État temps réel")
        grid = QGridLayout(live_box)

        self.lbl_mode = QLabel("Mode: joints/cartesian (selon combos)")
        self.lbl_active = QLabel("Axes actifs: -")
        self.lbl_cmd = QLabel("Commande: -")

        grid.addWidget(self.lbl_mode,   0, 0, 1, 2)
        grid.addWidget(self.lbl_active, 1, 0, 1, 2)
        grid.addWidget(self.lbl_cmd,    2, 0, 1, 2)

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl_deadman)
        lay.addWidget(help_box)
        lay.addWidget(live_box)
        lay.addStretch(1)

    def set_state(self, st: GamepadState):
        # --- Deadman RT
        deadman_ok = st.deadman
        if deadman_ok:
            self.lbl_deadman.setText("DEADMAN (RT): OK")
            self.lbl_deadman.setStyleSheet(
                "font-weight:800; padding:6px; border:2px solid black; background:#00C853;"
            )
        else:
            self.lbl_deadman.setText("DEADMAN (RT): NO")
            self.lbl_deadman.setStyleSheet(
                "font-weight:800; padding:6px; border:2px solid black; background:#D50000; color:white;"
            )

        # --- Lecture inputs (avec deadzone)
        lx, ly = dz(st.lx), dz(st.ly)
        rx, ry = dz(st.rx), dz(st.ry)
        dx, dy = st.dpad

        # --- Détection mode/axes selon TES règles
        active = []
        cmd_lines = []

        # CARTÉSIEN : X maintenu + D-pad (X/Y) et LT + stick gauche (Z)
        cart_x = st.x and (dx != 0)
        cart_y = st.x and (dy != 0)
        cart_z = (st.lt > 0.10) and (abs(ly) > 0.0)  # ly<0 = stick haut généralement

        if cart_x or cart_y or cart_z:
            self.lbl_mode.setText("Mode: CARTÉSIEN")
            if cart_x:
                active.append("X")
                cmd_lines.append(f"X = {'+' if dx>0 else '-'}")
            if cart_y:
                active.append("Y")
                cmd_lines.append(f"Y = {'+' if dy>0 else '-'}")
            if cart_z:
                active.append("Z")
                # convention: stick haut (ly < 0) => +Z
                z_dir = "+" if (-ly) > 0 else "-"
                cmd_lines.append(f"Z = {z_dir} (LT + stick G)")

        else:
            # JOINTS : A ou B maintenu (groupes)
            joints_active = False

            if st.a:
                self.lbl_mode.setText("Mode: JOINTS (A)")
                # J1: stick gauche X (ou Y si tu préfères, ici on prend X)
                if abs(lx) > 0.0:
                    active.append("J1")
                    cmd_lines.append(f"J1 = {lx:+.2f} (stick G)")
                    joints_active = True
                # J2: stick droit X
                if abs(rx) > 0.0:
                    active.append("J2")
                    cmd_lines.append(f"J2 = {rx:+.2f} (stick D)")
                    joints_active = True
                # J3: dpad up/down (prioritaire) ou left/right (si tu veux)
                if dy != 0 or dx != 0:
                    active.append("J3")
                    sign = dy if dy != 0 else dx
                    cmd_lines.append(f"J3 = {'+' if sign>0 else '-'} (D-pad)")
                    joints_active = True

            elif st.b:
                self.lbl_mode.setText("Mode: JOINTS (B)")
                if abs(lx) > 0.0:
                    active.append("J4")
                    cmd_lines.append(f"J4 = {lx:+.2f} (stick G)")
                    joints_active = True
                if abs(rx) > 0.0:
                    active.append("J5")
                    cmd_lines.append(f"J5 = {rx:+.2f} (stick D)")
                    joints_active = True
                if dy != 0 or dx != 0:
                    active.append("J6")
                    sign = dy if dy != 0 else dx
                    cmd_lines.append(f"J6 = {'+' if sign>0 else '-'} (D-pad)")
                    joints_active = True

            else:
                self.lbl_mode.setText("Mode: - (aucun combo)")

        # --- Affichage
        self.lbl_active.setText("Axes actifs: " + (", ".join(active) if active else "-"))

        if not deadman_ok and active:
            self.lbl_cmd.setText("Commande: (deadman absent) → STOP")

        else:
            self.lbl_cmd.setText("Commande: " + (" | ".join(cmd_lines) if cmd_lines else "-"))
