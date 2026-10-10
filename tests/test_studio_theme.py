"""Shared chrome stays readable and paints all editor/dialog control states."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import Qt, qInstallMessageHandler
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QLabel, QLineEdit, QListWidget, QMenu, QPlainTextEdit,
    QPushButton, QSlider, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget,
)

from studio_theme import COLORS, apply_theme, terminal_font, ui_font


@pytest.fixture
def themed_app():
    app = QApplication.instance() or QApplication([])
    old_font = QFont(app.font()); old_palette = QPalette(app.palette())
    old_style = app.style().objectName(); old_sheet = app.styleSheet()
    apply_theme(app)
    yield app
    app.setStyleSheet(''); app.setStyle(old_style)
    app.setFont(old_font); app.setPalette(old_palette); app.setStyleSheet(old_sheet)


def _contrast(first, second):
    def luminance(color):
        components = QColor(color).getRgbF()[:3]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in components]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    values = sorted((luminance(first), luminance(second)))
    return (values[1] + .05) / (values[0] + .05)


def test_shared_palette_and_numeric_typography(themed_app):
    # Custom painting and native delegates need the same readable palette as QSS.
    for surface in ('background', 'panel', 'input', 'raised'):
        assert _contrast(COLORS['text'], COLORS[surface]) >= 7
        assert _contrast(COLORS['muted'], COLORS[surface]) >= 4.5
    assert _contrast(COLORS['on_accent'], COLORS['accent']) >= 7
    assert _contrast(COLORS['selection_text'], COLORS['selected']) >= 7
    palette = themed_app.palette()
    assert palette.color(QPalette.ColorRole.Text) == QColor(COLORS['text'])
    assert palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text) == QColor(COLORS['disabled'])
    dialog = QDialog(); layout = QFormLayout(dialog)
    label = QLabel('Parameter'); value = QDoubleSpinBox(); clock = QLabel('00:12.00'); clock.setObjectName('timecode')
    layout.addRow(label, value); layout.addRow(clock); dialog.show(); themed_app.processEvents()
    try:
        assert label.font().family() == ui_font().family()
        assert label.font().family() in QFontDatabase.families()
        assert value.font().family() == terminal_font().family()
        assert clock.font().family() == terminal_font().family()
    finally:
        dialog.close()


def test_dialog_widget_matrix_has_no_style_parser_errors(themed_app):
    messages = []
    previous = qInstallMessageHandler(lambda _kind, _context, message: messages.append(message))
    apply_theme(themed_app)
    dialog = QDialog(); layout = QVBoxLayout(dialog)
    group = QGroupBox('Controls'); form = QFormLayout(group); layout.addWidget(group)
    combo = QComboBox(); combo.addItems(['First', 'Second'])
    for label, widget in (
        ('Choice', combo), ('Integer', QSpinBox()), ('Amount', QDoubleSpinBox()),
        ('Search', QLineEdit()), ('Text', QPlainTextEdit()),
        ('Slider', QSlider(Qt.Orientation.Horizontal)), ('Enabled', QCheckBox('Enabled')),
    ):
        form.addRow(label, widget)
    tabs = QTabWidget(); tabs.addTab(QWidget(), 'Parameters'); tabs.addTab(QWidget(), 'Advanced'); layout.addWidget(tabs)
    table = QTableWidget(1, 1); table.setHorizontalHeaderLabels(['Study']); table.setItem(0, 0, QTableWidgetItem('Selected Study')); table.selectRow(0); layout.addWidget(table)
    items = QListWidget(); items.addItems(['Automation', 'Disabled automation']); items.setCurrentRow(0); layout.addWidget(items)
    menu = QMenu(dialog); menu.addAction('Open'); menu.addSeparator(); menu.addAction('Unavailable').setEnabled(False)
    button = QToolButton(); button.setText('Options'); button.setMenu(menu); button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup); layout.addWidget(button)
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); layout.addWidget(box)
    try:
        dialog.resize(500, 700); dialog.show(); themed_app.processEvents(); dialog.grab()
        combo.showPopup(); themed_app.processEvents(); combo.view().grab(); combo.hidePopup()
        menu.ensurePolished(); menu.grab()
        assert not [message for message in messages if any(term in message.lower() for term in ('parse', 'stylesheet', 'unknown property', 'could not create pixmap'))]
    finally:
        dialog.close(); qInstallMessageHandler(previous)


def test_primary_disabled_and_keyboard_focus_are_visibly_distinct(themed_app):
    dialog = QDialog(); layout = QVBoxLayout(dialog)
    normal = QPushButton('Normal'); primary = QPushButton('Create'); primary.setObjectName('primary')
    disabled = QPushButton('Unavailable'); disabled.setEnabled(False)
    field = QLineEdit('Editable')
    for widget in (normal, primary, disabled, field): layout.addWidget(widget)
    dialog.resize(300, 200); dialog.show(); field.setFocus(); themed_app.processEvents()
    try:
        def surface(widget):
            return widget.grab().toImage().pixelColor(widget.width() // 2, widget.height() - 8)
        assert surface(normal) == QColor(COLORS['raised'])
        assert surface(primary) == QColor(COLORS['accent'])
        assert surface(disabled) == QColor(COLORS['disabled_surface'])
        idle = normal.grab().toImage()
        normal.setFocus(); themed_app.processEvents()
        assert normal.hasFocus()
        assert normal.grab().toImage() != idle
    finally:
        dialog.close()
