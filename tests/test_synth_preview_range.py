import copy

from PySide6.QtCore import Qt
from synth_preview import PreviewScope, preview_window
from synth_preview_range import frames_in
from synth_sequence import render_sequence_frame
from synth_visual_sound import instrument_sound
from test_synth_composer_ui import window, wait_until
from test_synth_preview_scope import short_document, settle, prepared


def test_window_keeps_absolute_times_and_clamps_without_duplicate_frames():
    scope = PreviewScope(((10, 15), (30, 40)))
    assert preview_window(scope, 13, 6).intervals == ((13, 15), (30, 34))
    assert preview_window(scope, 39, 6).intervals == ((34, 40),)
    assert preview_window(scope, 0, 200).intervals == scope.intervals
    assert preview_window(PreviewScope(()), 0, 150).count == 0


def setup(window, monkeypatch):
    window.auto_prepare.setChecked(False)
    monkeypatch.setattr(window, 'preview_size', lambda: (64, 48))
    window.set_composition(short_document()); settle(window)
    window.preview_frames.budget = 64 * 48 * 3 * 2
    window.preview_range_frames.setValue(7)
    window.timeline.setValue(4); settle(window)
    return copy.deepcopy(window.composition)


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
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
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


def test_audio_edits_keep_range_visual_edits_and_resolution_release_it(window, monkeypatch):
    setup(window, monkeypatch)
    window.prepare_playback(); prepared(window)
    window.loop_preview_range.setChecked(True)
    window.apply_visual_sound(instrument_sound())
    assert window.loop_preview_range.isChecked()
    window.undo_composition()
    assert window.loop_preview_range.isChecked()
    window.quality.setCurrentIndex(1)  # Size monkeypatch is constant: use a real visual edit below.
    window.composer.macro_controls['width'].spin.setValue(1.3)
    assert not window.loop_preview_range.isChecked()
    assert not window.loop_preview_range.isEnabled()
    settle(window)
    window.prepare_playback(); prepared(window)
    window.loop_preview_range.setChecked(True)
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
    assert list(frames_in(window.active_preview_scope())) == [0,1,2,6]
    window.preview_scope.setCurrentIndex(0)
    assert not window.loop_preview_range.isChecked() and window.prepared_range_scope is None
    window.preview_range_frames.setValue(12)
    window.timeline.setValue(0)
    window.prepare_playback()
    wait_until(lambda: len(window.preview_frames.available()) >= 6)
    window.prepare_playback()  # Cancel; keep completed frames.
    retained = set(window.preview_frames.available())
    assert not window.preparation_explicit and not window.loop_preview_range.isEnabled()
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
    assert not window.loop_preview_range.isChecked()
    assert window.preview_frames.complete(window.timeline.maximum()+1)


def test_count_is_a_workspace_preference_and_loop_is_never_saved(window, monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings
    from synth_studio import SynthStudio
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
