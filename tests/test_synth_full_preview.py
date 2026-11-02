"""Every selected-resolution pixel survives RAM eviction, audio edits and seeks."""
import copy
from pathlib import Path
import pytest
from synth_comparison_preview import ComparisonFrames
from synth_preview import PreviewScheduler
from synth_sequence import render_sequence_frame
from synth_visual_sound import instrument_sound
from test_synth_composer_ui import window,wait_until
from test_synth_preview_scope import short_document,settle,prepared


def test_lossless_disk_frames_are_bounded_isolated_retained_and_cleaned():
    cache=ComparisonFrames(budget=12);cache.switch('a');cache.enable_full((2,1),9)
    folder=Path(cache.disk_banks['a'].folder.name)
    for i in range(9): cache.put(i,((2,1),bytes([i])*6))
    assert cache.complete(9) and cache.bytes<=12 and len(cache.items)<=2
    for i in range(9): assert cache.get(i)==((2,1),bytes([i])*6)
    assert cache.ranges()==[(0,9)]
    cache.switch('b');assert not cache.contains(0)
    cache.enable_full((2,1),9);cache.put(0,((2,1),b'bbbbbb'))
    cache.switch('a');assert cache.get(0)[1]==bytes(6)
    cache.retain(lambda frame:frame<4)
    assert cache.ranges()==[(0,4)] and not cache.contains(8)
    cache.clear();assert not folder.exists() and not cache.disk_banks


def test_disk_failure_never_marks_an_unwritten_frame_ready(monkeypatch):
    cache=ComparisonFrames(budget=1);cache.switch('a');cache.enable_full((2,1),2)
    def fail(*_): raise OSError('Disk full')
    monkeypatch.setattr(Path,'write_bytes',fail)
    with pytest.raises(OSError,match='Disk full'): cache.put(0,((2,1),b'123456'))
    assert not cache.contains(0)
    cache.clear()


def test_missing_or_truncated_frame_is_rendered_again():
    cache=ComparisonFrames(budget=1);cache.switch('a');cache.enable_full((2,1),1)
    cache.put(0,((2,1),b'123456'));cache.disk_banks['a'].path(0).write_bytes(b'bad')
    assert cache.get(0) is None and not cache.complete(1)
    assert PreviewScheduler().batch(range(10**9),cache)==(0,1,2,3)
    cache.clear()


def setup_full(window):
    window.auto_prepare.setChecked(False)
    project=short_document()
    window.set_composition(project);settle(window)
    window.preview_frames.budget=window.preview_size()[0]*window.preview_size()[1]*3*2
    return copy.deepcopy(window.composition)


def test_entire_preview_at_selected_size_survives_audio_apply_and_undo(window,monkeypatch):
    monkeypatch.setattr(window,'preview_size',lambda:(96,72) if window.quality.currentIndex()==0 else (192,144))
    before=setup_full(window);window.quality.setCurrentIndex(2);settle(window)
    window.preview_frames.budget=192*144*3*2
    window.prepare_full_playback();prepared(window)
    total=window.timeline.maximum()+1;cache=window.preview_frames
    assert cache.complete(total) and cache.bytes<=cache.budget and not window.play.isChecked()
    assert window.composition==before
    for frame in range(total):
        assert cache.get(frame)==((192,144),render_sequence_frame(window.sequence,frame/window.preview_fps(),(192,144)).tobytes())
    store=cache.disk_banks[cache.namespace];folder=Path(store.folder.name)
    window.apply_visual_sound(instrument_sound())
    assert cache.disk_banks[cache.namespace] is store and cache.complete(total)
    window.undo_composition();assert cache.complete(total)
    # A prepared seek must not start a foreground render, even outside the RAM LRU.
    window.timeline.setValue(total-1);window.timeline.setValue(0)
    assert not window.render_running and window.viewer.packet==cache.get(0)
    window.quality.setCurrentIndex(0)
    assert not folder.exists() and not cache.disk_banks


def test_full_preview_cancel_resume_and_sound_edit_during_preparation(window,monkeypatch):
    monkeypatch.setattr(window,'preview_size',lambda:(64,48));setup_full(window)
    window.prepare_full_playback()
    wait_until(lambda:len(window.preview_frames.available())>=5)
    window.prepare_full_playback() # cancel
    retained=set(window.preview_frames.available())
    assert not window.preparation_explicit
    window.prepare_full_playback()
    generation=window.settings_generation
    window.apply_visual_sound(instrument_sound())
    assert window.preparation_explicit and window.preparation_full
    assert window.settings_generation==generation
    prepared(window)
    assert retained<=set(window.preview_frames.available())
    assert window.preview_frames.complete(window.timeline.maximum()+1)


def test_full_preview_disk_failure_stops_preparation_visibly(window,monkeypatch):
    monkeypatch.setattr(window,'preview_size',lambda:(64,48));setup_full(window)
    window.prepare_full_playback()
    store=window.preview_frames.disk_banks[window.preview_frames.namespace]
    def fail(*_): raise OSError('Disk full')
    monkeypatch.setattr(store,'put',fail)
    prepared(window)
    assert 'storage stopped' in window.status.text() and not window.preview_frames.disk_banks


def test_auto_prepare_does_not_downgrade_complete_disk_preview(window,monkeypatch):
    monkeypatch.setattr(window,'preview_size',lambda:(64,48));setup_full(window)
    window.prepare_full_playback();prepared(window)
    before=window.preview_status.text()
    window.auto_prepare.setChecked(True);window._automatic_preparation()
    assert window.preview_frames.complete(window.timeline.maximum()+1)
    assert window.preview_status.text()==before and not window.preparation_limited
