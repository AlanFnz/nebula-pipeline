"""Presentation-only sound draft, audition and file state. No render settings."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtWidgets import QLabel, QHBoxLayout, QPushButton, QMessageBox


class SoundSession:
    def init_session_header(self, layout):
        self.applied_available = True
        self.applied_values = None
        row = QHBoxLayout()
        self.context_title = QLabel('Generate sound')
        self.context_title.setTextFormat(Qt.TextFormat.PlainText)
        self.context_title.setObjectName('effectTitle')
        self.context_title.setWordWrap(True)
        row.addWidget(self.context_title, 1)
        self.file_state = QLabel('File: Not saved')
        row.addWidget(self.file_state)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.workspace_hint = QLabel('Sound · All clips')
        self.workspace_hint.setToolTip('Sound controls are auditioned first. Apply sound updates the project; Save project writes the file.')
        row.addWidget(self.workspace_hint, 1)
        self.sound_state = QLabel('Sound: Applied')
        row.addWidget(self.sound_state)
        layout.addLayout(row)

    def init_session_actions(self, row):
        self.save_project_button = QPushButton('Save project')
        self.save_project_button.setToolTip('Save the project file, including applied sound and visual edits.')
        self.save_project_button.clicked.connect(self.save_project)
        self.save_project_button.setVisible(hasattr(self.parent(), 'save_sequence_dialog'))
        row.addWidget(self.save_project_button)
        self.save_project_action = QAction('Save project', self)
        self.save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_project_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.save_project_action.triggered.connect(self.save_project)
        self.addAction(self.save_project_action)

    def has_sound_draft(self):
        if not self.loaded: return False
        # Compare displayed precision against the displayed baseline. Opening a
        # historic document must not turn numeric rounding into a pending edit.
        return not self.applied_available or self.history_value != self.applied_values

    def refresh_session(self, *_):
        if not self.loaded or self.loading: return
        draft = self.has_sound_draft()
        self.sound_state.setText('Sound: Not applied' if draft else 'Sound: Applied')
        self.sound_state.setToolTip('Changes are only in the sound editor.' if draft else 'These sound settings are in the project. File status shows whether they are saved to disk.')
        self.apply_button.setText('Apply sound')
        self.apply_button.setEnabled(draft)
        self.apply_button.setToolTip('Use these settings in the project and in exports. This does not save the file.')
        visual = getattr(self, 'visuals_active', lambda: False)()
        self.workspace_hint.setText('Visuals · All clips · Edits apply immediately' if visual else 'Sound · All clips')
        self.refresh_history_actions()
        owner = self.parent()
        config = self.history_value or {}
        live = self.live.isChecked() and config.get('version') in (3, 4) and config.get('output') == 'generated'
        if live:
            source = 'Draft sound' if draft else 'Applied sound'
            if not config.get('enabled', True): source += ' · Disabled'
        else:
            applied = self.current if self.applied_available else None
            output = (applied or {}).get('output', 'existing')
            source = {'generated': 'Applied sound', 'existing': 'Existing soundtrack / footage', 'silent': 'Silent'}[output]
            if output == 'generated' and not applied.get('enabled', True): source = 'Silent · Sound disabled'
        generated = live or (self.applied_available and (self.current or {}).get('output') == 'generated')
        self.volume.setEnabled(generated); self.mute.setEnabled(generated)
        muted = self.mute.isChecked() if generated else getattr(owner, 'soundtrack_monitor_muted', False)
        if muted and 'Silent' not in source: source += ' · Monitor muted'
        prefix = 'Listening: ' if self.listen.isChecked() else 'Preview: '
        self.preview_source.setText(prefix + source)
        self.preview_source.setToolTip('Live audition plays draft synth settings. With live audition off, or another output selected, playback uses the applied project audio until you apply the changes.')

    def choose_pending_sound(self, purpose, leaving=False):
        box = QMessageBox(self)
        box.setWindowTitle('Unapplied sound')
        box.setText(f'Use your sound changes before {purpose}?')
        box.setInformativeText('Apply sound updates the project. Saving the project writes it to disk. Visual edits are kept separately.')
        apply = box.addButton('Apply sound', QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton('Discard sound changes' if leaving else 'Use applied sound', QMessageBox.ButtonRole.DestructiveRole if leaving else QMessageBox.ButtonRole.ActionRole)
        cancel = box.addButton('Keep editing' if leaving else 'Cancel', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel); box.setEscapeButton(cancel); box.exec()
        return 'apply' if box.clickedButton() is apply else 'discard' if box.clickedButton() is discard else 'cancel'

    def save_project(self):
        owner = self.parent()
        if hasattr(owner, 'save_sequence_dialog'): owner.save_sequence_dialog()

    def reject(self):
        owner = self.parent()
        if (hasattr(owner, 'resolve_sound_draft') and not owner.closing
                and not owner.resolve_sound_draft('closing the sound editor', leaving=True)):
            return
        super().reject()
