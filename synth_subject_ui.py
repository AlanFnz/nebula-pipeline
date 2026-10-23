"""One object inspector with controls for the actual source family."""
from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from studio_widgets import ComboBox, DoubleSpinBox, Slider
from synth_effects_ui import EffectParameter
from synth_subject import SUBJECTS, SOURCE_EFFECTS, active_subjects
from synth_inspector import grouped_paths
from synth_solids import hidden_controls as hidden_solid_controls


OBJECT_PATHS = {
    'memory': tuple('image_memory.'+key for key in ('persistence','drift','dissolve','trail_opacity','shape','size','sides','path','travel','amplitude_x','amplitude_y','period','variation','palette')),
    'lattice': tuple('chromatic_lattice.'+key for key in ('shape','sides','spacing','size','minimum','rotation','wave_shape','wavelength','period','phase','direction','angle','pulse','palette','color_period','color_phase','color_spread','gradient','saturation','light','rim','softness','glow','glow_radius','grain','background')),
    'solid': tuple('solid.'+key for key in ('shape','model_data','height_stretch','scale','yaw','pitch','roll','turn_speed','tumble_speed','roll_speed','variation','perspective','corner_radius','material','roughness','specular','glass_transmission','glass_refraction','pip_size','pip_light','pip_depth','palette','shading','light')),
    'prismatic': tuple('prismatic_field.'+key for key in ('shape','sides','center_shape','size','gather','opening','fold_depth','rotation','transition_ease','turn_settle','palette','wash','saturation','light')),
    'radial': tuple('radial_bloom.'+key for key in ('expansion','petals','detail','branching','flow','variation','center_drift','palette','light')),
    'text': tuple('text.' + key for key in ('content', 'font', 'weight', 'morph_balance', 'morph_roundness', 'size', 'tracking', 'leading', 'align', 'wrap_columns', 'fit', 'block_width', 'fit_width', 'copies', 'copy_gap', 'copy_floor', 'hue', 'saturation', 'brightness', 'stretch_x', 'stretch_y')),
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
    center_path_requested = Signal()

    def __init__(self):
        super().__init__()
        self.kind = 'none'; self.updating = False; self.controls = {}; self.control_cache = {}; self.group_labels = {}
        layout = QVBoxLayout(self)
        title = QLabel('OBJECT / source'); title.setObjectName('sectionTitle'); layout.addWidget(title)
        row = QHBoxLayout()
        self.selector = ComboBox(); self.selector.setAccessibleName('Object type')
        for key, (label, _) in SUBJECTS.items(): self.selector.addItem(label, key)
        self.selector.setToolTip('Replace the object in this scope. Treatments, canvas and clip durations stay in place.')
        self.selector.currentIndexChanged.connect(self.choose); row.addWidget(self.selector, 1)
        self.restore = QPushButton('↶'); self.restore.setAccessibleName('Restore study object')
        self.restore.setToolTip('Follow the study or project source activation again. Keep your object parameters.')
        self.restore.clicked.connect(self.restored.emit); row.addWidget(self.restore); layout.addLayout(row)
        self.note = QLabel(); self.note.setWordWrap(True); self.note.setObjectName('muted'); layout.addWidget(self.note)
        self.wording_host = QWidget(); self.wording_layout = QVBoxLayout(self.wording_host)
        self.wording_layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(self.wording_host)
        self.position_host = QWidget(); position_layout = QVBoxLayout(self.position_host)
        position_layout.setContentsMargins(0, 4, 0, 8)
        title = QLabel('POSITION / canvas pixels'); title.setObjectName('sectionTitle'); position_layout.addWidget(title)
        self.position_controls = {}; self.position_sliders = {}
        for axis, direction in (('x', 'right'), ('y', 'down')):
            row = QHBoxLayout(); row.addWidget(QLabel(f'Position {axis.upper()}'))
            slider = Slider(Qt.Orientation.Horizontal); slider.setAccessibleName(f'Object position {axis.upper()} slider')
            slider.setTracking(False)
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
        self.motion_frame = QWidget(); motion_layout = QVBoxLayout(self.motion_frame)
        motion_layout.setContentsMargins(0,0,0,6); motion_layout.setSpacing(4)
        self.center_path = QPushButton('Center path'); self.center_path.setProperty('compact',True)
        self.center_path.setToolTip('Balance the object’s left/right and top/bottom extremes over the editing scope. Updates Position X/Y in one undoable edit. Trails and later image effects can extend beyond the path.')
        self.center_path.clicked.connect(self.center_path_requested.emit); motion_layout.addWidget(self.center_path)
        self.motion_note = QLabel(); self.motion_note.setObjectName('muted'); self.motion_note.setWordWrap(True)
        motion_layout.addWidget(self.motion_note); self.motion_frame.hide()
        self.details = QPushButton('Source controls…'); self.details.clicked.connect(lambda: self.open_details(False)); layout.addWidget(self.details)
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
        self.position_note.setText('Clip offset adds to project position. 0 keeps the inherited placement.' if local else '0 keeps the authored placement. X → right · Y → down. Motion and background stay intact.')
        if local:
            self.position_note.setToolTip(f"Project offset: X {parent['position_x']:g} px · Y {parent['position_y']:g} px")
        else: self.position_note.setToolTip('')

    def choose(self, index):
        if not self.updating and index >= 0: self.selected.emit(self.selector.itemData(index))

    def open_details(self, timing):
        effect = {'memory': 'image_memory', 'lattice': 'chromatic_lattice', 'solid': 'solid', 'prismatic': 'prismatic_field', 'radial': 'radial_bloom', 'ink': 'ink_bloom', 'particles': 'particles', 'signal': self.signal_effect, 'silhouette': 'silhouette', 'text': 'text'}.get(self.kind)
        if effect: self.details_requested.emit(effect, timing)

    def refresh(self, summary, entries, parent_entries, local, *, context_key=None, scope_label=None):
        self.updating = True
        active = active_subjects(summary)
        self.kind = active[0] if active else 'none'
        self.signal_effect = 'forms' if summary['forms']['active'] else 'rays'
        with QSignalBlocker(self.selector): self.selector.setCurrentIndex(self.selector.findData(self.kind))
        self.restore.setEnabled(any(entries.get(key, {}).get('mode', 'recipe') != 'recipe' for key in SOURCE_EFFECTS))
        scope = 'this clip' if local else 'the entire project'
        notes = {'prismatic': 'Choose the final shape and its placement. Transition easing and Turn settle shape the authored movements. Source controls opens the fold rhythm, rotation, ribbon and color drift. Color emulsion adds the film texture separately.', 'radial': 'Expanding crowns and fine branching rays. Source controls opens the full motion, palette and optical settings.', 'silhouette': 'A fixed human silhouette. Adjust its pose and framing here; Edge phosphor and Scan drag treat its outline.',
                 'text': 'Edit your wording below and apply it. Text appearance opens background, opacity and rotation; Motion & timing controls word changes and animation.',
                 'ink': 'Edit the printed silhouette here. Its unfold, turn and refold motion stays with it.',
                 'particles': 'The model is the target of the particles. Adjust its size, pose and point density here.',
                 'signal': 'The luminous form and ray aperture share this geometry.',
                 'none': 'Choose an object to introduce a source into the scene.'}
        notes['memory'] = 'Persistence holds past positions; Drift carries the traces away; Dissolution erodes old silhouettes. This object generates its own history. Source controls opens trace direction, expansion, color aging and optical finish.'
        notes['lattice'] = 'A fixed grid with traveling waves of size and color. Choose the cell shape, wave geometry and palette. Pulse period controls size movement; Color cycle controls color movement. Glow and softness shape the optical finish.'
        notes['solid'] = 'A die, cube or imported GLB/glTF model rotating around its center. Adjust rounded corners, material, reflections, pose, rotation speeds and dots here. Imported models use static geometry and the studio material. Color field controls the background; Color emulsion textures both together.'
        note = f'{notes[self.kind]} Changes apply to {scope}.'
        if len(active) > 1:
            note += ' Also present: ' + ', '.join(SUBJECTS[key][0] for key in active[1:]) + '. Choosing a type replaces the source families in this scope.'
        self.note.setText(note)
        self.position_host.setVisible(bool(active))
        self.signal_host.setVisible(self.kind == 'signal')
        self.control_host.setVisible(self.kind in OBJECT_PATHS)
        self.wording_host.setVisible(self.kind == 'text')
        self.details.setText('Text appearance…' if self.kind == 'text' else 'Source controls…')
        self.timing.setText('Creative motion…' if self.kind == 'particles' else 'Motion & timing…')
        paths = OBJECT_PATHS.get(self.kind, ())
        reading = self.kind == 'text' and summary['text']['ranges']['text.reveal'] == (4, 4)
        if reading:
            paths = tuple('text.' + key for key in ('reading_duration', 'reading_final', 'reading_transition',
                          'reading_weight', 'reading_breakup', 'reading_fragments', 'reading_loop')) + paths
            self.note.setText(f'Edit Wording and apply it: the montage adapts to complete words and letters. '
                             f'Montage duration includes the final phrase; match the clip duration for one full pass. '
                             f'Print collage and Film burn follow these reading beats. Changes apply to {scope}.')
            self.timing.setText('Reading & interruptions…')
        if set(self.controls) != set(paths):
            # Memory's exploration controls precede placement. Only move the
            # host when the source family changes, keeping edits scroll-stable.
            host_layout = self.layout()
            host_layout.removeWidget(self.control_host)
            anchor = self.position_host if self.kind == 'memory' else self.details
            host_layout.insertWidget(host_layout.indexOf(anchor), self.control_host)
            for host_layout in (self.control_layout, self.wording_layout):
                while host_layout.count():
                    widget = host_layout.takeAt(0).widget()
                    if widget: widget.hide()
            self.controls = {}
            for title, members in grouped_paths(paths):
                if title not in self.group_labels:
                    label = QLabel(title.upper()); label.setObjectName('controlGroup')
                    self.group_labels[title] = label
                label = self.group_labels[title]; self.control_layout.addWidget(label); label.show()
                for path in members:
                    if path not in self.control_cache:
                        control = EffectParameter(path); effect = path.split('.')[0]
                        control.changed.connect(lambda value, e=effect, p=path: self.parameter_changed.emit(e, p, value))
                        control.reset.connect(lambda e=effect, p=path: self.parameter_reset.emit(e, p))
                        self.control_cache[path] = control
                    control = self.control_cache[path]
                    (self.wording_layout if path == 'text.content' else self.control_layout).addWidget(control)
                    control.show(); self.controls[path] = control
                    if path == 'image_memory.amplitude_y':
                        self.control_layout.addWidget(self.motion_frame); self.motion_frame.show()
        for path, control in self.controls.items():
            effect = path.split('.')[0]; entry = entries.get(effect, {'params': {}})
            parent_params = parent_entries.get(effect, {}).get('params', {})
            control.refresh(summary[effect]['ranges'][path], entry['params'].get(path),
                            path in parent_params, True, parent_value=parent_params.get(path),
                            context_key=context_key, scope_label=scope_label)
        if self.kind == 'memory':
            shape = summary['image_memory']['ranges']['image_memory.shape']
            self.controls['image_memory.sides'].setVisible(shape[0] != shape[1] or shape[0] == 2)
        if self.kind == 'lattice':
            ranges=summary['chromatic_lattice']['ranges']
            shape=ranges['chromatic_lattice.shape']
            self.controls['chromatic_lattice.sides'].setVisible(shape[0]!=shape[1] or shape[0]==3)
            wave=ranges['chromatic_lattice.wave_shape']
            self.controls['chromatic_lattice.angle'].setVisible(wave[0]!=wave[1] or wave[0]==2)
        if self.kind == 'solid':
            hidden = hidden_solid_controls(summary['solid']['ranges'])
            for path, control in self.controls.items():
                control.setVisible(path not in hidden)
        if self.kind == 'prismatic':
            shape = summary['prismatic_field']['ranges']['prismatic_field.shape']
            self.controls['prismatic_field.sides'].setVisible(shape[0] != shape[1] or shape[0] == 0)
        if self.kind == 'ink':
            shape = summary['ink_bloom']['ranges']['ink_bloom.shape']
            self.controls['ink_bloom.artwork'].setVisible(shape[0] == shape[1] == 5)
            self.controls['ink_bloom.sides'].setVisible(shape[0] != shape[1] or shape[0] == 4)
        if self.kind == 'particles':
            model = summary['particles']['ranges']['particles.attractor']
            self.controls['particles.neck_fade'].setVisible(model[0] != model[1] or model[0] in (0, 3, 4, 5))
        if self.kind == 'text':
            ranges = summary['text']['ranges']
            morph = ranges['text.reveal'][0] == ranges['text.reveal'][1] == 3
            self.controls['text.weight'].setVisible(ranges['text.font'][0] != ranges['text.font'][1] or ranges['text.font'][0] in (3, 4, 5))
            self.controls['text.morph_balance'].setVisible(morph)
            self.controls['text.morph_roundness'].setVisible(morph)
            for key in ('leading', 'align', 'wrap_columns', 'fit', 'copies', 'copy_gap'):
                self.controls['text.' + key].setVisible(not morph and (not reading or key in ('leading', 'align')))
            fit = ranges['text.fit']
            self.controls['text.block_width'].setVisible(not morph and not reading and (fit[0] != fit[1] or fit[0] == 2))
            self.controls['text.fit_width'].setVisible(reading or morph or fit[0] != fit[1] or fit[0] == 1)
            self.controls['text.copy_floor'].setVisible(not morph and not reading and (fit[0] != fit[1] or fit[0] == 1))
        self.details.setVisible(bool(active)); self.timing.setVisible(self.kind in ('ink', 'text'))
        self.updating = False

    def set_motion_bounds(self, bounds, local):
        if self.kind != 'memory': return
        self.center_path.setEnabled(bounds is not None)
        maxima = [bounds.maximum(axis) if bounds is not None else None for axis in range(2)]
        for axis,key in enumerate(('amplitude_x','amplitude_y')):
            control=self.controls['image_memory.'+key]
            control.set_numeric_maximum(maxima[axis])
            control.setEnabled(maxima[axis] is not None)
        scope='this clip' if local else 'the project'
        note=f'Canvas limits across {scope} · Center path balances both axes. Amplitude edits keep that center.'
        if bounds is None:
            note='No visible Image memory object in this scope.'
        elif any(value is None for value in maxima):
            note += ' An axis with no available travel is disabled. Check Travel distance, Center path, Object size or clip overrides.'
        elif any(self.controls['image_memory.'+key].input.value()>maxima[axis]+.01 for axis,key in enumerate(('amplitude_x','amplitude_y'))):
            note += ' Existing travel exceeds the canvas; the next amplitude edit uses its new limit.'
        self.motion_note.setText(note)
