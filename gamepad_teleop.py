"""Xbox (pygame) teleoperation logic for UR robots.

Refactor of `ur_xbox_rtde_teleop.py` into a pollable class usable from a GUI.

Controls (as in the original script):
  - Hold A: deadman (authorizes motion)
  - B: stop request (speedStop) + request to disable teleop
  - Y: toggle mode cartesian <-> joint
  - D-pad up/down (edge): increase/decrease linear gain
  - D-pad left/right (edge) + deadman: step (cartesian: ±X 5mm, joint: J1 ±2°)
  - Sticks/triggers/LB/RB: continuous Cartesian command via speedL
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class TeleopCommand:
    """A command produced by the teleop layer."""

    kind: str
    payload: Optional[Sequence[float]] = None
    message: str = ""

def deadzone(x: float, dz: float = 0.12) -> float:
    return 0.0 if abs(x) < dz else x


class XboxTeleop:
    """Poll pygame gamepad and emit UR RTDE commands.

    Call :meth:`poll` at ~50 Hz from a GUI timer.
    """

    # ====== MAPPING (from ur_xbox_rtde_teleop.py) ======
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
    # ===================================================

    def __init__(
        self,
        hz: float = 50.0,
        deadzone: float = 0.12,
        acc_lin: float = 0.20,
        lin_gain: float = 0.06,
        ang_gain: float = 0.50,
    ):
        self.hz = float(hz)
        self.dt = 1.0 / self.hz
        self.deadzone = float(deadzone)
        self.acc_lin = float(acc_lin)

        # Gains adjustable with D-pad up/down
        self.lin_gain = float(lin_gain)
        self.ang_gain = float(ang_gain)
        self.lin_min, self.lin_max = 0.01, 0.20
        self.ang_min, self.ang_max = 0.10, 1.50
        self.gain_step = 0.01

        # Step sizes
        self.step_m = 0.005
        self.step_rad = 2.0 * 3.14159 / 180.0

        self.mode = "cartesian"  # or "joint"

        self._prev_hat: Tuple[int, int] = (0, 0)
        self._prev_y: int = 0
        self._initialized = False
        self._pygame = None
        self._js = None

        self.deadman_btn = None 
        self._was_deadman = False


    # ---------------- utils ----------------
    def _dz(self, x: float, eps: float = 0.08) -> float:
        return 0.0 if abs(x) < eps else x


    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    def _trigger_to_01(self, x: float) -> float:
        # pygame triggers souvent: -1 (relâché) -> +1 (pressé)
        return 0.5 * (x + 1.0)


    # -------------- lifecycle --------------
    def init(self) -> None:
        """Initialize pygame joystick. Safe to call multiple times."""
        if self._initialized:
            return

        import pygame  # local import to keep optional dependency

        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            raise RuntimeError("Aucune manette détectée.")

        js = pygame.joystick.Joystick(0)
        js.init()

        self._pygame = pygame
        self._js = js
        self._initialized = True

    def shutdown(self) -> None:
        """Stop pygame cleanly."""
        if self._pygame is not None:
            try:
                self._pygame.quit()
            except Exception:
                pass
        self._pygame = None
        self._js = None
        self._initialized = False

    # --------------- polling ---------------
    def poll(self) -> TeleopCommand:
        """Poll controller once and return a command.

        Returned kinds:
          - "noop": nothing to do
          - "stop": request speedStop (payload None)
          - "speedL": continuous speedL, payload = [vx,vy,vz,wx,wy,wz]
          - "step_cart": step in Cartesian, payload = [dx, dy, dz, dRx, dRy, dRz]
          - "step_joint": step in joint, payload = [dq0, dq1, dq2, dq3, dq4, dq5]
          - "toggle_mode": mode changed (payload None)
          - "gain": gain updated (payload None)
        """

        if not self._initialized:
            self.init()

        pygame = self._pygame
        js = self._js
        assert pygame is not None and js is not None

        pygame.event.pump()
        # DEBUG: affiche axes au-dessus d'un seuil
        axes = [js.get_axis(i) for i in range(js.get_numaxes())]
        for i, a in enumerate(axes):
            if abs(a) > 0.2:  # seuil
                print(f"[AXIS] {i} = {a:.3f}")


        # Stop / quit
        if js.get_button(self.BTN_B):
            return TeleopCommand(kind="stop", message="B pressed")


        if self.deadman_btn is None:
            for i in range(js.get_numbuttons()):
                if js.get_button(i):
                    self.deadman_btn = i
                    print(f"[GAMEPAD] deadman_btn={i}")
                    break
        deadman = bool(js.get_button(self.deadman_btn)) if self.deadman_btn is not None else False

        #deadman = (js.get_button(self.BTN_A) == 1)
        
        # ---- Deadman gating (A)
        if not deadman:
            self._was_deadman = False          # <-- IMPORTANT
            self._last_v = [0, 0, 0, 0, 0, 0]   # reset filtre
            return TeleopCommand(kind="stop", payload=None)

        # deadman pressé (front montant)
        if not self._was_deadman:
            self._was_deadman = True
            self._last_v = [0, 0, 0, 0, 0, 0]   # <-- clear aussi ici
            return TeleopCommand(kind="stop", message="deadman pressed -> stop (clear old motion)")


        # ---- D-pad edge detection
        hat = js.get_hat(0) if js.get_numhats() > 0 else (0, 0)
        hat_pressed = (self._prev_hat == (0, 0) and hat != (0, 0))
        self._prev_hat = hat

        # ---- Toggle mode with Y (edge)
        y_now = js.get_button(self.BTN_Y)
        if y_now == 1 and self._prev_y == 0:
            self.mode = "joint" if self.mode == "cartesian" else "cartesian"
            self._prev_y = y_now
            return TeleopCommand(kind="toggle_mode", message=f"mode={self.mode}")
        self._prev_y = y_now

        # ---- Adjust speed with D-pad up/down (edge)
        if hat_pressed and hat == (0, 1):
            self.lin_gain = self._clamp(self.lin_gain + self.gain_step, self.lin_min, self.lin_max)
            return TeleopCommand(kind="gain", message=f"lin_gain={self.lin_gain:.3f} m/s")
        if hat_pressed and hat == (0, -1):
            self.lin_gain = self._clamp(self.lin_gain - self.gain_step, self.lin_min, self.lin_max)
            return TeleopCommand(kind="gain", message=f"lin_gain={self.lin_gain:.3f} m/s")

        # ---- Step left/right (edge) with deadman
        if hat_pressed and deadman and (hat == (1, 0) or hat == (-1, 0)):
            if self.mode == "cartesian":
                dx = self.step_m if hat == (1, 0) else -self.step_m
                return TeleopCommand(kind="step_cart", payload=[dx, 0.0, 0.0, 0.0, 0.0, 0.0])
            else:
                dq0 = self.step_rad if hat == (1, 0) else -self.step_rad
                return TeleopCommand(kind="step_joint", payload=[dq0, 0.0, 0.0, 0.0, 0.0, 0.0])

        # ---- Continuous command (speedL)
        lx = self._dz(js.get_axis(self.AX_LX))
        ly = self._dz(js.get_axis(self.AX_LY))
        rx = self._dz(js.get_axis(self.AX_RX),eps=0.12)
        ry = self._dz(js.get_axis(self.AX_RY), eps=0.12)

        lt = self._trigger_to_01(js.get_axis(self.AX_LT))
        rt = self._trigger_to_01(js.get_axis(self.AX_RT))
        z_cmd = (rt - lt)

        rz_cmd = (1.0 if js.get_button(self.BTN_RB) else 0.0) - (
            1.0 if js.get_button(self.BTN_LB) else 0.0
        )
        

        vx = self.lin_gain * lx
        vy = self.lin_gain * (-ly)
        vz = self.lin_gain * z_cmd

        wx = self.ang_gain * (-ry)
        wy = self.ang_gain * (rx)
        wz = self.ang_gain * rz_cmd

        v = [vx, vy, vz, wx, wy, wz]

        # si rien ne dépasse un seuil, on force l'arrêt
        if max(abs(a) for a in v) < 1e-3:
            return TeleopCommand(kind="stop", message="deadzone -> stop")

        print("[GAMEPAD] speedL payload:", v)

        return TeleopCommand(kind="speedL", payload=v)

    def reset(self):
        self._last_v = [0,0,0,0,0,0]   # ou ton filtre

        


