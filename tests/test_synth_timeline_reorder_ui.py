"""Clip reordering changes chronology while preserving stable authored clips."""
import copy

import pytest
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition, load_composition, normalize_composition, save_composition, section_ranges
from synth_effects import effect_preset
from synth_video import video_composition
from test_synth_timeline_loops import window
from test_synth_video import clip


def ids(document):
    return [section['id'] for section in document['sections']]


def selected_id(window):
    return window.composition['sections'][window.composer.index]['id']


@pytest.mark.parametrize('selection,before,expected',[
    ([3,1],0,[1,3,0,2,4,5]),
    ([0],None,[1,2,3,4,5,0]),
    ([5],0,[5,0,1,2,3,4]),
    ([0,2],5,[1,3,4,0,2,5]),
    ([4,5],1,[0,4,5,1,2,3]),
])
def test_backend_moves_selected_ids_together_in_document_order(window,selection,before,expected):
    panel = window.composer
    original = copy.deepcopy(window.composition)
    original_ids = ids(original)
    panel.select_section(2)
    actions = []
    seeks = []
    panel.changed.connect(lambda document,action:actions.append(action))
    panel.sectionSelected.connect(seeks.append)
    panel.reorder_sections((original_ids[index] for index in selection),
                           None if before is None else original_ids[before])
    assert ids(window.composition) == [original_ids[index] for index in expected]
    assert {section['id']:section for section in window.composition['sections']} == {
        section['id']:section for section in original['sections']}
    assert selected_id(window) == original_ids[2]
    assert seeks == [expected.index(2)]
    assert window.current_time == pytest.approx(section_ranges(window.composition)[panel.index][0],abs=1/window.composition['fps'])
    assert actions == ['section-reorder']
    assert len(window.undo_compositions) == 1


@pytest.mark.parametrize('selection,before',[
    ([],None),(['missing'],None),([0],'missing'),([0],0),
    ([0],1),([4,5],None),([0,1,2,3,4,5],None),
    (None,None),('section-1',None),([[0]],None),([0],[]),
])
def test_invalid_and_noop_reorders_do_not_commit_or_seek(window,selection,before):
    original = copy.deepcopy(window.composition)
    original_ids = ids(original)
    if isinstance(selection,list):
        selection = [original_ids[item] if isinstance(item,int) else item for item in selection]
    before = original_ids[before] if isinstance(before,int) else before
    actions = []
    seeks = []
    window.composer.changed.connect(lambda document,action:actions.append(action))
    window.composer.sectionSelected.connect(seeks.append)
    index = window.composer.index
    window.composer.reorder_sections(selection,before)
    assert window.composition == original
    assert window.composer.index == index
    assert actions == seeks == []
    assert window.undo_compositions == []


def test_studio_signal_reorder_undo_redo_save_reopen_preserves_ids_and_retiming(window,clip,tmp_path):
    project = video_composition(clip)
    prototype = project['sections'][0]
    project['sections'] = []
    for index in range(4):
        section = copy.deepcopy(prototype)
        section.update(id=f'cut-{index}',duration=.25,effects_rate=.5+index*.25,
                       video_rate=1.5+index*.25,variation=11+index)
        section['effects']['slice_echo'] = effect_preset('slice_echo')
        section['effects']['slice_echo']['params']['slice_echo.period'] = .2+index*.05
        project['sections'].append(section)
    project['timeline_loops'] = [{'sections':['cut-0','cut-2'],'loops':3}]
    project['footage'].update(end_mode='loop',motion_fps=6.,treatment_fps=12.)
    window.set_composition(normalize_composition(project))
    window.composer.select_section(2)
    original = copy.deepcopy(window.composition)
    original_sequence = copy.deepcopy(window.sequence)
    actions = []
    window.composer.changed.connect(lambda document,action:actions.append(action))
    window.section_timeline.reorderRequested.emit(('cut-2',),'cut-0')
    QApplication.processEvents()
    reordered = copy.deepcopy(window.composition)
    reordered_sequence = copy.deepcopy(window.sequence)
    assert ids(reordered) == ['cut-2','cut-0','cut-1','cut-3']
    assert reordered['timeline_loops'] == [{'sections':['cut-2','cut-0'],'loops':3}]
    assert reordered['footage'] == original['footage']
    assert {section['id']:section for section in reordered['sections']} == {
        section['id']:section for section in original['sections']}
    assert selected_id(window) == 'cut-2' and window.composer.index == 0
    assert window.current_time == 0.
    assert actions == ['section-reorder'] and len(window.undo_compositions) == 1
    assert reordered_sequence['duration'] == original_sequence['duration']
    assert reordered_sequence['time_map'] != original_sequence['time_map']
    window.undo_composition()
    assert window.composition == original
    assert window.sequence == original_sequence
    assert selected_id(window) == 'cut-2' and window.composer.index == 2
    window.redo_composition()
    assert window.composition == reordered
    assert window.sequence == reordered_sequence
    assert selected_id(window) == 'cut-2' and window.composer.index == 0
    path = tmp_path/'reordered.json'
    save_composition(path,window.composition)
    restored = load_composition(path)
    assert restored == reordered
    assert compile_composition(restored) == reordered_sequence
    window.set_composition(restored)
    assert ids(window.composition) == ids(reordered)
    assert window.sequence == reordered_sequence


def test_real_multi_section_gesture_preserves_selection_and_commits_once(window):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    timeline = window.section_timeline
    original = copy.deepcopy(window.composition)
    original_ids = ids(original)
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=timeline.rectangles()[0].center().toPoint())
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier,
                     timeline.rectangles()[1].center().toPoint())
    QTest.mousePress(timeline, Qt.MouseButton.LeftButton, pos=timeline.rectangles()[0].center().toPoint())
    target = QPoint(timeline.width() - 2, 40)
    QTest.mouseMove(timeline, target)
    assert window.composition == original and window.undo_compositions == []
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=target)
    assert ids(window.composition) == original_ids[2:] + original_ids[:2]
    assert len(window.undo_compositions) == 1
    assert timeline.selected_ids == set(original_ids[:2])
    assert selected_id(window) == original_ids[0]
    window.undo_composition()
    assert window.composition == original
    assert timeline.selected_ids == set(original_ids[:2])
    assert selected_id(window) == original_ids[0]
    window.redo_composition()
    assert ids(window.composition) == original_ids[2:] + original_ids[:2]
    assert timeline.selected_ids == set(original_ids[:2])
