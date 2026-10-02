"""Creative adjustments retain animation; detailed parameters edit their base."""
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from studio_widgets import DoubleSpinBox, SpinBox, Slider
from synth_creative import CREATIVE_CONTROLS
from synth_effects import parameter


class CreativeValue(QWidget):
    changed = Signal(object)
    restored = Signal()

    def __init__(self, spec):
        super().__init__()
        self.spec = spec; self.updating = False
        self.unit = 1 if spec.operation == 'offset' else 100
        self.slider_unit = self.unit
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 8); layout.setSpacing(3)
        row = QHBoxLayout(); row.setSpacing(5)
        label = QLabel(spec.label); label.setWordWrap(True); row.addWidget(label, 1)
        self.input = SpinBox() if spec.operation == 'offset' else DoubleSpinBox()
        self.input.setRange(spec.minimum * self.unit, spec.maximum * self.unit)
        self.input.setKeyboardTracking(False)
        self.input.setSingleStep(1 if self.unit == 1 else 5)
        self.input.setSuffix(' copies' if self.unit == 1 else ' %')
        if self.unit != 1: self.input.setDecimals(2)
        self.input.setMinimumWidth(110); self.input.setMaximumWidth(145)
        self.input.setAccessibleName(spec.label)
        self.input.valueChanged.connect(self.commit_input); row.addWidget(self.input)
        self.reset = QPushButton('↶'); self.reset.setFixedWidth(30)
        self.reset.setAccessibleName('Restore ' + spec.label); self.reset.clicked.connect(self.restored.emit)
        row.addWidget(self.reset); layout.addLayout(row)
        self.slider = Slider(Qt.Orientation.Horizontal); self.slider.setTracking(False)
        self.slider.setRange(round(spec.minimum * self.slider_unit), round(spec.maximum * self.slider_unit))
        self.slider.setSingleStep(1 if self.unit == 1 else 5)
        self.slider.setPageStep(1 if self.unit == 1 else 10)
        self.slider.setAccessibleName(spec.label + ' slider')
        self.slider.sliderMoved.connect(self.preview_slider)
        self.slider.valueChanged.connect(self.commit_slider)
        layout.addWidget(self.slider)
        self.origin = QLabel(); self.origin.setObjectName('muted'); self.origin.setWordWrap(True)
        layout.addWidget(self.origin)
        targets = ', '.join(parameter(path).label for path in spec.paths)
        self.setToolTip(spec.hint + ' Affects: ' + targets + '.')
        self.input.setToolTip(self.toolTip()); self.slider.setToolTip(self.toolTip())

    def commit_input(self, value):
        with QSignalBlocker(self.slider): self.slider.setValue(round(value / self.unit * self.slider_unit))
        if not self.updating: self.changed.emit(value / self.unit)

    def preview_slider(self, value):
        with QSignalBlocker(self.input): self.input.setValue(value)

    def commit_slider(self, value):
        with QSignalBlocker(self.input): self.input.setValue(value)
        if not self.updating: self.changed.emit(value / self.slider_unit)

    def refresh(self, value, authored, inherited, available, local):
        self.updating = True
        with QSignalBlocker(self.input), QSignalBlocker(self.slider):
            display = int(value) if self.unit == 1 else value * self.unit
            self.input.setValue(display); self.slider.setValue(round(value * self.slider_unit))
        self.input.setEnabled(available); self.slider.setEnabled(available)
        self.reset.setEnabled(authored)
        self.reset.setToolTip('Remove this adjustment and follow the whole clip.' if local else 'Restore the study’s original values for this adjustment.')
        origin = ('Section' if local else 'Whole clip') if authored else 'Whole clip · inherited' if inherited else 'Original values'
        self.origin.setText(origin + (' · neutral' if value == self.spec.neutral else '') + ('' if available else ' · unavailable'))
        self.updating = False


class CreativeControlsPanel(QWidget):
    changed = Signal(str, object)
    restored = Signal(object)

    def __init__(self):
        super().__init__()
        self.effect_id = None; self.controls = {}
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.note = QLabel('Adjust the existing animation. 100% keeps its authored values; copy count adds or removes copies. Parameters edits the base values underneath.')
        self.note.setWordWrap(True); self.note.setObjectName('muted'); layout.addWidget(self.note)
        self.compatibility = QLabel(); self.compatibility.setWordWrap(True)
        self.compatibility.setObjectName('muted'); layout.addWidget(self.compatibility)
        self.host = QWidget(); self.body = QVBoxLayout(self.host); self.body.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(self.host)
        self.restore = QPushButton('Restore creative controls'); self.restore.clicked.connect(lambda: self.restored.emit(None))
        layout.addWidget(self.restore)

    def refresh(self, effect_id, entry, parent, info, available, local):
        notes = {
            'tape': 'Adjust the existing tape pattern. 100% follows its original values. Parameters edits the base tracking, dropouts and color settings.',
            'frame_jitter': 'Keep the authored movement pattern. 100% follows its original values. Pose change speed controls how long each pose is held.',
            'ghosts': 'Add or remove copies from the existing count. 100% keeps the original reach and brightness, including the trail’s fading.',
            'particles': 'Adjust the existing release and return. 100% follows the original motion; these controls do not start a new burst or change the total cycle.',
        }
        self.note.setText(notes.get(effect_id, ''))
        if self.effect_id != effect_id:
            while self.body.count():
                item = self.body.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            self.effect_id = effect_id; self.controls = {}
            for spec in CREATIVE_CONTROLS.get(effect_id, ()):
                control = CreativeValue(spec)
                control.changed.connect(lambda value, key=spec.key: self.changed.emit(key, value))
                control.restored.connect(lambda key=spec.key: self.restored.emit(key))
                self.controls[spec.key] = control; self.body.addWidget(control)
        values = entry.get('creative', {}).get('values', {})
        inherited = parent.get('creative', {}).get('values', {})
        self.restore.setEnabled(bool(values))
        for spec in CREATIVE_CONTROLS.get(effect_id, ()):
            enabled = available
            if effect_id == 'particles' and spec.key in ('outward', 'return'):
                enabled = enabled and info['ranges']['particles.motion'][1] == 2
            if effect_id == 'particles' and spec.key == 'distance':
                enabled = enabled and (info['ranges']['particles.breathing'][1] > 0 or info['ranges']['particles.assembly'][0] < 1)
            self.controls[spec.key].refresh(values.get(spec.key, inherited.get(spec.key, spec.neutral)),
                                           spec.key in values, spec.key in inherited, enabled, local)
        note = ''
        if effect_id == 'particles':
            ranges = info['ranges']
            if ranges['particles.breathing'][1] == 0 and ranges['particles.assembly'][0] == 1:
                note = 'The head stays assembled. Open Parameters → Motion & timing and enable Assembly cycle to animate a release.'
            if ranges['particles.motion'][1] != 2:
                note += ' Outward and Return time need Motion set to Impulse in Parameters.'
            else:
                note += ' Impulse durations are capped by Cycle seconds; changes affect Impulse intervals only.'
        self.compatibility.setText(note.strip()); self.compatibility.setVisible(bool(note))
