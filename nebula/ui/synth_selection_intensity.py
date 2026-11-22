"""Edit one effect's base intensity across an explicit selection of clips."""
import math

from PySide6.QtCore import QLocale, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from nebula.ui.studio_widgets import Slider


class SelectionIntensity(QWidget):
    offset_requested = Signal(float)
    absolute_requested = Signal(float)

    def __init__(self):
        super().__init__()
        self.context = None
        self.bounds = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toggle = QPushButton()
        self.toggle.setCheckable(True)
        self.toggle.setProperty('compact', True)
        self.toggle.setToolTip('Edit the intensity of this effect on the selected timeline clips.')
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.controls = QWidget()
        row = QHBoxLayout(self.controls)
        row.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel()
        row.addWidget(self.summary)
        label = QLabel('Offset')
        row.addWidget(label)
        self.slider = Slider(Qt.Orientation.Horizontal)
        label.setBuddy(self.slider)
        self.slider.setAccessibleName('Offset selected clip intensities')
        self.slider.setToolTip('Drag to offset each base intensity. The group stops when one clip reaches 0 or 100%. Release to apply.')
        self.slider.setTracking(False)
        self.slider.setSingleStep(10)
        self.slider.setPageStep(100)
        row.addWidget(self.slider, 1)
        label = QLabel('Set all (%)')
        self.number = QLineEdit()
        self.number.setAccessibleName('Set all selected clip intensities in percent')
        self.number.setToolTip('Enter a fixed base intensity for all selected clips. Clip automation still applies.')
        self.number.setMaximumWidth(78)
        self.number.setPlaceholderText('Mixed')
        validator = QDoubleValidator(0., 100., 2, self.number)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        locale = self.number.locale()
        locale.setNumberOptions(locale.numberOptions() | QLocale.NumberOption.RejectGroupSeparator)
        validator.setLocale(locale)
        self.number.setValidator(validator)
        label.setBuddy(self.number)
        row.addWidget(label)
        row.addWidget(self.number)
        layout.addWidget(self.controls)
        self.toggle.toggled.connect(self.controls.setVisible)
        self.slider.sliderMoved.connect(self.show_offset)
        self.slider.valueChanged.connect(self.apply_offset)
        self.number.editingFinished.connect(self.apply_absolute)
        self.number.returnPressed.connect(self.toggle.setFocus)
        self.controls.hide()
        self.hide()

    def set_target(self, effect_id, clip_ids):
        context = (effect_id, frozenset(clip_ids)) if effect_id and len(clip_ids) > 1 else None
        if self.context != context:
            self.context = context
            self.bounds = None
            self.number.setText('')
            with QSignalBlocker(self.slider):
                self.slider.setSliderDown(False)
            self.toggle.setChecked(False)
        self.setVisible(context is not None)
        if context:
            self.toggle.setText(f'Editing intensity · {len(clip_ids)} clips' if self.toggle.isChecked()
                                else f'Edit {len(clip_ids)} clips')

    def set_values(self, values):
        low, high = min(values), max(values)
        if self.bounds == (low, high):
            return
        self.bounds = low, high
        with QSignalBlocker(self.slider):
            self.slider.setRange(-math.ceil(low * 10), math.ceil((100. - high) * 10))
            self.slider.setValue(0)
        self.slider.setEnabled(low > 0 or high < 100)
        self.show_offset(0)
        self.number.setText(self.format_percent(low) if low == high else '')

    def format_percent(self, value):
        return self.number.locale().toString(value, 'f', 2).rstrip('0').rstrip(self.number.locale().decimalPoint())

    def offset(self, ticks):
        low, high = self.bounds
        return max(-low, min(100. - high, ticks / 10.))

    def show_offset(self, ticks):
        low, high = self.bounds
        delta = self.offset(ticks)
        text = self.format_percent(low + delta)
        if low != high:
            text = f'Mixed values · {text}–{self.format_percent(high + delta)}'
        self.summary.setText(text + ' %')

    def apply_offset(self, ticks):
        if ticks and self.toggle.isChecked():
            self.offset_requested.emit(self.offset(ticks))

    def apply_absolute(self):
        if self.toggle.isChecked() and self.number.isModified() and self.number.hasAcceptableInput():
            value, ok = self.number.validator().locale().toDouble(self.number.text())
            self.number.setModified(False)
            if ok:
                self.absolute_requested.emit(value)
