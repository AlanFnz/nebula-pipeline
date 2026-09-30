"""Shared parameter widgets for effect and object inspectors."""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget
from studio_widgets import ComboBox as QComboBox, DoubleSpinBox as QDoubleSpinBox, SpinBox as QSpinBox
from studio_widgets import Slider, configure_parameter_spin, parameter_number
from synth_effects import parameter
from synth_artwork_ui import ArtworkControl
from synth_text_ui import TextControl
from synth_ink_timing import DURATION_KEYS

INK_DURATIONS = {f'ink_bloom.{key}' for key in DURATION_KEYS}


def format_value(path, value):
    spec = parameter(path)
    if spec.kind == 'text': return value.replace('\n', ' / ')[:60] or 'Empty text'
    if spec.kind == 'artwork': return 'Embedded artwork' if value else 'No artwork'
    if spec.choices:
        return spec.choices[int(value)]
    return parameter_number(spec, value)


class EffectParameter(QWidget):
    changed = Signal(object)
    reset = Signal()

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.spec = spec = parameter(path)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 8); layout.setSpacing(3)
        self.slider = None
        row = QHBoxLayout()
        label = QLabel(spec.label); label.setToolTip(spec.hint); row.addWidget(label, 1)
        if spec.kind in ('artwork', 'text'):
            self.input = ArtworkControl() if spec.kind == 'artwork' else TextControl(); self.input.changed.connect(self.changed.emit)
        elif spec.choices:
            self.input = QComboBox(); self.input.addItems(spec.choices)
            self.input.currentIndexChanged.connect(self.changed.emit)
        else:
            self.input = QSpinBox() if spec.kind == "int" else QDoubleSpinBox()
            configure_parameter_spin(self.input, spec)
            if path in INK_DURATIONS: self.input.setMinimum(0)
            self.input.valueChanged.connect(self.changed.emit)
            self.slider = Slider(Qt.Orientation.Horizontal)
            self.slider.setRange(0, 1000); self.slider.setTracking(False)
            self.slider.setAccessibleName(spec.label + ' slider')
            self.slider.setToolTip('Drag to adjust. Release to update the preview. You can also type a value.')
            self.slider.sliderMoved.connect(self.preview_slider)
            self.slider.valueChanged.connect(self.commit_slider)
            self.input.valueChanged.connect(self.sync_slider)
        self.input.setMinimumWidth(110); self.input.setToolTip(spec.hint)
        self.input.setAccessibleName(spec.label)
        if spec.kind == 'float' and spec.step < .01:
            self.input.setToolTip(spec.hint + ' Displayed as a percentage; 100% = 1 in the saved recipe. Saved precision is preserved.')
        self.value_stack = QStackedWidget()
        self.value_stack.addWidget(self.input)
        self.animated_value = QPushButton()
        self.animated_value.setAccessibleName(f"Fix {spec.label}")
        self.animated_value.clicked.connect(lambda: self.changed.emit(self.fixed_start))
        self.value_stack.addWidget(self.animated_value)
        block_input = spec.kind in ('artwork', 'text')
        if not block_input: row.addWidget(self.value_stack)
        self.reset_button = QPushButton("↶"); self.reset_button.setFixedWidth(30)
        self.reset_button.setToolTip("Follow the recipe or whole-clip value again.")
        self.reset_button.setAccessibleName(f"Reset {spec.label}")
        self.reset_button.clicked.connect(self.reset.emit); row.addWidget(self.reset_button)
        layout.addLayout(row)
        if block_input: layout.addWidget(self.value_stack)
        if self.slider: layout.addWidget(self.slider)
        self.origin = QLabel(); self.origin.setObjectName("muted"); layout.addWidget(self.origin)

    def slider_value(self, position):
        spec = self.spec
        low, high = self.input.minimum(), self.input.maximum()
        raw = low + position / 1000 * (high - low)
        value = max(low, min(high, round(raw / spec.step) * spec.step))
        return round(value) if spec.kind == 'int' else value

    def preview_slider(self, position):
        with QSignalBlocker(self.input): self.input.setValue(self.slider_value(position))

    def commit_slider(self, position):
        value = self.slider_value(position)
        with QSignalBlocker(self.input): self.input.setValue(value)
        self.changed.emit(value)

    def sync_slider(self, value):
        if self.slider:
            with QSignalBlocker(self.slider):
                self.slider.setValue(round(1000 * (value-self.input.minimum()) / max(1e-12, self.input.maximum()-self.input.minimum())))

    def refresh(self, bounds, fixed, inherited, available):
        low, high = bounds
        if self.path in INK_DURATIONS and fixed is not None and fixed < 0:
            fixed = None; inherited = False
        value = fixed if fixed is not None else low
        self.fixed_start = low
        animated = fixed is None and low != high and available
        self.value_stack.setCurrentIndex(1 if animated else 0)
        self.animated_value.setText("Varies" if self.spec.choices or self.spec.kind in ('artwork', 'text') else f"{format_value(self.path, low)} … {format_value(self.path, high)}")
        self.animated_value.setToolTip(f"Animated range. Click to set a fixed value, starting at {format_value(self.path, low)}.")
        with QSignalBlocker(self.input):
            if self.spec.choices: self.input.setCurrentIndex(int(value))
            else: self.input.setValue(value)
        self.input.setEnabled(available)
        if self.slider:
            self.sync_slider(value); self.slider.setVisible(not animated); self.slider.setEnabled(available)
        self.reset_button.setEnabled(fixed is not None)
        if fixed is not None:
            text = "Fixed in this scope"
        elif not available:
            text = "Enable this effect to edit"
        elif low != high:
            text = f"Animated / varying: {format_value(self.path, low)} … {format_value(self.path, high)}"
        else:
            text = "From whole clip" if inherited else "From recipe"
        self.origin.setText(text)
        self.setToolTip("Editing fixes this parameter across the scope; all other recipe changes keep playing.")

