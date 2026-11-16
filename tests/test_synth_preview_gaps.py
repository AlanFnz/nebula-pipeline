"""Click a missing preview span, preserve pixels, and join its loop on completion."""
import copy

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from synth_preview import PreviewScope, cached_gap
from test_synth_composer_ui import window
from test_synth_preview_range import setup
from test_synth_preview_scope import prepared, settle


def seed(window, ranges=((0, 4), (8, 12), (15, 18))):
    window.preview_frames.clear()
    window.preview_frames.enable_full(window.preview_size(), window.timeline.maximum()+1)
    packet = (window.preview_size(), bytes(window.preview_size()[0]*window.preview_size()[1]*3))
    for start, end in ranges:
        for frame in range(start, end): window.preview_frames.put(frame, packet)
    window.remember_preview_range(PreviewScope((ranges[0],)))
    window.refresh_cached_ranges()
    return packet


def click_gap(window, frame):
    strip = window.cached_ranges
    origin = strip.mapFromGlobal(window.timeline.mapToGlobal(QPoint())).x()
    x = origin + (frame+.5)*window.timeline.width()/(window.timeline.maximum()+1)
    QTest.mouseClick(strip, Qt.MouseButton.LeftButton, pos=QPoint(round(x), strip.height()//2))


def test_only_internal_gaps_with_two_selected_neighbors_are_fillable():
    ranges = [(2, 5), (8, 10), (13, 20)]
    scope = PreviewScope(((0, 10), (13, 24)))
    assert cached_gap(ranges, 5, scope) == ((5, 8), (2, 10))
    assert cached_gap(ranges, 7, scope) == ((5, 8), (2, 10))
    for frame in (-1, 0, 4, 8, 11, 20, 24):
        assert cached_gap(ranges, frame, scope) is None
    assert cached_gap(ranges, 11, PreviewScope(((0, 13), (13, 24)))) == ((10, 13), (8, 20))


def test_click_fills_only_missing_frames_then_loops_both_spans(window, monkeypatch):
    before = setup(window, monkeypatch)
    seed(window)
    cached = {f: window.preview_frames.get(f) for f in window.preview_frames.available()}
    jobs = []
    start = window.jobs.start
    monkeypatch.setattr(window.jobs, 'start', lambda job: (jobs.append(job), start(job)))
    playhead = window.timeline.value()
    generation = window.settings_generation
    click_gap(window, 6)
    prepared(window)
    assert window.timeline.value() == playhead and not window.play.isChecked()
    assert window.prepared_range_scope.intervals == ((0, 12),)
    assert window.prepared_range_mode == 'joined'
    assert {f for job in jobs for f in job.frames} == {4, 5, 6, 7}
    assert all(job.size == (64, 48) for job in jobs)
    assert all(window.preview_frames.get(f) == packet for f, packet in cached.items())
    assert window.cached_ranges.ranges == [(0, 12), (15, 18)]
    window.loop_preview_range.setChecked(True)  # Must not revert to the 7-frame setting.
    assert window.active_preview_scope().intervals == ((0, 12),)
    assert 'Joined range:' in window.preview_range_summary.text()
    assert window.composition == before and window.settings_generation == generation
    assert window.preparing_gap is None and not window.gap_feedback.isVisible()
    assert window.timeline.isEnabled() and window.prepare_full_preview.isEnabled()
    assert window.preview_frames.bytes + window.preview_frames.reserved <= window.preview_frames.budget
    # Join the next gap; a short preparation request cannot shrink the loop.
    click_gap(window, 13); prepared(window)
    assert window.active_preview_scope().intervals == ((0, 18),)
    window.prepare_playback(); prepared(window)
    assert window.active_preview_scope().count == 18


def test_playing_loop_grows_through_gap_and_joins_without_audio_seek(window, monkeypatch):
    setup(window, monkeypatch)
    packet = seed(window)
    window.prepared_range_mode = 'joined'  # Keep the existing four-frame loop.
    window.loop_preview_range.setChecked(True)
    clock = [100.]
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    audio = []
    monkeypatch.setattr(window, 'sync_soundtrack', lambda **kw: audio.append(kw))
    window.play.setChecked(True)
    started = []
    monkeypatch.setattr(window.jobs, 'start', started.append)
    click_gap(window, 6)
    job = started[-1]
    assert window.gap_feedback.isVisible()
    assert window.gap_progress.maximum() == 4 and window.gap_progress.value() == 0
    assert window.active_preview_scope().intervals == ((0, 4),)
    for f in (4, 5, 6): window.prepared_frame(job, (window.settings_generation, f, packet))
    assert window.gap_progress.value() == 3
    assert '3/4 frames' in window.gap_status.text()
    assert window.active_preview_scope().intervals == ((0, 7),)
    assert '7/7 frames' in window.cache_status.text()
    for i in range(1, 10):
        clock[0] = 100+i/25
        window.advance()
        assert window.timeline.value() == i % 7
        assert window.gap_feedback.isVisible() and '3/4 frames' in window.gap_status.text()
    clock[0] += .01
    window.prepared_frame(job, (window.settings_generation, 7, packet))
    window.advance()
    assert window.active_preview_scope().intervals == ((0, 12),)
    assert window.timeline.value() == 2 and not audio[-1]['force']
    assert window.play.isChecked() and window.loop_preview_range.isChecked()
    window.cancel_preparation(); window.preparation_finished(job)
    window.play.setChecked(False)


def test_old_request_cannot_limit_loop_enabled_mid_job_and_single_frame_hole_joins(window, monkeypatch):
    before = setup(window, monkeypatch)
    packet = seed(window, ((0, 10), (11, 18)))
    # Auto preparation has moved on, but the remembered request is still short.
    window.remember_preview_range(PreviewScope(((0, 4),)))
    started = []
    monkeypatch.setattr(window.jobs, 'start', started.append)
    window.preparation_target = (10,)
    window._start_warm_batch()
    job = started[-1]
    window.loop_preview_range.setChecked(True)
    assert window.prepare_job is job and not job.cancel.event.is_set()
    assert window.active_preview_scope().intervals == ((0, 10),)
    clock = [100.]
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    audio = []
    monkeypatch.setattr(window, 'sync_soundtrack', lambda **kw: audio.append(kw))
    window.play.setChecked(True)
    clock[0] += 2/25
    window.advance()
    position = window.timeline.value()
    clock[0] += .01
    window.prepared_frame(job, (window.settings_generation, 10, packet))
    assert window.cached_ranges.ranges == [(0, 18)]
    assert window.active_preview_scope().intervals == ((0, 18),)
    window.advance()
    assert window.timeline.value() == position and not audio[-1]['force']
    assert 'Loop: 0.00–0.72s · 18 frames' in window.preview_range_summary.text()
    # Seeking into ready frames outside the old request keeps the loop enabled.
    window.timeline.setValue(16)
    assert window.loop_preview_range.isChecked()
    window.play.setChecked(False)
    window.cancel_preparation(); window.preparation_finished(job)
    assert window.composition == before


def test_longer_ready_island_takes_over_and_updates_audio_time(window, monkeypatch):
    setup(window, monkeypatch)
    packet = seed(window, ((0, 4), (8, 11)))
    window.loop_preview_range.setChecked(True)
    clock = [100.]
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    audio = []
    monkeypatch.setattr(window, 'sync_soundtrack', lambda **kw: audio.append(kw))
    window.play.setChecked(True)
    clock[0] += 1/25
    window.advance()
    window.preview_frames.put(11, packet); window.refresh_cached_ranges()
    assert window.active_preview_scope().intervals == ((0, 4),)  # Equal: keep stable.
    window.preview_frames.put(12, packet); window.refresh_cached_ranges()
    assert window.active_preview_scope().intervals == ((8, 13),)
    window.advance()
    assert window.timeline.value() == 8
    assert audio[-1]['force'] and abs(audio[-1]['seconds'] - 8/25) < 1e-7
    window.play.setChecked(False)


def test_left_growth_preserves_playhead_and_fractional_audio_position(window, monkeypatch):
    setup(window, monkeypatch)
    packet = seed(window, ((8, 14),))
    window.loop_preview_range.setChecked(True)
    clock = [100.]
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    audio = []
    monkeypatch.setattr(window, 'sync_soundtrack', lambda **kw: audio.append(kw))
    window.play.setChecked(True)
    clock[0] += 2.25/25
    window.advance()
    assert window.timeline.value() == 10
    for frame in (7, 6):
        window.preview_frames.put(frame, packet); window.refresh_cached_ranges()
    window.advance()
    assert window.active_preview_scope().intervals == ((6, 14),)
    assert window.timeline.value() == 10 and not audio[-1]['force']
    assert abs(audio[-1]['seconds'] - 10.25/25) < 1e-7
    window.play.setChecked(False)


def test_cancel_gap_resume_and_quality_change_do_not_shrink_joined_target(window, monkeypatch):
    before = setup(window, monkeypatch)
    packet = seed(window)
    started = []
    monkeypatch.setattr(window.jobs, 'start', started.append)
    window.prepare_preview_gap(6)
    job = started[-1]
    window.prepared_frame(job, (window.settings_generation, 4, packet))
    window.cancel_preparation(); window.preparation_finished(job)
    assert window.preview_frames.contains(4)
    window.prepare_preview_gap(6)
    job = started[-1]
    assert job.frames == (5, 6)  # Bounded two-frame batch; cache skips frame 4.
    window.loop_preview_range.setChecked(True)
    monkeypatch.setattr(window, 'preview_size', lambda: (80, 60))
    window.quality.setCurrentIndex(1)
    assert window.preparing_gap is None and not window.gap_feedback.isVisible()
    assert window.timeline.isEnabled() and window.preview_range_frames.isEnabled()
    assert window.loop_preview_range.isChecked()
    assert window.prepared_range_scope.intervals == ((0, 12),)
    assert window.active_preview_scope().count == 0
    window.preparation_finished(job, result=(job.generation, [(5, packet)]))
    assert not window.preview_frames.contains(5)  # Late pixels at the old resolution are rejected.
    window.cancel_preparation()
    assert window.composition == before


def test_ready_and_outer_regions_never_start_jobs_or_move_playhead(window, monkeypatch):
    setup(window, monkeypatch)
    seed(window, ((2, 4), (8, 12)))
    started = []
    start = window.jobs.start
    monkeypatch.setattr(window.jobs, 'start', started.append)
    current = window.timeline.value()
    for frame in (0, 3, 8, 14, 17): click_gap(window, frame)
    assert not started and window.timeline.value() == current
    monkeypatch.setattr(window.jobs, 'start', start)
    window.section_timeline.select_at(0)
    window.section_timeline.select_at(3, Qt.KeyboardModifier.MetaModifier)
    window.preview_scope.setCurrentIndex(1); settle(window)
    started.clear()
    monkeypatch.setattr(window.jobs, 'start', started.append)
    click_gap(window, 6)  # Unselected clips must not become part of a joined loop.
    assert not started


def test_gap_prioritizes_missing_span_over_full_preparation_and_rejects_old_job(window, monkeypatch):
    setup(window, monkeypatch)
    packet = seed(window)
    started = []
    monkeypatch.setattr(window.jobs, 'start', started.append)
    window.prepare_full_playback()
    previous = started[-1]
    window.prepare_preview_gap(13)
    assert previous.cancel.event.is_set()
    assert window.prepared_range_scope.intervals == ((8, 18),)
    window.preparation_finished(previous, result=(previous.generation, [(4, packet)]))
    QApplication.processEvents()
    assert not window.preview_frames.contains(4)
    assert started[-1].frames == (12, 13)
    window.cancel_preparation(); window.preparation_finished(started[-1])


def test_gap_uses_output_coverage_and_deduplicated_perform_source_frames(window, monkeypatch):
    setup(window, monkeypatch)
    from synth_performance import defaults
    project = copy.deepcopy(window.composition)
    project['visual_performance'] = defaults()
    project['visual_performance']['values']['pace'] = 50
    window.set_composition(project); settle(window)
    seed(window, ((0, 2), (4, 6)))
    assert window.cached_ranges.ranges == [(0, 4), (8, 12)]
    jobs = []
    start = window.jobs.start
    monkeypatch.setattr(window.jobs, 'start', lambda job: (jobs.append(job), start(job)))
    click_gap(window, 6); prepared(window)
    assert {f for job in jobs for f in job.frames} == {2, 3}
    window.loop_preview_range.setChecked(True)
    assert window.active_preview_scope().intervals == ((0, 12),)


def test_strip_hover_marks_gap_and_has_a_practical_hit_area(window, monkeypatch):
    setup(window, monkeypatch)
    seed(window)
    QApplication.processEvents()
    strip = window.cached_ranges
    x = int(6.5 * window.timeline.width() / (window.timeline.maximum()+1))
    strip.update_hover(x)
    assert strip.hover_gap == (4, 8)
    assert '4 frames' in strip.toolTip()
    assert strip.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert strip.height() >= 12
    strip.grab()  # Exercise custom hover painting.
    strip.update_hover(0)
    assert strip.hover_gap is None


def test_busy_gap_blocks_replacement_and_cancel_stays_cancelled_with_auto_prepare(window, monkeypatch):
    before = setup(window, monkeypatch)
    packet = seed(window)
    window.prepared_range_mode = 'joined'
    window.loop_preview_range.setChecked(True)
    window.auto_prepare.setChecked(True)
    started = []
    monkeypatch.setattr(window.jobs, 'start', started.append)
    click_gap(window, 6)
    job = started[-1]
    target = window.preparation_target
    assert window.cached_ranges.preparing_gap == (4, 8)
    assert not window.timeline.isEnabled() and not window.preview_range_frames.isEnabled()
    assert not window.prepare_full_preview.isEnabled() and not window.preview_scope.isEnabled()
    assert window.prepare_preview.text() == 'Cancel gap'
    for frame in (6, 13):
        click_gap(window, frame)
        window.prepare_preview_gap(frame)  # The controller rejects replacement too.
    window.prepare_full_playback()
    window.prepare_configured_range()
    assert window.prepare_job is job and not job.cancel.event.is_set()
    assert window.preparation_target == target and len(started) == 1
    window.cached_ranges.update_hover(0)
    assert window.cached_ranges.hover_gap is None
    assert 'Cancel preparation' in window.cached_ranges.toolTip()
    window.cached_ranges.grab()  # Busy marker is painted even without hovering.
    window.prepared_frame(job, (window.settings_generation, 4, packet))
    window.cancel_gap.click()
    assert job.cancel.event.is_set()
    assert not window.gap_feedback.isVisible() and window.cached_ranges.preparing_gap is None
    assert window.timeline.isEnabled() and window.prepare_full_preview.isEnabled()
    assert window.preview_frames.contains(4)
    window.preparation_finished(job, result=(job.generation, [(5, packet)]))
    assert not window.preview_frames.contains(5)
    window.schedule_auto_preparation()
    window._automatic_preparation()
    assert not window.warm_debounce.isActive() and not window.preparation_target
    assert len(started) == 1  # Auto prepare must not undo Cancel.
    click_gap(window, 6)
    assert not window.gap_preparation_paused
    assert window.preparing_gap == (5, 8) and started[-1].frames == (5, 6)
    assert window.gap_progress.maximum() == 3
    window.prepare_preview.click()  # Lower preparation row cancels the same job.
    window.preparation_finished(started[-1])
    assert window.gap_preparation_paused and window.composition == before


def test_gap_failure_unlocks_controls_and_play_without_loop_keeps_job(window, monkeypatch):
    setup(window, monkeypatch)
    seed(window)
    started = []
    monkeypatch.setattr(window.jobs, 'start', started.append)
    window.prepare_preview_gap(6)
    job = started[-1]
    window.play.setChecked(True)
    window.request_frame()  # Current frame is missing: must not cancel the gap worker.
    assert window.prepare_job is job and not job.cancel.event.is_set()
    window.play.setChecked(False)
    window.preparation_finished(job, error='Test render failure')
    assert window.preparing_gap is None and not window.gap_feedback.isVisible()
    assert window.timeline.isEnabled() and window.preview_range_frames.isEnabled()
    assert window.prepare_full_preview.isEnabled()
    assert 'Test render failure' in window.preview_status.text()
