"""Preview-only A/B routing; the working document remains the export source."""
import copy

from PySide6.QtCore import QPoint, QSignalBlocker, Qt
from PySide6.QtWidgets import QLabel, QPushButton
from synth_composition import compile_composition
from synth_exploration import comparison_problem, content, restore_snapshot, snapshot_by_id


class ExplorationStudio:
    def build_exploration_controls(self, view_row, monitor_row):
        self.snapshots_button = QPushButton('Snapshots…'); self.snapshots_button.clicked.connect(self.open_snapshots)
        self.snapshots_button.setToolTip('Capture complete named variations, compare A/B and restore them. Saved in this composition.')
        view_row.addWidget(self.snapshots_button); self.composition_widgets.append(self.snapshots_button)
        self.compare_a = QPushButton('A'); self.compare_b = QPushButton('B'); self.compare_exit = QPushButton('×')
        for button, side in ((self.compare_a, 'a'), (self.compare_b, 'b')):
            button.setAccessibleName('Preview ' + side.upper())
            button.setCheckable(True); button.setFixedWidth(30); button.hide()
            button.clicked.connect(lambda _checked=False, side=side: self.set_comparison_side(side))
            view_row.addWidget(button)
        self.compare_exit.setFixedWidth(28); self.compare_exit.hide(); self.compare_exit.clicked.connect(self.end_comparison)
        self.compare_exit.setAccessibleName('End A/B comparison'); view_row.addWidget(self.compare_exit)
        self.compare_label = QLabel(); self.compare_label.setObjectName('monitorMeta'); self.compare_label.hide()
        self.compare_label.setTextFormat(Qt.TextFormat.PlainText)
        monitor_row.insertWidget(1, self.compare_label)

    def preview_sequence(self):
        if self.comparison:
            if self.comparison['side'] == 'a': return self.comparison['a_sequence']
            if self.comparison.get('candidate') is not None: return self.comparison['b_sequence']
        return self.sequence

    def preview_document(self):
        if self.comparison:
            if self.comparison['side'] == 'a': return self.comparison['a_document']
            if self.comparison.get('candidate') is not None: return self.comparison['candidate']
        return self.composition

    def preview_bypass(self):
        return False if self.comparison else self.source_preview.isChecked()

    def comparison_context(self):
        return (self.comparison['token'], self.comparison['side']) if self.comparison else None

    def refresh_comparison_controls(self):
        active = self.comparison is not None
        for button in (self.compare_a, self.compare_b, self.compare_exit): button.setVisible(active)
        self.compare_label.setVisible(active); self.source_preview.setEnabled(not active)
        if active:
            side = self.comparison['side']; label = self.comparison['label_a'] if side == 'a' else self.comparison['label_b']
            discovery = self.comparison.get('purpose') in ('effect', 'contribution')
            text = (('Before' if side == 'a' else 'Preview') if discovery else side.upper()) + ' · ' + label + (' · updating' if self.comparison.get('pending') else '')
            self.compare_label.setText(self.compare_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, 240))
            self.compare_label.setToolTip(text + ' · same absolute playhead and preview quality. Export uses the working piece.')
            for button, key in ((self.compare_a, 'a'), (self.compare_b, 'b')):
                with QSignalBlocker(button): button.setChecked(side == key)
            self.compare_a.setToolTip('Preview saved A. Editing still targets working B.'); self.compare_b.setToolTip('Preview working B or the temporary audition.')
        if hasattr(self, 'export_button'):
            self.export_button.setText('Export B MP4' if active else 'Export MP4')
            self.export_button.setToolTip('Export working B. A/B comparison only changes the viewer.' if active else '')

    def begin_comparison(self, first, label, candidate=None, snapshot_id=None, purpose=None):
        if self.discovery_session and purpose not in ('effect', 'contribution'): self.dismiss_effect_discovery()
        first = content(first); a = compile_composition(first)
        b = compile_composition(candidate) if candidate is not None else self.sequence
        problem = comparison_problem(a, b)
        if problem: raise ValueError(problem)
        before_source = self.comparison['before_source'] if self.comparison else self.source_preview.isChecked()
        with QSignalBlocker(self.source_preview): self.source_preview.setChecked(False)
        self.comparison = dict(a_document=first, a_sequence=a, b_sequence=b, b_reference=copy.deepcopy(self.sequence),
                               candidate=copy.deepcopy(candidate), snapshot_id=snapshot_id, token=object(), side='b', pending=True,
                               purpose=purpose or ('variation' if candidate is not None else 'snapshot'), label_a=label, label_b='audition' if candidate else 'working', before_source=before_source)
        self.viewer.set_packet(None); self.refresh_comparison_controls(); self.invalidate(force_clear=True)

    def set_comparison_side(self, side):
        if self.comparison is None or side not in ('a', 'b') or side == self.comparison['side']: return
        self.comparison['side'] = side; self.comparison['pending'] = True
        self.viewer.set_packet(None); self.refresh_comparison_controls(); self.invalidate(comparison_switch=True)

    def end_comparison(self, *_):
        if self.comparison is None: return
        before_source = self.comparison['before_source']; self.comparison = None
        with QSignalBlocker(self.source_preview): self.source_preview.setChecked(before_source and bool(self.composition and 'footage' in self.composition))
        self.viewer.set_packet(None); self.refresh_comparison_controls(); self.invalidate(force_clear=True)

    def snapshot_comparison_problem(self, identifier):
        return comparison_problem(compile_composition(snapshot_by_id(self.composition, identifier)['document']), self.sequence)

    def compare_snapshot(self, identifier):
        snapshot = snapshot_by_id(self.composition, identifier)
        self.begin_comparison(snapshot['document'], snapshot['name'], snapshot_id=identifier)
        self.set_comparison_side('a')

    def restore_saved_snapshot(self, identifier):
        restored = restore_snapshot(self.composition, identifier)
        self.end_comparison(); self.composer.commit(restored, 'snapshot-restore')

    def preview_audition(self, base, candidate):
        self.begin_comparison(base, 'before variation', candidate)
        self.update_document_title()

    def keep_audition(self):
        if not self.comparison or self.comparison.get('candidate') is None: return
        candidate = self.comparison['candidate']; self.end_comparison()
        self.composer.commit(candidate, 'effect-variation')

    def audition_pending(self):
        return bool(self.comparison and self.comparison.get('candidate') is not None and self.comparison.get('purpose', 'variation') == 'variation')

    def preparation_budget(self):
        return self.preview_frames.budget // 2 if self.comparison else self.preview_frames.budget

    def reconcile_comparison(self):
        if not self.comparison: return
        identifier = self.comparison.get('snapshot_id')
        if (identifier and not any(s['id'] == identifier for s in self.composition.get('snapshots', []))) or comparison_problem(self.comparison['a_sequence'], self.sequence):
            self.end_comparison(); return
        if self.sequence != self.comparison['b_reference']:
            # A is preview-only. A real edit returns to B so its result is visible.
            if getattr(self, 'discovery_session', None):
                self.discovery_session.fail('The piece changed. Close this audition and open a fresh preview.')
                self.discovery_session.close(restore=False)
                return
            if self.comparison['side'] == 'a': self.viewer.set_packet(None)
            self.comparison['side'] = 'b'; self.comparison['pending'] = True
            self.comparison['b_reference'] = copy.deepcopy(self.sequence)
            self.comparison['candidate'] = None
        self.refresh_comparison_controls()

    def open_snapshots(self):
        if self.composition is None or not self.prepare_document_save(): return
        from synth_exploration_ui import SnapshotsDialog
        dialog = SnapshotsDialog(self); self.position_exploration_dialog(dialog); dialog.exec(); dialog.deleteLater()

    def open_effect_variation(self, effect_id):
        if self.composition is None or not self.prepare_document_save(): return
        from synth_exploration_ui import VaryEffectDialog
        dialog = VaryEffectDialog(self, effect_id); self.position_exploration_dialog(dialog); dialog.exec(); dialog.deleteLater()

    def position_exploration_dialog(self, dialog):
        # Leave the monitor visible while a modal audition owns the controls.
        host = self.inspector_host.mapToGlobal(QPoint())
        frame = self.frameGeometry()
        dialog.move(min(host.x(), frame.right() - dialog.width()),
                    min(host.y(), frame.bottom() - dialog.height()))

    def dismiss_effect_discovery(self):
        dialog = getattr(self, 'discovery_dialog', None)
        if dialog is not None: dialog.reject()
        elif self.discovery_session: self.discovery_session.close(restore=False)

    def open_effect_discovery(self, effect_id='', preset=0, operation='add'):
        from synth_effect_discovery_ui import EffectAuditionDialog
        from PySide6.QtWidgets import QMessageBox
        if self.discovery_session: self.dismiss_effect_discovery()
        if self.audition_pending():
            choice = QMessageBox.question(self, 'Temporary variation', 'Keep this variation before previewing an effect?',
                QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Cancel: return
            if choice == QMessageBox.StandardButton.Apply: self.keep_audition()
            else: self.end_comparison()
        try:
            dialog = EffectAuditionDialog(self, effect_id or None, preset, operation)
        except ValueError as exc:
            QMessageBox.information(self, 'Effect preview', str(exc)); return
        self.discovery_dialog = dialog
        dialog.finished.connect(lambda _result, d=dialog: setattr(self, 'discovery_dialog', None) if getattr(self, 'discovery_dialog', None) is d else None)
        self.position_exploration_dialog(dialog)
        dialog.show()
