"""Native snapshot management and temporary effect auditions."""
import copy
import secrets
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QCheckBox, QDialogButtonBox
from studio_widgets import ComboBox, PlaybackButton
from synth_creative import CREATIVE_CONTROLS
from synth_effects import EFFECT_BY_ID
from synth_exploration import TIMING_CONTROLS, capture_snapshot, remove_snapshot, vary_effect


def comparison_transport(dialog, studio, layout):
    row = QHBoxLayout()
    dialog.a = QPushButton('A · original'); dialog.b = QPushButton('B · working')
    dialog.a.clicked.connect(lambda: studio.set_comparison_side('a'))
    dialog.b.clicked.connect(lambda: studio.set_comparison_side('b'))
    dialog.play = PlaybackButton(); dialog.play.setChecked(studio.play.isChecked())
    dialog.play.toggled.connect(studio.play.setChecked); studio.play.toggled.connect(dialog.play.setChecked)
    row.addWidget(dialog.a); row.addWidget(dialog.b); row.addWidget(dialog.play); layout.addLayout(row)


class SnapshotsDialog(QDialog):
    def __init__(self, studio):
        super().__init__(studio); self.studio = studio
        self.setWindowTitle('Snapshots & comparison'); self.resize(460, 450)
        layout = QVBoxLayout(self)
        note = QLabel('Capture a complete composition, including sources, effects, canvas and timing. A previews a saved snapshot; B is your working piece. Export uses B.'); note.setWordWrap(True); layout.addWidget(note)
        row = QHBoxLayout(); self.name = QLineEdit('Snapshot ' + str(len(studio.composition.get('snapshots', [])) + 1)); self.name.setMaxLength(80)
        self.name.setAccessibleName('Snapshot name'); row.addWidget(self.name)
        self.capture = QPushButton('Capture current B'); self.capture.clicked.connect(self.capture_current); row.addWidget(self.capture); layout.addLayout(row)
        self.list = QListWidget(); self.list.setAccessibleName('Saved composition snapshots'); self.list.currentItemChanged.connect(self.selection_changed); layout.addWidget(self.list)
        row = QHBoxLayout()
        self.compare = QPushButton('Compare with B'); self.compare.clicked.connect(self.compare_selected)
        self.restore = QPushButton('Restore as working B'); self.restore.clicked.connect(self.restore_selected)
        self.remove = QPushButton('Remove'); self.remove.clicked.connect(self.remove_selected)
        for button in (self.compare, self.restore, self.remove): row.addWidget(button)
        layout.addLayout(row); comparison_transport(self, studio, layout)
        self.a.setText('A · snapshot')
        self.notice = QLabel(); self.notice.setWordWrap(True); self.notice.setObjectName('muted'); layout.addWidget(self.notice)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(self.reject); layout.addWidget(close)
        self.refresh()

    def selected_id(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def refresh(self, selected=None):
        selected = selected or self.selected_id(); self.list.clear()
        for snapshot in self.studio.composition.get('snapshots', []):
            stamp = datetime.fromisoformat(snapshot['created_at']).astimezone().strftime('%Y-%m-%d %H:%M')
            item = QListWidgetItem(snapshot['name'] + ' · ' + stamp)
            item.setData(Qt.ItemDataRole.UserRole, snapshot['id']); self.list.addItem(item)
            if snapshot['id'] == selected: self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count(): self.list.setCurrentRow(0)
        self.selection_changed()

    def selection_changed(self, *_):
        identifier = self.selected_id(); problem = self.studio.snapshot_comparison_problem(identifier) if identifier else ''
        self.compare.setEnabled(bool(identifier) and not problem)
        self.restore.setEnabled(bool(identifier)); self.remove.setEnabled(bool(identifier))
        self.notice.setText(problem or ('Compare at the current playhead; select a short preview loop before opening this window.' if identifier else 'Capture the first snapshot to begin. Snapshots are saved with this document.'))
        enabled = self.studio.comparison is not None
        self.a.setEnabled(enabled); self.b.setEnabled(enabled)

    def capture_current(self):
        if not self.studio.prepare_document_save(): return
        try:
            document, identifier = capture_snapshot(self.studio.composition, self.name.text())
            self.studio.composer.commit(document, 'snapshot-capture'); self.refresh(identifier)
        except ValueError as exc: self.notice.setText(str(exc))

    def compare_selected(self):
        try:
            self.studio.compare_snapshot(self.selected_id()); self.selection_changed()
            self.a.setText('A · snapshot'); self.b.setText('B · working')
        except ValueError as exc: self.notice.setText(str(exc))

    def restore_selected(self):
        self.studio.restore_saved_snapshot(self.selected_id()); self.refresh()

    def remove_selected(self):
        self.studio.composer.commit(remove_snapshot(self.studio.composition, self.selected_id()), 'snapshot-remove')
        self.refresh()


class VaryEffectDialog(QDialog):
    def __init__(self, studio, effect_id):
        super().__init__(studio); self.studio = studio; self.effect_id = effect_id
        self.base = copy.deepcopy(studio.composition); self.candidate = None
        self.section_id = studio.composer.document['sections'][studio.composer.index]['id'] if studio.composer.scope else None
        self.setWindowTitle('Vary ' + EFFECT_BY_ID[effect_id].label); self.resize(390, 450)
        layout = QVBoxLayout(self)
        scope = 'Selected clip' if self.section_id else 'Entire project'
        self.scope = QLabel(scope); self.scope.setObjectName('sectionTitle'); layout.addWidget(self.scope)
        note = QLabel('Only checked controls vary. Object, palette, source and noise seed stay fixed. Timing starts unchecked. Try previews a temporary B; Keep commits one undoable edit.'); note.setWordWrap(True); layout.addWidget(note)
        self.amount = ComboBox(); self.amount.setAccessibleName('Variation amount')
        for name in ('subtle', 'moderate', 'strong'): self.amount.addItem(name.title(), name)
        layout.addWidget(self.amount); self.controls = {}
        editor = studio.composer.effects_panel.creative_panel
        for spec in CREATIVE_CONTROLS[effect_id]:
            check = QCheckBox(spec.label + (' · timing' if spec.key in TIMING_CONTROLS else ''))
            available = editor.controls[spec.key].input.isEnabled()
            check.setEnabled(available); check.setChecked(available and spec.key not in TIMING_CONTROLS)
            check.setToolTip(spec.hint); self.controls[spec.key] = check; layout.addWidget(check)
        self.try_button = QPushButton('Try variation'); self.try_button.clicked.connect(self.try_variation); layout.addWidget(self.try_button)
        comparison_transport(self, studio, layout); self.a.setText('A · before'); self.b.setText('B · audition')
        self.a.setEnabled(False); self.b.setEnabled(False)
        self.result = QLabel('Nothing changes until you keep a variation.'); self.result.setWordWrap(True); self.result.setObjectName('muted'); layout.addWidget(self.result)
        row = QHBoxLayout(); self.keep = QPushButton('Keep variation'); self.keep.setObjectName('primary'); self.keep.setEnabled(False); self.keep.clicked.connect(self.keep_variation)
        self.discard = QPushButton('Discard / close'); self.discard.clicked.connect(self.reject)
        row.addWidget(self.keep); row.addWidget(self.discard); layout.addLayout(row)

    def try_variation(self):
        try:
            keys = [key for key, control in self.controls.items() if control.isChecked() and control.isEnabled()]
            seed = secrets.randbelow(2**31)
            candidate = vary_effect(self.base, self.effect_id, self.amount.currentData(), keys, seed, self.section_id)
            self.studio.preview_audition(self.base, candidate)
            self.candidate = candidate; self.keep.setEnabled(True); self.a.setEnabled(True); self.b.setEnabled(True)
            self.try_button.setText('Try another variation')
            target = candidate if self.section_id is None else next(s for s in candidate['sections'] if s['id'] == self.section_id)
            values = target['effects'][self.effect_id]['creative']['values']
            controls = {spec.key: spec for spec in CREATIVE_CONTROLS[self.effect_id]}
            labels = [controls[key].label + (' ' + f'{values[key]:+g} copies' if controls[key].operation == 'offset' else ' ' + f'{values[key]*100:.2f}%') for key in keys]
            self.result.setText('Audition · ' + '; '.join(labels) + f'. Variation seed {seed}.')
        except ValueError as exc: self.result.setText(str(exc))

    def keep_variation(self):
        if self.candidate is None: return
        self.studio.keep_audition(); self.candidate = None; self.accept()

    def reject(self):
        if self.candidate is not None: self.studio.end_comparison()
        self.candidate = None; super().reject()
