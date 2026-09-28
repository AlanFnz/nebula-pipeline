"""One object inspector with controls for the actual source family."""
from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from studio_widgets import ComboBox, DoubleSpinBox, Slider
from synth_effects_ui import EffectParameter
from synth_subject import SUBJECTS, SOURCE_EFFECTS, active_subjects


OBJECT_PATHS = {
    'text': tuple('text.' + key for key in ('content', 'font', 'size', 'tracking', 'leading', 'align', 'fit', 'block_width', 'hue', 'saturation', 'brightness', 'stretch_x', 'stretch_y')),
    'silhouette': ('silhouette.model', 'silhouette.scale', 'silhouette.yaw', 'silhouette.definition', 'silhouette.pitch', 'silhouette.roll', 'silhouette.center_x', 'silhouette.center_y', 'silhouette.neck_length', 'silhouette.neck_fullness', 'silhouette.softness'),
    'ink': ('ink_bloom.shape', 'ink_bloom.artwork', 'ink_bloom.shape_width', 'ink_bloom.shape_height',
            'ink_bloom.sides', 'ink_bloom.shape_rotation', 'ink_bloom.size', 'ink_bloom.count',
            'ink_bloom.spread'),
    'particles': ('particles.attractor', 'particles.scale', 'particles.count', 'particles.dot_size',
                  'particles.yaw', 'particles.pitch',
                  'particles.neck_fade'),
}


class SubjectPanel(QWidget):
    selected = Signal(str)
    restored = Signal()
    parameter_changed = Signal(str, str, object)
    parameter_reset = Signal(str, str)
    details_requested = Signal(str, bool)
    position_changed = Signal(str, float)
    position_reset = Signal()

    def __init__(self):
        super().__init__()
        self.kind = 'none'; self.updating = False; self.controls = {}
        layout = QVBoxLayout(self)
        title = QLabel('OBJECT / source'); title.setObjectName('sectionTitle'); layout.addWidget(title)
        row = QHBoxLayout()
        self.selector = ComboBox(); self.selector.setAccessibleName('Object type')
        for key, (label, _) in SUBJECTS.items(): self.selector.addItem(label, key)
        self.selector.setToolTip('Replace the object in this scope. Treatments, canvas and section durations stay in place.')
        self.selector.currentIndexChanged.connect(self.choose); row.addWidget(self.selector, 1)
        self.restore = QPushButton('↶'); self.restore.setAccessibleName('Restore study object')
        self.restore.setToolTip('Follow the study or whole-clip source activation again. Keep your object parameters.')
        self.restore.clicked.connect(self.restored.emit); row.addWidget(self.restore); layout.addLayout(row)
        self.note = QLabel(); self.note.setWordWrap(True); self.note.setObjectName('muted'); layout.addWidget(self.note)
        self.position_host = QWidget(); position_layout = QVBoxLayout(self.position_host)
        position_layout.setContentsMargins(0, 4, 0, 8)
        title = QLabel('POSITION / canvas pixels'); title.setObjectName('sectionTitle'); position_layout.addWidget(title)
        self.position_controls = {}; self.position_sliders = {}
        for axis, direction in (('x', 'right'), ('y', 'down')):
            row = QHBoxLayout(); row.addWidget(QLabel(f'Position {axis.upper()}'))
            slider = Slider(Qt.Orientation.Horizontal); slider.setAccessibleName(f'Object position {axis.upper()} slider')
            spin = DoubleSpinBox(); spin.setRange(-4096, 4096); spin.setDecimals(1); spin.setSingleStep(1); spin.setSuffix(' px')
            spin.setKeyboardTracking(False); spin.setFixedWidth(110); spin.setAccessibleName(f'Object position {axis.upper()}')
            tip = f'Offset in output canvas pixels. Positive moves {direction}; 0 keeps the authored placement and motion.'
            slider.setToolTip(tip); spin.setToolTip(tip)
            slider.valueChanged.connect(lambda value, control=spin: control.setValue(value))
            spin.valueChanged.connect(lambda value, a=axis: self.change_position(a, value))
            row.addWidget(slider, 1); row.addWidget(spin); position_layout.addLayout(row)
            self.position_controls[axis] = spin; self.position_sliders[axis] = slider
        self.position_note = QLabel(); self.position_note.setWordWrap(True); self.position_note.setObjectName('muted'); position_layout.addWidget(self.position_note)
        self.reset_position = QPushButton('Reset position'); self.reset_position.clicked.connect(self.position_reset.emit); position_layout.addWidget(self.reset_position)
        layout.addWidget(self.position_host)
        self.signal_host = QWidget(); self.signal_layout = QVBoxLayout(self.signal_host)
        self.signal_layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(self.signal_host)
        self.control_host = QWidget(); self.control_layout = QVBoxLayout(self.control_host)
        self.control_layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(self.control_host)
        self.details = QPushButton('More object controls…'); self.details.clicked.connect(lambda: self.open_details(False)); layout.addWidget(self.details)
        self.timing = QPushButton('Motion & timing…'); self.timing.clicked.connect(lambda: self.open_details(True)); layout.addWidget(self.timing)
        layout.addStretch(1)

    def change_position(self, axis, value):
        if self.updating: return
        with QSignalBlocker(self.position_sliders[axis]): self.position_sliders[axis].setValue(round(value))
        self.position_changed.emit(f'position_{axis}', value)

    def refresh_position(self, geometry, parent, canvas, local):
        for axis, dimension in (('x', 'width'), ('y', 'height')):
            value = geometry[f'position_{axis}']
            spin, slider = self.position_controls[axis], self.position_sliders[axis]
            with QSignalBlocker(spin), QSignalBlocker(slider):
                extent = max(canvas[dimension], abs(round(value)))
                slider.setRange(-extent, extent); slider.setValue(round(value)); spin.setValue(value)
        self.reset_position.setEnabled(any(geometry[f'position_{axis}'] for axis in ('x', 'y')))
        self.position_note.setText('Section offset adds to whole-clip position. 0 keeps the inherited placement.' if local else '0 keeps the authored placement. X → right · Y → down. Motion and background stay intact.')
        if local:
            self.position_note.setToolTip(f"Whole-clip offset: X {parent['position_x']:g} px · Y {parent['position_y']:g} px")
        else: self.position_note.setToolTip('')

    def choose(self, index):
        if not self.updating and index >= 0: self.selected.emit(self.selector.itemData(index))

    def open_details(self, timing):
        effect = {'ink': 'ink_bloom', 'particles': 'particles', 'signal': self.signal_effect, 'silhouette': 'silhouette', 'text': 'text'}.get(self.kind)
        if effect: self.details_requested.emit(effect, timing)

    def refresh(self, summary, entries, parent_entries, local):
        self.updating = True
        active = active_subjects(summary)
        self.kind = active[0] if active else 'none'
        self.signal_effect = 'forms' if summary['forms']['active'] else 'rays'
        with QSignalBlocker(self.selector): self.selector.setCurrentIndex(self.selector.findData(self.kind))
        self.restore.setEnabled(any(entries.get(key, {}).get('mode', 'recipe') != 'recipe' for key in SOURCE_EFFECTS))
        scope = 'this section' if local else 'the whole clip'
        notes = {'silhouette': 'A fixed human silhouette. Adjust its pose and framing here; Edge phosphor and Scan drag treat its outline.',
                 'text': 'Editable type. Line breaks, spacing and font stay editable; image treatments follow the lettering. More object controls includes reveal and size motion.',
                 'ink': 'Edit the printed silhouette here. Its unfold, turn and refold motion stays with it.',
                 'particles': 'The model is the target of the particles. Adjust its size, pose and point density here.',
                 'signal': 'The luminous form and ray aperture share this geometry.',
                 'none': 'Choose an object to introduce a source into the scene.'}
        note = f'{notes[self.kind]} Changes apply to {scope}.'
        if len(active) > 1:
            note += ' Also present: ' + ', '.join(SUBJECTS[key][0] for key in active[1:]) + '. Choosing a type replaces the source families in this scope.'
        self.note.setText(note)
        self.position_host.setVisible(bool(active))
        self.signal_host.setVisible(self.kind == 'signal')
        self.control_host.setVisible(self.kind in OBJECT_PATHS)
        paths = OBJECT_PATHS.get(self.kind, ())
        if tuple(self.controls) != paths:
            while self.control_layout.count():
                widget = self.control_layout.takeAt(0).widget(); widget.hide(); widget.deleteLater()
            self.controls = {}
            for path in paths:
                control = EffectParameter(path); effect = path.split('.')[0]
                control.changed.connect(lambda value, e=effect, p=path: self.parameter_changed.emit(e, p, value))
                control.reset.connect(lambda e=effect, p=path: self.parameter_reset.emit(e, p))
                self.control_layout.addWidget(control); self.controls[path] = control
        for path, control in self.controls.items():
            effect = path.split('.')[0]; entry = entries.get(effect, {'params': {}})
            control.refresh(summary[effect]['ranges'][path], entry['params'].get(path),
                            path in parent_entries.get(effect, {}).get('params', {}), True)
        if self.kind == 'ink':
            shape = summary['ink_bloom']['ranges']['ink_bloom.shape']
            self.controls['ink_bloom.artwork'].setVisible(shape[0] == shape[1] == 5)
            self.controls['ink_bloom.sides'].setVisible(shape[0] != shape[1] or shape[0] == 4)
        if self.kind == 'particles':
            model = summary['particles']['ranges']['particles.attractor']
            self.controls['particles.neck_fade'].setVisible(model[0] != model[1] or model[0] in (0, 3, 4, 5))
        if self.kind == 'text':
            fit = summary['text']['ranges']['text.fit']
            self.controls['text.block_width'].setVisible(fit[0] != fit[1] or fit[0] == 2)
        self.details.setVisible(bool(active)); self.timing.setVisible(self.kind in ('ink', 'text'))
        self.updating = False
