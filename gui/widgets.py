#widgets.py
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QSlider, QPushButton, QGridLayout,QWidget


class LabeledSlider(QWidget):
    def __init__(self, label_text: str, lo: float, hi: float, step: float, initial_value: float):
        super().__init__()
        self.initial_value = int(initial_value)
        self.label = QLabel(label_text)
        self.slider = QSlider()
        self.slider.setOrientation(Qt.Orientation.Horizontal)
        self.slider.setRange(int(lo), int(hi))
        self.slider.setSingleStep(int(step))
        self.slider.setValue(self.initial_value)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.slider)
        self.setLayout(layout)

    def value(self) -> float:
        return self.slider.value()

class JointGroup(QGroupBox):
    def __init__(self, title: str = "Joints (deg)", ranges_deg: list[tuple] | None = None, initials_deg: list[float] | None = None):
        super().__init__(title)
        self.setLayout(QVBoxLayout())
        self.sliders: list[LabeledSlider] = []
        if ranges_deg is None:
            ranges_deg = [(-360.0, 360.0)] * 6
        if initials_deg is None:
            initials_deg = [0.0, -45.0, 45.0, 0.0, 0.0, 0.0]
        for i in range(6):
            lo, hi = ranges_deg[i]
            widget = LabeledSlider(f"J{i+1} (°)", lo, hi, 0.1, initials_deg[i])
            self.sliders.append(widget)
            self.layout().addWidget(widget)

    def values_deg(self) -> list[float]:
        return [w.value() for w in self.sliders]

    def set_values_deg(self, vals: list[float]):
        for w, v in zip(self.sliders, vals):
            w.slider.setValue(int(v))


