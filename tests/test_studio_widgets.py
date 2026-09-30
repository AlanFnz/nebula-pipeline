import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget

from studio_widgets import ComboBox, DoubleSpinBox, Slider, SpinBox


@pytest.mark.parametrize('kind', [ComboBox, SpinBox, DoubleSpinBox, Slider])
def test_focused_controls_pass_wheel_to_panel_without_editing(kind):
    app = QApplication.instance() or QApplication([])
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.resize(320, 180)
    content = QWidget(); content.setMinimumHeight(800); layout = QVBoxLayout(content)
    control = kind()
    if isinstance(control, ComboBox):
        control.addItems(['First', 'Second', 'Third']); control.setCurrentIndex(1)
        read = control.currentIndex
    else:
        control.setRange(0, 100); control.setValue(50); read = control.value
        if isinstance(control, Slider): control.setOrientation(Qt.Orientation.Horizontal)
    layout.addWidget(control); layout.addStretch(); scroll.setWidget(content)
    scroll.show(); app.processEvents()
    try:
        for focused in (False, True):
            scroll.verticalScrollBar().setValue(0)
            control.setFocus() if focused else control.clearFocus()
            app.processEvents()
            point = control.mapTo(scroll, control.rect().center())
            QTest.wheelEvent(scroll.windowHandle(), point, QPoint(0, -120))
            app.processEvents()
            assert read() == (1 if isinstance(control, ComboBox) else 50)
            assert scroll.verticalScrollBar().value() > 0
        # Deliberate keyboard edits still work after scrolling over the control.
        QTest.keyClick(control, Qt.Key.Key_Down if isinstance(control, ComboBox) else Qt.Key.Key_Up)
        assert read() == (2 if isinstance(control, ComboBox) else 51)
    finally:
        scroll.close(); app.processEvents()


def test_dropdown_still_opens_and_accepts_a_clicked_option():
    app = QApplication.instance() or QApplication([])
    combo = ComboBox(); combo.addItems(['First', 'Second', 'Third']); combo.show(); app.processEvents()
    try:
        QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
        app.processEvents()
        view = combo.view()
        assert view.isVisible()
        # Qt briefly blocks release events after opening a popup.
        QTest.qWait(150)
        target = view.model().index(2, 0)
        point = QPoint(view.viewport().rect().center().x(), view.visualRect(target).center().y())
        QTest.mouseMove(view.viewport(), point)
        app.processEvents()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        app.processEvents()
        assert combo.currentText() == 'Third'
    finally:
        combo.close(); app.processEvents()
