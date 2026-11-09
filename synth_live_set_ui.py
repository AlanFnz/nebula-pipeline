"""Link a composition to an existing Live Set; open only on an explicit click."""
import copy
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl, QSignalBlocker
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QToolButton, QMenu, QFileDialog, QMessageBox

from synth_live_set import LIVE_SET, normalize_live_set
from synth_live_mode import LIVE_OUTPUT, is_live, supports_live


class LiveSetButton(QToolButton):
    openRequested = Signal()
    linkRequested = Signal()
    unlinkRequested = Signal()
    playbackRequested = Signal(bool)

    def __init__(self, *, compact=False):
        super().__init__()
        self.path = None
        self.compact = compact
        self.setFixedWidth(150 if compact else 270)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu = QMenu(self)
        self.playback_action = menu.addAction('Use Ableton Live for playback')
        self.playback_action.setCheckable(True)
        self.playback_action.triggered.connect(self.playbackRequested)
        menu.addSeparator()
        self.link_action = menu.addAction('Link Live Set…')
        self.unlink_action = menu.addAction('Unlink Live Set')
        self.link_action.triggered.connect(self.linkRequested)
        self.unlink_action.triggered.connect(self.unlinkRequested)
        self.setMenu(menu)
        self.clicked.connect(self.activate)
        self.set_link(None)

    def set_playback(self, config):
        with QSignalBlocker(self.playback_action):
            self.playback_action.setChecked(is_live(config))
        self.playback_action.setEnabled(supports_live(config))
        self.playback_action.setToolTip('Save Live as the playback destination. Notes and motion leave through Nebula Visuals; instruments and audio stay in Live.')

    def activate(self):
        (self.openRequested if self.path else self.linkRequested).emit()

    def set_link(self, path):
        self.path = path
        title = f'Open in Live · {Path(path).name}' if path else 'Link Live Set'
        visible = 'Open in Live' if path and self.compact else title
        label = self.fontMetrics().elidedText(visible, Qt.TextElideMode.ElideMiddle, self.width()-36)
        self.setText(label.replace('&', '&&'))
        self.setAccessibleName(title)
        self.setToolTip(f'Open this Set in Ableton Live:\n{path}' if path else
                        'Choose the Live Set for this composition. Save the project to keep the link.')
        self.link_action.setText('Change Live Set…' if path else 'Link Live Set…')
        self.unlink_action.setEnabled(bool(path))


class LiveSetActions:
    def live_playback_config(self):
        config = (self.composition or {}).get('generated_sound')
        if config: return config
        sequence = self.preview_sequence() or {}
        supported = any(set(state.get('enabled', ())) & {'pleated_field', 'chromatic_lattice'}
                        for state in sequence.get('states', {}).values())
        return self.sound_dialog_config() if supported else None

    def connect_live_set_button(self, button):
        button.linkRequested.connect(self.link_live_set)
        button.openRequested.connect(self.open_linked_live_set)
        button.unlinkRequested.connect(self.unlink_live_set)
        button.playbackRequested.connect(self.set_live_playback)

    def refresh_live_set_actions(self):
        path = (self.composition or {}).get(LIVE_SET)
        config = self.live_playback_config() if self.composition else None
        button = getattr(self, 'workspace_live_set_button', None)
        if button is not None:
            button.set_link(path)
            button.set_playback(config)
            button.setEnabled(self.composition is not None and not self.audition_pending())
        if self.visual_sound_dialog is not None:
            self.visual_sound_dialog.live_set_button.set_link(path)
            self.visual_sound_dialog.live_set_button.set_playback(config)

    def set_live_playback(self, enabled, *, resolved=False):
        if not self.composition or self.audition_pending(): return False
        config = copy.deepcopy(self.live_playback_config())
        if not supports_live(config): return False
        if not resolved and not self.resolve_sound_draft('changing playback destination', leaving=True):
            self.refresh_live_set_actions();return False
        config = copy.deepcopy(self.live_playback_config())
        if not supports_live(config):
            self.refresh_live_set_actions();return False
        config['output'] = LIVE_OUTPUT if enabled else 'generated'
        self.apply_visual_sound(config)
        self.refresh_live_set_actions()
        return True

    def live_set_dialog_parent(self):
        dialog = self.visual_sound_dialog
        return dialog if dialog is not None and dialog.isVisible() else self

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
        path, _ = QFileDialog.getOpenFileName(self.live_set_dialog_parent(), 'Locate Live Set' if missing else 'Link Live Set',
                                             current, 'Ableton Live Set (*.als *.ALS)')
        if not path or identity is not self.document_identity: return None
        try:
            selected = Path(normalize_live_set(path)).expanduser().absolute()
            if not selected.is_file(): raise ValueError('The Live Set could not be found. Choose its current location.')
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self.live_set_dialog_parent(), 'Could not link Live Set', str(exc))
            return None
        return selected if self.set_linked_live_set(str(selected)) else None

    def link_live_set(self):
        self.choose_live_set()

    def unlink_live_set(self):
        self.set_linked_live_set(None)

    def open_linked_live_set(self):
        if self.audition_pending(): return
        path = (self.composition or {}).get(LIVE_SET)
        if not path: return
        if not self.resolve_sound_draft('opening in Live', leaving=True): return
        selected = Path(path).expanduser()
        if not selected.is_file():
            selected = self.choose_live_set(missing=True)
            if selected is None: return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(selected))):
            QMessageBox.critical(self.live_set_dialog_parent(), 'Could not open Live Set',
                                 'Check that Ableton Live is installed and opens .als files, then try again.')
            return
        self.set_live_playback(True, resolved=True)
