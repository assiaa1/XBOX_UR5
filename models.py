#model.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List

@dataclass
class JointState:
    q: List[float]  # rad, len=6

@dataclass
class SpeedJointProfile:
    vj: float = 0.25        # rad/s
    aj: float = 0.25        # rad/s^2

@dataclass
class JointLimits:
    # en rad (UR10e ~ ±360° selon axes, ajustez selon votre robot)
    min_rad: List[float]
    max_rad: List[float]