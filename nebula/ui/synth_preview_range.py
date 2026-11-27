"""Workspace-only preparation windows. Never serialized into an artwork."""
import copy
import math
import time

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QCheckBox, QLabel, QWidget, QHBoxLayout, QPushButton, QProgressBar
from nebula.ui.studio_widgets import SpinBox
from nebula.render.synth_preview import PreviewScope, preview_window, cached_gap, longest_cached_scope


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
        self.preparing_gap = None
        self.gap_preparation_paused = False
        self.prepare_range_hint = self.prepare_preview.toolTip()
        self.preview_range_frames = SpinBox()
        self.preview_range_frames.setRange(1, 100000)
        self.preview_range_frames.setValue(150)
        self.preview_range_frames.setSuffix(' frames')
        self.preview_range_frames.setAccessibleName('Preview range frame count')
        self.preview_range_frames.setKeyboardTracking(False)
        self.preview_range_frames.setToolTip('Frames to prepare from the playhead. Near the end, the range starts earlier to keep this length. Selected clips skip gaps. Preview only; does not change the project or export.')
        self.preview_range_frames.valueChanged.connect(self.preview_range_count_changed)
        self.loop_preview_range = QCheckBox('Loop prepared range')
        self.loop_preview_range.setToolTip('Loop the longest continuous prepared span within the playback scope. Enabling it does not start a new preparation; work already in progress continues. Updates as frames arrive; never skips a missing frame. Stays enabled when editing. Audio and MIDI follow the original timeline times. Does not change export or clip repeats.')
        self.loop_preview_range.toggled.connect(self.preview_range_loop_changed)
        self.preview_range_summary = QLabel()
        self.preview_range_summary.setObjectName('monitorMeta')
        self.preview_range_summary.setWordWrap(True)
        self.gap_feedback = QWidget()
        row = QHBoxLayout(self.gap_feedback)
        row.setContentsMargins(0, 0, 0, 0)
        self.gap_status = QLabel()
        self.gap_status.setWordWrap(True)
        self.gap_status.setAccessibleName('Gap preparation status')
        self.gap_progress = QProgressBar()
        self.gap_progress.setFixedWidth(90)
        self.gap_progress.setAccessibleName('Gap preparation progress')
        self.cancel_gap = QPushButton('Cancel')
        self.cancel_gap.setAccessibleName('Cancel gap preparation')
        self.cancel_gap.setToolTip('Stop preparing this gap. Frames already prepared are kept; click the remaining gap to resume.')
        self.cancel_gap.clicked.connect(self.cancel_preview_gap)
        row.addWidget(self.gap_status, 1)
        row.addWidget(self.gap_progress)
        row.addWidget(self.cancel_gap)
        self.gap_feedback.hide()

    def refresh_gap_feedback(self):
        """Persistent feedback beside the monitor, independent of playback FPS."""
        gap = self.preparing_gap
        busy = gap is not None
        self.gap_feedback.setVisible(busy)
        self.cached_ranges.set_preparing_gap(gap)
        self.timeline.setEnabled(not busy)
        self.frame_number.setEnabled(not busy)
        self.preview_range_frames.setEnabled(not busy)
        self.preview_scope.setEnabled(not busy and self.composition is not None)
        self.prepare_full_preview.setEnabled(not busy)
        self.prepare_preview.setToolTip(self.cancel_gap.toolTip() if busy else self.prepare_range_hint)
        if busy:
            start, end = gap
            done = sum(self.preview_frames.contains(source) for frame, source in self.prepared_range_mapping
                       if start <= frame < end)
            self.gap_status.setText(f'Preparing gap · {start/self.preview_fps():.2f}–{end/self.preview_fps():.2f}s · {done}/{end-start} frames')
            self.gap_status.setToolTip('This gap is being prepared. Playback can continue. Cancel to choose another range; completed frames are kept.')
            self.gap_progress.setRange(0, end-start)
            self.gap_progress.setValue(done)
            self.prepare_preview.setText('Cancel gap')
            self.prepare_preview.setAccessibleName('Cancel gap preparation')
        else:
            self.prepare_preview.setAccessibleName('Cancel preview range' if self.preparation_explicit and not self.preparation_full else 'Prepare preview range')

    def cancel_preview_gap(self):
        if self.preparing_gap is None: return
        self.cancel_preparation()
        # A cancelled explicit job must not restart via Auto prepare or playback.
        # A new preparation request or an edited preview context releases this.
        self.gap_preparation_paused = True
        self.preview_status.setText('Gap preparation cancelled · completed frames kept. Click the remaining gap to resume.')

    def preview_range_stamp(self):
        sequence = self.preview_sequence() or {}
        return (self.document_identity, self.settings_generation, self.preview_frames.namespace,
                copy.deepcopy(sequence.get('visual_performance')))

    def remember_preview_range(self, scope, *, mode='range'):
        self.gap_preparation_paused = False
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
        self.gap_preparation_paused = False

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
        elif self.prepared_range_mode in ('joined', 'cached'):
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
        available = longest_cached_scope(self.cached_timeline_scope(), self.base_preview_scope(),
                                         self.prepared_playback_scope, self.timeline.value())
        self.rebase_prepared_loop(available)
        self.prepared_playback_scope = available
        fps = self.preview_fps()
        if self.loop_preview_range.isChecked():
            self.scope_summary.setText(f'{available.count/fps:.2f}s loop' if available.count else 'Waiting for frames')
        if scope:
            spans = ', '.join(f'{start/fps:.2f}–{end/fps:.2f}s' for start, end in scope.intervals)
            short = spans if len(scope.intervals) <= 2 else f'{len(scope.intervals)} spans'
            state = 'prepared' if ready else f'{done}/{len(self.prepared_range_sources)} prepared'
            if self.loop_preview_range.isChecked():
                if available.count:
                    start, end = available.intervals[0]
                    state += f' · Loop: {start/fps:.2f}–{end/fps:.2f}s · {available.count} frames'
                else:
                    state += ' · waiting for frames'
            label = {'all': 'Entire timeline', 'joined': 'Joined range', 'cached': 'Prepared span'}.get(self.prepared_range_mode, 'Range')
            self.preview_range_summary.setText(f'{label}: {short} · {scope.count} frames · {state}')
            self.preview_range_summary.setToolTip(spans + '. Preparation target only. The loop always uses the longest continuous prepared span in the playback scope, including frames from earlier requests. Prepare range changes what to render, not the loop limit. The project stays unchanged.')
        else:
            count = min(self.preview_range_frames.value(), self.base_preview_scope().count)
            self.preview_range_summary.setText(f'{count} frames · {count/fps:.2f}s at {fps:g} fps')
            self.preview_range_summary.setToolTip('Choose a playhead position and frame count. Enable Loop prepared range at any time; Play repeats the longest continuous prepared span while preparation continues.')

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
        self.trace_preview('loop_requested', enabled=checked)
        playing = self.play.isChecked()
        self.play.setChecked(False)
        if checked:
            if not self.ensure_preview_context(): return
            active = self.preparation_explicit or (self.prepare_job is not None
                and self.prepare_job.generation == self.settings_generation and not self.prepare_job.cancel.event.is_set())
            self.refresh_prepared_range()
            if not active:
                # A remembered preparation request is not a command to resume it.
                # Anchor future edit rebuilds to the actual ready span, not an old
                # playhead elsewhere in the timeline. Also discard queued auto work.
                ready = self.prepared_playback_scope
                if ready.count:
                    if ready != self.prepared_range_scope: self.remember_preview_range(ready, mode='cached')
                    self.preparation_target = ()
                    self.warm_debounce.stop()
                else:
                    self.remember_preview_range(preview_window(self.base_preview_scope(), self.timeline.value(), self.preview_range_frames.value()))
            # Retain packets while worker reservations displace the memory LRU.
            self.retain_preview_range()
        self.refresh_preview_scope()
        if playing: self.play.setChecked(True)
        self.refresh_preview_activity()
        self.trace_preview('loop_changed', enabled=checked)

    def trace_preview(self, event, **details):
        from nebula.core.studio_diagnostics import enabled, record
        if not enabled() or not hasattr(self, 'loop_preview_range'): return
        record('preview.'+event, generation=self.settings_generation, playhead=self.timeline.value(),
               fps=self.preview_fps(), size=self.preview_size(), loop=self.loop_preview_range.isChecked(),
               playing=self.play.isChecked(), auto=self.auto_prepare.isChecked(),
               cached=self.cached_timeline_scope().intervals,
               target=self.prepared_range_scope.intervals if self.prepared_range_scope else (),
               mode=self.prepared_range_mode, explicit=self.preparation_explicit,
               ready_loop=self.prepared_playback_scope.intervals, **details)

    def cached_timeline_scope(self):
        """Coverage is shown in output time, even when Perform changes the clock."""
        sequence = self.preview_sequence() or {}
        config = sequence.get('visual_performance')
        if not config or self.preview_bypass():
            maximum = self.timeline.maximum() + 1
            return PreviewScope(tuple((max(0, a), min(maximum, b)) for a, b in self.preview_frames.ranges()
                                      if b > 0 and a < maximum))
        import numpy as np
        from nebula.documents.synth_performance import source_times
        fps = self.preview_fps()
        frames = np.arange(self.timeline.maximum() + 1)
        sources = np.rint(source_times(config, frames / fps, sequence['duration'], fps) * fps).astype(int)
        return scope_from_frames(int(frame) for frame, source in zip(frames, sources)
                                 if self.preview_frames.contains(int(source)))

    def refresh_cached_ranges(self):
        self.cached_ranges.set_ranges(self.cached_timeline_scope().intervals)

    def prepare_preview_gap(self, frame):
        if self.still_poster or self.preparing_gap is not None or self.closing or self.export_job or self.audition_pending(): return
        if not self.ensure_preview_context(): return
        coverage = self.cached_timeline_scope()
        match = cached_gap(coverage.intervals, frame, self.base_preview_scope())
        if not match: return  # A completed/stale gap, or outside the playback scope.
        gap, joined = match
        self.cancel_preparation()
        self.remember_preview_range(PreviewScope((joined,)), mode='joined')
        if not self.retain_preview_range():
            self.refresh_preview_scope()
            return
        # The scheduler skips existing packets, including a source frame shared
        # by multiple output frames. Existing previews keep their exact pixels.
        self.preparation_target = self.prepared_range_sources
        self.preparation_explicit = True
        self.preparation_limited = False
        self.preparing_gap = gap
        self.trace_preview('prepare_requested', reason='gap', gap=gap)
        self.refresh_preview_scope()
        self._start_warm_batch()

    def prepare_configured_range(self):
        if self.still_poster or self.preparing_gap is not None: return
        looping = self.loop_preview_range.isChecked()
        if not looping:
            self.play.setChecked(False)
            self.discard_preview_range()
        self.cancel_preparation()
        if not self.ensure_preview_context(): return
        requested = min(self.preview_range_frames.value(), self.base_preview_scope().count)
        scope = self.prepared_range_scope if (looping and self.prepared_range_mode == 'range'
                and self.prepared_range_scope and self.prepared_range_scope.count == requested) else None
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
        self.trace_preview('prepare_requested', reason='range')
        self.refresh_preview_scope()
        self._start_warm_batch()
