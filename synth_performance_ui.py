"""Reusable visual performance panel for the inspector and sound workspace."""
from PySide6.QtCore import Signal, QSignalBlocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QGroupBox, QGridLayout, QPushButton, QCheckBox)
from synth_sound_knob import SoundKnob
from synth_performance import defaults, values_at, source_time, SURFACE_CONTROLS


class PerformancePanel(QWidget):
    edited = Signal(str, float)
    enabledChanged = Signal(bool)
    recordChanged = Signal(bool)
    resetRequested = Signal()
    clearRequested = Signal()
    prepareRequested = Signal()
    gestureStarted = Signal()
    gestureFinished = Signal()

    def __init__(self, controls, parent=None):
        super().__init__(parent)
        self.setProperty('visualPerformance', True)
        self.config = defaults()
        self.knobs = {}; self.origins = {}
        self.boxes = {}; self.control_groups = {}; self.surface_hint = None
        layout = QVBoxLayout(self)
        self.scope_hint = intro = QLabel()
        self.set_scope('All clips in this composition')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.enabled = QCheckBox('Enable controls'); self.enabled.setChecked(True)
        self.record = QPushButton('Record knobs'); self.record.setCheckable(True)
        self.record.setToolTip('Start playback, then turn knobs. A recording ends when playback stops or loops. Undo restores the whole take.')
        row.addWidget(self.enabled); row.addStretch(1); row.addWidget(self.record)
        layout.addLayout(row)
        self.summary = QLabel('No recorded movements'); self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        prepare = QPushButton('Prepare all video frames')
        prepare.clicked.connect(self.prepareRequested); layout.addWidget(prepare)
        self.groups = QWidget(); groups = QVBoxLayout(self.groups); groups.setContentsMargins(0, 0, 0, 0)
        for group in dict.fromkeys(c.group for c in controls):
            box = QGroupBox(group); grid = QGridLayout(box)
            self.boxes[group] = box
            entries = [c for c in controls if c.group == group]
            for index, control in enumerate(entries):
                knob = SoundKnob(control.title, control.low, control.high, 1., control.suffix)
                knob.setValue(control.default); knob.setToolTip(control.hint)
                knob.valueChanged.connect(lambda value, key=control.key: self.edited.emit(key, value))
                knob.dial.sliderPressed.connect(self.gestureStarted)
                knob.dial.sliderReleased.connect(self.gestureFinished)
                self.knobs[control.key] = knob
                self.control_groups[control.key] = group
                grid.addWidget(knob, (index // 2) * 2, index % 2)
                origin = QLabel(); origin.setObjectName('muted'); origin.setWordWrap(True)
                self.origins[control.key] = origin
                grid.addWidget(origin, (index // 2) * 2 + 1, index % 2)
            groups.addWidget(box)
            if group == 'Surface':
                hint = QLabel('Surface controls reshape the object and need new frames. Their recordings follow the visual source clock. Frame, Motion and Finish reuse prepared frames at your selected resolution.')
                hint.setWordWrap(True); groups.addWidget(hint); self.surface_hint = hint
        layout.addWidget(self.groups)
        row = QHBoxLayout()
        clear = QPushButton('Clear recording'); reset = QPushButton('Reset controls')
        clear.clicked.connect(self.clearRequested); reset.clicked.connect(self.resetRequested)
        row.addWidget(clear); row.addWidget(reset); layout.addLayout(row); layout.addStretch(1)
        self.enabled.toggled.connect(self.enabledChanged)
        self.record.toggled.connect(self.recordChanged)

    def set_scope(self, scope):
        self.scope_hint.setText('Perform · ' + scope + '. Adjustments follow base values and clip automation. '
                               'With Record off, editing a recorded knob replaces its recording with a fixed adjustment; Undo restores it.')

    def set_available(self, controls):
        keys = {c.key for c in controls}
        for key, knob in self.knobs.items(): knob.setVisible(key in keys)
        for key, label in self.origins.items(): label.setVisible(key in keys)
        for group, box in self.boxes.items():
            box.setVisible(any(self.control_groups[key] == group for key in keys))
        if self.surface_hint: self.surface_hint.setVisible(any(key in keys for key in SURFACE_CONTROLS))

    def set_config(self, config, seconds, duration, recording=False, fps=30, force=False):
        self.fps = fps
        self.config = config or defaults()
        with QSignalBlocker(self.enabled): self.enabled.setChecked(self.config.get('enabled', True))
        with QSignalBlocker(self.record): self.record.setChecked(recording)
        self.groups.setEnabled(self.enabled.isChecked())
        self.record.setText('Stop recording' if recording else 'Record knobs')
        count = len(self.config.get('tracks', {}))
        self.summary.setText('Recording · turn knobs while playing' if recording else f'{count} recorded controls · movements replay and export' if count else 'No recorded movements')
        for key, label in self.origins.items():
            recorded = bool(self.config.get('tracks', {}).get(key))
            label.setText(('Recorded movement' if recorded else 'Fixed adjustment') +
                          ('' if self.enabled.isChecked() else ' · bypassed'))
            label.setToolTip('With Record off, editing this knob replaces its recorded movement. Undo restores it.'
                            if recorded else 'This adjustment stays constant until you change or record it.')
        self.set_playhead(seconds, duration, force=force)

    def set_playhead(self, seconds, duration, force=False):
        values = values_at(self.config, seconds, duration)
        surface = values_at(self.config, source_time(self.config, seconds, duration, self.fps), duration)
        values.update({k: surface[k] for k in SURFACE_CONTROLS})
        # Disabled controls retain their saved settings visibly.
        if not self.config.get('enabled', True): values = self.config['values']
        for key, knob in self.knobs.items():
            if knob.dial.isSliderDown() or (knob.number.hasFocus() and not force): continue
            with QSignalBlocker(knob): knob.setValue(values[key])
