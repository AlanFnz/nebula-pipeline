"""Read-only document identity and scope wording shared by workspace views."""
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolTip, QWidget

from synth_workspace_widgets import ElidingLabel


@dataclass(frozen=True)
class DocumentContext:
    location: str
    owner: str
    path: object
    dirty: bool
    block: bool = False

    @property
    def file_state(self):
        return 'Not saved' if self.path is None else 'Unsaved changes' if self.dirty else 'Saved'

    @property
    def all_clips(self):
        return 'All internal clips in this block' if self.block else 'All clips in this composition'

    @property
    def save_hint(self):
        return (f'Save writes the complete {self.owner}, including applied edits.' +
                (f'\n{self.path}' if self.path else '\nSave to create a file.'))


def studio_context(studio):
    kind, document = studio.document_state()
    dirty = hasattr(studio, 'clean_document') and studio.has_unsaved_changes()
    navigation = studio.workspace_navigation
    if navigation and navigation.editor is studio and navigation.montage:
        montage = navigation.montage
        return DocumentContext(
            f"{montage.document['name']} › {montage.block_label(navigation.clip_id)}",
            'montage', montage.path, dirty or montage.document != montage.clean, True)
    label = 'Composition' if kind == 'composition' else 'Detailed sequence copy' if studio.detailed_copy else kind.title()
    return DocumentContext(f"{label} · {document.get('name', 'Untitled')}", kind,
                           studio.document_path, dirty)


def montage_context(montage):
    return DocumentContext(f"Montage · {montage.document['name']}", 'montage', montage.path,
                           montage.document != montage.clean)


class ContextLabel(ElidingLabel):
    """Keep names compact; keyboard focus and hover expose the complete text."""
    def __init__(self, text=''):
        super().__init__(text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), self.toolTip(), self)

    def focusOutEvent(self, event):
        QToolTip.hideText()
        super().focusOutEvent(event)


class ContextHeader(QWidget):
    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self); row.setContentsMargins(0, 0, 0, 0)
        self.location = ContextLabel(); self.location.setAccessibleName('Document context')
        self.state = QLabel(); self.state.setObjectName('muted')
        self.state.setAccessibleName('Document file status')
        row.addWidget(self.location, 1); row.addWidget(self.state)

    def refresh(self, context):
        self.location.setText(context.location)
        self.location.setToolTip(context.location + '\n' + context.save_hint)
        self.state.setText(context.file_state)
        self.state.setToolTip(context.save_hint)


class ContextSummary(QLabel):
    """Keep selection, editing and playback readable together at narrow widths."""
    def __init__(self):
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setMinimumWidth(0)
        self.setObjectName('monitorMeta')
        self.setAccessibleName('Selection, editing and playback context')


class DialogContext(ContextLabel):
    """Carry the owning document into auxiliary editors, including nested blocks."""
    def __init__(self, dialog):
        super().__init__()
        self.owner = None
        candidate = dialog.parentWidget()
        fallback = None
        while candidate is not None:
            if hasattr(candidate, 'document_state'):
                self.owner = candidate; break
            if hasattr(candidate, 'document'):
                fallback = candidate
                if candidate.document.get('format') == 'nebula-montage':
                    self.owner = candidate; break
            candidate = candidate.parentWidget()
        self.owner = self.owner or fallback
        self.setAccessibleName('Editor document context')
        if self.owner is not None:
            self.owner.windowTitleChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        if self.owner is None:
            self.hide(); return
        if hasattr(self.owner, 'document_state'): context = studio_context(self.owner)
        elif self.owner.document.get('format') == 'nebula-montage': context = montage_context(self.owner)
        else:
            self.setText('Composition · ' + self.owner.document.get('name', 'Untitled')); return
        self.setText(context.location)
        self.setToolTip(context.location + '\n' + context.save_hint)
