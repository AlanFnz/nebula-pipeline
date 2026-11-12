"""Workspace-only preparation windows. Never serialized into an artwork."""
import copy
import math
import time

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
        self.prepared_range_mapping = ()
        self.prepared_playback_scope = PreviewScope(())
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
        self.loop_preview_range.setToolTip('Loop available frames while the range prepares. You can enable this before preparation; Play waits for the first frame and the loop grows as more arrive. Audio and MIDI follow the original timeline times. Does not change export or clip repeats.')
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
        self.prepared_range_mapping = tuple((frame, round(self.performance_source_time(frame / fps) * fps))
                                            for frame in frames_in(scope))
        self.prepared_range_sources = tuple(dict.fromkeys(source for _, source in self.prepared_range_mapping))
        self.prepared_range_stamp = self.preview_range_stamp()

    def discard_preview_range(self):
        if not hasattr(self, 'loop_preview_range'): return
        if self.loop_preview_range.isChecked():
            self.play.setChecked(False)
            with QSignalBlocker(self.loop_preview_range): self.loop_preview_range.setChecked(False)
        self.prepared_range_scope = None
        self.prepared_range_sources = ()
        self.prepared_range_mapping = ()
        self.prepared_playback_scope = PreviewScope(())

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
        available = scope_from_frames(frame for frame, source in self.prepared_range_mapping
                                      if self.preview_frames.contains(source))
        self.rebase_prepared_loop(available)
        self.prepared_playback_scope = available
        fps = self.preview_fps()
        if self.loop_preview_range.isChecked():
            self.scope_summary.setText(f'{available.count/fps:.2f}s loop' if available.count else 'Waiting for frames')
        if scope:
            spans = ', '.join(f'{start/fps:.2f}–{end/fps:.2f}s' for start, end in scope.intervals)
            short = spans if len(scope.intervals) <= 2 else f'{len(scope.intervals)} spans'
            state = 'ready to loop' if ready else f'{done}/{len(self.prepared_range_sources)} prepared'
            if self.loop_preview_range.isChecked():
                state += f' · looping {available.count} frames' if available.count else ' · waiting for frames'
            self.preview_range_summary.setText(f'Range: {short} · {scope.count} frames · {state}')
            self.preview_range_summary.setToolTip(spans + '. Only this prepared range repeats; the project stays unchanged.')
        else:
            count = min(self.preview_range_frames.value(), self.base_preview_scope().count)
            self.preview_range_summary.setText(f'{count} frames · {count/fps:.2f}s at {fps:g} fps')
            self.preview_range_summary.setToolTip('Choose a playhead position and frame count. Enable Loop prepared range at any time; Play repeats available frames while preparation continues.')

    def rebase_prepared_loop(self, available):
        """Changing the cache must not change the current transport phase."""
        previous = self.prepared_playback_scope
        if previous == available or not self.loop_preview_range.isChecked() or not self.play.isChecked(): return
        now = time.monotonic()
        elapsed = self.play_origin + (now - self.play_started) * self.preview_fps()
        whole = math.floor(elapsed + 1e-8)
        frame = previous.frame_at(whole % max(1, previous.count))
        fraction = max(0., elapsed - whole) if previous.count and available.contains(frame) else 0.
        self.play_origin = available.position(frame) + fraction
        self.play_started = now

    def retain_preview_range(self):
        try:
            count = len(set(self.preview_frames.available()) | set(self.prepared_range_sources))
            self.preview_frames.enable_full(self.preview_size(), count)
            return True
        except OSError as exc:
            self.preview_status.setText(str(exc)); self.status.setText(str(exc))
            return False

    def preview_range_loop_changed(self, checked):
        playing = self.play.isChecked()
        self.play.setChecked(False)
        if checked:
            if not self.ensure_preview_context(): return
            requested = min(self.preview_range_frames.value(), self.base_preview_scope().count)
            if not self.prepared_range_scope or self.prepared_range_scope.count != requested:
                self.remember_preview_range(preview_window(self.base_preview_scope(), self.timeline.value(), self.preview_range_frames.value()))
            # Retain packets while worker reservations displace the memory LRU.
            self.retain_preview_range()
        self.refresh_preview_scope()
        if playing: self.play.setChecked(True)
        self.schedule_auto_preparation()

    def prepare_configured_range(self):
        looping = self.loop_preview_range.isChecked()
        if not looping:
            self.play.setChecked(False)
            self.discard_preview_range()
        self.cancel_preparation()
        if not self.ensure_preview_context(): return
        scope = self.prepared_range_scope if looping else None
        if scope is None:
            scope = preview_window(self.base_preview_scope(), self.timeline.value(), self.preview_range_frames.value())
            self.remember_preview_range(scope)
        if not scope.count:
            self.refresh_prepared_range()
            return
        if not self.retain_preview_range():
            self.refresh_prepared_range()
            return
        self.preparation_explicit = True
        self.preparation_limited = False
        self.preparation_target = self.prepared_range_sources
        self.refresh_preview_scope()
        self._start_warm_batch()
