"""Shared parameter widgets for effect and object inspectors."""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QStackedWidget, QSizePolicy, QGridLayout)
from studio_widgets import ComboBox as QComboBox, DoubleSpinBox as QDoubleSpinBox, SpinBox as QSpinBox
from studio_widgets import Slider, configure_parameter_spin, parameter_number
from synth_effects import parameter
from synth_artwork_ui import ArtworkControl
from synth_text_ui import TextControl
from synth_ink_timing import DURATION_KEYS
from synth_parameter_presentation import presentation

INK_DURATIONS = {f'ink_bloom.{key}' for key in DURATION_KEYS}


class ParameterRowLayout(QGridLayout):
    def __init__(self, control):
        super().__init__()
        self.control = control

    def heightForWidth(self, width):
        # Ancestor layouts ask for a height before assigning the new geometry.
        # Reflow now so a scroll area's cached height includes the wrapped row.
        self.control._arrange_row(width)
        return super().heightForWidth(width)

    def minimumSize(self):
        # The wide arrangement must allow its host to shrink far enough to
        # trigger wrapping; its current columns are not the narrow minimum.
        size = super().minimumSize()
        size.setWidth(min(size.width(), 240))
        return size


def format_value(path, value):
    spec = parameter(path)
    if spec.kind == 'text': return value.replace('\n', ' / ')[:60] or 'Empty text'
    if spec.kind == 'artwork': return 'Embedded artwork' if value else 'No artwork'
    if spec.choices:
        return spec.choices[int(value)]
    # Respect the shared percentage convention, including its saved precision.
    unit = '' if spec.kind == 'float' and spec.step < .01 else presentation(path).unit
    return parameter_number(spec, value) + unit


class EffectParameter(QWidget):
    changed = Signal(object)
    reset = Signal()
    animate = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.spec = spec = parameter(path)
        self.presentation = presentation(path)
        self._context_key = None
        self._text_drafts = {}
        self.fixed_start = spec.default
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 6); layout.setSpacing(4)
        self.slider = None
        self._row = ParameterRowLayout(self); self._row.setSpacing(6)
        self._row_mode = None
        self._label_container = QWidget()
        label_row = QHBoxLayout(self._label_container)
        label_row.setContentsMargins(0, 0, 0, 0); label_row.setSpacing(5)
        self.label = QLabel(spec.label); self.label.setWordWrap(True)
        self.label.setMinimumWidth(0); self.label.setToolTip(spec.hint)
        label_row.addWidget(self.label, 1)
        self.hue_swatch = None
        if self.presentation.hue:
            self.hue_swatch = QLabel(); self.hue_swatch.setFixedSize(14, 14)
            self.hue_swatch.setAccessibleName(spec.label + ' hue indication')
            label_row.addWidget(self.hue_swatch)
        if spec.kind in ('artwork', 'text'):
            self.input = ArtworkControl() if spec.kind == 'artwork' else TextControl()
            self.input.changed.connect(self.emit_change)
        elif spec.choices:
            self.input = QComboBox(); self.input.addItems(spec.choices)
            self.input.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.input.setMinimumContentsLength(12)
            self.input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.input.currentIndexChanged.connect(self.emit_change)
        else:
            self.input = QSpinBox() if spec.kind == 'int' else QDoubleSpinBox()
            configure_parameter_spin(self.input, spec)
            if spec.kind != 'float' or spec.step >= .01:
                self.input.setSuffix(self.presentation.unit)
            if path in INK_DURATIONS: self.input.setMinimum(0)
            self.input.valueChanged.connect(self.emit_change)
            self.slider = Slider(Qt.Orientation.Horizontal)
            self.slider.setRange(0, 1000); self.slider.setTracking(False)
            self.slider.setAccessibleName(spec.label + ' slider')
            self.slider.setToolTip('Drag to adjust. Release to update the preview. You can also type a value.')
            self.slider.sliderMoved.connect(self.preview_slider)
            self.slider.valueChanged.connect(self.commit_slider)
            self.input.valueChanged.connect(self.sync_slider)
        block_input = spec.kind in ('artwork', 'text')
        self._block_input = block_input
        self.input.setMinimumWidth(0 if block_input or spec.choices else 110)
        if not block_input and not spec.choices: self.input.setMaximumWidth(145)
        self.input.setToolTip(spec.hint); self.input.setAccessibleName(spec.label)
        if spec.kind == 'float' and spec.step < .01:
            self.input.setToolTip(spec.hint + ' Displayed as a percentage; 100% = 1 in the saved recipe. Saved precision is preserved.')
        self._input_hint = self.input.toolTip()
        self.value_stack = QStackedWidget()
        self.value_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.value_stack.addWidget(self.input)
        if not block_input:
            # The read-only label gives this stack height-for-width behavior.
            # Qt may otherwise shrink a fixed spin/combo page to label height,
            # clipping its themed padding and text inside a short inspector.
            self.input.ensurePolished()
            self.value_stack.setMinimumHeight(self.input.minimumSizeHint().height())
        self.animated_value = QLabel()
        self.animated_value.setWordWrap(True); self.animated_value.setMinimumWidth(0)
        self.animated_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.animated_value.setAccessibleName(spec.label + ' animated range')
        self.value_stack.addWidget(self.animated_value)
        self.animate_button = None
        from synth_automation import TARGETS
        from synth_instances import base_path
        if base_path(path) in TARGETS:
            self.animate_button = QPushButton("Animate…"); self.animate_button.setProperty("compact", True)
            self.animate_button.setMinimumHeight(28)
            self.animate_button.setAccessibleName("Animate " + spec.label)
            self.animate_button.setToolTip("Add a temporary clip gesture; the displayed value remains the base. Existing events are edited separately.")
            self.animate_button.clicked.connect(lambda: self.animate.emit(self.path))
        self.reset_button = QPushButton('↶'); self.reset_button.setFixedSize(30, 28)
        self.reset_button.setAccessibleName(f'Restore {spec.label}')
        self.reset_button.clicked.connect(self.reset.emit)
        layout.addLayout(self._row)
        if block_input: layout.addWidget(self.value_stack)
        self.fixed_choice = QWidget(); choice = QHBoxLayout(self.fixed_choice)
        choice.setContentsMargins(0, 0, 0, 0); choice.setSpacing(5)
        self.proposed_value = QLabel(); self.proposed_value.setWordWrap(True)
        self.proposed_value.setMinimumWidth(0); self.proposed_value.setObjectName('muted')
        choice.addWidget(self.proposed_value, 1)
        self.use_fixed = QPushButton('Use fixed value')
        self.use_fixed.setAccessibleName(f'Use fixed value for {spec.label}')
        self.use_fixed.clicked.connect(lambda: self.changed.emit(self.fixed_start))
        choice.addWidget(self.use_fixed); layout.addWidget(self.fixed_choice)
        self.fixed_choice.hide()
        self.origin = QLabel(); self.origin.setWordWrap(True)
        self.origin.setObjectName('muted'); layout.addWidget(self.origin)
        self._arrange_row()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange_row()

    def _arrange_row(self, width=None):
        """Wrap controls before their useful editing widths become cramped."""
        animated = self.value_stack.currentWidget() is self.animated_value
        if not self._block_input:
            maximum_height = 16777215 if animated else self.input.sizeHint().height()
            if self.value_stack.maximumHeight() != maximum_height:
                self.value_stack.setMaximumHeight(maximum_height)
        label_width = self.label.fontMetrics().horizontalAdvance(self.label.text())
        if self.hue_swatch: label_width += self.hue_swatch.width() + 5
        label_width = max(120, min(160, label_width))
        action_width = self.reset_button.width()
        if self.animate_button: action_width += self.animate_button.sizeHint().width() + 6
        if self.spec.choices:
            value_width = max(self.input.fontMetrics().horizontalAdvance(choice)
                              for choice in self.spec.choices) + 40
        else:
            value_width = max(110, self.input.minimumSizeHint().width())
        needed = label_width + action_width + value_width + 18
        if self.slider and not animated: needed += 106
        wrapped = self._block_input or (self.width() if width is None else width) < needed
        mode = (wrapped, animated)
        if mode == self._row_mode: return
        self._row_mode = mode
        while self._row.count(): self._row.takeAt(0)
        for column in range(5):
            self._row.setColumnStretch(column, 0)
            self._row.setColumnMinimumWidth(column, 0)
        if wrapped:
            self._row.addWidget(self._label_container, 0, 0, 1, 2)
            if self.animate_button:
                self._row.addWidget(self.reset_button, 0, 2)
                self._row.addWidget(self.animate_button, 0, 3)
            else:
                self._row.addWidget(self.reset_button, 0, 2, 1, 2, Qt.AlignmentFlag.AlignRight)
            self._row.setColumnStretch(0, 1)
            if not self._block_input:
                if self.slider and not animated:
                    self._row.addWidget(self.slider, 1, 0, 1, 2)
                    self._row.addWidget(self.value_stack, 1, 2, 1, 2)
                else:
                    self._row.addWidget(self.value_stack, 1, 0, 1, 4)
        else:
            self._row.addWidget(self._label_container, 0, 0)
            self._row.setColumnMinimumWidth(0, label_width)
            self._row.setColumnStretch(0, 1)
            if self.slider and not animated:
                self._row.addWidget(self.slider, 0, 1)
                self._row.setColumnStretch(1, 2)
            self._row.addWidget(self.value_stack, 0, 2)
            if self.spec.choices or animated: self._row.setColumnStretch(2, 2)
            self._row.addWidget(self.reset_button, 0, 3)
            if self.animate_button: self._row.addWidget(self.animate_button, 0, 4)
        self._row.invalidate()
        self.updateGeometry()

    def set_automation_count(self, count):
        if self.animate_button:
            text = f"Automations ({count})…" if count else "Animate…"
            label = self.spec.label + (" · Base" if count else "")
            if self.animate_button.text() == text and self.label.text() == label: return
            self.animate_button.setText(text)
            self.animate_button.setAccessibleName(f"{self.spec.label}: {count} automation events" if count else "Animate " + self.spec.label)
            self.label.setText(label)
            self._row_mode = None
            self._arrange_row()

    def emit_change(self, value):
        self.update_swatch(value)
        self.changed.emit(value)

    def update_swatch(self, value, *, animated=False):
        if self.hue_swatch is None: return
        if animated:
            self.hue_swatch.setStyleSheet('border: 1px solid #777; background: transparent;')
            self.hue_swatch.setToolTip('Hue varies across the animated range. A fixed hue shows a hue indication here.')
            self.hue_swatch.setAccessibleDescription('Animated hue; no single hue is selected.')
        else:
            color = QColor.fromHsvF(float(value) % 1., 1., 1.)
            self.hue_swatch.setStyleSheet(f'border: 1px solid #777; background: {color.name()};')
            tip = 'Hue indication only. Saturation, brightness and compositing determine the final color.'
            self.hue_swatch.setToolTip(tip); self.hue_swatch.setAccessibleDescription(tip)

    def slider_value(self, position):
        spec = self.spec
        low, high = self.input.minimum(), self.input.maximum()
        raw = low + position / 1000 * (high - low)
        value = max(low, min(high, round(raw / spec.step) * spec.step))
        return round(value) if spec.kind == 'int' else value

    def preview_slider(self, position):
        value = self.slider_value(position)
        with QSignalBlocker(self.input): self.input.setValue(value)
        self.update_swatch(value)

    def commit_slider(self, position):
        value = self.slider_value(position)
        with QSignalBlocker(self.input): self.input.setValue(value)
        self.emit_change(value)

    def sync_slider(self, value):
        if self.slider:
            with QSignalBlocker(self.slider):
                self.slider.setValue(round(1000 * (value-self.input.minimum()) / max(1e-12, self.input.maximum()-self.input.minimum())))

    def draft_state(self):
        """Presentation draft for panels that recreate controls while navigating."""
        if self.spec.kind != 'text': return None
        return {'value': self.input.value(), 'text': self.input.editor.toPlainText()}

    def restore_draft(self, draft):
        """Restore wording only when its authored baseline still matches."""
        if self.spec.kind == 'text' and draft and draft['value'] == self.input.value():
            self.input.editor.setPlainText(draft['text'])

    def pending_text_drafts(self):
        """Return unapplied wording in retained scopes, including the current one."""
        if self.spec.kind != 'text': return ()
        drafts = dict(self._text_drafts)
        drafts[self._context_key] = self.draft_state()
        return tuple((context, draft) for context, draft in drafts.items()
                     if draft and draft['value'] != draft['text'])

    def acknowledge_text_draft(self, context_key, value):
        """Forget a draft only after its owning panel has authored that wording."""
        draft = self._text_drafts.get(context_key)
        if draft and draft['text'] == value: self._text_drafts.pop(context_key)
        if context_key == self._context_key and self.spec.kind == 'text' and self.input.editor.toPlainText() == value:
            with QSignalBlocker(self.input): self.input.setValue(value)

    def refresh(self, bounds, fixed, inherited, available, *, scope_label=None,
                parent_value=None, origin_label=None, context_key=None):
        low, high = bounds
        if self.path in INK_DURATIONS and fixed is not None and fixed < 0:
            fixed = None; inherited = False
        if context_key != self._context_key and self.spec.kind == 'text':
            self._text_drafts[self._context_key] = self.draft_state()
        context_changed = context_key != self._context_key
        self._context_key = context_key
        inherited_fixed = fixed is None and inherited and parent_value is not None
        value = fixed if fixed is not None else parent_value if inherited_fixed else low
        self.fixed_start = low
        if self.path in INK_DURATIONS: self.fixed_start = max(0, low)
        animated = fixed is None and not inherited_fixed and low != high
        self.value_stack.setCurrentIndex(1 if animated else 0)
        range_text = f'{format_value(self.path, low)} … {format_value(self.path, high)}'
        self.animated_value.setText(range_text)
        self.animated_value.setToolTip('Read-only animated range. Use fixed value below to replace this animation in the selected scope.')
        self.proposed_value.setText(f'Start: {format_value(self.path, self.fixed_start)}')
        proposal = 'Proposed initial fixed value from the displayed range; this is not a sampled playhead value.'
        self.proposed_value.setToolTip(proposal)
        self.use_fixed.setToolTip(proposal + ' Other parameters keep following their animation.')
        self.fixed_choice.setVisible(animated); self.use_fixed.setEnabled(available)
        with QSignalBlocker(self.input):
            if self.spec.choices: self.input.setCurrentIndex(int(value))
            else: self.input.setValue(value)
        if context_changed and self.spec.kind == 'text':
            # TextControl skips identical setValue calls to preserve edits on a
            # mere refresh. A different scope must start from its own baseline.
            self.input.editor.setPlainText(value)
            self.restore_draft(self._text_drafts.get(context_key))
        self.input.setEnabled(available)
        self.update_swatch(value, animated=animated)
        if self.slider:
            self.sync_slider(value); self.slider.setVisible(not animated); self.slider.setEnabled(available)
        self.reset_button.setEnabled(fixed is not None)
        provenance = 'Entire project' if inherited else 'Study'
        if fixed is not None:
            provenance = 'Entire project' if scope_label == 'Entire project' else 'Clip' if scope_label and scope_label.startswith('Clip') else 'Local'
        state = 'Animated' if animated else 'Fixed' if fixed is not None or inherited_fixed else 'Following'
        self.origin.setText(origin_label or f'{state} · {provenance}' + ('' if available else ' · Unavailable'))
        explanation = f'{state} value from {scope_label or "this scope" if fixed is not None else provenance.lower()}. ' + \
                      ('Enable or add this effect to edit its values.' if not available else 'Editing authors a fixed value in the selected scope.')
        self.origin.setToolTip(explanation)
        self.origin.setAccessibleDescription(explanation)
        ordinary_project = available and not animated and not inherited and not origin_label and scope_label == 'Entire project'
        self.origin.setVisible(not ordinary_project)
        self.setAccessibleDescription(self.origin.text() + '. ' + explanation)
        self.label.setAccessibleDescription(explanation)
        self.input.setAccessibleDescription(explanation)
        self.input.setToolTip(self._input_hint + ' ' + explanation)
        if self.spec.choices:
            self.input.setToolTip(self.spec.choices[int(value)] + '. ' + self.input.toolTip())
            self.input.view().setMinimumWidth(max(self.input.fontMetrics().horizontalAdvance(choice) for choice in self.spec.choices) + 40)
        self.animated_value.setAccessibleDescription(explanation + ' ' + self.animated_value.toolTip())
        if self.slider: self.slider.setAccessibleDescription(explanation)
        self._arrange_row()
        restore_target = 'entire project' if inherited else 'study'
        self.reset_button.setToolTip(f'Remove only this parameter’s local override and follow the {restore_target} again.')
        self.setToolTip('Editing fixes this parameter across the scope; other study changes keep playing.')
