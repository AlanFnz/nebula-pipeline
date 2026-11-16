"""A compact palette menu with visual samples; applying remains document-owned."""
from PySide6.QtCore import Signal, QSignalBlocker, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from studio_widgets import ComboBox
from synth_color_ui import display_color


class PaletteSelector(QWidget):
    chosen = Signal(str)

    def __init__(self, palettes):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(0,4,0,6); layout.setSpacing(4)
        row = QHBoxLayout(); row.addWidget(QLabel('Color palette'))
        self.combo = ComboBox(); self.combo.setAccessibleName('Color palette')
        self.combo.setMinimumWidth(0); self.combo.setIconSize(QSize(80,18))
        self.combo.addItem('Custom / animated', None)
        self.combo.model().item(0).setEnabled(False)
        for palette in palettes:
            image = QPixmap(80,18); painter = QPainter(image)
            # Background first, then the two figures, eye and ink.
            for i, index in enumerate((2,0,1,3,4)):
                painter.fillRect(i*16,0,16,18,display_color(palette.colors[index]))
            painter.end()
            self.combo.addItem(QIcon(image),palette.label,palette.key)
        self.combo.setToolTip('Apply a coordinated palette to the current editing scope. Individual colors remain editable. Command-Z undoes the whole palette change.')
        self.combo.activated.connect(self.choose)
        row.addWidget(self.combo,1); layout.addLayout(row)
        self.note = QLabel(); self.note.setObjectName('muted'); self.note.setWordWrap(True)
        layout.addWidget(self.note)

    def choose(self, index):
        key = self.combo.itemData(index)
        if key is not None: self.chosen.emit(key)

    def refresh(self, key, note):
        with QSignalBlocker(self.combo):
            self.combo.setCurrentIndex(max(0,self.combo.findData(key)))
        self.note.setText(note)
