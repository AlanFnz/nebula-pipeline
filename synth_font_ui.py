"""One searchable picker for bundled typefaces and active system styles."""
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QDialog, QLineEdit, QListWidget, QListWidgetItem,
                               QDialogButtonBox)
from PIL.ImageQt import ImageQt
from studio_widgets import ComboBox
from synth_fonts import FONTS, font_label, validate_font, reference_for_face, system_catalog, resolve_font, clear_font_catalog


def bundled_index(choices, index):
    if choices == FONTS: return index
    if choices == ('Source pixels',) + FONTS: return index-1 if index else None
    return (None, 3, 4)[index]  # Optical print's original fragment choices.


class FontPicker(QDialog):
    def __init__(self, value, choices=FONTS, parent=None):
        super().__init__(parent); self.setWindowTitle('Choose typeface'); self.resize(640, 620)
        self.choices = choices; self.selected = value; self.rows = []; self.system_rows = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText('Search family or style…')
        self.search.setAccessibleName('Search typefaces'); row.addWidget(self.search, 1)
        self.library = ComboBox(); self.library.addItems(('All fonts', 'Nebula fonts', 'System fonts'))
        self.library.setAccessibleName('Font library'); row.addWidget(self.library)
        self.refresh_button = QPushButton('Refresh'); self.refresh_button.clicked.connect(self.reload); row.addWidget(self.refresh_button); layout.addLayout(row)
        self.list = QListWidget(); self.list.setAccessibleName('Available typefaces and styles'); layout.addWidget(self.list, 1)
        self.sample = QLineEdit('Aa Bb · Revolution 0123'); self.sample.setAccessibleName('Typeface preview text'); layout.addWidget(self.sample)
        self.preview = QLabel(); self.preview.setMinimumHeight(110); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet('background: #141819; color: #e5e8e4; border-radius: 5px;'); layout.addWidget(self.preview)
        self.note = QLabel('Loading active system fonts…'); self.note.setWordWrap(True); self.note.setObjectName('muted'); layout.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.use_button = buttons.button(QDialogButtonBox.StandardButton.Ok); self.use_button.setText('Use typeface'); self.use_button.setEnabled(False)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.search.textChanged.connect(self.filter); self.library.currentIndexChanged.connect(self.filter)
        self.list.currentRowChanged.connect(self.update_preview); self.sample.textChanged.connect(self.update_preview)
        self.list.itemDoubleClicked.connect(lambda _: self.accept() if self.use_button.isEnabled() else None)
        QTimer.singleShot(0, self.reload)

    def reload(self):
        clear_font_catalog()
        try:
            self.system_rows = list(system_catalog()); self.catalog_error = ''
        except (OSError, ValueError) as exc:
            self.system_rows = []; self.catalog_error = f'System fonts could not be read: {exc}'
        self.filter()

    def filter(self, *_):
        self.rows = []; self.list.clear()
        query = self.search.text().casefold().strip(); library = self.library.currentIndex()
        selected_label = font_label(self.selected, self.choices)
        for index, name in enumerate(self.choices):
            if library == 2 or query not in name.casefold(): continue
            self.rows.append(index); self.list.addItem(QListWidgetItem(name + '   · Nebula'))
        for row in self.system_rows:
            label = f"{row['family']} · {row['style']}"
            if library == 1 or query not in label.casefold(): continue
            self.rows.append(row); self.list.addItem(QListWidgetItem(label + '   · System'))
        index = next((i for i, row in enumerate(self.rows) if
                      (font_label(row, self.choices) if isinstance(row, int) else f"{row['family']} · {row['style']}") == selected_label), 0)
        if self.rows: self.list.setCurrentRow(index)
        else:
            self.preview.clear(); self.use_button.setEnabled(False); self.note.setText('No matching typefaces.')

    def update_preview(self, *_):
        index = self.list.currentRow()
        if index < 0 or index >= len(self.rows): return
        row = self.rows[index]
        try:
            value = row if isinstance(row, int) else reference_for_face(row)
            face = bundled_index(self.choices, row) if isinstance(row, int) else value
            if face is None:
                self.preview.setText('Use the source image’s existing lettering')
            else:
                from synth_text import glyph_mask
                from PIL import Image
                sample = self.sample.text()[:120] or 'Aa Bb 0123'
                mask = glyph_mask(sample, face, 0., 1., 1)
                mask.thumbnail((580, 100), Image.Resampling.LANCZOS)
                canvas = Image.new('RGB', mask.size, '#141819'); canvas.paste('#e5e8e4', mask=mask)
                self.preview.setPixmap(QPixmap.fromImage(ImageQt(canvas)))
            self.selected = value; self.use_button.setEnabled(True)
            self.note.setText(self.catalog_error or ('Included in Nebula. Studies keep this exact font on every installation.' if isinstance(value, int) else
                              'System font · Uses this style as installed. Other computers need the same font file; it is not embedded in the project.'))
        except (OSError, ValueError) as exc:
            self.preview.clear(); self.use_button.setEnabled(False); self.note.setText(str(exc))


class FontControl(QWidget):
    changed = Signal(object)

    def __init__(self, choices=FONTS):
        super().__init__(); self.choices = choices; self._value = 0
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
        self.choose = QPushButton(); self.choose.setAccessibleName('Choose typeface'); self.choose.clicked.connect(self.open_picker); layout.addWidget(self.choose)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setObjectName('muted'); layout.addWidget(self.status)
        self.refresh()

    def value(self): return self._value
    def currentText(self): return font_label(self._value, self.choices)
    def currentIndex(self): return self._value if isinstance(self._value, int) else -1
    def setCurrentIndex(self, value): self.setValue(value)

    def setValue(self, value):
        value = validate_font(value, len(self.choices)-1)
        changed = value != self._value
        self._value = value; self.refresh()
        if changed: self.changed.emit(value)

    def refresh(self):
        label = font_label(self._value, self.choices)
        self.choose.setText(label + '  ▾'); self.choose.setToolTip('Choose from Nebula fonts or search the active fonts on this Mac.')
        self.status.hide()
        if isinstance(self._value, str):
            try:
                resolve_font(self._value)
                self.status.setText('System font · ' + label); self.status.show()
            except ValueError as exc:
                self.status.setText(str(exc)); self.status.show()

    def open_picker(self):
        dialog = FontPicker(self._value, self.choices, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.setValue(dialog.selected)

