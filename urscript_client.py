# urscript_client.py
from typing import List
from .models import SpeedJointProfile

class URScriptClient:
    def __init__(self, rtde_c):
        self._rtde_c = rtde_c

    def move_j(self, q: List[float], prof: SpeedJointProfile, async_: bool = True) -> bool:
        speed, accel = prof.vj, prof.aj
        if async_ and hasattr(self._rtde_c, "moveJAsync"):
            return self._rtde_c.moveJAsync(q, speed, accel)
        return self._rtde_c.moveJ(q, speed, accel)
