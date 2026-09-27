"""Shared native artwork importer for the composer and detailed editor."""
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QInputDialog, QMessageBox

from synth_artwork import decode_artwork, encode_artwork, validate_artwork


class ArtworkControl(QWidget):
    changed = Signal(object)

    def __init__(self):
        super().__init__()
        self._value = ''
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.import_button = QPushButton('Import…')
        self.import_button.setAccessibleName('Import stamp artwork')
        self.import_button.clicked.connect(self.import_file); row.addWidget(self.import_button)
        self.clear_button = QPushButton('Clear')
        self.clear_button.setAccessibleName('Clear stamp artwork')
        self.clear_button.clicked.connect(lambda: self.setValue('')); row.addWidget(self.clear_button)
        layout.addLayout(row)
        self.status = QLabel(); self.status.setObjectName('muted'); self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh()

    def value(self):
        return self._value

    def setValue(self, value):
        value = validate_artwork(value)
        if value == self._value: return
        self._value = value; self.refresh(); self.changed.emit(value)

    def refresh(self):
        if self._value:
            image = decode_artwork(self._value)
            self.status.setText(f'Embedded · {image.width} × {image.height}')
        else:
            self.status.setText('PNG cutout or silhouette')
        self.clear_button.setEnabled(bool(self._value))

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import stamp artwork', str(Path.home() / 'Pictures'), 'Artwork (*.png *.webp *.tif *.tiff *.jpg *.jpeg *.bmp)')
        if not path: return
        try:
            with Image.open(path) as image:
                mode = 'auto'
                if image.convert('RGBA').getchannel('A').getextrema()[0] == 255:
                    choice, accepted = QInputDialog.getItem(self, 'Silhouette from artwork', 'Which part should receive ink?', ('Light areas on dark background', 'Dark areas on light background'), 0, False)
                    if not accepted: return
                    mode = 'dark' if choice.startswith('Dark') else 'light'
                value = encode_artwork(image, mode)
            self.setValue(value)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            QMessageBox.warning(self, 'Cannot import artwork', str(exc))
