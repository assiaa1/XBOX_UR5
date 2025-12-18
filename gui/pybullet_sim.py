#pybullet_sim.py
from __future__ import annotations
import pybullet as p
import pybullet_data
import numpy as np
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TriggerZone:
    name: str
    aabb_min: tuple[float, float, float]
    aabb_max: tuple[float, float, float]
    body_id: int | None = None  

class PyBulletSim:
    def __init__(self, use_egl: bool = False):
        """Mode DIRECT = pas de fenêtre, rendu offscreen via TinyRenderer/EGL"""
        self.client = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.client)
        p.setGravity(0, 0, -9.81, physicsClientId=self.client)
        self.robot_id = None
        self.camera_setup = dict(
            width=900, height=700,
            fov=60, near=0.01, far=5.0,
            eye=[1.0, 0.0, 0.8], target=[0.0, 0.0, 0.4], up=[0,0,1]
            )
        self.trigger_zones: list[TriggerZone] = []
        self.ee_link_index: int | None = None

    def reset(self):
        p.resetSimulation(physicsClientId=self.client)
        p.setGravity(0, 0, -9.81, physicsClientId=self.client)
        p.loadURDF("plane.urdf", physicsClientId=self.client)
        self.robot_id = None

    def load_robot(self, urdf_path: str, base_pos=(0,0,0), base_orn=(0,0,0,1)):
        urdf_path = str(Path(urdf_path).resolve())

        # Important: résoudre les chemins de meshes
        urdf_dir = str(Path(urdf_path).parent)
        ur_description_dir = str(Path(urdf_path).parent.parent)  # .../ur_description

        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.client)
        p.setAdditionalSearchPath(urdf_dir, physicsClientId=self.client)
        p.setAdditionalSearchPath(ur_description_dir, physicsClientId=self.client)

        self.robot_id = p.loadURDF(
            urdf_path,
            base_pos,
            base_orn,
            useFixedBase=True,
            physicsClientId=self.client,
            flags=p.URDF_USE_SELF_COLLISION
        )
        self.joint_name_to_id = {}
        

        for jid in range(p.getNumJoints(self.robot_id, physicsClientId=self.client)):
            info = p.getJointInfo(self.robot_id, jid, physicsClientId=self.client)
            name = info[1].decode("utf-8")
            jtype = info[2]
            if jtype == p.JOINT_REVOLUTE:
                self.joint_name_to_id[name] = jid

        ur_order = [
            "shoulder_pan_joint",
            "shoulder_lift_joint",
            "elbow_joint",
            "wrist_1_joint",
            "wrist_2_joint",
            "wrist_3_joint",
        ]

        missing = [n for n in ur_order if n not in self.joint_name_to_id]
        if missing:
            print("[PyBulletSim] Missing joints in URDF:", missing)

        self.ur_joint_ids = [self.joint_name_to_id[n] for n in ur_order if n in self.joint_name_to_id]
        print("[PyBulletSim] UR joint ids:", self.ur_joint_ids)

        return self.robot_id

        

    def set_joints(self, q):
        if self.robot_id is None:
            return
        if not hasattr(self, "ur_joint_ids") or len(self.ur_joint_ids) < 6:
            return
        n = min(6, len(q))
        for i in range(n):
            p.resetJointState(
                self.robot_id,
                self.ur_joint_ids[i],
                float(q[i]),
                physicsClientId=self.client
            )


    def step(self, dt=1/240):
        p.stepSimulation(physicsClientId=self.client)

    def render_rgb(self) -> np.ndarray:
        c = self.camera_setup
        view = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=[0,0,0.4],
        distance=2.0,   # au lieu de 1.2
        yaw=90, pitch=-35, roll=0, upAxisIndex=2
        )
        proj = p.computeProjectionMatrixFOV(c["fov"], c["width"]/c["height"], c["near"], c["far"])
        width, height, rgb, depth, seg = p.getCameraImage(
            c["width"], c["height"], view, proj, renderer=p.ER_TINY_RENDERER, physicsClientId=self.client
        )
        img = np.reshape(rgb, (height, width, 4))[:,:,:3]  # RGBA->RGB
        return img
    
    def set_ee_link(self, link_index: int):
        self.ee_link_index = link_index

    def get_ee_pos(self) -> tuple[float, float, float] | None:
        if self.robot_id is None or self.ee_link_index is None:
            return None
        st = p.getLinkState(self.robot_id, self.ee_link_index, computeForwardKinematics=True,
                            physicsClientId=self.client)
        # st[4] = worldLinkFramePosition
        return tuple(st[4])

    def add_trigger_zone(self, name: str, aabb_min, aabb_max, rgba=(0, 1, 0, 0.15)) -> None:
        # affichage d’une boîte semi-transparente dans la vue caméra
        center = [(aabb_min[i] + aabb_max[i]) * 0.5 for i in range(3)]
        half = [(aabb_max[i] - aabb_min[i]) * 0.5 for i in range(3)]

        vis = p.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=rgba,
                                physicsClientId=self.client)
        body = p.createMultiBody(baseMass=0,
                                baseVisualShapeIndex=vis,
                                basePosition=center,
                                physicsClientId=self.client)

        self.trigger_zones.append(TriggerZone(name=name,
                                            aabb_min=tuple(aabb_min),
                                            aabb_max=tuple(aabb_max),
                                            body_id=body))


    def disconnect(self):
        p.disconnect(physicsClientId=self.client)