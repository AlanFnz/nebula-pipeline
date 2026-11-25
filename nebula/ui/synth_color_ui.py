"""Visual color editing over existing HSV parameters; no rendering changes."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QDialog, QColorDialog,
                               QDialogButtonBox)
from nebula.ui.studio_widgets import ComboBox
from nebula.sources.synth_palettes import SHARED_PALETTES


@dataclass(frozen=True)
class ColorSpec:
    key: str
    label: str
    channels: tuple[str, str, str]
    module: str = 'dye_transfer'

    @property
    def paths(self):
        return tuple(self.module + '.' + channel for channel in self.channels)


COLORS = (
    ColorSpec('paper', 'Background color', ('paper_hue', 'paper_saturation', 'paper_light')),
    ColorSpec('ink', 'Ink color', ('ink_hue', 'ink_saturation', 'ink_light')),
)


def display_color(hsv):
    """Show the clamped RGB used by the renderer, including overbright stock."""
    import colorsys
    rgb = colorsys.hsv_to_rgb(*hsv)
    return QColor.fromRgbF(*(min(1., max(0., value)) for value in rgb))


def palette_icon(colors):
    image = QPixmap(80, 18)
    painter = QPainter(image)
    for index, color in enumerate(colors):
        left = index * image.width() // len(colors)
        right = (index + 1) * image.width() // len(colors)
        painter.fillRect(left, 0, right - left, image.height(), display_color(color))
    painter.end()
    return QIcon(image)


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
        from nebula.ui.synth_workspace_context import DialogContext
        self.document_context = DialogContext(self); layout.addWidget(self.document_context)
        title = QLabel(spec.label); title.setObjectName('effectTitle'); layout.addWidget(title)
        row = QHBoxLayout(); row.addWidget(QLabel('Apply to'))
        self.scope = ComboBox(); self.scope.setAccessibleName('Color editing scope')
        self.scope.addItem(context['shot_label'], context['section_id'])
        self.scope.addItem('Composition', None)
        if 'scope_id' in context:
            self.scope.setCurrentIndex(max(0, self.scope.findData(context['scope_id'])))
        row.addWidget(self.scope, 1); layout.addLayout(row)
        self.scope_note = QLabel(); self.scope_note.setObjectName('muted'); self.scope_note.setWordWrap(True)
        layout.addWidget(self.scope_note)
        self.scope.currentIndexChanged.connect(self.update_scope_note); self.update_scope_note()
        swatch_row = QHBoxLayout()
        swatch_row.addWidget(QLabel('Swatches'))
        self.swatch_source = ComboBox()
        self.swatch_source.setAccessibleName('Swatch palette')
        self.swatch_source.setIconSize(QSize(64, 15))
        self.swatch_source.addItem('Project colors')
        for palette in SHARED_PALETTES:
            self.swatch_source.addItem(palette_icon(palette.colors), palette.label)
        swatch_row.addWidget(self.swatch_source, 1)
        layout.addLayout(swatch_row)
        self.swatch_sets = (context['palette'], *(p.colors for p in SHARED_PALETTES))
        palette = QGridLayout(); palette.setSpacing(6)
        self.palette_buttons = []
        for index in range(max(map(len, self.swatch_sets))):
            button = QPushButton(); button.setFixedSize(36, 30)
            button.setAutoDefault(False)
            button.clicked.connect(lambda checked=False, i=index: self.select_swatch(
                self.swatch_sets[self.swatch_source.currentIndex()][i]))
            palette.addWidget(button, index // 12, index % 12)
            self.palette_buttons.append(button)
        layout.addLayout(palette)
        self.swatch_source.currentIndexChanged.connect(self.show_swatches)
        self.show_swatches(0)
        self.picker = QColorDialog(display_color(self.original), self)
        self.picker.setOptions(QColorDialog.ColorDialogOption.DontUseNativeDialog |
                               QColorDialog.ColorDialogOption.NoButtons)
        self.picker.setWindowFlags(Qt.WindowType.Widget)
        layout.addWidget(self.picker)
        # Switching away from the native macOS dialog creates fresh widgets;
        # initialize them after the options and window flags are in place.
        self.picker.setCurrentColor(display_color(self.original))
        self.picker.currentColorChanged.connect(self.color_changed)
        comparison = QHBoxLayout()
        self.before_swatch = QLabel(); self.after_swatch = QLabel()
        for label, swatch in (('Current', self.before_swatch), ('New', self.after_swatch)):
            comparison.addWidget(QLabel(label)); swatch.setFixedSize(64, 30); comparison.addWidget(swatch)
        comparison.addStretch(1); layout.addLayout(comparison)
        self.before_swatch.setStyleSheet(swatch_style(display_color(self.original)))
        self.after_swatch.setStyleSheet(swatch_style(display_color(self.original)))
        self.picker.currentColorChanged.connect(lambda c: self.after_swatch.setStyleSheet(swatch_style(c)))
        self.note = QLabel('Color before texture, lighting and other effects. The monitor shows the finished result.')
        self.note.setObjectName('muted'); self.note.setWordWrap(True); layout.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Apply color')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def show_swatches(self, index):
        colors = self.swatch_sets[index]
        label = self.swatch_source.itemText(index) if index else 'Project'
        for i, button in enumerate(self.palette_buttons):
            button.setVisible(i < len(colors))
            if i < len(colors):
                color = display_color(colors[i])
                button.setStyleSheet(swatch_style(color))
                name = f'{label} color {color.name().upper()}'
                button.setAccessibleName(name)
                button.setToolTip(name)

    def update_scope_note(self):
        if 'scope_note' in self.context:
            self.scope_note.setText(self.context['scope_note']); return
        self.scope_note.setText('Sets a fixed color for this shot. Other shots keep their colors.'
                                if self.scope.currentData() is not None else
                                'Sets one shared color across the composition, replacing its color changes. Explicit clip colors still take priority.')

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
    """Color cards and compact palette swatches share the same scoped picker."""
    changed = Signal(str, object, object)
    restored = Signal(str)

    def __init__(self, specs=COLORS, *, palette=()):
        super().__init__()
        self.specs = (*specs, *palette)
        self.active_keys = {spec.key for spec in self.specs}
        self.context_provider = None
        self.cards = {}
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 4, 0, 4); layout.setSpacing(6)
        self.chips = {}
        self.chip_row = QWidget()
        row = QHBoxLayout(self.chip_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        for spec in palette:
            button = QPushButton()
            button.setMinimumWidth(0)
            button.setFixedHeight(26)
            button.setAccessibleName('Choose ' + spec.label.lower())
            button.clicked.connect(lambda _checked=False, key=spec.key: self.open_picker(key))
            restore = QAction('Restore ' + spec.label.lower(), button)
            restore.triggered.connect(lambda _checked=False, key=spec.key: self.restored.emit(key))
            button.addAction(restore)
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
            self.chips[spec.key] = button
            row.addWidget(button, 1)
        self.chip_row.setVisible(bool(palette))
        layout.addWidget(self.chip_row)
        for spec in specs:
            card = ColorCard(spec); self.cards[spec.key] = card
            card.choose.connect(self.open_picker); card.restore.connect(self.restored.emit)
            layout.addWidget(card)
        note = QLabel('Click a swatch to choose a color. Animated colors follow the preview frame.')
        note.setObjectName('muted'); note.setWordWrap(True); layout.addWidget(note)

    def refresh(self):
        if self.context_provider is None: return
        for spec in self.specs:
            if spec.key in self.active_keys:
                context = self.context_provider(spec.key)
                if spec.key in self.chips:
                    button = self.chips[spec.key]
                    color = display_color(context['hsv'])
                    style = f'background: {color.name()}; border: 1px solid #778181; border-radius: 3px; padding: 0;'
                    if button.styleSheet() != style:
                        button.setStyleSheet(style)
                    button.setToolTip(f'{spec.label} · {color.name().upper()}')
                    button.setAccessibleDescription(button.toolTip())
                    button.actions()[0].setEnabled(context['overridden'])
                else:
                    self.cards[spec.key].refresh(context)

    def show_colors(self, keys):
        self.active_keys = set(keys)
        for key, card in self.cards.items(): card.setVisible(key in self.active_keys)
        for key, chip in self.chips.items(): chip.setVisible(key in self.active_keys)
        self.chip_row.setVisible(bool(self.active_keys.intersection(self.chips)))
        self.setVisible(bool(self.active_keys))
        self.refresh()

    def open_picker(self, key):
        if self.context_provider is None: return
        context = self.context_provider(key)
        spec = next(spec for spec in self.specs if spec.key == key)
        dialog = ColorPicker(spec, context, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Opening and accepting an unchanged selection must not freeze an
            # animated color or quantize its hidden precision.
            hsv = dialog.selected_hsv()
            if (tuple(hsv) != tuple(context['hsv']) or
                    (dialog.scope.currentData() is None and 'scope_id' not in context) or
                    ('scope_id' in context and dialog.scope.currentData() != context['scope_id'])):
                self.changed.emit(key, hsv, dialog.scope.currentData())
        dialog.deleteLater()
