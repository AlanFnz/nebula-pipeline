"""Compact effect audition controls; rendering stays in the Studio scheduler."""
import time
import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget, QVBoxLayout
from synth_effect_browser import EffectBrowserDialog
from synth_effect_preview import EffectPreviewSession
from synth_effects import EFFECT_BY_ID


class EffectAuditionDialog(EffectBrowserDialog):
    def __init__(self, studio, effect_id=None, preset=0, operation='add'):
        panel = studio.composer.effects_panel
        section_id = studio.composer.target()['id'] if studio.composer.scope else None
        self.session = EffectPreviewSession(studio, section_id, operation)
        self.studio = studio; self.operation = operation; self.locked_effect = effect_id
        allowed = (effect_id,) if effect_id else panel.allowed_effects
        super().__init__(allowed, () if effect_id else panel.browser_applied_ids(), studio, compact=True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.ApplicationModal if sys.platform == 'darwin' else Qt.WindowModality.WindowModal)
        self.setWindowTitle('Compare contribution' if operation == 'without' else 'Preview effect preset')
        self.resize(430, 620); self.setMinimumWidth(380)
        self.browser_hint.setText('Choose a preset to audition on your piece, then Apply effect.' if operation == 'add' else 'Preview fixed preset values in this scope before replacing.' if operation == 'replace' else 'Compare the piece with this treatment temporarily bypassed.')
        self.action.setAccessibleName('Replace with preset' if operation == 'replace' else 'Apply selected effect')
        self.action.setText('Replace with preset' if operation == 'replace' else 'Apply effect')
        self.action.clicked.disconnect()
        self.action.clicked.connect(self.apply_candidate)
        self.table.setMaximumHeight(180); self.results.setMaximumHeight(180)
        self.body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.target_label = QLabel('Whole clip' if section_id is None else panel.context_scope_label.removeprefix('Editing: '))
        self.target_label.setWordWrap(True)
        self.body_layout.insertWidget(1, self.target_label)
        self.diagnostic_note = QLabel(); self.diagnostic_note.setWordWrap(True)
        self.diagnostic_note.setObjectName('muted'); self.body_layout.insertWidget(self.body_layout.count()-1, self.diagnostic_note)
        self.transport_host = QWidget(); transport_layout = QVBoxLayout(self.transport_host)
        transport_layout.setContentsMargins(0, 0, 0, 0)
        self.layout().insertWidget(self.layout().count()-1, self.transport_host)
        self.preview_note = QLabel('Select a treatment to preview.'); self.preview_note.setWordWrap(True)
        self.preview_note.setAccessibleName('Effect preview status')
        transport_layout.addWidget(self.preview_note)
        row = QHBoxLayout()
        self.before = QPushButton('Before'); self.after = QPushButton('Preview')
        self.before.setCheckable(True); self.after.setCheckable(True)
        self.preview_play = QPushButton('Play preview'); self.preview_play.setCheckable(True)
        for button in (self.before, self.after, self.preview_play):
            button.setAutoDefault(False); row.addWidget(button)
        transport_layout.addLayout(row)
        self.before.clicked.connect(lambda: self.switch_side('a'))
        self.after.clicked.connect(lambda: self.switch_side('b'))
        self.preview_play.toggled.connect(self.play_sample)
        self.scrubber = QSlider(Qt.Orientation.Horizontal); self.scrubber.setAccessibleName('Sampled effect preview position')
        self.scrubber.valueChanged.connect(self.scrub_sample)
        transport_layout.addWidget(self.scrubber)
        row = QHBoxLayout()
        self.selected_section = QPushButton('Preview selected section'); self.selected_section.clicked.connect(self.seek_section)
        self.retry = QPushButton('Retry'); self.retry.clicked.connect(self.render_selection)
        self.prepare = QPushButton('Prepare preview'); self.prepare.clicked.connect(lambda: self.render_selection(explicit=True))
        for button in (self.selected_section, self.retry, self.prepare): button.setAutoDefault(False); row.addWidget(button)
        transport_layout.addLayout(row)
        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(300)
        self.debounce.timeout.connect(self.render_selection)
        self.transport = QTimer(self); self.transport.setInterval(83); self.transport.timeout.connect(self.advance_sample)
        self.poll = QTimer(self); self.poll.setInterval(100); self.poll.timeout.connect(self.refresh_preview); self.poll.start()
        self.preset.currentIndexChanged.connect(self.selection_changed)
        self.finished.connect(self.cleanup)
        self.effectInspected.connect(panel.inspect_effect)
        self.instanceRequested.connect(self.add_instance)
        self.objectRequested.connect(panel.object_requested.emit)
        if effect_id:
            self.search.hide(); self.category.hide(); self.results.hide(); self.status.hide()
            self.object_button.hide(); self.object_note.hide(); self.object_heading.hide()
            self.preset.setCurrentIndex(preset)
            self.preset_row.setVisible(operation != 'without')
            self.selection_note.setText('Fixed preset values replace this effect in the displayed scope.' if operation == 'replace' else 'Temporary bypass only. Close restores your piece.')
        if operation == 'without': self.action.hide(); self.cancel_button.setText('Close')
        screen = studio.screen().availableGeometry()
        self.resize(430, min(620, screen.height()-60))
        self.selection_changed()

    def update_selection(self):
        super().update_selection()
        if hasattr(self, 'debounce'):
            self.action.setAccessibleName('Inspect selected effect' if self.selected_effect_id() in self.applied_ids else 'Replace with preset' if self.operation == 'replace' else 'Apply selected effect')
            self.selection_changed()

    def add_instance(self, identifier):
        # Release any temporary audition before committing the new pass.
        self.cleanup()
        self.studio.composer.add_effect_instance(identifier)

    def selection_changed(self, *_):
        if not hasattr(self, 'debounce'): return
        self.transport.stop(); self.preview_play.setChecked(False)
        self.session.ready = False
        self.session.candidate = None; self.session.owner = None
        self.session.effect_id = None
        self.studio.cancel_preparation()
        if self.studio.comparison: self.studio.end_comparison()
        self.action.setEnabled(False)
        self.studio.viewer.set_packet(None)
        self.preview_note.setText('Loading selected preset…')
        self.diagnostic_note.clear(); self.diagnostic_key = None
        self.debounce.start()

    def render_selection(self, explicit=False):
        identifier = self.selected_effect_id()
        if identifier in self.applied_ids:
            self.preview_note.setText('Already applied. Inspect keeps its current settings.')
            self.action.setText('Inspect effect'); self.action.setEnabled(True)
            return
        self.action.setText('Replace with preset' if self.operation == 'replace' else 'Apply effect')
        if identifier == 'subject_cutout' and not explicit:
            self.preview_note.setText('Subject cutout needs local masks. Choose Prepare preview to prepare them explicitly.')
            self.prepare.show(); return
        try:
            self.session.select(identifier, self.preset.currentIndex())
            label = EFFECT_BY_ID[identifier].label
            preset = self.preset.currentText()
            self.studio.comparison['label_b'] = ('Without ' + label) if self.operation == 'without' else 'Preset preview · ' + label + ' / ' + preset
            self.studio.refresh_comparison_controls()
            self.scrubber.setRange(0, max(0, len(self.session.samples)-1))
        except (ValueError, KeyError) as exc: self.session.fail(exc)
        self.refresh_preview()

    def refresh_preview(self):
        session = self.session
        if session.closed:
            self.reject(); return
        if not session.valid():
            session.fail('The piece or media changed. Close and open a fresh preview.')
            self.transport.stop()
            self.studio.viewer.set_packet(None)
        applied = self.selected_effect_id() in self.applied_ids
        matching = session.effect_id == self.selected_effect_id() and session.preset == self.preset.currentIndex()
        self.action.setEnabled(applied or (matching and session.ready and not session.error and not self.debounce.isActive()))
        self.selected_section.setVisible(session.section_id is not None and not session.target_scope.contains(self.studio.timeline.value()))
        self.prepare.setVisible(self.selected_effect_id() == 'subject_cutout')
        self.retry.setVisible(bool(session.error))
        side = self.studio.comparison['side'] if self.studio.comparison else None
        self.before.setChecked(side == 'a'); self.after.setChecked(side == 'b')
        self.before.setEnabled(session.candidate is not None); self.after.setEnabled(session.candidate is not None)
        self.preview_play.setEnabled(session.ready and bool(session.samples))
        self.scrubber.setEnabled(bool(session.samples))
        if session.error:
            self.transport.stop(); self.preview_play.setChecked(False)
            self.preview_note.setText('Preview unavailable: ' + session.error)
        elif session.candidate is not None:
            seconds = self.studio.timeline.value()/self.studio.preview_fps()
            size = self.studio.preview_size()
            note = f'{"Ready" if session.ready else "Loading"} · {seconds:.2f}s · {size[0]}×{size[1]} · sampled up to 12 fps'
            if session.section_id and not session.target_scope.contains(self.studio.timeline.value()): note += '\nCurrent frame is outside the selected section.'
            if session.section_id and session.target_scope.contains(self.studio.timeline.value()):
                occurrence = next(i+1 for i, (start,end) in enumerate(session.target_scope.intervals) if start<=self.studio.timeline.value()<end)
                note += f'\nSection occurrence {occurrence} of {len(session.target_scope.intervals)} · original absolute clock'
            if self.operation == 'without' and session.section_id is None:
                note += '\nExplicit section Resume overrides Whole clip bypass.'
            if session.operation == 'replace' and self.studio.composer.effects_panel.is_bypassed(session.effect_id): note += '\nBypassed settings stay bypassed. Resume separately in the inspector.'
            if self.preview_play.isChecked() and getattr(self, 'waiting', False):
                note = 'Preparing sampled loop… ' + str(sum(frame in self.studio.preview_frames.items for frame in session.samples)) + '/' + str(len(session.samples)) + ' frames\n' + note
            self.preview_note.setText(note)
            key = (session.owner, self.studio.timeline.value(), session.ready)
            if self.diagnostic_key != key:
                self.diagnostic_key = key
                from synth_effect_diagnostics import explain_effect
                facts = explain_effect(session.candidate, self.studio.comparison['b_sequence'], session.effect_id,
                                       seconds, session.section_id)
                text = '\n'.join(f.scope + ': ' + f.message for f in facts)
                matching = session.matching_samples()
                if matching: text += '\nNo visible difference in these matching preview frames. Try relevant strength or threshold controls after Apply.'
                self.diagnostic_note.setText(text + '\nIntermittent treatments may not fire in this short window.')

    def switch_side(self, side):
        self.studio.set_comparison_side(side)
        if self.transport.isActive(): self.waiting = True; self.session.prepare_samples()

    def seek_section(self):
        self.session.seek_selected()
        self.scrubber.setRange(0, max(0, len(self.session.samples)-1))

    def play_sample(self, checked):
        if checked:
            self.session.prepare_samples(); self.waiting = True; self.started = time.monotonic(); self.transport.start()
        else: self.transport.stop()

    def advance_sample(self):
        if getattr(self, 'waiting', False):
            if not all(frame in self.studio.preview_frames.items for frame in self.session.samples): return
            self.waiting = False; self.started = time.monotonic()
        if self.session.samples:
            index = int((time.monotonic()-self.started)*min(12,self.studio.preview_fps())) % len(self.session.samples)
            self.scrubber.setValue(index)

    def scrub_sample(self, index):
        if self.session.samples: self.studio.timeline.setValue(self.session.samples[index])

    def apply_candidate(self):
        identifier = self.selected_effect_id()
        if identifier in self.applied_ids:
            self.effectInspected.emit(identifier); self.accept(); return
        if self.session.effect_id != identifier or self.session.preset != self.preset.currentIndex(): return
        try: self.session.apply()
        except ValueError as exc: self.session.fail(exc); self.refresh_preview(); return
        self.accept()

    def cleanup(self, *_):
        self.debounce.stop(); self.transport.stop(); self.poll.stop(); self.session.close()
