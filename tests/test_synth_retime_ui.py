"""Real studio gestures select a resize mode and commit one undoable retime."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from synth_composition import compile_composition, load_composition, save_composition
from test_synth_video import clip
from test_synth_video_ui import window


def test_video_resize_modes_drag_undo_redo_and_reload(window, tmp_path):
    original = copy.deepcopy(window.composition)
    timeline = window.section_timeline
    mode = window.section_resize_mode
    assert not mode.isHidden()
    assert mode.currentData() == 'effects'
    original_duration = original['sections'][0]['duration']
    old_undo = len(window.undo_compositions)
    point = QPoint(timeline.width() - 2, 40)
    QTest.mousePress(timeline, Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(timeline, point - QPoint(round(timeline.pixels_per_second() * .5), 0))
    assert window.composition == original
    assert len(window.undo_compositions) == old_undo
    timeline._finish_resize(True)
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=point)
    updated = window.composition
    section = updated['sections'][0]
    assert section['duration'] == pytest.approx(original_duration - .5)
    assert section['effects_rate'] == pytest.approx(original_duration / section['duration'])
    assert 'video_rate' not in section
    assert len(window.undo_compositions) == old_undo + 1
    window.undo_composition()
    assert window.composition == original
    window.redo_composition()
    assert window.composition == updated
    window.undo_composition()
    mode.setCurrentIndex(mode.findData('video'))
    assert window.composer.resize_mode == 'video'
    window.composer.section_duration.setValue(2.)
    section = window.composition['sections'][0]
    assert section['duration'] == 2.
    assert section['video_rate'] == section['effects_rate'] == .5
    assert window.sequence['duration'] == 2.
    path = tmp_path / 'resized.json'
    save_composition(path, window.composition)
    expected = copy.deepcopy(window.sequence)
    window.set_composition(load_composition(path))
    assert window.sequence == expected
    assert window.composer.resize_mode == 'video'
    window.load_starter_id('approved')
    assert mode.isHidden()
    window.composer.section_duration.setValue(6.)
    assert 'video_rate' not in window.composition['sections'][0]
    assert 'effects_rate' in window.composition['sections'][0]


def test_cancel_does_not_change_composition_or_undo_stack(window):
    original = copy.deepcopy(window.composition)
    count = len(window.undo_compositions)
    timeline = window.section_timeline
    point = QPoint(timeline.width() - 2, 40)
    QTest.mousePress(timeline, Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(timeline, point - QPoint(60, 0))
    QTest.keyClick(timeline, Qt.Key.Key_Escape)
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=point - QPoint(60, 0))
    assert window.composition == original
    assert len(window.undo_compositions) == count


def test_detailed_copy_duration_preserves_stretched_clocks_and_one_frame_minimum(window):
    from synth_composition import blank_composition, stretch_section
    from synth_retime import mapped_time
    project = stretch_section(blank_composition(), 'section-1', 2.)
    window.set_composition(project)
    window.open_detailed_copy()
    detail = window.detail_windows[-1]
    try:
        before = copy.deepcopy(detail.sequence['time_map'])
        control = detail.sequence_field_controls['duration']
        control.setValue(3.)
        assert detail.sequence['duration'] == 3.
        assert detail.sequence['time_map'][-1]['end'] == 3.
        assert mapped_time(detail.sequence['time_map'], 1.) == mapped_time(before, 1.)
        control.setValue(.04)
        assert detail.sequence['duration'] == .04
        assert detail.sequence['time_map'][-1]['end'] == .04
        detail.sequence_field_controls['fps'].setValue(10)
        assert detail.sequence['duration'] == .1
        assert detail.sequence['time_map'][-1]['end'] == .1
        assert control.minimum() == .1
    finally:
        detail.close()
    window.set_composition(stretch_section(blank_composition(), 'section-1', .04))
    window.open_detailed_copy()
    detail = window.detail_windows[-1]
    try:
        assert detail.sequence_field_controls['duration'].value() == .04
    finally:
        detail.close()
