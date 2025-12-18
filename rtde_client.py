from .models import JointState, SpeedJointProfile 
from rtde_control import RTDEControlInterface 
from rtde_receive import RTDEReceiveInterface

class RTDEClient:
    def __init__(self, rtde_r: RTDEReceiveInterface, rtde_c: RTDEControlInterface):
        self.rtde_r = rtde_r
        self._rtde_c = rtde_c

    def get_q(self) -> JointState:
        return JointState(q=self.rtde_r.getActualQ())

    def move_j(self, q: list[float], prof: SpeedJointProfile, async_: bool = True) -> bool:
        try:
            if hasattr(self, "speed_stop"):
                self.speed_stop(10.0)
            else:
                self._rtde_c.speedStop(10.0)
        except Exception:
            pass

        speed = prof.vj
        accel = prof.aj
        if async_ and hasattr(self._rtde_c, "moveJAsync"):
            return self._rtde_c.moveJAsync(q, speed, accel)
        return self._rtde_c.moveJ(q, speed, accel)

    # ---------------- Teleop helpers (speedL / moveL) ----------------
    def get_tcp_pose(self) -> list[float]:
        """Return current TCP pose [x,y,z,Rx,Ry,Rz]."""
        return list(self.rtde_r.getActualTCPPose())

    def speed_l(self, v: list[float], a: float = 0.20, t: float = 0.02) -> bool:
        """Cartesian velocity command (UR RTDE speedL)."""
        return bool(self._rtde_c.speedL(v, a, t))

    def speed_stop(self, a: float = 10.0) -> bool:
        """Stop any running speed command."""
        return bool(self._rtde_c.speedStop(a))

    def move_l(self, pose: list[float], speed: float = 0.10, accel: float = 0.10) -> bool:
        """Cartesian pose move (UR RTDE moveL)."""
        return bool(self._rtde_c.moveL(pose, speed, accel))

    def stop_script(self) -> bool:
        """Stops the URScript program running on controller (if any)."""
        try:
            self._rtde_c.stopScript()
            return True
        except Exception:
            return False

    def freedrive_on(self) -> bool:
        try:
            self._rtde_c.freedriveMode()     
            return True
        except Exception as e:
            print(f"[RTDE] freedrive_on failed: {e}")
            return False

    def freedrive_off(self) -> bool:
        try:
            self._rtde_c.endFreedriveMode()   
            return True
        except Exception as e:
            print(f"[RTDE] freedrive_off failed: {e}")
            return False

    def is_freedrive(self) -> bool:
        try:
            return bool(self._rtde_c.getFreedriveStatus())
        except Exception:
            return False
        
