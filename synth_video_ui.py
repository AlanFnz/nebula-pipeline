"""Global source controls for video compositions."""
from pathlib import Path
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
from studio_widgets import ComboBox, DoubleSpinBox
from synth_video import TREATMENTS


class VideoSourcePanel(QWidget):
    edited = Signal(str, object)
    relinkRequested = Signal()
    durationRequested = Signal(float)
    treatmentRequested = Signal(int)

    def __init__(self):
        super().__init__()
        self.updating = False
        self.footage = None
        layout = QVBoxLayout(self)
        title = QLabel('VIDEO SOURCE / whole clip'); title.setObjectName('sectionTitle'); layout.addWidget(title)
        self.name = QLabel(); self.name.setWordWrap(True); self.name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); layout.addWidget(self.name)
        self.metadata = QLabel(); self.metadata.setWordWrap(True); self.metadata.setObjectName('muted'); layout.addWidget(self.metadata)
        relink = QPushButton('Relink / replace video…'); relink.clicked.connect(self.relinkRequested.emit); layout.addWidget(relink)
        self.controls = {}
        for key, label, low, high, step, suffix in (
            ('in', 'In', 0., 86400., .1, ' s'), ('out', 'Out', 0., 86400., .1, ' s'),
            ('zoom', 'Scale', .05, 8., .05, ' ×'), ('x', 'Position X', -100000., 100000., 10., ' px'),
            ('y', 'Position Y', -100000., 100000., 10., ' px'), ('treatment_fps', 'Effect cadence', 1., 120., 1., ' fps')):
            row = QHBoxLayout(); row.addWidget(QLabel(label))
            control = DoubleSpinBox(); control.setRange(low, high); control.setSingleStep(step); control.setDecimals(3 if key in ('in', 'out') else 2)
            control.setSuffix(suffix); control.setKeyboardTracking(False); control.setAccessibleName(f'Video {label}')
            control.valueChanged.connect(lambda value, key=key: self.change(key, value)); row.addWidget(control); layout.addLayout(row)
            self.controls[key] = control
        self.controls['treatment_fps'].setToolTip('How often procedural treatment changes. Footage keeps playing at its own speed; export frame rate stays independent.')
        self.fit = ComboBox(); self.fit.setAccessibleName('Video framing')
        for label, value in (('Fit inside canvas', 'contain'), ('Fill canvas / crop edges', 'cover'), ('Original pixel size', 'original')): self.fit.addItem(label, value)
        self.fit.currentIndexChanged.connect(lambda _: self.change('fit', self.fit.currentData()))
        layout.addWidget(QLabel('Framing · proportions are always preserved')); layout.addWidget(self.fit)
        self.end = ComboBox(); self.end.setAccessibleName('When video ends')
        for label, value in (('Loop trimmed range', 'loop'), ('Hold last frame', 'hold')): self.end.addItem(label, value)
        self.end.currentIndexChanged.connect(lambda _: self.change('end_mode', self.end.currentData()))
        layout.addWidget(QLabel('When footage ends')); layout.addWidget(self.end)
        self.audio = QCheckBox('Keep source audio in export'); self.audio.setAccessibleName('Keep source audio in export')
        self.audio.toggled.connect(lambda checked: self.change('audio', 'keep' if checked else 'mute')); layout.addWidget(self.audio)
        note = QLabel('Preview is silent. Export follows the trim and loop; Hold ends the audio in silence. Sections change treatments without restarting the footage.')
        note.setWordWrap(True); note.setObjectName('muted'); layout.addWidget(note)
        duration = QPushButton('Use trimmed duration for timeline')
        duration.clicked.connect(lambda: self.footage and self.durationRequested.emit(self.footage['out'] - self.footage['in']))
        layout.addWidget(duration)
        layout.addWidget(QLabel('TREATMENT PRESETS / keep this source'))
        self.treatment = ComboBox(); self.treatment.setAccessibleName('Video treatment preset'); self.treatment.addItems([name for name, _ in TREATMENTS]); layout.addWidget(self.treatment)
        apply = QPushButton('Apply treatment preset'); apply.clicked.connect(lambda: self.treatmentRequested.emit(self.treatment.currentIndex()))
        apply.setToolTip('Replace image effects and master adjustments throughout this composition. Source, framing and section durations stay in place. Undo restores the previous treatment.')
        layout.addWidget(apply)
        layout.addStretch(1)

    def change(self, key, value):
        if not self.updating: self.edited.emit(key, value)

    def refresh(self, footage):
        if footage is None: return
        self.updating = True
        self.footage = footage
        try:
            self.name.setText(Path(footage['path']).name); self.name.setToolTip(footage['path'])
            missing = ' · MISSING — relink below' if not Path(footage['path']).exists() else ''
            self.metadata.setText(f"{footage['width']}×{footage['height']} · {footage['fps']:.3f} fps · {footage['duration']:.2f}s · {'audio' if footage['has_audio'] else 'no audio'}{missing}")
            for key, control in self.controls.items():
                if key in ('in', 'out'): control.setMaximum(footage['duration'])
                control.setValue(footage[key])
            self.fit.setCurrentIndex(self.fit.findData(footage['fit']))
            self.end.setCurrentIndex(self.end.findData(footage['end_mode']))
            self.audio.setEnabled(footage['has_audio']); self.audio.setChecked(footage['has_audio'] and footage['audio'] == 'keep')
        finally: self.updating = False
