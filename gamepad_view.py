# gui/gamepad_view.py
from __future__ import annotations
from dataclasses import dataclass, field
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from PyQt6.QtWidgets import QWidget


@dataclass
class GamepadState:
    # boutons (bool)
    a: bool = False  # deadman
    b: bool = False
    x: bool = False
    y: bool = False
    lb: bool = False
    rb: bool = False

    # sticks (-1..1)
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0

    # dpad (hat)
    dpad: tuple[int, int] = (0, 0)  # (x,y) in {-1,0,1}
    # triggers (0..1)
    lt: float = 0.0
    rt: float = 0.0

    deadman: bool = False
    deadman_btn: int | None = None
    mode: str = "cartesian"



class GamepadView(QWidget):
    """
    Schéma simple noir/blanc.
    - touches pressées: vert
    - deadman (A): rouge si NON pressé, vert si pressé
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._st = GamepadState()
        self.setMinimumSize(360, 220)

    def set_state(self, st: GamepadState):
        self._st = st
        self.update()

    def _fill_for(self, pressed: bool, *, is_deadman: bool = False) -> QColor:
        if is_deadman:
            return QColor("#00C853") if pressed else QColor("#D50000")  # vert / rouge
        return QColor("#00C853") if pressed else QColor("#FFFFFF")     # vert / blanc

    def paintEvent(self, _):
        st = self._st
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # styles
        outline_pen = QPen(QColor("#000000"), 2)
        thin_pen = QPen(QColor("#000000"), 1)

        # --- Corps manette (forme simplifiée) ---
        p.setPen(outline_pen)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        body_x = int(w * 0.05)
        body_y = int(h * 0.15)
        body_w = int(w * 0.90)
        body_h = int(h * 0.70)
        p.drawRoundedRect(body_x, body_y, body_w, body_h, 40, 40)

        # --- Poignées (2 ronds) ---
        grip_r = int(min(w, h) * 0.18)
        p.drawEllipse(int(w * 0.15) - grip_r, int(h * 0.70) - grip_r, 2*grip_r, 2*grip_r)
        p.drawEllipse(int(w * 0.85) - grip_r, int(h * 0.70) - grip_r, 2*grip_r, 2*grip_r)

        # helpers
        def circle(cx, cy, r, fill: QColor, label: str = ""):
            p.setPen(outline_pen)
            p.setBrush(QBrush(fill))
            p.drawEllipse(int(cx - r), int(cy - r), int(2*r), int(2*r))
            if label:
                p.setPen(QPen(QColor("#000000"), 2))
                p.drawText(int(cx - r), int(cy - r), int(2*r), int(2*r),
                           int(Qt.AlignmentFlag.AlignCenter), label)

        def rect(x, y, rw, rh, fill: QColor, label: str = ""):
            p.setPen(outline_pen)
            p.setBrush(QBrush(fill))
            p.drawRoundedRect(int(x), int(y), int(rw), int(rh), 8, 8)
            if label:
                p.setPen(QPen(QColor("#000000"), 1))
                p.drawText(int(x), int(y), int(rw), int(rh),
                           int(Qt.AlignmentFlag.AlignCenter), label)

        # --- Boutons ABXY (droite) ---
        r_btn = int(min(w, h) * 0.06)
        cx = w * 0.78
        cy = h * 0.48
        circle(cx,         cy,         r_btn, self._fill_for(st.b), "B")
        circle(cx - 2*r_btn, cy,         r_btn, self._fill_for(st.x), "X")
        circle(cx - r_btn,   cy - r_btn,  r_btn, self._fill_for(st.y), "Y")
        # A = deadman important
        circle(cx - r_btn,   cy + r_btn,  r_btn, self._fill_for(st.a, is_deadman=True), "A")

        # --- LB / RB (haut) ---
        trig_w = w * 0.18
        trig_h = h * 0.10
        rect(w * 0.18, h * 0.18, trig_w, trig_h, self._fill_for(st.lb), "LB")
        rect(w * 0.64, h * 0.18, trig_w, trig_h, self._fill_for(st.rb), "RB")

        # --- Triggers LT / RT (barres) ---
        # on affiche un petit niveau (0..1) en noir
        p.setPen(thin_pen)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        bar_w = w * 0.18
        bar_h = h * 0.05
        x_lt, y_lt = w * 0.18, h * 0.10
        x_rt, y_rt = w * 0.64, h * 0.10
        p.drawRect(int(x_lt), int(y_lt), int(bar_w), int(bar_h))
        p.drawRect(int(x_rt), int(y_rt), int(bar_w), int(bar_h))
        p.fillRect(int(x_lt), int(y_lt), int(bar_w * max(0.0, min(1.0, st.lt))), int(bar_h), QBrush(QColor("#000000")))
        p.fillRect(int(x_rt), int(y_rt), int(bar_w * max(0.0, min(1.0, st.rt))), int(bar_h), QBrush(QColor("#000000")))
        p.drawText(int(x_lt), int(y_lt - 2), int(bar_w), 14, int(Qt.AlignmentFlag.AlignLeft), "LT")
        p.drawText(int(x_rt), int(y_rt - 2), int(bar_w), 14, int(Qt.AlignmentFlag.AlignLeft), "RT")

        # --- D-pad (gauche) ---
        dpad_cx = w * 0.25
        dpad_cy = h * 0.50
        s = min(w, h) * 0.05
        # Up/Down/Left/Right rectangles
        dx, dy = st.dpad
        rect(dpad_cx - s, dpad_cy - 2*s, 2*s, 2*s, self._fill_for(dy == 1), "↑")
        rect(dpad_cx - s, dpad_cy + 0*s, 2*s, 2*s, self._fill_for(dy == -1), "↓")
        rect(dpad_cx - 2*s, dpad_cy - s, 2*s, 2*s, self._fill_for(dx == -1), "←")
        rect(dpad_cx + 0*s, dpad_cy - s, 2*s, 2*s, self._fill_for(dx == 1), "→")
        rect(dpad_cx - s, dpad_cy - s, 2*s, 2*s, QColor("#FFFFFF"), "")

        deadman_ok = st.deadman
        p.setPen(QPen(QColor("#000000"), 2))
        p.setBrush(QBrush(QColor("#00C853") if deadman_ok else QColor("#D50000")))
        p.drawRoundedRect(int(w*0.55), int(h*0.86), int(w*0.40), 22, 8, 8)
        p.setPen(QPen(QColor("#000000") if deadman_ok else QColor("#FFFFFF"), 1))
        label = "DEADMAN"
        if st.deadman_btn is not None:
            label += f" (BTN {st.deadman_btn})"
        p.drawText(int(w*0.55), int(h*0.86), int(w*0.40), 22,
                int(Qt.AlignmentFlag.AlignCenter), label)

        p.end()
