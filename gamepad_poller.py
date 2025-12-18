# gui/gamepad_poller.py
from __future__ import annotations
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
import pygame

from .gamepad_view import GamepadState

# mapping identique au script pygame :contentReference[oaicite:1]{index=1}
AX_LX = 0
AX_LY = 1
AX_RX = 2
AX_RY = 3
AX_LT = 4
AX_RT = 5


BTN_A = 0
BTN_B = 1
BTN_X = 2
BTN_Y = 3
BTN_LB = 4
BTN_RB = 5


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def trigger_to_01(raw: float) -> float:
    # même logique que ton script
    if raw < -0.05:
        return (raw + 1.0) * 0.5
    return clamp(raw, 0.0, 1.0)


class GamepadPoller(QObject):
    stateChanged = pyqtSignal(object)  # GamepadState

    def __init__(self, hz: int = 60, parent=None):
        super().__init__(parent)
        self._ok = False
        self._js = None

        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self._js = pygame.joystick.Joystick(0)
            self._js.init()
            self._ok = True

        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / hz))
        self._timer.timeout.connect(self._tick)
        self._deadman_btn = None
        self._was_y = False
        self._mode = "cartesian"


    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def is_ok(self) -> bool:
        return self._ok

    def _tick(self):
        if not self._ok or self._js is None:
            return

        pygame.event.pump()
        # auto-deadman: premier bouton pressé devient deadman
        if self._deadman_btn is None:
            for i in range(self._js.get_numbuttons()):
                if self._js.get_button(i):
                    self._deadman_btn = i
                    break

        deadman = False
        if self._deadman_btn is not None:
            deadman = bool(self._js.get_button(self._deadman_btn))

        y_now = bool(self._js.get_button(BTN_Y))
        if y_now and not self._was_y:
            self._mode = "joint" if self._mode == "cartesian" else "cartesian"
        self._was_y = y_now


        # axes sticks (souvent Xbox: 0,1,2,3)
        lx = self._js.get_axis(0) if self._js.get_numaxes() > 0 else 0.0
        ly = self._js.get_axis(1) if self._js.get_numaxes() > 1 else 0.0
        rx = self._js.get_axis(2) if self._js.get_numaxes() > 2 else 0.0
        ry = self._js.get_axis(3) if self._js.get_numaxes() > 3 else 0.0

        # triggers: souvent 4/5 sur pygame, sinon fallback 2/5
        ax_lt = 4 if self._js.get_numaxes() > 4 else 2
        ax_rt = 5 if self._js.get_numaxes() > 5 else 5

        st = GamepadState(
            a=bool(self._js.get_button(BTN_A)),
            b=bool(self._js.get_button(BTN_B)),
            x=bool(self._js.get_button(BTN_X)),
            y=y_now,
            lb=bool(self._js.get_button(BTN_LB)),
            rb=bool(self._js.get_button(BTN_RB)),
            dpad=self._js.get_hat(0) if self._js.get_numhats() > 0 else (0, 0),
            lt=trigger_to_01(self._js.get_axis(AX_LT)) if self._js.get_numaxes() > AX_LT else 0.0,
            rt=trigger_to_01(self._js.get_axis(AX_RT)) if self._js.get_numaxes() > AX_RT else 0.0,
            lx=self._js.get_axis(AX_LX) if self._js.get_numaxes() > AX_LX else 0.0,
            ly=self._js.get_axis(AX_LY) if self._js.get_numaxes() > AX_LY else 0.0,
            rx=self._js.get_axis(AX_RX) if self._js.get_numaxes() > AX_RX else 0.0,
            ry=self._js.get_axis(AX_RY) if self._js.get_numaxes() > AX_RY else 0.0,
            deadman=deadman,
            deadman_btn=self._deadman_btn,
            mode=self._mode,
        )


        self.stateChanged.emit(st)
