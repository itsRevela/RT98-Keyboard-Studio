"""Bottom-dock editing controls: adjustment sliders + crop/orientation.

Public API is stable (used by main_window): ``changed`` signal, ``apply_to`` /
``load``, and the ``aspect`` checkbox, ``clear_crop`` / ``reset`` buttons.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from rt98.imaging import EditState
from ..theme import PALETTE


class _Slider(QWidget):
    """A compact labelled slider column (name on top, value below)."""

    def __init__(self, label, lo, hi, default, scale, fmt, on_change):
        super().__init__()
        self.scale = scale
        self.fmt = fmt
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        name = QLabel(label)
        name.setObjectName("muted")
        name.setAlignment(Qt.AlignCenter)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(default)
        self.slider.setFixedWidth(118)
        self.value = QLabel()
        self.value.setAlignment(Qt.AlignCenter)
        self.slider.valueChanged.connect(lambda _v: (self._update(), on_change()))
        v.addWidget(name)
        v.addWidget(self.slider, 0, Qt.AlignCenter)
        v.addWidget(self.value)
        self._update()

    def _update(self):
        self.value.setText(self.fmt % (self.slider.value() * self.scale))

    def get(self) -> float:
        return self.slider.value() * self.scale

    def set(self, real: float):
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(real / self.scale)))
        self.slider.blockSignals(False)
        self._update()


def _divider() -> QFrame:
    line = QFrame()
    line.setFixedWidth(1)
    line.setStyleSheet(f"background:{PALETTE['border']};")
    return line


class ControlsPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(16)
        emit = self.changed.emit

        self.brightness = _Slider("Brightness", 20, 200, 100, 0.01, "%.2f", emit)
        self.contrast = _Slider("Contrast", 20, 200, 100, 0.01, "%.2f", emit)
        self.saturation = _Slider("Saturation", 0, 200, 100, 0.01, "%.2f", emit)
        self.hue = _Slider("Hue", -180, 180, 0, 1.0, "%d°", emit)
        self.speed = _Slider("Speed", 25, 400, 100, 0.01, "%.2fx", emit)
        for s in (self.brightness, self.contrast, self.saturation, self.hue, self.speed):
            row.addWidget(s)

        row.addWidget(_divider())

        orient = QVBoxLayout()
        orient.setSpacing(6)
        self.aspect = QCheckBox("Lock crop 240:136")
        self.aspect.setChecked(True)
        self.aspect.stateChanged.connect(lambda _s: self.changed.emit())
        orient.addWidget(self.aspect)
        ro = QHBoxLayout()
        ro.setSpacing(6)
        ro.addWidget(QLabel("Rotate"))
        self.rotate = QComboBox()
        self.rotate.addItems(["0°", "90°", "180°", "270°"])
        self.rotate.currentIndexChanged.connect(lambda _i: self.changed.emit())
        ro.addWidget(self.rotate)
        self.flip_h = QCheckBox("Flip H")
        self.flip_v = QCheckBox("Flip V")
        self.flip_h.stateChanged.connect(lambda _s: self.changed.emit())
        self.flip_v.stateChanged.connect(lambda _s: self.changed.emit())
        ro.addWidget(self.flip_h)
        ro.addWidget(self.flip_v)
        orient.addLayout(ro)
        self.clear_crop = QPushButton("Clear crop")
        self.clear_crop.setObjectName("ghost")
        orient.addWidget(self.clear_crop)
        row.addLayout(orient)

        row.addStretch(1)
        self.reset = QPushButton("Reset edits")
        self.reset.setObjectName("ghost")
        row.addWidget(self.reset, 0, Qt.AlignBottom)

    def apply_to(self, edit: EditState) -> EditState:
        edit.brightness = self.brightness.get()
        edit.contrast = self.contrast.get()
        edit.saturation = self.saturation.get()
        edit.hue = int(self.hue.get())
        edit.speed = self.speed.get()
        edit.rotate = int(self.rotate.currentText().rstrip("°"))
        edit.flip_h = self.flip_h.isChecked()
        edit.flip_v = self.flip_v.isChecked()
        return edit

    def load(self, edit: EditState):
        widgets = (self.aspect, self.flip_h, self.flip_v, self.rotate)
        for w in widgets:
            w.blockSignals(True)
        self.brightness.set(edit.brightness)
        self.contrast.set(edit.contrast)
        self.saturation.set(edit.saturation)
        self.hue.set(edit.hue)
        self.speed.set(edit.speed)
        self.rotate.setCurrentText(f"{edit.rotate}°")
        self.flip_h.setChecked(edit.flip_h)
        self.flip_v.setChecked(edit.flip_v)
        for w in widgets:
            w.blockSignals(False)

    def set_enabled(self, on: bool):
        for s in (self.brightness, self.contrast, self.saturation, self.hue, self.speed):
            s.setEnabled(on)
        for w in (self.aspect, self.rotate, self.flip_h, self.flip_v, self.clear_crop, self.reset):
            w.setEnabled(on)
