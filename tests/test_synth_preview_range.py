import copy
import pytest

from PySide6.QtCore import Qt
from nebula.render.synth_preview import PreviewScope, preview_window, longest_cached_scope
from nebula.ui.synth_preview_range import frames_in
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.audio.synth_visual_sound import instrument_sound
from test_synth_composer_ui import window, wait_until
from test_synth_preview_scope import short_document, settle, prepared


def test_window_keeps_absolute_times_and_clamps_without_duplicate_frames():
    scope = PreviewScope(((10, 15), (30, 40)))
    assert preview_window(scope, 13, 6).intervals == ((13, 15), (30, 34))
    assert preview_window(scope, 39, 6).intervals == ((34, 40),)
    assert preview_window(scope, 0, 200).intervals == scope.intervals
    assert preview_window(PreviewScope(()), 0, 150).count == 0


def test_longest_ready_span_never_crosses_holes_and_keeps_equal_runs_stable():
    coverage = PreviewScope(((0, 6), (7, 13), (17, 22)))
    whole = PreviewScope(((0, 30),))
    assert longest_cached_scope(coverage, whole).intervals == ((0, 6),)
    assert longest_cached_scope(coverage, whole, current=9).intervals == ((7, 13),)
    previous = PreviewScope(((7, 13),))
    assert longest_cached_scope(coverage, whole, previous, current=1) == previous
    # Selected clip boundaries join only if adjacent; other clips remain excluded.
    selected = PreviewScope(((2, 4), (4, 6), (8, 11)))
    assert longest_cached_scope(coverage, selected).intervals == ((2, 6),)
    assert longest_cached_scope(PreviewScope(()), whole).count == 0
    assert longest_cached_scope(coverage, PreviewScope(())).count == 0
    assert longest_cached_scope(PreviewScope(((0, 1000000000),)), whole) == whole


def setup(window, monkeypatch):
    window.auto_prepare.setChecked(False)
    monkeypatch.setattr(window, 'preview_size', lambda: (64, 48))
    window.set_composition(short_document()); settle(window)
    window.preview_frames.budget = 64 * 48 * 3 * 2
    window.preview_range_frames.setValue(7)
    window.timeline.setValue(4); settle(window)
    return copy.deepcopy(window.composition)


@pytest.mark.parametrize('playing', [False, True])
def test_enabling_cached_loop_never_restarts_a_stale_preparation_window(window, monkeypatch, playing):
    before = setup(window, monkeypatch)
    window.preview_frames.clear()
    window.preview_frames.enable_full(window.preview_size(), window.timeline.maximum()+1)
    packet = (window.preview_size(), bytes(64*48*3))
    for frame in (*range(6), 9, 10): window.preview_frames.put(frame, packet)
    window.timeline.setValue(0); settle(window)
    # A past automatic request is incomplete and far from the current ready loop.
    window.remember_preview_range(PreviewScope(((8, 15),)))
    window.auto_prepare.setChecked(True)
    window.warm_debounce.stop()
    window.play.setChecked(playing)
    started = []; monkeypatch.setattr(window.jobs, 'start', started.append)
    window.loop_preview_range.setChecked(True)
    assert window.active_preview_scope().intervals == ((0, 6),)
    assert not window.warm_debounce.isActive()
    window._automatic_preparation()  # A queued callback cannot resurrect the old request either.
    assert not started
    assert window.prepared_range_scope.intervals == ((0, 6),)
    window.play.setChecked(True)
    window.schedule_auto_preparation()
    assert not window.warm_debounce.isActive()
    assert not started and window.composition == before
    window.play.setChecked(False)


def test_auto_prepare_remembers_current_request_after_scrubbing(window, monkeypatch):
    setup(window, monkeypatch)
    window.auto_prepare.setChecked(True)
    window._automatic_preparation(); prepared(window)
    previous = window.prepared_range_scope
    window.timeline.setValue(14); settle(window)
    window._automatic_preparation(); prepared(window)
    assert window.prepared_range_scope != previous
    assert set(window.prepared_range_sources) == set(window.preparation_target)
    assert window.prepared_range_scope.contains(14)


def test_preview_events_capture_loop_and_preparation_decisions(window, monkeypatch, tmp_path):
    import json
    from nebula.core.studio_diagnostics import configure, close
    setup(window, monkeypatch)
    path = configure(tmp_path)
    try:
        window.prepare_playback(); prepared(window)
        window.loop_preview_range.setChecked(True)
        events = [json.loads(line) for line in path.read_text().splitlines()]
        assert any(e['event'] == 'preview.prepare_requested' and e['reason'] == 'range' for e in events)
        changed = next(e for e in events if e['event'] == 'preview.loop_changed')
        assert changed['enabled'] and [4, 11] in changed['cached']
        assert changed['ready_loop'] == [[4, 11]]
    finally: close()


def test_chosen_range_survives_eviction_and_loops_audio_at_absolute_time(window, monkeypatch):
    before = setup(window, monkeypatch)
    generation = window.settings_generation
    window.prepare_playback(); prepared(window)
    assert window.prepared_range_scope.intervals == ((4, 11),)
    assert window.loop_preview_range.isEnabled()
    cache = window.preview_frames
    for frame in range(4, 11):
        assert cache.get(frame) == ((64,48), render_sequence_frame(window.sequence, frame/25, (64,48)).tobytes())
    assert cache.bytes <= cache.budget
    clock = [100.]
    monkeypatch.setattr('nebula.ui.synth_studio.time.monotonic', lambda: clock[0])
    audio = []
    monkeypatch.setattr(window, 'sync_soundtrack', lambda **kw: audio.append(kw))
    window.loop_preview_range.setChecked(True)
    window.play.setChecked(True)
    for i in range(1, 17):
        clock[0] = 100 + i/25
        window.advance()
        assert window.timeline.value() == 4 + i % 7
        assert not window.render_running and not window.render_queued
    assert audio[-1]['seconds'] == 6/25 or abs(audio[-1]['seconds'] - 6/25) < 1e-8
    assert sum(bool(call.get('force')) for call in audio) >= 3  # First tick + loop boundaries.
    window.play.setChecked(False)
    assert window.composition == before and window.settings_generation == generation
    assert 'Prepared range loop' in window.timeline_context.text()
    window.loop_preview_range.setChecked(False)
    assert window.active_preview_scope().count == window.timeline.maximum()+1


def test_edits_and_undo_keep_loop_choice_but_explicit_seek_exits_it(window, monkeypatch):
    setup(window, monkeypatch)
    window.prepare_playback(); prepared(window)
    window.loop_preview_range.setChecked(True)
    window.apply_visual_sound(instrument_sound())
    assert window.loop_preview_range.isChecked()
    window.undo_composition()
    assert window.loop_preview_range.isChecked()
    window.quality.setCurrentIndex(1)  # Size monkeypatch is constant: use a real visual edit below.
    requested = window.prepared_range_scope
    window.composer.macro_controls['width'].spin.setValue(1.3)
    assert window.loop_preview_range.isChecked()
    assert window.loop_preview_range.isEnabled()
    assert window.prepared_range_scope == requested
    assert window.active_preview_scope().count == 0  # No stale pixels.
    settle(window)
    window.prepare_playback(); prepared(window)
    assert window.active_preview_scope().count == 7
    window.undo_composition()
    assert window.loop_preview_range.isChecked() and window.prepared_range_scope == requested
    window.timeline.setValue(15)  # Explicit seek outside the range exits loop mode.
    assert not window.loop_preview_range.isChecked()
    assert window.timeline.value() == 15


def test_selected_clips_and_preparation_cancel_resume(window, monkeypatch):
    setup(window, monkeypatch)
    window.section_timeline.select_at(0)
    window.section_timeline.select_at(2, Qt.KeyboardModifier.MetaModifier)
    window.preview_scope.setCurrentIndex(1)
    window.preview_range_frames.setValue(4)
    window.timeline.setValue(0)
    window.prepare_playback(); prepared(window)
    assert window.prepared_range_scope.intervals == ((0, 3), (6, 7))
    window.loop_preview_range.setChecked(True)
    assert list(frames_in(window.active_preview_scope())) == [0,1,2]
    window.preview_scope.setCurrentIndex(0)
    assert not window.loop_preview_range.isChecked() and window.prepared_range_scope is None
    window.preview_range_frames.setValue(12)
    window.timeline.setValue(0)
    window.prepare_playback()
    wait_until(lambda: len(window.preview_frames.available()) >= 6)
    window.prepare_playback()  # Cancel; keep completed frames.
    retained = set(window.preview_frames.available())
    assert not window.preparation_explicit and window.loop_preview_range.isEnabled()
    window.prepare_playback(); prepared(window)
    assert retained <= set(window.preview_frames.available())
    assert window.loop_preview_range.isEnabled()


def test_range_prepares_perform_source_times_and_does_not_narrow_full_preview(window, monkeypatch):
    setup(window, monkeypatch)
    monkeypatch.setattr(window, 'performance_source_time', lambda seconds: seconds * .5)
    window.prepare_playback(); prepared(window)
    assert window.prepared_range_sources == (2, 3, 4, 5)
    assert window.loop_preview_range.isEnabled()
    window.loop_preview_range.setChecked(True)
    window.prepare_full_playback(); prepared(window)
    assert window.loop_preview_range.isChecked()
    assert window.preview_frames.complete(window.timeline.maximum()+1)
    assert window.active_preview_scope().count == window.timeline.maximum()+1


def test_full_preparation_then_enable_loop_uses_every_frame_even_after_cancel(window, monkeypatch):
    before = setup(window, monkeypatch)
    window.prepare_full_playback(); prepared(window)
    window.cancel_preparation()  # Worker state is separate from the chosen target.
    window.loop_preview_range.setChecked(True)
    total = window.timeline.maximum() + 1
    assert window.active_preview_scope().intervals == ((0, total),)
    assert window.preview_range_summary.text().startswith('Entire timeline:')
    clock = [100.]
    monkeypatch.setattr('nebula.ui.synth_studio.time.monotonic', lambda: clock[0])
    window.play.setChecked(True)
    for i in range(1, total * 2 + 1):
        clock[0] = 100 + i/25
        window.advance()
        assert window.timeline.value() == (4 + i) % total
    window.play.setChecked(False)
    # A smaller preparation request never narrows an already prepared loop.
    window.prepare_playback(); prepared(window)
    assert window.active_preview_scope().count == total
    assert window.preview_range_summary.text().startswith('Range:')
    assert window.composition == before


def test_full_preparation_keeps_growing_when_loop_enabled_mid_job(window, monkeypatch):
    setup(window, monkeypatch)
    window.preview_frames.clear(); window.cached_ranges.set_ranges([])
    started = []; monkeypatch.setattr(window.jobs, 'start', started.append)
    window.prepare_full_playback()
    job = started[-1]
    window.loop_preview_range.setChecked(True)
    window.play.setChecked(True)
    assert window.prepare_job is job and not job.cancel.event.is_set()
    packet = ((64, 48), bytes(64*48*3))
    for frame in range(12):
        window.prepared_frame(job, (window.settings_generation, frame, packet))
    assert window.active_preview_scope().count == 12 > window.preview_range_frames.value()
    window.prepare_full_playback()  # Cancel preserves all 12 ready frames and loop.
    assert window.play.isChecked() and window.loop_preview_range.isChecked()
    assert window.active_preview_scope().count == 12
    window.preparation_finished(job)
    window.play.setChecked(False)


def test_visual_edit_rebuilds_loop_while_playing_and_quality_never_uses_old_pixels(window, monkeypatch):
    setup(window, monkeypatch)
    window.prepare_playback(); prepared(window)
    window.loop_preview_range.setChecked(True)
    window.auto_prepare.setChecked(True)
    window.play.setChecked(True)
    window.composer.macro_controls['width'].spin.setValue(1.3)
    assert window.loop_preview_range.isChecked() and window.play.isChecked()
    assert window.active_preview_scope().count == 0
    wait_until(lambda: window.active_preview_scope().count == 7)
    assert window.play.isChecked()
    window.play.setChecked(False)
    monkeypatch.setattr(window, 'preview_size', lambda: (80, 60))
    window.quality.setCurrentIndex(1)
    assert window.loop_preview_range.isChecked() and window.active_preview_scope().count == 0
    wait_until(lambda: window.active_preview_scope().count == 7)
    for source in window.prepared_range_sources:
        assert window.preview_frames.get(source)[0] == (80, 60)


def test_range_count_and_duration_edits_keep_loop_and_new_document_resets_it(window, monkeypatch):
    before = setup(window, monkeypatch)
    window.prepare_full_playback(); prepared(window)
    window.loop_preview_range.setChecked(True)
    window.timeline.setValue(window.timeline.maximum())
    window.composer.duration.setValue(.48)
    assert window.loop_preview_range.isChecked()
    assert window.prepared_range_scope.intervals == ((0, window.timeline.maximum()+1),)
    window.preview_range_frames.setValue(3)
    assert window.loop_preview_range.isChecked() and window.prepared_range_scope.count == 3
    window.set_composition(before, guard=False)
    assert not window.loop_preview_range.isChecked()
    assert window.prepared_range_scope is None


def test_count_is_a_workspace_preference_and_loop_is_never_saved(window, monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings
    from nebula.ui.synth_studio import SynthStudio
    before = setup(window, monkeypatch)
    settings = QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat)
    window.workspace_settings = settings
    window.preview_range_frames.setValue(300)
    window.save_workspace()
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda self: None)
    restored = SynthStudio(composition=before, settings=settings)
    try:
        assert restored.preview_range_frames.value() == 300
        assert not restored.loop_preview_range.isChecked()
        assert restored.composition == before
    finally:
        restored.close(); restored.deleteLater()


def test_armed_loop_waits_then_grows_without_cancelling_worker_or_seeking_audio(window, monkeypatch):
    before = setup(window, monkeypatch)
    window.preview_frames.clear()
    window.cached_ranges.set_ranges([])
    started = []
    monkeypatch.setattr(window.jobs, 'start', started.append)
    window.loop_preview_range.setChecked(True)
    assert window.loop_preview_range.isEnabled()
    assert window.active_preview_scope().count == 0
    window.prepare_playback()
    job = started[-1]
    clock = [100.]
    monkeypatch.setattr('nebula.ui.synth_studio.time.monotonic', lambda: clock[0])
    audio = []
    monkeypatch.setattr(window.soundtrack_playback, 'sync', lambda seconds, playing, **kw: audio.append((seconds, playing, kw)))
    monkeypatch.setattr(window, 'sync_visual_sound', lambda *args: None)
    window.play.setChecked(True)
    window.advance()
    assert not audio[-1][1] and window.timeline.value() == 4
    assert window.prepare_job is job and not job.cancel.event.is_set()
    assert window.preview_status.mode == 'loading'
    assert window.preview_status.text() == 'Preparing playback range · 0/7 frames'
    assert 'Waiting for prepared frames' in window.preview_status.detail
    packet = ((64, 48), bytes(64*48*3))
    for frame in (4, 5):
        window.prepared_frame(job, (window.settings_generation, frame, packet))
    window.advance()
    assert audio[-1][1]
    for i in range(1, 7):
        clock[0] = 100 + i/25
        window.advance()
        assert window.timeline.value() == 4 + i % 2
        assert not window.render_running and not window.render_queued
    # Several wraps must not change position when another packet arrives.
    clock[0] = 100.26
    window.prepared_frame(job, (window.settings_generation, 6, packet))
    window.advance()
    assert window.timeline.value() == 4
    assert not audio[-1][2]['force']
    assert abs(audio[-1][0] - 4.5/25) < 1e-7
    for seconds, expected in ((100.28, 5), (100.32, 6), (100.36, 4)):
        clock[0] = seconds
        window.advance()
        assert window.timeline.value() == expected
    assert audio[-1][2]['force']  # Real wrap, unlike cache growth.
    assert window.composition == before
    window.cancel_preparation()
    assert window.play.isChecked() and window.loop_preview_range.isChecked()
    assert window.active_preview_scope().count == 3
    window.preparation_finished(job)
    window.play.setChecked(False)


def test_playback_does_not_interrupt_real_preparation_and_cancel_keeps_loop(window, monkeypatch):
    setup(window, monkeypatch)
    window.preview_range_frames.setValue(12)
    window.prepare_playback()
    job = window.prepare_job
    window.loop_preview_range.setChecked(True)
    window.play.setChecked(True)
    assert window.prepare_job is job and not job.cancel.event.is_set()
    prepared(window)
    assert window.play.isChecked() and window.loop_preview_range.isChecked()
    assert window.active_preview_scope().count == 12
    assert all(window.preview_frames.contains(frame) for frame in window.prepared_range_sources)
    window.cancel_preparation()
    assert window.play.isChecked() and window.active_preview_scope().count == 12
    window.play.setChecked(False)


def test_partial_loop_uses_longest_continuous_output_span_with_perform_mapping(window, monkeypatch):
    setup(window, monkeypatch)
    from nebula.documents.synth_performance import defaults
    project = copy.deepcopy(window.composition)
    project['visual_performance'] = defaults()
    project['visual_performance']['values']['pace'] = 50
    window.set_composition(project); settle(window)
    window.preview_frames.clear()
    window.preview_frames.enable_full(window.preview_size(), window.timeline.maximum()+1)
    window.cached_ranges.set_ranges([])
    packet = ((64, 48), bytes(64*48*3))
    for source in (2, 4, 5): window.preview_frames.put(source, packet)
    window.loop_preview_range.setChecked(True)
    assert list(frames_in(window.active_preview_scope())) == [8, 9, 10, 11]
    assert '4/4 frames' in window.cache_status.text()
    clock = [100.]
    monkeypatch.setattr('nebula.ui.synth_studio.time.monotonic', lambda: clock[0])
    audio = []
    monkeypatch.setattr(window, 'sync_soundtrack', lambda **kw: audio.append(kw))
    window.play.setChecked(True)
    for i, expected in enumerate((9, 10, 11, 8, 9), 1):
        clock[0] = 100 + i/25
        window.advance()
        assert window.timeline.value() == expected
        assert abs(audio[-1]['seconds'] - expected/25) < 1e-7
        assert not window.render_running and not window.render_queued
    window.play.setChecked(False)


def test_auto_preparation_finishes_fixed_window_while_loop_plays(window, monkeypatch):
    setup(window, monkeypatch)
    window.preview_frames.clear()
    window.cached_ranges.set_ranges([])
    window.loop_preview_range.setChecked(True)
    window.auto_prepare.setChecked(True)
    window.play.setChecked(True)
    window._automatic_preparation()
    requested = window.prepared_range_scope
    wait_until(lambda: window.active_preview_scope().count == 7)
    assert window.prepared_range_scope == requested
    assert window.play.isChecked() and window.loop_preview_range.isChecked()
    assert window.preview_frames.bytes + window.preview_frames.reserved <= window.preview_frames.budget
    window.play.setChecked(False)


def test_loop_keeps_memory_limited_auto_window_until_explicit_prepare_request(window, monkeypatch):
    setup(window, monkeypatch)
    window.auto_prepare.setChecked(True)
    window._automatic_preparation()
    wait_until(lambda: window.prepare_job is None and window.prepared_range_scope is not None)
    assert window.prepared_range_scope.count == 2  # Only two RGB frames fit in RAM.
    window.loop_preview_range.setChecked(True)
    assert window.prepared_range_scope.count == 2
    window.prepare_playback()
    assert window.prepared_range_scope.count == window.preview_range_frames.value() == 7
    window.play.setChecked(True)
    # Previously warmed neighbors join too, so the ready loop can exceed seven.
    wait_until(lambda: window.active_preview_scope().count >= 7)
    assert all(window.active_preview_scope().contains(frame) for frame in window.prepared_range_sources)
    assert window.play.isChecked()
    assert window.preview_frames.bytes + window.preview_frames.reserved <= window.preview_frames.budget
    window.play.setChecked(False)
