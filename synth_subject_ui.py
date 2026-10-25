"""One object inspector with controls for the actual source family."""
from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame, QTabBar

from studio_widgets import ComboBox, DoubleSpinBox, Slider
from synth_effects_ui import EffectParameter, EffectsPanel, TEXT_TIMING
from synth_effects import EFFECT_BY_ID
from synth_subject import SUBJECTS, SOURCE_EFFECTS, active_subjects
from synth_inspector import grouped_paths
from synth_solids import hidden_controls as hidden_solid_controls
from synth_fonts import variable_weight


OBJECT_PATHS = {
    'memory': tuple('image_memory.'+key for key in ('persistence','drift','dissolve','trail_opacity','shape','size','sides','path','travel','amplitude_x','amplitude_y','period','variation','palette')),
    'lattice': tuple('chromatic_lattice.'+key for key in ('shape','sides','spacing','size','minimum','rotation','wave_shape','wavelength','period','phase','direction','angle','pulse','palette','color_period','color_phase','color_spread','gradient','saturation','light','rim','softness','glow','glow_radius','grain','background')),
    'solid': tuple('solid.'+key for key in ('shape','model_data','height_stretch','scale','yaw','pitch','roll','turn_speed','tumble_speed','roll_speed','variation','perspective','corner_radius','material','roughness','specular','glass_transmission','glass_refraction','pip_size','pip_light','pip_depth','palette','shading','light')),
    'prismatic': tuple('prismatic_field.'+key for key in ('shape','sides','center_shape','size','gather','opening','fold_depth','rotation','transition_ease','turn_settle','palette','wash','saturation','light')),
    'radial': tuple('radial_bloom.'+key for key in ('expansion','petals','detail','branching','flow','variation','center_drift','palette','light')),
    'text': EFFECT_BY_ID['text'].paths,
    'silhouette': ('silhouette.model', 'silhouette.scale', 'silhouette.yaw', 'silhouette.definition', 'silhouette.pitch', 'silhouette.roll', 'silhouette.center_x', 'silhouette.center_y', 'silhouette.neck_length', 'silhouette.neck_fullness', 'silhouette.softness'),
    'ink': ('ink_bloom.shape', 'ink_bloom.artwork', 'ink_bloom.shape_width', 'ink_bloom.shape_height',
            'ink_bloom.sides', 'ink_bloom.shape_rotation', 'ink_bloom.size', 'ink_bloom.count',
            'ink_bloom.spread'),
    'particles': ('particles.attractor', 'particles.scale', 'particles.count', 'particles.dot_size',
                  'particles.yaw', 'particles.pitch',
                  'particles.neck_fade'),
}
TEXT_PAGE_PATHS = ('text.font', 'text.weight', 'text.content', 'text.badge',
                   'text.badge_show_subtitle', 'text.badge_subtitle')


class SubjectPanel(QWidget):
    selected = Signal(str)
    restored = Signal()
    parameter_changed = Signal(str, str, object)
    parameter_reset = Signal(str, str)
    details_requested = Signal(str, bool)
    position_changed = Signal(str, float)
    position_reset = Signal()
    center_path_requested = Signal()
    automation_requested = Signal(str)
    navigation_changed = Signal()

    def __init__(self):
        super().__init__()
        self.kind = 'none'; self.updating = False; self.controls = {}; self.control_cache = {}; self.group_labels = {}
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self.header = QWidget(); header = QVBoxLayout(self.header)
        header.setContentsMargins(8, 4, 8, 0); header.setSpacing(5); root.addWidget(self.header)
        self.pages = QStackedWidget(); root.addWidget(self.pages)
        self.overview = QWidget(); layout = QVBoxLayout(self.overview)
        self.overview_scroll = QScrollArea(); self.overview_scroll.setWidgetResizable(True)
        self.overview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.overview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.overview_scroll.setWidget(self.overview); self.pages.addWidget(self.overview_scroll)
        self.details_editor = EffectsPanel()
        self.details_editor.scope_label.hide(); self.details_editor.add_button.hide()
        self.details_editor.back_button.clicked.disconnect()
        self.details_editor.back_button.setText('← Object')
        self.details_editor.back_button.setAccessibleName('Back to object')
        self.details_editor.back_button.clicked.connect(self.show_overview)
        self.pages.addWidget(self.details_editor)
        title = QLabel('OBJECT / content'); title.setObjectName('sectionTitle'); header.addWidget(title)
        row = QHBoxLayout()
        self.selector = ComboBox(); self.selector.setAccessibleName('Object type')
        for key, (label, _) in SUBJECTS.items(): self.selector.addItem(label, key)
        self.selector.setToolTip('Replace the object in this scope. Treatments, canvas and clip durations stay in place.')
        self.selector.currentIndexChanged.connect(self.choose); row.addWidget(self.selector, 1)
        self.restore = QPushButton('↶'); self.restore.setAccessibleName('Restore study object')
        self.restore.setToolTip('Follow the study or project source activation again. Keep your object parameters.')
        self.restore.clicked.connect(self.restored.emit); row.addWidget(self.restore); header.addLayout(row)
        self.note = QLabel(); self.note.setWordWrap(True); self.note.setObjectName('muted'); header.addWidget(self.note)
        self.text_tabs = QTabBar()
        for label in ('Text', 'Layout', 'Motion'): self.text_tabs.addTab(label)
        self.text_tabs.currentChanged.connect(self.change_text_tab); header.addWidget(self.text_tabs)
        self.text_layout_note = QLabel(); self.text_layout_note.setWordWrap(True)
        self.text_layout_note.setObjectName('muted'); layout.addWidget(self.text_layout_note)
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

    def show_overview(self):
        self.pages.setCurrentWidget(self.overview_scroll)
        self.navigation_changed.emit()

    def change_text_tab(self, index):
        self.show_text_controls(index)
        self.overview_scroll.verticalScrollBar().setValue(0)

    def show_details(self, effect, timing=False):
        if effect == 'text':
            self.show_overview(); self.text_tabs.setCurrentIndex(2 if timing else 1)
        else:
            from synth_creative import CREATIVE_CONTROLS
            self.details_editor.inspect_effect(effect)
            self.details_editor.parameter_tabs.setCurrentIndex((0 if timing else 1) if effect in CREATIVE_CONTROLS else (1 if timing else 0))
            self.pages.setCurrentWidget(self.details_editor)
        self.navigation_changed.emit()

    def reveal_control(self, path):
        if path not in self.controls or self.kind != 'text': return False
        self.show_overview()
        self.text_tabs.setCurrentIndex(0 if path in TEXT_PAGE_PATHS else 2 if path in TEXT_TIMING else 1)
        self.overview_scroll.ensureWidgetVisible(self.controls[path])
        return True

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
        previous_kind = self.kind
        self.kind = active[0] if active else 'none'
        if self.kind != previous_kind: self.show_overview()
        self.signal_effect = 'forms' if summary['forms']['active'] else 'rays'
        with QSignalBlocker(self.selector): self.selector.setCurrentIndex(self.selector.findData(self.kind))
        self.restore.setEnabled(any(entries.get(key, {}).get('mode', 'recipe') != 'recipe' for key in SOURCE_EFFECTS))
        scope = 'this clip' if local else 'the entire project'
        notes = {'prismatic': 'Choose the final shape and its placement. Transition easing and Turn settle shape the authored movements. Source controls opens the fold rhythm, rotation, ribbon and color drift. Color emulsion adds the film texture separately.', 'radial': 'Expanding crowns and fine branching rays. Source controls opens the full motion, palette and optical settings.', 'silhouette': 'A fixed human silhouette. Adjust its pose and framing here; Edge phosphor and Scan drag treat its outline.',
                 'text': 'Text edits the typeface, main wording and subtitle. The typeface applies to both text blocks. Layout controls size, spacing, frame and placement; Motion controls word changes and animation. Effects treats the resulting image.',
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
        self.text_tabs.setVisible(self.kind == 'text')
        self.text_layout_note.hide()
        self.details.setText('Text appearance…' if self.kind == 'text' else 'Source controls…')
        self.timing.setText('Creative motion…' if self.kind == 'particles' else 'Motion & timing…')
        paths = OBJECT_PATHS.get(self.kind, ())
        reading = self.kind == 'text' and summary['text']['ranges']['text.reveal'] == (4, 4)
        if reading:
            self.note.setText(f'Edit Wording and apply it: the montage adapts to complete words and letters. '
                             f'Montage duration includes the final phrase; match the clip duration for one full pass. '
                             f'Print collage and Film burn follow these reading beats. Changes apply to {scope}.')
            self.timing.setText('Reading & interruptions…')
        if set(self.controls) != set(paths):
            # Memory's exploration controls precede placement. Only move the
            # host when the source family changes, keeping edits scroll-stable.
            host_layout = self.overview.layout()
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
                        control = EffectParameter(path, editable_text=True); effect = path.split('.')[0]
                        control.changed.connect(lambda value, e=effect, p=path: self.parameter_changed.emit(e, p, value))
                        control.reset.connect(lambda e=effect, p=path: self.parameter_reset.emit(e, p))
                        control.animate.connect(self.automation_requested.emit)
                        self.control_cache[path] = control
                    control = self.control_cache[path]
                    if path not in TEXT_PAGE_PATHS: self.control_layout.addWidget(control)
                    if path in ('text.content', 'text.badge_subtitle'):
                        name = 'Main text' if path == 'text.content' else 'Subtitle'
                        control.label.setText(name)
                        control.input.editor.setAccessibleName(name)
                        control.input.apply.setText('Apply main text' if path == 'text.content' else 'Apply subtitle')
                    control.show(); self.controls[path] = control
                    if path == 'image_memory.amplitude_y':
                        self.control_layout.addWidget(self.motion_frame); self.motion_frame.show()
            # Keep shared typography above the text editors, independent of the
            # parameter registry's grouping and the length of either text block.
            for path in TEXT_PAGE_PATHS:
                if path in self.controls: self.wording_layout.addWidget(self.controls[path])
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
            self.text_ranges = summary['text']['ranges']
            self.show_text_controls()
        self.details.setVisible(bool(active) and self.kind != 'text'); self.timing.setVisible(self.kind == 'ink')
        self.updating = False

    def show_text_controls(self, _index=None):
        if self.kind != 'text' or not hasattr(self, 'text_ranges'): return
        ranges = self.text_ranges
        tab = self.text_tabs.currentIndex()
        reveal, fit = ranges['text.reveal'], ranges['text.fit']
        morph, reading = reveal == (3, 3), reveal == (4, 4)
        visible = set(TEXT_PAGE_PATHS if tab == 0 else TEXT_TIMING if tab == 2 else
                      (p for p in self.controls if p not in TEXT_PAGE_PATHS and p not in TEXT_TIMING))
        hidden = set()
        if ranges['text.font'][0] == ranges['text.font'][1] and not variable_weight(ranges['text.font'][0]): hidden.add('text.weight')
        if reveal[0] == reveal[1]:
            if not morph: hidden.update(p for p in self.controls if p.startswith('text.morph_'))
            if not reading: hidden.update(p for p in self.controls if p.startswith('text.reading_'))
            if morph or reading:
                hidden.update('text.'+p for p in ('word_seconds','fit','block_width','copies','copy_gap','copy_floor','wrap_columns'))
            if morph: hidden.update(('text.leading','text.align'))
        if fit[0] == fit[1] and fit[0] != 2: hidden.add('text.block_width')
        if not morph and not reading and fit[0] == fit[1] and fit[0] != 1: hidden.update(('text.fit_width','text.copy_floor'))
        if ranges['text.motion'][0] == ranges['text.motion'][1] and ranges['text.motion'][0] != 1: hidden.add('text.ease')
        visible -= hidden
        label_active = ranges['text.badge'] != (0, 0) and not (morph or reading)
        for path, control in self.controls.items():
            control.setVisible(path in visible)
            if path.startswith('text.badge_'): control.setEnabled(label_active)
        for title, paths in grouped_paths(self.controls):
            self.group_labels[title].setVisible(bool(visible.intersection(p for p in paths if p not in TEXT_PAGE_PATHS)))
        self.wording_host.setVisible(tab == 0)
        self.position_host.setVisible(tab == 1)
        self.control_host.setVisible(tab != 0)
        self.text_layout_note.setText('This word animation uses the main text only. Choose Whole phrase, One word or Type on in Motion to use a subtitle and frame.' if morph or reading else
                                     'Turn on Framed label to use a subtitle and frame. Choose Frame shape → None in Layout for text without an outline.')
        self.text_layout_note.setVisible(tab == 0 and not label_active)
        self.navigation_changed.emit()

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
