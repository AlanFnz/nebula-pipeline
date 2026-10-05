"""Choose material before entering the existing Object and Effects workflow."""
from PySide6.QtWidgets import (QButtonGroup, QDialog, QDialogButtonBox, QGridLayout,
                              QLabel, QPlainTextEdit, QPushButton, QStackedWidget,
                              QVBoxLayout, QWidget)

from studio_widgets import ComboBox
from synth import SHAPES
from synth_starting_points import DEFAULT_TEXT
from synth_text import validate_text


class NewPieceDialog(QDialog):
    def __init__(self, canvas, fps, studies, selected_study=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('New piece'); self.resize(580, 480)
        self.kind = 'text'
        layout = QVBoxLayout(self)
        title = QLabel('START / choose your material'); title.setObjectName('sectionTitle')
        layout.addWidget(title)
        note = QLabel('Start with a visible object, then build its treatment in Effects. '
                      'You can change the object and resize or add clips later.')
        note.setWordWrap(True); layout.addWidget(note)
        dimensions = QLabel(f"Canvas {canvas['width']} × {canvas['height']} · Timeline {fps} fps")
        dimensions.setObjectName('muted'); layout.addWidget(dimensions)
        grid = QGridLayout(); layout.addLayout(grid)
        self.choices = {}; self.group = QButtonGroup(self); self.group.setExclusive(True)
        choices = (('text', 'Text', 'Editable typography'),
                   ('shape', 'Shape', 'A geometric source'),
                   ('model', 'Model', 'A classical human head'),
                   ('video', 'Video', 'Import your footage'),
                   ('remix', 'Remix a study', 'Build on an example'))
        for index, (key, label, hint) in enumerate(choices):
            button = QPushButton(f'{label}\n{hint}'); button.setCheckable(True)
            button.setMinimumHeight(64); button.setAccessibleName(f'Start with {label}')
            self.group.addButton(button); self.choices[key] = button
            button.clicked.connect(lambda _checked=False, kind=key: self.select(kind))
            grid.addWidget(button, index // 3, index % 3)
        self.pages = QStackedWidget(); layout.addWidget(self.pages, 1)
        self.page_by_kind = {}
        for key, _label, _hint in choices:
            page = QWidget(); page_layout = QVBoxLayout(page); page_layout.setContentsMargins(0, 8, 0, 0)
            self.page_by_kind[key] = page; self.pages.addWidget(page)
            if key == 'text':
                page_layout.addWidget(QLabel('Wording'))
                self.text = QPlainTextEdit(DEFAULT_TEXT); self.text.setAccessibleName('New piece wording')
                self.text.setMaximumHeight(96); self.text.textChanged.connect(self.validate)
                page_layout.addWidget(self.text)
            elif key == 'shape':
                page_layout.addWidget(QLabel('Shape'))
                self.shape = ComboBox(); self.shape.setAccessibleName('Starting shape')
                for value in SHAPES: self.shape.addItem(value, value.lower())
                page_layout.addWidget(self.shape)
            elif key == 'model':
                page_layout.addWidget(QLabel('Doryphoros / presentation'))
                self.model = ComboBox(); self.model.setAccessibleName('Starting model presentation')
                self.model.addItem('Solid silhouette', 'silhouette')
                self.model.addItem('Particle head', 'particles'); page_layout.addWidget(self.model)
            elif key == 'video':
                description = QLabel('Choose a video next. Its native canvas and frame rate will '
                                     'be used. Source controls handle framing and trim; Effects treats the image.')
                description.setWordWrap(True); page_layout.addWidget(description)
            else:
                page_layout.addWidget(QLabel('Study'))
                self.study = ComboBox(); self.study.setAccessibleName('Study to remix')
                self.study.setSizeAdjustPolicy(ComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                self.study.setMinimumContentsLength(24)
                for entry in studies: self.study.addItem(entry.label, entry.identifier)
                if selected_study is not None:
                    index = self.study.findData(selected_study)
                    if index >= 0: self.study.setCurrentIndex(index)
                self.study.currentIndexChanged.connect(self.validate)
                page_layout.addWidget(self.study)
                description = QLabel('Open an independent editable copy with the study’s saved canvas and timing.')
                description.setWordWrap(True); page_layout.addWidget(description)
            page_layout.addStretch(1)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setObjectName('muted')
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.create = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.create.setObjectName('primary'); self.create.setAccessibleName('Create new piece')
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons); self.select('text')

    def select(self, kind):
        self.kind = kind; self.choices[kind].setChecked(True)
        self.pages.setCurrentWidget(self.page_by_kind[kind]); self.validate()

    def validate(self, *_args):
        if not hasattr(self, 'create'): return
        self.create.setText({'video': 'Choose video…', 'remix': 'Remix study'}.get(self.kind, 'Create piece'))
        message = ''
        if self.kind == 'text':
            try:
                if not validate_text(self.text.toPlainText()).strip(): message = 'Enter some text to start with.'
            except ValueError as exc: message = str(exc)
        elif self.kind == 'remix' and self.study.currentData() is None:
            message = 'Choose a study to remix.'
        self.error.setText(message); self.create.setEnabled(not message)

    def request(self):
        return dict(kind=self.kind, text=self.text.toPlainText(), shape=self.shape.currentData(),
                    model=self.model.currentData(), study=self.study.currentData())
