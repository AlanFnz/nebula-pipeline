"""Visual color editing over existing HSV parameters; no rendering changes."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QDialog, QColorDialog,
                               QDialogButtonBox)
from studio_widgets import ComboBox


@dataclass(frozen=True)
class ColorSpec:
    key: str
    label: str
    channels: tuple[str, str, str]

    @property
    def paths(self):
        return tuple('dye_transfer.' + channel for channel in self.channels)


COLORS = (
    ColorSpec('paper', 'Background color', ('paper_hue', 'paper_saturation', 'paper_light')),
    ColorSpec('ink', 'Ink color', ('ink_hue', 'ink_saturation', 'ink_light')),
)


def display_color(hsv):
    """Show the clamped RGB used by the renderer, including overbright stock."""
    import colorsys
    rgb = colorsys.hsv_to_rgb(*hsv)
    return QColor.fromRgbF(*(min(1., max(0., value)) for value in rgb))


def swatch_style(color):
    return (f'background: {color.name()}; border: 1px solid #778181; border-radius: 5px;'
            ' min-width: 28px; padding: 0px;')


class ColorPicker(QDialog):
    """Cancel is read-only; Apply emits one complete HSV transaction."""
    def __init__(self, spec, context, parent=None):
        super().__init__(parent)
        self.setWindowTitle(spec.label)
        self.context = context
        self.original = tuple(context['hsv'])
        self.exact_selection = self.original
        self._selecting_swatch = False
        layout = QVBoxLayout(self)
        title = QLabel(spec.label); title.setObjectName('effectTitle'); layout.addWidget(title)
        row = QHBoxLayout(); row.addWidget(QLabel('Apply to'))
        self.scope = ComboBox(); self.scope.setAccessibleName('Color editing scope')
        self.scope.addItem(context['shot_label'], context['section_id'])
        self.scope.addItem('Entire project', None)
        row.addWidget(self.scope, 1); layout.addLayout(row)
        self.scope_note = QLabel(); self.scope_note.setObjectName('muted'); self.scope_note.setWordWrap(True)
        layout.addWidget(self.scope_note)
        self.scope.currentIndexChanged.connect(self.update_scope_note); self.update_scope_note()
        layout.addWidget(QLabel('Colors in this project'))
        palette = QGridLayout(); palette.setSpacing(6)
        self.palette_buttons = []
        for index, hsv in enumerate(context['palette']):
            color = display_color(hsv)
            button = QPushButton(); button.setFixedSize(36, 30)
            button.setStyleSheet(swatch_style(color))
            button.setAccessibleName(f'Project color {color.name().upper()}')
            button.setToolTip(f'{color.name().upper()} · use this project color')
            button.clicked.connect(lambda checked=False, hsv=hsv: self.select_swatch(hsv))
            palette.addWidget(button, index // 12, index % 12)
            self.palette_buttons.append(button)
        layout.addLayout(palette)
        self.picker = QColorDialog(display_color(self.original), self)
        self.picker.setOptions(QColorDialog.ColorDialogOption.DontUseNativeDialog |
                               QColorDialog.ColorDialogOption.NoButtons)
        self.picker.setWindowFlags(Qt.WindowType.Widget)
        layout.addWidget(self.picker)
        # Switching away from the native macOS dialog creates fresh widgets;
        # initialize them after the options and window flags are in place.
        self.picker.setCurrentColor(display_color(self.original))
        self.picker.currentColorChanged.connect(self.color_changed)
        self.note = QLabel('Color before texture, lighting and other effects. The monitor shows the finished result.')
        self.note.setObjectName('muted'); self.note.setWordWrap(True); layout.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Apply color')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def update_scope_note(self):
        self.scope_note.setText('Sets a fixed color for this shot. Other shots keep their colors.'
                                if self.scope.currentData() is not None else
                                'Sets one shared color across the project, replacing its color changes. Explicit clip colors still take priority.')

    def select_swatch(self, hsv):
        self._selecting_swatch = True
        self.picker.setCurrentColor(display_color(hsv))
        self._selecting_swatch = False
        self.exact_selection = tuple(hsv)

    def color_changed(self, _color):
        if not self._selecting_swatch:
            self.exact_selection = None

    def selected_hsv(self):
        if self.exact_selection is not None: return self.exact_selection
        color = self.picker.currentColor()
        h, s, v, _ = color.getHsvF()
        # Grey/black has no hue. Preserve the authored hue for later saturation
        # edits. A manually chosen RGB/hex color must match the chosen swatch;
        # unedited and project palette colors keep their original HDR values.
        return (self.original[0] if h < 0 else h, s, v)


class ColorCard(QFrame):
    choose = Signal(str)
    restore = Signal(str)

    def __init__(self, spec):
        super().__init__()
        self.spec = spec; self.setObjectName('colorCard')
        self.setMinimumWidth(0)
        row = QHBoxLayout(self); row.setContentsMargins(10, 9, 10, 9); row.setSpacing(10)
        self.swatch = QPushButton(); self.swatch.setFixedSize(48, 42)
        self.swatch.setAccessibleName('Choose ' + spec.label.lower())
        self.swatch.clicked.connect(lambda: self.choose.emit(spec.key)); row.addWidget(self.swatch)
        labels = QVBoxLayout(); labels.setSpacing(2)
        label = QLabel(spec.label); label.setObjectName('sectionTitle'); labels.addWidget(label)
        self.value = QLabel(); self.value.setObjectName('muted'); self.value.setWordWrap(True)
        self.value.setMinimumWidth(0); labels.addWidget(self.value); row.addLayout(labels, 1)
        self.button = QPushButton('Choose…'); self.button.clicked.connect(lambda: self.choose.emit(spec.key))
        self.button.setAccessibleName('Choose ' + spec.label.lower() + ' from palette'); row.addWidget(self.button)
        self.reset = QPushButton('↶'); self.reset.setFixedSize(30, 28)
        self.reset.setAccessibleName('Restore ' + spec.label.lower())
        self.reset.clicked.connect(lambda: self.restore.emit(spec.key)); row.addWidget(self.reset)

    def refresh(self, context):
        color = display_color(context['hsv'])
        style = swatch_style(color)
        if self.swatch.styleSheet() != style: self.swatch.setStyleSheet(style)
        self.swatch.setToolTip('Click to choose a color. Preview before texture and other effects.')
        self.value.setText(f'{color.name().upper()} · {context["preview_label"]}')
        self.swatch.setAccessibleDescription(self.value.text())
        self.reset.setEnabled(context['overridden'])
        self.reset.setToolTip('Restore all three color channels in the current editing scope; other settings stay intact.')


class ColorPanel(QWidget):
    """Two aligned visual controls; their numeric channels remain discoverable."""
    changed = Signal(str, object, object)
    restored = Signal(str)

    def __init__(self):
        super().__init__()
        self.context_provider = None
        self.cards = {}
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 4, 0, 4); layout.setSpacing(6)
        for spec in COLORS:
            card = ColorCard(spec); self.cards[spec.key] = card
            card.choose.connect(self.open_picker); card.restore.connect(self.restored.emit)
            layout.addWidget(card)
        note = QLabel('Click a swatch to choose a color. Animated colors follow the preview frame.')
        note.setObjectName('muted'); note.setWordWrap(True); layout.addWidget(note)

    def refresh(self):
        if self.context_provider is None: return
        for spec in COLORS:
            self.cards[spec.key].refresh(self.context_provider(spec.key))

    def open_picker(self, key):
        if self.context_provider is None: return
        context = self.context_provider(key)
        spec = next(spec for spec in COLORS if spec.key == key)
        dialog = ColorPicker(spec, context, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Opening and accepting an unchanged selection must not freeze an
            # animated color or quantize its hidden precision.
            hsv = dialog.selected_hsv()
            if tuple(hsv) != tuple(context['hsv']) or dialog.scope.currentData() is None:
                self.changed.emit(key, hsv, dialog.scope.currentData())
        dialog.deleteLater()
