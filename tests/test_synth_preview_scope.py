"""Absolute preview intervals and bounded, non-playing preparation."""
import copy
import time
from PIL import Image
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from synth_composition import reference_composition, section_placements
from synth_preview import PreviewFrames, PreviewScope, PreviewScheduler, resolve_scope
from synth_sequence import render_sequence_frame
from synth_studio import PreparePreviewJob
from test_synth_composer_ui import window, wait_until


def short_document():
    project = reference_composition(refined=True)
    for section in project['sections']: section['duration'] = .12
    return project


def settle(window):
    wait_until(lambda: not window.render_running and not window.render_queued)


def prepared(window):
    wait_until(lambda: not window.preparation_explicit and window.prepare_job is None)


def test_scope_uses_every_selected_occurrence_and_steps_across_gaps():
    project = short_document()
    ids = [section['id'] for section in project['sections']]
    project['timeline_loops'] = [{'sections': ids[:3], 'loops': 2}]
    scope = resolve_scope(project, {ids[0], ids[2]}, 26, True)
    expected = tuple((round(start*25), round(end*25)) for index, start, end, _ in section_placements(project) if index in (0, 2))
    assert scope.intervals == expected and scope.occurrences == 4 and scope.count == 12
    assert scope.step(2, 1) == 6 and scope.step(8, 1) == 9
    assert scope.step(0, -10) == 0 and scope.frame_at(11) == 17


def test_scheduler_limits_long_scope_without_materializing_it_and_preserves_absolute_times():
    planner = PreviewScheduler(); scope = PreviewScope(((1000, 1000000000),))
    target, limited = planner.plan(scope, 1050, 20, (2, 1), 30, explicit=True)
    assert limited and len(target) == 5 and target[0] == 1050
    assert 1050 in target and all(scope.contains(frame) for frame in target)
    cache = PreviewFrames(30)
    assert len(planner.batch(target, cache)) == 4
    cache.reserve(24)
    assert cache.bytes + cache.reserved <= cache.budget
    cache.release(24)
    for frame in target: cache.put(frame, ((2, 1), b'pixels'))
    assert planner.batch(target, cache) == ()


def test_cached_and_pending_packets_share_memory_budget():
    cache = PreviewFrames(18)
    for frame in range(3): cache.put(frame, ((2, 1), bytes([frame])*6))
    cache.reserve(12, (1,))
    assert cache.bytes + cache.reserved == 18 and list(cache.items) == [1]
    cache.release(12)
    cache.put(3, ((2, 1), b'a'*6)); cache.put(4, ((2, 1), b'b'*6))
    assert cache.bytes == 18 and cache.reserved == 0
    assert cache.ranges() == [(1, 2), (3, 5)]


def test_selected_preparation_has_renderer_parity_and_never_starts_play(window):
    window.auto_prepare.setChecked(False)
    project = short_document(); ids = [s['id'] for s in project['sections']]
    project['timeline_loops'] = [{'sections': ids[:3], 'loops': 2}]
    window.set_composition(project); settle(window)
    window.section_timeline.select_at(0)
    window.section_timeline.select_at(2, Qt.KeyboardModifier.MetaModifier)
    window.preview_scope.setCurrentIndex(1)
    before = copy.deepcopy(window.composition)
    generation = window.settings_generation
    window.prepare_playback(); prepared(window)
    scope = window.active_preview_scope()
    for start, end in scope.intervals:
        for frame in range(start, end):
            size, raw = window.preview_frames.get(frame)
            assert raw == render_sequence_frame(window.sequence, frame/25, size).tobytes()
    assert window.settings_generation == generation and window.composition == before and not window.play.isChecked()
    assert '4 occurrences' in window.scope_summary.text()
    window.timeline.setValue(2); window.step_frame(1)
    assert window.timeline.value() == 6
    window.timeline.setValue(10)
    window.preview_scope.setCurrentIndex(0)
    assert window.timeline.value() == 10 and not window.play.isChecked()


def test_scope_clock_skips_gaps_and_retains_repeated_seek(window, monkeypatch):
    window.auto_prepare.setChecked(False)
    project = short_document(); ids = [s['id'] for s in project['sections']]
    project['timeline_loops'] = [{'sections': ids[:3], 'loops': 2}]
    window.set_composition(project); settle(window)
    window.section_timeline.select_at(0)
    window.section_timeline.select_at(2, Qt.KeyboardModifier.MetaModifier)
    window.preview_scope.setCurrentIndex(1)
    window.timeline.setValue(10)
    clock = [100.]; monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    window.play.setChecked(True); clock[0] += .08; window.advance()
    assert window.timeline.value() == 15  # Original absolute frame in the repeated third section.
    window.play.setChecked(False)
    window.section_timeline.select_at(0)
    assert window.timeline.value() == 0
    start = section_placements(window.composition)[3][1]
    window.section_timeline.seekRequested.emit(start)
    assert window.timeline.value() == 9


def test_explicit_preparation_waits_for_foreground_and_oversize_warms_useful_window(window):
    window.auto_prepare.setChecked(False)
    window.set_composition(short_document())
    frame_bytes = window.preview_size()[0]*window.preview_size()[1]*3
    window.preview_frames.budget = frame_bytes*5
    window.prepare_playback()  # Current-frame debounce/render is still pending.
    prepared(window)
    assert len(window.preparation_target) == 5 and all(frame in window.preview_frames.items for frame in window.preparation_target)
    assert window.preview_frames.bytes + window.preview_frames.reserved <= window.preview_frames.budget
    assert 'partially prepared' in window.preview_status.text() and not window.play.isChecked()
    old = dict(window.preview_frames.items)
    QTest.qWait(500)
    assert dict(window.preview_frames.items) == old and window.prepare_job is None
    window.preview_frames.clear(); window.preview_frames.budget = frame_bytes
    window.prepare_playback(); prepared(window)
    assert len(window.preview_frames.items) == 1 and window.preview_frames.reserved == 0


def test_automatic_warming_settles_without_idle_render_churn(window, monkeypatch):
    window.auto_prepare.setChecked(False)
    window.set_composition(short_document()); settle(window)
    starts = []
    original = window.jobs.start
    monkeypatch.setattr(window.jobs, 'start', lambda job: starts.append(job) or original(job))
    window.auto_prepare.setChecked(True)
    wait_until(lambda: bool(window.preparation_target) and all(frame in window.preview_frames.items for frame in window.preparation_target) and window.warming_job is None)
    count = len(starts); QTest.qWait(550)
    assert len(starts) == count and count > 0 and not window.play.isChecked()
    assert all(len(job.frames) <= 4 for job in starts if isinstance(job, PreparePreviewJob))
    assert window.preview_frames.reserved == 0


def test_cancelled_delivery_and_export_cannot_repopulate_cache(window, monkeypatch, tmp_path):
    window.auto_prepare.setChecked(False)
    window.set_composition(short_document()); settle(window)
    window.preview_frames.clear()
    queued = []; monkeypatch.setattr(window.jobs, 'start', queued.append)
    window.prepare_playback(); job = window.prepare_job
    assert job and len(job.frames) <= 4
    window.cancel_preparation()
    before = dict(window.preview_frames.items)
    window.preparation_finished(job, result=(job.generation, [(0, ((1, 1), b'old'))]))
    assert dict(window.preview_frames.items) == before and not window.play.isChecked()
    window.prepare_playback(); job = window.prepare_job
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path/'out.mp4'), ''))
    window.export_dialog()
    assert window.prepare_job is None and not window.warm_debounce.isActive()
    window.preparation_finished(job, result=(job.generation, [(0, ((1, 1), b'old'))]))
    assert dict(window.preview_frames.items) == before and window.preview_frames.reserved == 0
    window._finish_export(window.export_job)


@pytest.mark.parametrize('capacity', [1, 2, 3, 4])
def test_small_budget_seek_waits_for_cancelled_warm_delivery(window, monkeypatch, capacity):
    from synth_studio import RenderJob
    window.auto_prepare.setChecked(False)
    window.set_composition(short_document()); settle(window)
    size = window.preview_size(); frame_bytes = size[0]*size[1]*3
    window.preview_frames.clear(); window.preview_frames.budget = frame_bytes*capacity
    queued = []; monkeypatch.setattr(window.jobs, 'start', queued.append)
    window.prepare_playback(); warm = window.prepare_job
    assert warm and window.preview_frames.reserved == frame_bytes*capacity
    window.timeline.setValue(7)
    assert warm.cancel.event.is_set() and window.render_queued and not window.render_running
    assert queued == [warm] and window.preview_frames.bytes + window.preview_frames.reserved <= window.preview_frames.budget
    window.preparation_finished(warm, result=(warm.generation, [(0, (size, bytes(frame_bytes)))]))
    QApplication.processEvents()
    foreground = queued[-1]
    assert isinstance(foreground, RenderJob) and window.preview_frames.reserved == frame_bytes
    assert not window.preview_frames.items
    result = (foreground.settings_generation, foreground.request_serial, foreground.time_seconds, size, bytes(frame_bytes), .01)
    window._receive_foreground_frame(foreground, result); window._release_job(foreground)
    assert window.preview_frames.reserved == 0 and window.preview_frames.bytes == frame_bytes


from test_synth_video import clip


@pytest.mark.parametrize('bypass', [False, True])
def test_selected_video_preview_keeps_absolute_source_and_effect_clocks(window, clip, tmp_path, monkeypatch, bypass):
    from pathlib import Path
    from synth_video import video_composition, VideoFrameProvider, apply_treatment
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    window.auto_prepare.setChecked(False)
    project = apply_treatment(video_composition(clip), 1)
    base = project['sections'][0]
    project['sections'] = [dict(copy.deepcopy(base), id=f'video-{i}', duration=1/6,
                                effects_rate=.5 if i == 1 else 1., video_rate=.5 if i == 2 else 1.) for i in range(3)]
    ids = [s['id'] for s in project['sections']]
    project['timeline_loops'] = [{'sections': ids, 'loops': 2}]
    window.set_composition(project); window.source_preview.setChecked(bypass); settle(window)
    window.section_timeline.select_at(0)
    window.section_timeline.select_at(2, Qt.KeyboardModifier.MetaModifier)
    window.preview_scope.setCurrentIndex(1)
    window.prepare_playback(); prepared(window)
    scope = window.active_preview_scope()
    assert scope.intervals == ((0, 2), (4, 6), (6, 8), (10, 12))
    with VideoFrameProvider(preview=True, directory=tmp_path/'fresh-proxy') as provider:
        for start, end in scope.intervals:
            for frame in range(start, end):
                size, raw = window.preview_frames.get(frame)
                fresh = render_sequence_frame(window.sequence, frame/12, size, provider, bypass)
                assert raw == fresh.tobytes()
        size, raw = window.preview_frames.get(10)
        shortened = render_sequence_frame(window.sequence, scope.position(10)/12, size, provider, bypass)
        assert raw != shortened.tobytes()  # Compressing the selected timeline would change the source clock.
