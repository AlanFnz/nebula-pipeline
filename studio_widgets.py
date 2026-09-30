"""Parameter controls that leave wheel/trackpad scrolling to their panel.

Click, typing, keyboard arrows and dragging still edit values. An open combo's
popup owns its own scrolling; passing over a closed control never edits it.
"""
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSlider, QSpinBox


class ScrollThrough:
    def wheelEvent(self, event):
        event.ignore()


class ComboBox(ScrollThrough, QComboBox):
    pass


class DoubleSpinBox(ScrollThrough, QDoubleSpinBox):
    """Compact display without quantizing a recipe merely by showing it."""
    display_scale = 1.

    def textFromValue(self, value):
        return self.locale().toString(value * self.display_scale, 'f', min(2, self.decimals()))

    def valueFromText(self, text):
        clean = text.removeprefix(self.prefix()).removesuffix(self.suffix()).strip()
        if clean == self.textFromValue(self.value()):
            return self.value()  # Focus/blur must preserve hidden precision.
        value, valid = self.locale().toDouble(clean)
        return value / self.display_scale if valid else self.value()

    def validate(self, text, position):
        if self.display_scale == 1: return super().validate(text, position)
        clean = text.removeprefix(self.prefix()).removesuffix(self.suffix()).strip()
        if clean in ('', '-', '+', self.locale().decimalPoint()):
            return QValidator.State.Intermediate, text, position
        value, valid = self.locale().toDouble(clean)
        state = QValidator.State.Acceptable if valid and self.minimum() <= value / self.display_scale <= self.maximum() else QValidator.State.Invalid
        return state, text, position


def configure_parameter_spin(control, spec):
    """Small normalized quantities read as percentages, e.g. .0007 → .07%."""
    if spec.kind == 'float':
        control.setDecimals(12)
        control.display_scale = 100. if spec.step < .01 else 1.
        control.setSuffix(' %' if control.display_scale == 100 else '')
    control.setRange(spec.minimum, spec.maximum)
    control.setSingleStep(spec.step)
    control.setKeyboardTracking(False)


def parameter_number(spec, value):
    if spec.kind == 'int': return str(int(value))
    return f'{value * 100:.2f} %' if spec.step < .01 else f'{value:.2f}'


class SpinBox(ScrollThrough, QSpinBox):
    pass


class Slider(ScrollThrough, QSlider):
    pass
