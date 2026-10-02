"""One temporary discovery owner layered on Studio's A3 render/cache routing."""
import copy
import time

from PySide6.QtCore import QSignalBlocker
from synth_effect_discovery import document_fingerprint, effect_candidate
from synth_preview import PreviewScope, preview_context, resolve_scope


def sampled_window(scope, frame, fps):
    """At most two seconds, using distinct original absolute timeline frames."""
    if not scope.count or not scope.contains(frame): return ()
    origin = scope.position(frame)
    count = min(scope.count, max(1, round(fps * 2)))
    first = min(origin, max(0, scope.count - count))
    step = max(1, fps / 12)
    ranks = sorted(set(min(first + count - 1, round(first + i * step)) for i in range(max(1, round(count / step)))))
    return tuple(scope.frame_at(rank) for rank in ranks)


class EffectPreviewSession:
    def __init__(self, studio, section_id=None, operation='add'):
        if studio.export_job: raise ValueError('Previews become available after export finishes.')
        if studio.audition_pending(): raise ValueError('Keep or discard the Creative variation before auditioning an effect.')
        if studio.pending_text_edits(): raise ValueError('Apply or discard the wording draft in the editor before auditioning.')
        self.studio = studio; self.section_id = section_id; self.operation = operation
        self.base = copy.deepcopy(studio.composition)
        self.identity = studio.document_identity; self.fingerprint = document_fingerprint(self.base)
        self.entry_frame = studio.timeline.value()
        self.entry_source = studio.source_preview.isChecked()
        self.prior = studio.comparison
        self.media = preview_context(studio.sequence, studio.preview_size(), False, studio.video_frames.directory)[2]
        self.candidate = None; self.owner = None; self.closed = False; self.ready = False
        self.error = ''; self.effect_id = None; self.preset = 0
        studio.play.setChecked(False); studio.cancel_preparation()
        studio.discovery_session = self
        self.scope = studio.active_preview_scope()
        self.target_scope = resolve_scope(self.base, (section_id,), studio.timeline.maximum(), section_id is not None)
        if section_id is not None:
            intervals = tuple((max(a,c), min(b,d)) for a,b in self.scope.intervals for c,d in self.target_scope.intervals if max(a,c)<min(b,d))
            self.scope = PreviewScope(intervals, len(intervals))
        self.samples = sampled_window(self.scope, self.entry_frame, studio.preview_fps())

    def valid(self):
        studio = self.studio
        return (not self.closed and self.identity is studio.document_identity and
                document_fingerprint(studio.composition) == self.fingerprint and
                self.media[:1] == preview_context(studio.sequence, studio.preview_size(), False, studio.video_frames.directory)[2][:1])

    def select(self, effect_id, preset=0):
        if not self.valid(): raise ValueError('The piece or media changed. Close this audition and open a fresh preview.')
        self.ready = False; self.error = ''; self.effect_id = effect_id; self.preset = preset
        self.candidate = effect_candidate(self.base, self.section_id, effect_id, self.operation, preset)
        self.studio.begin_comparison(self.base, 'Before', self.candidate, purpose='contribution' if self.operation == 'without' else 'effect')
        self.owner = self.studio.comparison['token']
        self.studio.comparison['label_b'] = 'Without effect' if self.operation == 'without' else 'Preset preview'
        self.studio.refresh_comparison_controls()

    def accept_packet(self):
        comparison = self.studio.comparison
        if self.valid() and comparison and comparison['token'] is self.owner and comparison['side'] == 'b':
            self.ready = True; self.error = ''
            self.success_media = preview_context(self.studio.sequence, self.studio.preview_size(), False, self.studio.video_frames.directory)[2]

    def fail(self, message):
        self.ready = False; self.error = str(message)

    def seek_selected(self):
        if not self.target_scope.count: return
        frame = self.studio.timeline.value()
        interval = min(self.target_scope.intervals, key=lambda ab: min(abs(frame-ab[0]), abs(frame-ab[1]+1)))
        chosen = min(max(frame, interval[0]), interval[1]-1)
        self.studio.timeline.setValue(chosen)
        if not self.scope.contains(chosen): self.scope = self.target_scope
        self.samples = sampled_window(self.scope, chosen, self.studio.preview_fps())

    def prepare_samples(self):
        studio = self.studio
        studio.cancel_preparation()
        if self.samples:
            studio.preparation_target = self.samples
            studio.preparation_explicit = True
            studio.preparation_limited = False
            studio._start_warm_batch()

    def apply(self):
        if not self.valid(): raise ValueError('The piece or media changed. Open a fresh preview before applying.')
        if (not self.ready or self.error or self.candidate is None or
                self.success_media != preview_context(self.studio.sequence, self.studio.preview_size(), False, self.studio.video_frames.directory)[2]): raise ValueError('Wait for a successful current preset preview before applying.')
        candidate = self.candidate
        self.close(restore=False)
        self.studio.composer.commit(candidate, 'effect-' + self.operation)
        self.studio.composer.effects_panel.inspect_effect(self.effect_id)
        self.studio.composer.effects_panel.parameter_tabs.setCurrentIndex(0)

    def close(self, restore=True):
        if self.closed: return
        valid = self.valid(); self.closed = True
        studio = self.studio
        studio.discovery_session = None
        studio.play.setChecked(False); studio.cancel_preparation()
        studio.end_comparison()
        if valid:
            with QSignalBlocker(studio.timeline): studio.timeline.setValue(self.entry_frame)
            with QSignalBlocker(studio.source_preview): studio.source_preview.setChecked(self.entry_source)
            if restore: studio.comparison = self.prior
        studio.viewer.set_packet(None); studio.refresh_comparison_controls(); studio.invalidate(force_clear=True)
