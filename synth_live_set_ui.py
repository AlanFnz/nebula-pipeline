"""Link a composition to an existing Live Set; open only on an explicit click."""
import copy
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QToolButton, QMenu, QFileDialog, QMessageBox

from synth_live_set import LIVE_SET, normalize_live_set


class LiveSetButton(QToolButton):
    openRequested = Signal()
    linkRequested = Signal()
    unlinkRequested = Signal()

    def __init__(self):
        super().__init__()
        self.path = None
        self.setFixedWidth(270)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu = QMenu(self)
        self.link_action = menu.addAction('Link Live Set…')
        self.unlink_action = menu.addAction('Unlink Live Set')
        self.link_action.triggered.connect(self.linkRequested)
        self.unlink_action.triggered.connect(self.unlinkRequested)
        self.setMenu(menu)
        self.clicked.connect(self.activate)
        self.set_link(None)

    def activate(self):
        (self.openRequested if self.path else self.linkRequested).emit()

    def set_link(self, path):
        self.path = path
        title = f'Open in Live · {Path(path).name}' if path else 'Link Live Set…'
        label = self.fontMetrics().elidedText(title, Qt.TextElideMode.ElideMiddle, self.width()-36)
        self.setText(label.replace('&', '&&'))
        self.setAccessibleName(title)
        self.setToolTip(f'Open this Set in Ableton Live:\n{path}' if path else
                        'Choose the Live Set for this composition. Save the project to keep the link.')
        self.link_action.setText('Change Live Set…' if path else 'Link Live Set…')
        self.unlink_action.setEnabled(bool(path))


class LiveSetActions:
    def set_linked_live_set(self, path):
        if not self.composition or not self.composer or self.audition_pending(): return False
        if path is not None: path = normalize_live_set(path)
        project = copy.deepcopy(self.composition)
        if path is None: project.pop(LIVE_SET, None)
        else: project[LIVE_SET] = path
        if project != self.composition: self.composer.commit(project, 'live-set')
        return True

    def choose_live_set(self, *, missing=False):
        if not self.composition or self.audition_pending(): return None
        identity = self.document_identity
        current = self.composition.get(LIVE_SET, '')
        path, _ = QFileDialog.getOpenFileName(self.visual_sound_dialog, 'Locate Live Set' if missing else 'Link Live Set',
                                             current, 'Ableton Live Set (*.als *.ALS)')
        if not path or identity is not self.document_identity: return None
        try:
            selected = Path(normalize_live_set(path)).expanduser().absolute()
            if not selected.is_file(): raise ValueError('The Live Set could not be found. Choose its current location.')
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self.visual_sound_dialog, 'Could not link Live Set', str(exc))
            return None
        return selected if self.set_linked_live_set(str(selected)) else None

    def link_live_set(self):
        self.choose_live_set()

    def unlink_live_set(self):
        self.set_linked_live_set(None)

    def open_linked_live_set(self):
        path = (self.composition or {}).get(LIVE_SET)
        if not path: return
        selected = Path(path).expanduser()
        if not selected.is_file():
            selected = self.choose_live_set(missing=True)
            if selected is None: return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(selected))):
            QMessageBox.critical(self.visual_sound_dialog, 'Could not open Live Set',
                                 'Check that Ableton Live is installed and opens .als files, then try again.')
