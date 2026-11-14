"""Workspace-only preparation windows. Never serialized into an artwork."""
import copy
import math
import time

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QCheckBox, QLabel
from studio_widgets import SpinBox
from synth_preview import PreviewScope, preview_window, cached_gap


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
        self.prepared_range_mode = 'range'
        self.prepared_range_fps = None
        self.prepared_gap_hold = None
        self.preview_range_frames = SpinBox()
        self.preview_range_frames.setRange(1, 100000)
        self.preview_range_frames.setValue(150)
        self.preview_range_frames.setSuffix(' frames')
        self.preview_range_frames.setAccessibleName('Preview range frame count')
        self.preview_range_frames.setKeyboardTracking(False)
        self.preview_range_frames.setToolTip('Frames to prepare from the playhead. Near the end, the range starts earlier to keep this length. Selected clips skip gaps. Preview only; does not change the project or export.')
        self.preview_range_frames.valueChanged.connect(self.preview_range_count_changed)
        self.loop_preview_range = QCheckBox('Loop prepared range')
        self.loop_preview_range.setToolTip('Loop available frames from the last preparation: the chosen range or the entire timeline after Prepare all frames. The loop grows as frames arrive and stays enabled when editing. Audio and MIDI follow the original timeline times. Does not change export or clip repeats.')
        self.loop_preview_range.toggled.connect(self.preview_range_loop_changed)
        self.preview_range_summary = QLabel()
        self.preview_range_summary.setObjectName('monitorMeta')
        self.preview_range_summary.setWordWrap(True)

    def preview_range_stamp(self):
        sequence = self.preview_sequence() or {}
        return (self.document_identity, self.settings_generation, self.preview_frames.namespace,
                copy.deepcopy(sequence.get('visual_performance')))

    def remember_preview_range(self, scope, *, mode='range'):
        self.prepared_gap_hold = None
        self.prepared_range_scope = scope
        self.prepared_range_mode = mode
        fps = self.preview_fps()
        self.prepared_range_fps = fps
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
        self.prepared_range_stamp = None
        self.prepared_range_mode = 'range'
        self.prepared_gap_hold = None

    def refresh_preview_range_target(self):
        """Invalidate packets without discarding the user's playback choice."""
        if not self.prepared_range_scope: return
        stamp = self.preview_range_stamp()
        if self.prepared_range_stamp == stamp: return
        if self.prepared_range_stamp[0] is not self.document_identity:
            self.discard_preview_range()
            return
        if self.prepared_range_mode == 'all':
            scope = PreviewScope(((0, self.timeline.maximum() + 1),))
        elif self.prepared_range_mode == 'joined':
            ratio = self.preview_fps() / self.prepared_range_fps
            maximum = self.timeline.maximum() + 1
            scope = PreviewScope(tuple((round(start*ratio), min(maximum, round(end*ratio)))
                                       for start, end in self.prepared_range_scope.intervals
                                       if round(start*ratio) < maximum))
        else:
            start = self.prepared_range_scope.frame_at(0)
            start = round(start / self.prepared_range_fps * self.preview_fps())
            scope = preview_window(self.base_preview_scope(), start, self.preview_range_frames.value())
        self.remember_preview_range(scope, mode=self.prepared_range_mode)

    def preview_range_count_changed(self, *_):
        self.cancel_preparation()
        if self.loop_preview_range.isChecked():
            self.remember_preview_range(preview_window(self.base_preview_scope(), self.timeline.value(), self.preview_range_frames.value()))
        else:
            self.discard_preview_range()
        self.refresh_preview_scope()
        self.schedule_auto_preparation()

    def refresh_prepared_range(self):
        if not hasattr(self, 'loop_preview_range'): return
        self.refresh_preview_range_target()
        scope = self.prepared_range_scope
        done = sum(self.preview_frames.contains(frame) for frame in self.prepared_range_sources)
        ready = bool(scope and scope.count and done == len(self.prepared_range_sources))
        available = scope_from_frames(frame for frame, source in self.prepared_range_mapping
                                      if self.preview_frames.contains(source))
        if self.prepared_gap_hold is not None:
            if ready:
                self.prepared_gap_hold = None
            else:
                # Keep the current loop continuous until both sides are joined.
                available = scope_from_frames(frame for frame in frames_in(self.prepared_gap_hold)
                    if self.preview_frames.contains(round(self.performance_source_time(frame/self.preview_fps()) * self.preview_fps())))
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
            label = {'all': 'Entire timeline', 'joined': 'Joined range'}.get(self.prepared_range_mode, 'Range')
            self.preview_range_summary.setText(f'{label}: {short} · {scope.count} frames · {state}')
            self.preview_range_summary.setToolTip(spans + '. The loop follows this preparation target. Prepare range switches back to the chosen frame count; Prepare all frames covers the entire timeline. The project stays unchanged.')
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
            if not self.prepared_range_scope or (self.prepared_range_mode == 'range' and self.prepared_range_scope.count != requested):
                self.remember_preview_range(preview_window(self.base_preview_scope(), self.timeline.value(), self.preview_range_frames.value()))
            # Retain packets while worker reservations displace the memory LRU.
            self.retain_preview_range()
        self.refresh_preview_scope()
        if playing: self.play.setChecked(True)
        self.schedule_auto_preparation()

    def cached_timeline_scope(self):
        """Coverage is shown in output time, even when Perform changes the clock."""
        sequence = self.preview_sequence() or {}
        config = sequence.get('visual_performance')
        if not config or self.preview_bypass():
            maximum = self.timeline.maximum() + 1
            return PreviewScope(tuple((max(0, a), min(maximum, b)) for a, b in self.preview_frames.ranges()
                                      if b > 0 and a < maximum))
        import numpy as np
        from synth_performance import source_times
        fps = self.preview_fps()
        frames = np.arange(self.timeline.maximum() + 1)
        sources = np.rint(source_times(config, frames / fps, sequence['duration'], fps) * fps).astype(int)
        return scope_from_frames(int(frame) for frame, source in zip(frames, sources)
                                 if self.preview_frames.contains(int(source)))

    def refresh_cached_ranges(self):
        self.cached_ranges.set_ranges(self.cached_timeline_scope().intervals)

    def prepare_preview_gap(self, frame):
        if self.closing or self.export_job or self.audition_pending(): return
        if not self.ensure_preview_context(): return
        coverage = self.cached_timeline_scope()
        match = cached_gap(coverage.intervals, frame, self.base_preview_scope())
        if not match: return  # A completed/stale gap, or outside the playback scope.
        gap, joined = match
        hold = self.active_preview_scope() if self.loop_preview_range.isChecked() else None
        if not hold or not hold.count:
            hold = PreviewScope(((joined[0], gap[0]),))
        self.cancel_preparation()
        self.remember_preview_range(PreviewScope((joined,)), mode='joined')
        self.prepared_gap_hold = hold
        if not self.retain_preview_range():
            self.refresh_preview_scope()
            return
        # The scheduler skips existing packets, including a source frame shared
        # by multiple output frames. Existing previews keep their exact pixels.
        self.preparation_target = self.prepared_range_sources
        self.preparation_explicit = True
        self.preparation_limited = False
        self.refresh_preview_scope()
        self._start_warm_batch()

    def prepare_configured_range(self):
        looping = self.loop_preview_range.isChecked()
        if not looping:
            self.play.setChecked(False)
            self.discard_preview_range()
        self.cancel_preparation()
        if not self.ensure_preview_context(): return
        scope = self.prepared_range_scope if looping and self.prepared_range_mode == 'range' else None
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
