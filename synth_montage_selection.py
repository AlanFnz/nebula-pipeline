"""Montage selection and timing drafts; no changes to stored montage clocks."""
import copy

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QMessageBox


class MontageSelection:
    def block_label(self, key):
        for i, clip in enumerate(self.document['clips']):
            if clip['id'] == key: return f"Block {i+1:02d} · {clip['name']}"
        return 'No target selected'

    def active_clip(self):
        if len(self.selected) != 1: return None
        return next((c for c in self.document['clips'] if c['id'] in self.selected), None)

    def select_clip(self, key, additive=False):
        if key not in {c['id'] for c in self.document['clips']}: return False
        selected = self.selected ^ {key} if additive else {key}
        return self.select_blocks(selected)

    def select_blocks(self, selected):
        selected = set(selected) & {c['id'] for c in self.document['clips']}
        if selected != self.selected and not self.resolve_timing('changing the target block'): return False
        self.selected = selected
        self.timeline.selected = set(selected); self.timeline.update(); self.update_inspector()
        return True

    def select_all(self):
        selected = {c['id'] for c in self.document['clips']}
        if selected != self.selected and not self.resolve_timing('selecting all blocks'): return False
        self.selected = selected
        self.timeline.selected = set(selected); self.timeline.update(); self.update_inspector()
        return True

    def update_material_context(self, *_):
        key = self.library_key(); asset = self.document['assets'].get(key)
        if asset:
            uses = sum(c['asset'] == key for c in self.document['clips'])
            text = f"Material source: {asset['name']}\n{asset['kind'].title()} · {uses} use{'s' if uses != 1 else ''}"
        else: text = 'Material source: None'
        self.material_context.setText(text); self.material_context.setToolTip(text)
        clip = self.active_clip()
        self.insert_button.setEnabled(asset is not None)
        self.replace_button.setEnabled(asset is not None and clip is not None)
        if asset is None: hint = 'Choose material to insert or replace a block.'
        elif clip is None: hint = 'Select exactly one timeline block to replace it. Insert range adds a new block.'
        else: hint = f"Replace targets {self.block_label(clip['id'])}."
        self.material_hint.setText(hint)
        self.replace_button.setToolTip(hint + ' Keeps target duration, speed and treatment.')

    def update_inspector(self):
        clip = self.active_clip(); count = len(self.selected)
        title = ('Target: ' + self.block_label(clip['id'])) if clip else f'Target: {count} blocks' if count else 'Target: None'
        self.clip_name.setText(title); self.clip_name.setToolTip(title)
        self.timing_fields.setVisible(clip is not None)
        self.timing_fields.setEnabled(clip is not None)
        self.timing_empty.setVisible(clip is None)
        self.timing_empty.setText('Select one timeline block to edit its timing.\nSource In —  ·  Duration —  ·  Speed —'
                                  if count != 0 else 'Select a timeline block to edit its timing.\nSource In —  ·  Duration —  ·  Speed —')
        values = {k: clip[k] for k in ('in_frame', 'frames', 'speed')} if clip else None
        key = clip['id'] if clip else None
        # Refreshing thumbnails, markers or material must not erase a draft.
        if self.timing_key != key or self.timing_base != values:
            self.timing_key = key; self.timing_base = values
            self.load_timing_values()
        self.edit_button.setEnabled(clip is not None); self.copy_button.setEnabled(clip is not None)
        self.paste_button.setEnabled(bool(count and self.look))
        self.duplicate_button.setEnabled(bool(count)); self.remove_button.setEnabled(bool(count))
        self.update_timing_state(); self.update_material_context(); self.update_block_identification()

    def load_timing_values(self):
        if self.timing_base is None: return
        for field, key in ((self.source_in, 'in_frame'), (self.length, 'frames'), (self.speed, 'speed')):
            with QSignalBlocker(field): field.setValue(self.timing_base[key])
        self.timing_display_base = self.displayed_timing_values()

    def displayed_timing_values(self):
        return dict(in_frame=self.source_in.value(), frames=self.length.value(), speed=self.speed.value())

    def timing_values(self):
        # A display precision limit is not an authored timing edit.
        return {key: self.timing_base[key] if value == self.timing_display_base[key] else value
                for key, value in self.displayed_timing_values().items()}

    def has_timing_draft(self):
        return self.timing_key is not None and self.timing_values() != self.timing_base

    def finish_timing_input(self):
        if self.timing_key is not None:
            for control in (self.source_in, self.length, self.speed): control.interpretText()

    def update_timing_state(self, *_):
        draft = self.has_timing_draft()
        self.apply_timing_button.setEnabled(draft); self.revert_timing_button.setVisible(draft)
        self.timing_state.setVisible(self.timing_key is not None)
        self.timing_state.setText(f"Timing draft for {self.block_label(self.timing_key)} · not applied"
                                 if draft else 'Timing applied to this block.')

    def timing_text_edited(self, *_):
        # Let a typed value be applied directly, before Tab/focus commits it.
        if self.timing_key is None: return
        self.apply_timing_button.setEnabled(True); self.revert_timing_button.show()
        self.timing_state.setText(f'Timing draft for {self.block_label(self.timing_key)} · not applied')

    def revert_timing(self):
        self.load_timing_values(); self.update_timing_state()

    def choose_pending_timing(self, purpose):
        label = self.block_label(self.timing_key)
        prompt = QMessageBox(self)
        prompt.setWindowTitle('Pending timing changes')
        prompt.setText(f'{label} has a timing draft.')
        prompt.setInformativeText(f'Resolve it before {purpose}. Apply updates this block; Save stores the montage file.')
        apply = prompt.addButton('Apply to ' + label.split(' · ')[0], QMessageBox.ButtonRole.AcceptRole)
        discard = prompt.addButton('Discard timing draft', QMessageBox.ButtonRole.DestructiveRole)
        stay = prompt.addButton('Stay', QMessageBox.ButtonRole.RejectRole)
        prompt.setDefaultButton(stay); prompt.setEscapeButton(stay); prompt.exec()
        return 'apply' if prompt.clickedButton() is apply else 'discard' if prompt.clickedButton() is discard else 'stay'

    def resolve_timing(self, purpose):
        self.finish_timing_input()
        if not self.has_timing_draft(): return True
        choice = self.choose_pending_timing(purpose)
        if choice == 'apply': return self.apply_timing()
        if choice == 'discard': self.revert_timing(); return True
        return False

    def apply_timing(self):
        self.finish_timing_input(); clip = self.active_clip()
        if not clip or clip['id'] != self.timing_key: return False
        if not self.has_timing_draft(): return True
        doc = copy.deepcopy(self.document)
        next(c for c in doc['clips'] if c['id'] == self.timing_key).update(self.timing_values())
        try: self.commit(doc)
        except (ValueError, OSError) as error:
            self.timing_state.setText(f'Timing not applied: {error}'); return False
        self.status.setText(f"Timing applied to {self.block_label(clip['id'])} · Save stores the montage.")
        return True
