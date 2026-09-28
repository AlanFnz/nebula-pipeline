"""Explicit multiline text edits shared by the object and detailed inspectors."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QPushButton, QLabel
from synth_text import validate_text


class TextControl(QWidget):
    changed = Signal(object)

    def __init__(self):
        super().__init__()
        self._value = ''
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.editor = QPlainTextEdit(); self.editor.setAccessibleName('Text wording')
        self.editor.setPlaceholderText('Write your phrase…'); self.editor.setMaximumHeight(105)
        layout.addWidget(self.editor)
        self.note = QLabel('Line breaks are preserved.'); self.note.setWordWrap(True); self.note.setObjectName('muted'); layout.addWidget(self.note)
        self.apply = QPushButton('Apply text'); self.apply.setEnabled(False); layout.addWidget(self.apply)
        self.editor.textChanged.connect(self.check)
        self.apply.clicked.connect(self.commit)

    def check(self):
        value = self.editor.toPlainText()
        try:
            validate_text(value)
            self.note.setText(f'{len(value)} / 512 characters · line breaks preserved')
            self.apply.setEnabled(value != self._value)
        except ValueError as exc:
            self.note.setText(str(exc)); self.apply.setEnabled(False)

    def commit(self):
        value = validate_text(self.editor.toPlainText())
        if value != self._value:
            self._value = value; self.check(); self.changed.emit(value)

    def value(self): return self._value

    def setValue(self, value):
        if value == self._value: return
        self._value = value
        self.editor.setPlainText(value)
        self.check()
