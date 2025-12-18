# app.py
import numpy as np
import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface
from core.rtde_client import RTDEClient
from gui.widgets import JointGroup

class Application(QApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hostname = '192.168.0.40'
        self.port = 30004
        self.frequency = 100.0

        self.rtde_r = None
        self.rtde_c = None
        try:
            self.rtde_r = RTDEReceiveInterface(hostname=self.hostname, 
                                            frequency=self.frequency,
                                            variables=[], 
                                            verbose=False)
            self.rtde_c = RTDEControlInterface(hostname=self.hostname) 
            if not self.rtde_r.isConnected() or not self.rtde_c.isConnected():
                print("[WARN] RTDE indisponible, lancement en mode dégradé.")
                self.rtde_r = self.rtde_c = None
        except Exception as e:
            print(f"[WARN] RTDE init error: {e}")
            self.rtde_r = self.rtde_c = None

        self.rtde_client = RTDEClient(self.rtde_r, self.rtde_c) if (self.rtde_r and self.rtde_c) else None
        
        # Initialiser les widgets
        self.joint_group = JointGroup("Joints (deg)")

        

        self.main_window = MainWindow(self.rtde_client)
        self.main_window.show()

if __name__ == "__main__":
    app = Application(sys.argv)
    sys.exit(app.exec())
