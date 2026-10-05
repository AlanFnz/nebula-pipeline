"""Choose a clip's look before importing its independent footage."""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from studio_widgets import ComboBox


class AddVideoSectionDialog(QDialog):
    def __init__(self, document, index, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add footage clip'); self.resize(440, 220)
        layout = QVBoxLayout(self)
        title = QLabel('NEW CLIP / choose its look'); title.setObjectName('sectionTitle')
        layout.addWidget(title)
        self.look = ComboBox(); self.look.setAccessibleName('New clip look')
        self.look.addItem('Project look · no clip overrides', None)
        for position, section in enumerate(document['sections']):
            name = document['phrases'][section['phrase']]['name']
            self.look.addItem(f'Copy clip {position + 1} · {name}', section['id'])
        self.look.setCurrentIndex(index + 1); layout.addWidget(self.look)
        self.note = QLabel(); self.note.setWordWrap(True); layout.addWidget(self.note)
        note = QLabel(f'Inserted after clip {index + 1}. Canvas and timeline FPS stay the same. '
                     'Choose the new video next; cancelling adds nothing.')
        note.setWordWrap(True); note.setObjectName('muted'); layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.choose = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.choose.setText('Choose footage…'); self.choose.setObjectName('primary')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.look.currentIndexChanged.connect(self.describe); self.describe()

    def describe(self, *_args):
        self.note.setText('Copy effects, automation, framing and duration. New footage starts at its beginning '
                          'at normal speed, with one play.' if self.look.currentData() else
                          'Use the current phrase and project effects, without clip overrides or automation. '
                          'Duration follows the new footage (up to five minutes).')

