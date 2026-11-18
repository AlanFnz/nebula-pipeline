"""Project filenames and desktop opening; document payloads stay unchanged."""
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QFileDialog

PROJECT_SUFFIXES = ('.nebula', '.json')
OPEN_FILTER = 'Nebula projects (*.nebula *.json)'
SAVE_FILTER = 'Nebula project (*.nebula);;Legacy JSON (*.json)'


def is_project_path(path):
    return Path(path).suffix.lower() in PROJECT_SUFFIXES


def choose_save_path(parent, title, suggestion):
    path, selected = QFileDialog.getSaveFileName(parent, title, str(suggestion), SAVE_FILTER)
    # Never redirect an existing destination after the dialog's overwrite check.
    # In particular, let the caller's source-media protections reject it intact.
    if path and not is_project_path(path) and not Path(path).expanduser().exists():
        path += '.json' if selected == 'Legacy JSON (*.json)' else '.nebula'
    return path


class ProjectFileOpener(QObject):
    """Queue Finder open events until the workspace and any modal dialog are ready.

    Installed before constructing the window, so cold launches and running-app
    opens take the same guarded document path. Never discard an unsaved session.
    """
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.window = None
        self.pending = []
        self.opening = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.deliver)
        app.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.app and event.type() == QEvent.Type.FileOpen:
            url = event.url()
            path = event.file() or (url.toLocalFile() if url.isLocalFile() else '')
            if path and is_project_path(path):
                self.request(path)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def request(self, path):
        path = Path(path).expanduser().resolve()
        if path not in self.pending and path != self.opening:
            self.pending.append(path)
        if self.window and not self.opening: self.timer.start(0)

    def bind(self, window, paths=()):
        self.window = window
        for path in paths: self.request(path)
        if self.pending: self.timer.start(0)

    def deliver(self):
        if not self.window or not self.pending or self.opening: return
        if self.window.closing: return
        if self.app.activeModalWidget() is not None:
            self.timer.start(100)
            return
        path = self.pending.pop(0)
        window = self.window
        if window.isMinimized(): window.showNormal()
        window.raise_(); window.activateWindow()
        navigation = window.workspace_navigation
        current = navigation.montage.path if navigation and navigation.montage else window.document_path
        # Finder can deliver the startup request again. Keep edits to an already
        # open document rather than reloading its last saved state.
        if current is None or Path(current).resolve() != path:
            self.opening = path
            try:
                if not window.open_document_path(path): self.pending.clear()
            finally:
                self.opening = None
        if self.pending: self.timer.start(0)
