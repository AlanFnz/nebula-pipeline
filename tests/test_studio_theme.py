"""Shared chrome stays readable and paints all editor/dialog control states."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt, qInstallMessageHandler
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QLabel, QLineEdit, QListWidget, QMenu, QPlainTextEdit,
    QPushButton, QSlider, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget,
)

from nebula.ui.studio_theme import COLORS, apply_theme, terminal_font, ui_font
from nebula.ui.synth_effect_parameter_ui import EffectParameter


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


@pytest.mark.parametrize('width, wrapped', [(560, False), (375, True)])
def test_inspector_numeric_fields_align_with_and_without_animation(themed_app, width, wrapped):
    panel = QWidget()
    panel.setObjectName('inspectorColumn')
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    controls = [EffectParameter(path) for path in ('film_burn.reading_clarity', 'film_burn.opening')]
    for control in controls:
        layout.addWidget(control)
    panel.resize(width, 190)
    panel.show()
    themed_app.processEvents()
    try:
        fixed, animatable = controls
        assert fixed.animate_button is None and animatable.animate_button is not None
        animatable.set_automation_count(2)
        animatable.refresh((0.2, 1.3), None, False, True)
        assert animatable.animated_value.isVisible() and not animatable.slider.isVisible()
        animatable.refresh((0.2, 1.3), 0.8, False, True)
        themed_app.processEvents()
        assert all(c._row_mode == (wrapped, False) for c in controls)
        for name in ('input', 'reset_button', 'slider'):
            positions = [getattr(c, name).mapTo(panel, QPoint()).x() for c in controls]
            assert positions[0] == positions[1]
        for c in controls:
            end_of_value = c.input.mapTo(panel, QPoint(c.input.width(), 0)).x()
            assert c.reset_button.mapTo(panel, QPoint()).x() == end_of_value + c._row.horizontalSpacing()
            assert c.reset_button.text() == 'Restore'
        if wrapped:
            assert animatable.animate_button.geometry().bottom() < animatable.reset_button.y()
        else:
            assert animatable.animate_button.x() > animatable.slider.geometry().right()
    finally:
        panel.close()


@pytest.mark.parametrize('width,height', [(1280, 800), (1726, 960)])
def test_mixer_aligns_common_controls_with_chimes_highpass(themed_app, width, height):
    from nebula.audio.synth_lattice_sound import color_wave_sound
    from nebula.ui.synth_visual_sound_ui import VisualSoundDialog

    dialog = VisualSoundDialog()
    try:
        dialog.set_config(color_wave_sound())
        dialog.tabs.setCurrentIndex(4)
        dialog.resize(width, height)
        dialog.sound_splitter.setSizes([width // 3, 2 * width // 3])
        dialog.show()
        themed_app.processEvents()
        mixer = dialog.mixer
        opening, chimes = mixer.channels['body'], mixer.channels['chimes']
        scroll = dialog.tabs.currentWidget()
        assert scroll.horizontalScrollBar().maximum() == 0
        for key in ('level_db', 'mute', 'solo', 'eq_enabled',
                    'low_db', 'mid_db', 'high_db', 'low_hz', 'mid_hz', 'high_hz'):
            left, right = opening[key], chimes[key]
            assert left.isVisible() and right.isVisible()
            assert left.mapTo(mixer, QPoint()).y() == right.mapTo(mixer, QPoint()).y()
        cutoff_top = chimes['highpass_hz'].mapTo(mixer, QPoint()).y()
        freq_bottom = chimes['high_hz'].mapTo(mixer, chimes['high_hz'].rect().bottomLeft()).y()
        assert cutoff_top > freq_bottom
        assert not dialog.has_sound_draft()
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
