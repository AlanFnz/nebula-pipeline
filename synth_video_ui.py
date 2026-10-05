"""Shared or section-owned source controls for video compositions."""
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
    sourceModeRequested = Signal(bool)
    speedRequested = Signal(float, bool)
    sharedEditRequested = Signal()

    def __init__(self):
        super().__init__()
        self.updating = False
        self.footage = None
        layout = QVBoxLayout(self)
        self.title = QLabel('VIDEO SOURCE / whole clip'); self.title.setObjectName('sectionTitle'); layout.addWidget(self.title)
        self.source_mode = ComboBox(); self.source_mode.setAccessibleName('Section footage source')
        self.source_mode.addItem('Use shared footage · continuous', False)
        self.source_mode.addItem('Independent footage · starts at In', True)
        self.source_mode.currentIndexChanged.connect(lambda _: not self.updating and self.sourceModeRequested.emit(self.source_mode.currentData()))
        layout.addWidget(self.source_mode)
        self.scope_note = QLabel(); self.scope_note.setWordWrap(True); self.scope_note.setObjectName('muted'); layout.addWidget(self.scope_note)
        self.playback_summary = QLabel(); self.playback_summary.setWordWrap(True)
        self.playback_summary.setAccessibleName('Section footage playback summary')
        self.playback_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); layout.addWidget(self.playback_summary)
        self.source_range = QLabel(); self.source_range.setWordWrap(True); self.source_range.setObjectName('muted'); layout.addWidget(self.source_range)
        self.shared_actions = QWidget(); shared_layout = QVBoxLayout(self.shared_actions); shared_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_shared = QPushButton('Edit shared source'); self.edit_shared.clicked.connect(self.sharedEditRequested.emit); shared_layout.addWidget(self.edit_shared)
        self.make_independent = QPushButton('Make independent for this section')
        self.make_independent.setToolTip('Use the same video with this section’s own trim and framing. Playback starts at its In point.')
        self.make_independent.clicked.connect(lambda: self.sourceModeRequested.emit(True)); shared_layout.addWidget(self.make_independent)
        layout.addWidget(self.shared_actions)
        self.name = QLabel(); self.name.setWordWrap(True); self.name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); layout.addWidget(self.name)
        self.metadata = QLabel(); self.metadata.setWordWrap(True); self.metadata.setObjectName('muted'); layout.addWidget(self.metadata)
        self.relink = QPushButton('Relink / replace video…'); self.relink.clicked.connect(self.relinkRequested.emit); layout.addWidget(self.relink)
        self.speed_row = QWidget(); speed_layout = QHBoxLayout(self.speed_row); speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.addWidget(QLabel('Playback speed'))
        self.speed = DoubleSpinBox(); self.speed.setRange(.05, 16.); self.speed.setDecimals(2); self.speed.setSingleStep(.1); self.speed.setSuffix(' ×'); self.speed.setKeyboardTracking(False)
        self.speed.setAccessibleName('Section playback speed')
        self.speed.setToolTip('Video speed for this section. 2× plays twice as fast. Match section duration also retimes effects and automation proportionally; turn it off to keep the section length.')
        self.speed.valueChanged.connect(lambda value: not self.updating and self.speedRequested.emit(value, self.match_duration.isChecked()))
        speed_layout.addWidget(self.speed); layout.addWidget(self.speed_row)
        self.match_duration = QCheckBox('Match section duration to speed'); self.match_duration.setChecked(True)
        self.match_duration.setToolTip('Keep the same source interval: 10 seconds at 1× becomes 5 seconds at 2×. Durations round to timeline frames.')
        layout.addWidget(self.match_duration)
        self.source_controls = QWidget(); controls_layout = QVBoxLayout(self.source_controls); controls_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.source_controls)
        self.controls = {}
        for key, label, low, high, step, suffix in (
            ('in', 'In', 0., 86400., .1, ' s'), ('out', 'Out', 0., 86400., .1, ' s'),
            ('zoom', 'Scale', .05, 8., .05, ' ×'), ('x', 'Position X', -100000., 100000., 10., ' px'),
            ('y', 'Position Y', -100000., 100000., 10., ' px'), ('rotation', 'Rotation', -180., 180., .5, ' °'),
            ('motion_fps', 'Motion cadence', 0., 120., 1., ' fps'), ('treatment_fps', 'Effect cadence', 1., 120., 1., ' fps')):
            row = QHBoxLayout(); row.addWidget(QLabel(label))
            control = DoubleSpinBox(); control.setRange(low, high); control.setSingleStep(step); control.setDecimals(3 if key in ('in', 'out') else 2)
            control.setSuffix(suffix); control.setKeyboardTracking(False); control.setAccessibleName(f'Video {label}')
            control.valueChanged.connect(lambda value, key=key: self.change(key, value)); row.addWidget(control); controls_layout.addLayout(row)
            self.controls[key] = control
        self.controls['motion_fps'].setSpecialValueText('Native FPS')
        self.controls['motion_fps'].setToolTip('Hold source frames at this rate without slowing the clip. Zero keeps native motion. Texture and export cadence stay independent.')
        self.controls['in'].setToolTip('Start of the selected source range. The section’s length and playback speed determine how much of this range plays.')
        self.controls['out'].setToolTip('End limit of the selected source range, not the section duration. After this point, footage holds or loops according to When footage ends.')
        self.controls['treatment_fps'].setToolTip('Base cadence for shared image treatments. Effects with their own FPS controls keep independent clocks. Use Timeline FPS beside Canvas to change the frame rate of the whole image.')
        cadence_note = QLabel('For the whole image, use Timeline FPS beside Canvas. These source controls can hold the video or shared treatments independently.')
        cadence_note.setWordWrap(True); cadence_note.setObjectName('muted'); controls_layout.addWidget(cadence_note)
        self.controls['rotation'].setToolTip('Rotate the source around its positioned center. Positive values turn clockwise; proportions and subject masks stay aligned. Increase Scale to fill any exposed corners.')
        self.fit = ComboBox(); self.fit.setAccessibleName('Video framing')
        for label, value in (('Fit inside canvas', 'contain'), ('Fill canvas / crop edges', 'cover'), ('Original pixel size', 'original')): self.fit.addItem(label, value)
        self.fit.currentIndexChanged.connect(lambda _: self.change('fit', self.fit.currentData()))
        controls_layout.addWidget(QLabel('Framing · proportions are always preserved')); controls_layout.addWidget(self.fit)
        self.end = ComboBox(); self.end.setAccessibleName('When video ends')
        for label, value in (('Loop trimmed range', 'loop'), ('Hold last frame', 'hold')): self.end.addItem(label, value)
        self.end.currentIndexChanged.connect(lambda _: self.change('end_mode', self.end.currentData()))
        controls_layout.addWidget(QLabel('When footage ends')); controls_layout.addWidget(self.end)
        self.audio = QCheckBox('Keep source audio in export'); self.audio.setAccessibleName('Keep source audio in export')
        self.audio.toggled.connect(lambda checked: self.change('audio', 'keep' if checked else 'mute')); controls_layout.addWidget(self.audio)
        note = QLabel('Preview is silent. Export follows each source’s trim and speed; Hold ends the audio in silence. Independent footage restarts at In on each section repeat.')
        note.setWordWrap(True); note.setObjectName('muted'); layout.addWidget(note)
        self.duration = QPushButton('Use trimmed duration for timeline')
        self.duration.clicked.connect(lambda: self.footage and self.durationRequested.emit((self.footage['out'] - self.footage['in']) / (self.speed.value() if self.section else 1.)))
        controls_layout.addWidget(self.duration)
        layout.addWidget(QLabel('TREATMENT PRESETS / whole clip · keep sources'))
        self.treatment = ComboBox(); self.treatment.setAccessibleName('Video treatment preset'); self.treatment.addItems([name for name, _ in TREATMENTS]); layout.addWidget(self.treatment)
        apply = QPushButton('Apply treatment preset'); apply.clicked.connect(lambda: self.treatmentRequested.emit(self.treatment.currentIndex()))
        apply.setToolTip('Replace image effects and master adjustments throughout this composition. Source, framing and section durations stay in place. Undo restores the previous treatment.')
        layout.addWidget(apply)
        layout.addStretch(1)

    def change(self, key, value):
        if not self.updating: self.edited.emit(key, value)

    def refresh(self, footage, section=None, *, sequence=None, start=0., repeated=False):
        if footage is None: return
        self.updating = True
        self.footage = footage
        self.section = section
        try:
            local = section is not None
            independent = local and 'footage' in section
            inherited = local and not independent
            self.title.setText('VIDEO SOURCE / selected section' if local else 'VIDEO SOURCE / whole clip')
            self.source_mode.setVisible(local); self.source_mode.setCurrentIndex(1 if independent else 0)
            self.scope_note.setText('Independent source: playback starts at In on each section repeat.' if independent else
                                   'This section continues the shared video. Trim and framing belong to the shared source. Later repeats continue from later source times.' if inherited and repeated else
                                   'This section continues the shared video. Trim and framing belong to the shared source.' if inherited else
                                   'Edits affect sections using shared footage. Independent sections keep their own source settings.')
            self.shared_actions.setVisible(inherited); self.source_controls.setVisible(not inherited)
            self.playback_summary.setVisible(local and sequence is not None)
            if local and sequence is not None:
                from synth_video_summary import section_playback_summary
                text, details = section_playback_summary(sequence, start, section['duration'], repeated=repeated)
                self.playback_summary.setText(text); self.playback_summary.setToolTip(details)
            from synth_video_summary import source_time_label
            self.source_range.setText(f"Selected source range: {source_time_label(footage['in'])} → {source_time_label(footage['out'])} ({footage['out']-footage['in']:.2f}s)")
            self.relink.setText('Choose video for this section…' if local else 'Relink / replace shared video…')
            self.speed_row.setVisible(local); self.match_duration.setVisible(local)
            rate = section.get('video_rate', 1.) if local else 1.
            self.speed.setRange(min(.05, rate), max(16., rate)); self.speed.setValue(rate)
            self.duration.setText('Use trimmed duration for this section' if local else 'Use trimmed duration for timeline')
            self.name.setText(Path(footage['path']).name); self.name.setToolTip(footage['path'])
            missing = ' · MISSING — relink below' if not Path(footage['path']).exists() else ''
            self.metadata.setText(f"{footage['width']}×{footage['height']} · {footage['fps']:.3f} fps · {footage['duration']:.2f}s · {'audio' if footage['has_audio'] else 'no audio'}{missing}")
            for key, control in self.controls.items():
                if key in ('in', 'out'): control.setMaximum(footage['duration'])
                control.setValue(footage[key])
                control.setEnabled(not local or independent)
            self.fit.setEnabled(not local or independent); self.end.setEnabled(not local or independent)
            self.fit.setCurrentIndex(self.fit.findData(footage['fit']))
            self.end.setCurrentIndex(self.end.findData(footage['end_mode']))
            self.audio.setEnabled(footage['has_audio'] and (not local or independent)); self.audio.setChecked(footage['has_audio'] and footage['audio'] == 'keep')
        finally: self.updating = False
