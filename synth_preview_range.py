"""Workspace-only preparation windows. Never serialized into an artwork."""
import copy

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QCheckBox, QLabel
from studio_widgets import SpinBox
from synth_preview import PreviewScope, preview_window


def frames_in(scope):
    return (frame for start, end in scope.intervals for frame in range(start, end))


def scope_from_frames(frames):
    intervals = []
    for frame in sorted(set(frames)):
        if intervals and frame == intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], frame + 1)
        else: intervals.append((frame, frame + 1))
    return PreviewScope(tuple(intervals))


class PreviewRangeStudio:
    def setup_preview_range(self):
        self.prepared_range_scope = None
        self.prepared_range_sources = ()
        self.prepared_range_stamp = None
        self.preview_range_frames = SpinBox()
        self.preview_range_frames.setRange(1, 100000)
        self.preview_range_frames.setValue(150)
        self.preview_range_frames.setSuffix(' frames')
        self.preview_range_frames.setAccessibleName('Preview range frame count')
        self.preview_range_frames.setKeyboardTracking(False)
        self.preview_range_frames.setToolTip('Frames to prepare from the playhead. Near the end, the range starts earlier to keep this length. Selected clips skip gaps. Preview only; does not change the project or export.')
        self.preview_range_frames.valueChanged.connect(self.preview_range_count_changed)
        self.loop_preview_range = QCheckBox('Loop prepared range')
        self.loop_preview_range.setEnabled(False)
        self.loop_preview_range.setToolTip('Repeat the prepared range when you press Play. Uses the original timeline times for audio and MIDI. Does not change export or clip repeats.')
        self.loop_preview_range.toggled.connect(self.preview_range_loop_changed)
        self.preview_range_summary = QLabel()
        self.preview_range_summary.setObjectName('monitorMeta')
        self.preview_range_summary.setWordWrap(True)

    def preview_range_stamp(self):
        sequence = self.preview_sequence() or {}
        return (self.document_identity, self.settings_generation, self.preview_frames.namespace,
                copy.deepcopy(sequence.get('visual_performance')))

    def remember_preview_range(self, scope):
        self.prepared_range_scope = scope
        fps = self.preview_fps()
        self.prepared_range_sources = tuple(dict.fromkeys(
            round(self.performance_source_time(frame / fps) * fps) for frame in frames_in(scope)))
        self.prepared_range_stamp = self.preview_range_stamp()

    def discard_preview_range(self):
        if not hasattr(self, 'loop_preview_range'): return
        if self.loop_preview_range.isChecked():
            self.play.setChecked(False)
            with QSignalBlocker(self.loop_preview_range): self.loop_preview_range.setChecked(False)
        self.prepared_range_scope = None
        self.prepared_range_sources = ()

    def preview_range_count_changed(self, *_):
        self.discard_preview_range()
        self.cancel_preparation()
        self.refresh_preview_scope()
        self.schedule_auto_preparation()

    def refresh_prepared_range(self):
        if not hasattr(self, 'loop_preview_range'): return
        if self.prepared_range_scope and self.prepared_range_stamp != self.preview_range_stamp():
            self.discard_preview_range()
            self.refresh_workspace_context()
        scope = self.prepared_range_scope
        done = sum(self.preview_frames.contains(frame) for frame in self.prepared_range_sources)
        ready = bool(scope and scope.count and done == len(self.prepared_range_sources))
        if self.loop_preview_range.isChecked() and not ready:
            self.play.setChecked(False)
            with QSignalBlocker(self.loop_preview_range): self.loop_preview_range.setChecked(False)
            self.refresh_workspace_context()
        self.loop_preview_range.setEnabled(ready)
        fps = self.preview_fps()
        if scope:
            spans = ', '.join(f'{start/fps:.2f}–{end/fps:.2f}s' for start, end in scope.intervals)
            short = spans if len(scope.intervals) <= 2 else f'{len(scope.intervals)} spans'
            state = 'ready to loop' if ready else f'{done}/{len(self.prepared_range_sources)} prepared'
            self.preview_range_summary.setText(f'Range: {short} · {scope.count} frames · {state}')
            self.preview_range_summary.setToolTip(spans + '. Only this prepared range repeats; the project stays unchanged.')
        else:
            count = min(self.preview_range_frames.value(), self.base_preview_scope().count)
            self.preview_range_summary.setText(f'{count} frames · {count/fps:.2f}s at {fps:g} fps')
            self.preview_range_summary.setToolTip('Choose a playhead position, then Prepare range. Loop becomes available when every frame in the range is ready.')

    def preview_range_loop_changed(self, checked):
        playing = self.play.isChecked()
        self.play.setChecked(False)
        self.cancel_preparation()
        scope = self.active_preview_scope()
        if checked and not scope.contains(self.timeline.value()): self.timeline.setValue(scope.frame_at(0))
        self.refresh_preview_scope()
        if playing: self.play.setChecked(True)
        if not checked: self.schedule_auto_preparation()

    def prepare_configured_range(self):
        self.play.setChecked(False)
        self.discard_preview_range()
        self.cancel_preparation()
        if not self.ensure_preview_context(): return
        scope = preview_window(self.base_preview_scope(), self.timeline.value(), self.preview_range_frames.value())
        self.remember_preview_range(scope)
        if not scope.count:
            self.refresh_prepared_range()
            return
        try:
            # Lossless disk backing retains the requested range even when it
            # exceeds RAM. Foreground LRU and worker reservations remain bounded.
            count = len(set(self.preview_frames.available()) | set(self.prepared_range_sources))
            self.preview_frames.enable_full(self.preview_size(), count)
        except OSError as exc:
            self.preview_status.setText(str(exc)); self.status.setText(str(exc))
            self.refresh_prepared_range()
            return
        self.preparation_explicit = True
        self.preparation_limited = False
        self.preparation_target = self.prepared_range_sources
        self.refresh_preview_scope()
        self._start_warm_batch()
