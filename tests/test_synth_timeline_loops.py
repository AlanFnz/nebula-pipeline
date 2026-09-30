"""Timeline gestures and sequence loops preserve ordering, state and edits."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from synth_composition import (compile_composition, load_composition, normalize_composition,
                               reference_composition, save_composition, section_placements, section_ranges)
from synth_studio import SynthStudio


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    from pathlib import Path
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    window = SynthStudio(); window.resize(1440, 960); window.show(); app.processEvents()
    yield window
    window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()


def click_section(window, occurrence, modifiers=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
    timeline = window.section_timeline
    point = timeline.rectangles()[occurrence].center().toPoint()
    QTest.mouseClick(timeline, button, modifiers, point)
    return point


def context_menu(window, occurrence):
    timeline = window.section_timeline
    point = click_section(window, occurrence, button=Qt.MouseButton.RightButton)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point, timeline.mapToGlobal(point))
    QApplication.sendEvent(timeline, event)
    assert timeline.context_menu.isVisible()
    return timeline.context_menu


def test_timeline_single_right_click_loop_count_and_undo(window):
    before = copy.deepcopy(window.composition)
    menu = context_menu(window, 1)
    assert window.section_timeline.selected_indices() == [1]
    assert menu.actions()[0].text() == 'Loop'
    menu.actions()[0].trigger(); menu.close()
    assert window.composition['sections'][1]['loops'] == 2
    assert window.sequence['duration'] == 18
    menu = context_menu(window, 1)
    repeat = next(action.menu() for action in menu.actions() if action.text() == 'Repeat count')
    repeat.actions()[1].trigger(); menu.close()  # 3 total plays.
    assert window.composition['sections'][1]['loops'] == 3
    assert window.sequence['duration'] == 21
    window.undo_composition(); assert window.sequence['duration'] == 18
    window.undo_composition(); assert window.composition == before
    window.redo_composition(); assert window.sequence['duration'] == 18
    menu = context_menu(window, 1)
    next(action for action in menu.actions() if action.text() == 'Remove loop').trigger(); menu.close()
    assert window.composition == before


def test_shift_selection_repeats_sequence_in_order_and_repeated_views_are_editable(window, tmp_path):
    before = copy.deepcopy(window.composition)
    click_section(window, 0)
    click_section(window, 2, Qt.KeyboardModifier.ShiftModifier)
    assert window.section_timeline.selected_indices() == [0, 1, 2]
    menu = context_menu(window, 1)
    assert window.section_timeline.selected_indices() == [0, 1, 2]
    menu.actions()[0].trigger(); menu.close()
    placements = section_placements(window.composition)
    assert [index for index, *_ in placements] == [0, 1, 2, 0, 1, 2, 3, 4, 5]
    assert len(window.composition['sections']) == 6  # Views share original sections.
    assert window.sequence['duration'] == pytest.approx(15 + sum(s['duration'] for s in before['sections'][:3]))
    assert window.section_timeline.selected_indices() == [0, 1, 2]
    # Clicking a repeated view seeks that occurrence and edits its shared source.
    click_section(window, 4)
    assert window.composer.index == 1
    assert window.current_time == placements[4][1]
    window.composer.section_duration.setValue(1.)
    assert [end - start for index, start, end, _ in section_placements(window.composition) if index == 1] == [1., 1.]
    path = tmp_path / 'loop.json'; save_composition(path, window.composition)
    assert compile_composition(load_composition(path)) == window.sequence
    window.undo_composition()
    window.undo_composition(); assert window.composition == before
    window.redo_composition()
    assert [index for index, *_ in section_placements(window.composition)] == [0, 1, 2, 0, 1, 2, 3, 4, 5]


def test_command_selection_is_stable_across_edits_and_new_study_clears_it(window):
    click_section(window, 0)
    click_section(window, 2, Qt.KeyboardModifier.MetaModifier)
    assert window.section_timeline.selected_indices() == [0, 2]
    context_menu(window, 2).close()
    assert window.section_timeline.selected_indices() == [0, 2]
    window.composer.loop_sections(tuple(window.section_timeline.selected_ids), 2)
    assert [index for index, *_ in section_placements(window.composition)] == [0, 1, 2, 0, 2, 3, 4, 5]
    window.composer.section_duration.setValue(1.)
    assert window.section_timeline.selected_indices() == [0, 2]
    context_menu(window, 7).close()
    assert window.section_timeline.selected_indices() == [5]
    window.load_starter_id('approved')
    assert window.section_timeline.selected_indices() == [0]


def test_reordering_and_removal_keep_group_members_valid_and_loop_can_be_removed(window):
    panel = window.composer
    members = [section['id'] for section in window.composition['sections'][:3]]
    panel.loop_sections(members, 2)
    panel.select_section(1); panel.move_section(1)
    group = window.composition['timeline_loops'][0]
    assert group['sections'] == [section['id'] for section in window.composition['sections'][:3]]
    panel.remove_section()
    assert window.composition['timeline_loops'][0]['sections'] == [members[0], members[2]]
    panel.loop_sections([members[0], members[2]], 1)
    assert 'timeline_loops' not in window.composition


def test_sequence_loops_repeat_edited_cues_without_changing_states_or_seeds(tmp_path):
    project = reference_composition(refined=True)
    project['variation'] = 3
    project['sections'][1]['duration'] = 1.24
    project['sections'][1]['macros']['rhythm'] = .7
    before = compile_composition(project)
    members = [section['id'] for section in project['sections'][:3]]
    project['timeline_loops'] = [{'sections': members, 'loops': 3}]
    looped = compile_composition(project)
    assert looped['states'] == before['states']
    fps = project['fps']
    cycle_frames = sum(round(section['duration'] * fps) for section in project['sections'][:3])
    original = [cue for cue in before['cues'] if cue['state'].split(':')[0] in members]
    repeated = [cue for cue in looped['cues'] if cue['state'].split(':')[0] in members]
    assert repeated == [dict(cue, time=(round(cue['time'] * fps) + repetition * cycle_frames) / fps)
                        for repetition in range(3) for cue in original]
    assert round(looped['duration'] * fps) == round(before['duration'] * fps) + 2 * cycle_frames
    assert section_ranges(project)[-1][1] == looped['duration']
    path = tmp_path / 'sequence-loop.json'; save_composition(path, project)
    assert compile_composition(load_composition(path)) == looped


@pytest.mark.parametrize('groups', [
    'invalid', [{'sections': ['missing'], 'loops': 2}],
    [{'sections': [], 'loops': 2}], [{'sections': ['section-1'] * 2, 'loops': 2}],
    [{'sections': ['section-1'], 'loops': 33}], [{'sections': ['section-1'], 'loops': True}],
    [{'sections': ['section-1'], 'loops': 1.5}],
    [{'sections': ['section-1'], 'loops': 2}, {'sections': ['section-1'], 'loops': 3}],
])
def test_bad_sequence_loop_groups_are_rejected(groups):
    project = reference_composition(); project['timeline_loops'] = groups
    with pytest.raises(ValueError): normalize_composition(project)


def test_sequence_loops_enforce_total_limit_and_default_compositions_stay_unchanged():
    project = reference_composition()
    assert 'timeline_loops' not in normalize_composition(project)
    project['timeline_loops'] = [{'sections': [s['id'] for s in project['sections']], 'loops': 32}]
    for section in project['sections']: section['duration'] = 300.
    with pytest.raises(ValueError, match='one hour'): normalize_composition(project)


def test_studies_picker_is_compact(window):
    assert window.starter_combo.width() <= 560
    assert window.starter_combo.width() < window.width() / 2
