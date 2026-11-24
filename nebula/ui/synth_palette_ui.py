"""A compact palette menu with visual samples; applying remains document-owned."""
from PySide6.QtCore import Signal, QSignalBlocker, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from nebula.ui.studio_widgets import ComboBox
from nebula.ui.synth_color_ui import display_color


class PaletteSelector(QWidget):
    chosen = Signal(str)

    def __init__(self):
        super().__init__()
        self.menu_layout = None
        layout = QVBoxLayout(self); layout.setContentsMargins(0,4,0,6); layout.setSpacing(4)
        row = QHBoxLayout(); row.addWidget(QLabel('Color palette'))
        self.combo = ComboBox(); self.combo.setAccessibleName('Color palette')
        self.combo.setMinimumWidth(0); self.combo.setIconSize(QSize(80,18))
        self.combo.setToolTip('Apply a coordinated palette to the current editing scope. Individual colors remain editable. Command-Z undoes the whole palette change.')
        self.combo.activated.connect(self.choose)
        row.addWidget(self.combo,1); layout.addLayout(row)
        self.note = QLabel(); self.note.setObjectName('muted'); self.note.setWordWrap(True)
        layout.addWidget(self.note)

    def choose(self, index):
        key = self.combo.itemData(index)
        if key is not None: self.chosen.emit(key)

    def refresh(self, key, note, palettes, *, order=None, inherit_label=None):
        with QSignalBlocker(self.combo):
            layout = (palettes, order, inherit_label)
            if self.menu_layout != layout:
                self.menu_layout = layout
                self.combo.clear()
                self.combo.addItem('Custom / animated', None)
                self.combo.model().item(0).setEnabled(False)
                if inherit_label:
                    self.combo.addItem(inherit_label, 'inherit')
                for palette in palettes:
                    colors = palette.colors if order is None else tuple(palette.colors[i] for i in order)
                    image = QPixmap(80, 18)
                    painter = QPainter(image)
                    for index, color in enumerate(colors):
                        left = index * image.width() // len(colors)
                        right = (index + 1) * image.width() // len(colors)
                        painter.fillRect(left, 0, right-left, image.height(), display_color(color))
                    painter.end()
                    self.combo.addItem(QIcon(image), palette.label, palette.key)
            self.combo.setCurrentIndex(max(0,self.combo.findData(key)))
        self.note.setText(note)
