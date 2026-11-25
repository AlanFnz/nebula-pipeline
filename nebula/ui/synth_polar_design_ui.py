"""Portable gradient designs for the radial object editor."""
import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from nebula.sources.synth_folded_gradient import MAX_DESIGN_BYTES, decode_design, default_design


class PolarDesignControl(QWidget):
    changed = Signal(object)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        buttons = QHBoxLayout()
        for title, action in [('Load design…', self.load), ('Save design…', self.save)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.status = QLabel()
        self.status.setObjectName('muted')
        layout.addWidget(self.status)
        self._value = None
        self.setValue('')

    def value(self):
        return self._value

    def setValue(self, value):
        if value == self._value:
            return
        times, poses, _, _ = decode_design(value)
        self._value = value
        self.status.setText(f'{len(times)} poses · {poses.shape[1]} mirrored sectors')
        self.changed.emit(value)

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Load gradient design', '', 'Gradient design (*.json)')
        if path:
            try:
                with Path(path).open('rb') as stream:
                    raw = stream.read(MAX_DESIGN_BYTES + 1)
                if len(raw) > MAX_DESIGN_BYTES:
                    raise ValueError('This gradient design is too large.')
                self.setValue(raw.decode('utf-8'))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Cannot load gradient design', str(exc))

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save gradient design', 'gradient.json', 'Gradient design (*.json)')
        if path:
            try:
                Path(path).write_text(self._value or json.dumps(default_design()), encoding='utf-8')
            except OSError as exc:
                QMessageBox.warning(self, 'Cannot save gradient design', str(exc))
