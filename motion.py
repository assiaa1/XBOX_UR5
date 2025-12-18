#motion.py
# core/motion.py
from __future__ import annotations
from typing import List
from .models import JointState, JointLimits
import math

def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

def clamp_joints(q: JointState, lim: JointLimits) -> JointState:
    return JointState([clamp(v, lo, hi) for v, lo, hi in zip(q.q, lim.min_rad, lim.max_rad)])

def deg2rad_list(vals_deg: List[float]) -> List[float]:
    return [math.radians(v) for v in vals_deg]

def rad2deg_list(vals_rad: List[float]) -> List[float]:
    return [math.degrees(v) for v in vals_rad]
