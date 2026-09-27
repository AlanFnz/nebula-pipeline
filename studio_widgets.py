"""Parameter controls that leave wheel/trackpad scrolling to their panel.

Click, typing, keyboard arrows and dragging still edit values. An open combo's
popup owns its own scrolling; passing over a closed control never edits it.
"""
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSlider, QSpinBox


class ScrollThrough:
    def wheelEvent(self, event):
        event.ignore()


class ComboBox(ScrollThrough, QComboBox):
    pass


class DoubleSpinBox(ScrollThrough, QDoubleSpinBox):
    pass


class SpinBox(ScrollThrough, QSpinBox):
    pass


class Slider(ScrollThrough, QSlider):
    pass
