"""Composition-wide master color controls, also usable by detailed sequences."""
from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox

from studio_widgets import DoubleSpinBox, Slider
from synth_master import DEFAULT_MASTER, normalize_master


class MasterPanel(QWidget):
    edited = Signal(str, object)
    resetRequested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel('MASTER / whole composition'); label.setObjectName('sectionTitle'); layout.addWidget(label)
        hint = QLabel('Adjust the finished image across every section, including textures and transitions. Neutral values keep the original look.')
        hint.setWordWrap(True); hint.setObjectName('muted'); layout.addWidget(hint)
        self.enabled = QCheckBox('Enable master'); self.enabled.setChecked(True)
        self.enabled.toggled.connect(lambda value: self.edited.emit('enabled', value)); layout.addWidget(self.enabled)
        self.controls = {}; self.sliders = {}; self.resets = {}
        for key, label, low, high, tip in (
            ('brightness', 'Brightness', -100, 100, 'Lift or lower the entire image. 0% keeps its original brightness.'),
            ('contrast', 'Contrast', 0, 300, 'Contrast around mid-gray. 100% is neutral; 0% flattens the image.'),
            ('saturation', 'Saturation', 0, 300, '100% keeps the original color; 0% is black and white.'),
        ):
            title = QLabel(label); title.setToolTip(tip); layout.addWidget(title)
            row = QHBoxLayout()
            slider = Slider(Qt.Orientation.Horizontal); slider.setRange(low, high); slider.setAccessibleName(f'Master {label.lower()} slider')
            slider.setTracking(False)
            spin = DoubleSpinBox(); spin.setRange(low, high); spin.setDecimals(1); spin.setSingleStep(1); spin.setSuffix(' %')
            spin.setKeyboardTracking(False); spin.setFixedWidth(100); spin.setAccessibleName(f'Master {label.lower()}')
            slider.setToolTip(tip); spin.setToolTip(tip)
            reset = QPushButton('↶'); reset.setFixedWidth(30); reset.setAccessibleName(f'Reset master {label.lower()}'); reset.setToolTip('Restore the neutral value.')
            reset.clicked.connect(lambda _checked=False, k=key: self.edited.emit(k, DEFAULT_MASTER[k]))
            slider.valueChanged.connect(lambda value, control=spin: control.setValue(value))
            spin.valueChanged.connect(lambda value, k=key: self.change_value(k, value))
            row.addWidget(slider, 1); row.addWidget(spin); row.addWidget(reset); layout.addLayout(row)
            self.controls[key] = spin; self.sliders[key] = slider; self.resets[key] = reset
        self.status = QLabel(); self.status.setObjectName('muted'); layout.addWidget(self.status)
        self.reset = QPushButton('Reset master'); self.reset.clicked.connect(self.resetRequested.emit); layout.addWidget(self.reset)
        layout.addStretch(1)
        self.set_values(DEFAULT_MASTER)

    def change_value(self, key, value):
        with QSignalBlocker(self.sliders[key]): self.sliders[key].setValue(round(value))
        self.edited.emit(key, value / 100)

    def set_values(self, settings):
        master = normalize_master(settings)
        with QSignalBlocker(self.enabled): self.enabled.setChecked(master['enabled'])
        for key, control in self.controls.items():
            with QSignalBlocker(control), QSignalBlocker(self.sliders[key]):
                control.setValue(master[key] * 100); self.sliders[key].setValue(round(master[key] * 100))
            self.resets[key].setEnabled(master[key] != DEFAULT_MASTER[key])
        self.status.setText('Bypassed · settings are preserved' if not master['enabled'] else 'Neutral · original image' if master == DEFAULT_MASTER else 'Applied to every section')
        self.reset.setEnabled(master != DEFAULT_MASTER)
