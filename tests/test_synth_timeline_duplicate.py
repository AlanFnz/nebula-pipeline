"""Real timeline shortcuts copy independent content in one undoable edit."""
import copy

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from synth_automation import duplicate_automation
from synth_composition import blank_composition, normalize_composition, compile_composition, save_composition, load_composition
from synth_effects import effect_preset
from test_synth_effects_editor_integration import make_window


def gesture(identifier='pull', start=.1, length=.1, **extra):
    return dict(id=identifier, path='tape@2.pull', amount=.18, enabled=True,
                easing='smooth', start_fraction=start, attack_fraction=length/4,
                hold_fraction=0., recovery_fraction=length*3/4, **extra)


def project():
    document = blank_composition()
    document['effects']['tape@2'] = effect_preset('tape@2', 3)
    section = document['sections'][0]
    section.update(duration=10., loops=2, automations=[gesture()])
    return normalize_composition(document)


def duplicate_key(widget):
    widget.window().activateWindow()
    widget.setFocus(); QApplication.processEvents()
    QTest.keySequence(widget, QKeySequence('Ctrl+D')); QApplication.processEvents()


def events(window):
    return window.composition['sections'][0]['automations']


def test_automation_duplicate_finds_gap_without_changing_curve_or_other_targets():
    original = gesture()
    blocker = gesture('later', .22)
    disabled = gesture('disabled', .32); disabled['enabled'] = False
    other = gesture('other', .42); other['path'] = 'warp.amount'
    authored = [original, blocker, disabled, other]; before = copy.deepcopy(authored)
    duplicate = duplicate_automation(authored, original['id'])
    assert authored == before
    assert duplicate['start_fraction'] == pytest.approx(.42)
    assert duplicate['id'] not in {e['id'] for e in authored}
    assert {k:v for k,v in duplicate.items() if k not in ('id','start_fraction')} == {
        k:v for k,v in original.items() if k not in ('id','start_fraction')}


def test_curve_click_duplicate_repeat_undo_redo_save_reopen(make_window, tmp_path):
    window = make_window(composition=project()); original = copy.deepcopy(window.composition)
    lane = window.section_timeline.automation_lane
    # Clicking a repeated occurrence still copies its shared authored event.
    QTest.mouseClick(lane, Qt.MouseButton.LeftButton, pos=lane.rectangles()[1][0].center().toPoint())
    duplicate_key(lane)
    assert len(events(window)) == 2 and len(window.undo_compositions) == 1
    assert events(window)[1]['start_fraction'] == pytest.approx(.2)
    assert lane.selected == ('section-1', events(window)[1]['id'])
    assert len(lane.rectangles()) == 4
    duplicate_key(lane)
    assert len(events(window)) == 3 and len(window.undo_compositions) == 2
    assert events(window)[2]['start_fraction'] == pytest.approx(.3)
    final = copy.deepcopy(window.composition)
    window.undo_composition(); window.undo_composition()
    assert window.composition == original
    window.redo_composition(); window.redo_composition()
    assert window.composition == final
    path = tmp_path/'duplicated.json'; save_composition(path, final)
    restored = load_composition(path)
    assert restored == final and compile_composition(restored) == window.sequence
    # Editing the copy does not modify its original.
    window.composer.change_automation('section-1', events(window)[1]['id'], 'toggle')
    assert events(window)[0]['enabled'] and not events(window)[1]['enabled']


def test_automation_no_room_is_atomic_and_reports_actionable_feedback(make_window):
    document = project(); document['sections'][0]['automations'][0]['start_fraction'] = .85
    window = make_window(composition=document); original = copy.deepcopy(window.composition)
    lane = window.section_timeline.automation_lane
    lane.selected = ('section-1', events(window)[0]['id'])
    duplicate_key(lane)
    assert window.composition == original and not window.undo_compositions
    assert 'Lengthen the section' in window.status.text()
    assert lane.selected == ('section-1', events(window)[0]['id'])


@pytest.mark.parametrize('indices', [(0,), (0,1), (0,2)])
def test_section_click_selection_duplicate_keeps_content_and_selects_copies(make_window, indices):
    document = project(); prototype = document['sections'][0]
    document['sections'] = []
    for i in range(4):
        section = copy.deepcopy(prototype)
        section.update(id=f'cut-{i}', duration=1.+i, variation=100+i,
                       effects_rate=.5+i*.25, video_rate=1.25+i*.25)
        document['sections'].append(section)
    window = make_window(composition=document); original = copy.deepcopy(window.composition)
    timeline = window.section_timeline
    for i, index in enumerate(indices):
        QTest.mouseClick(timeline, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.ControlModifier if i else Qt.KeyboardModifier.NoModifier,
                         timeline.rectangles()[index].center().toPoint())
    duplicate_key(timeline)
    insertion = indices[-1]+1
    copies = window.composition['sections'][insertion:insertion+len(indices)]
    originals = [original['sections'][i] for i in indices]
    assert len(window.composition['sections']) == 4+len(indices)
    assert len(window.undo_compositions) == 1
    assert timeline.selected_ids == {s['id'] for s in copies}
    assert timeline.index == insertion
    for source, duplicate in zip(originals,copies):
        assert source['id'] != duplicate['id']
        assert {k:v for k,v in source.items() if k!='id'} == {k:v for k,v in duplicate.items() if k!='id'}
    window.undo_composition(); assert window.composition == original
    window.redo_composition(); assert window.composition['sections'][insertion:insertion+len(indices)] == copies


def test_complete_sequence_loop_copies_independently_partial_selection_keeps_original(make_window):
    document = project(); second = copy.deepcopy(document['sections'][0]); second['id'] = 'second'
    document['sections'].append(second)
    document['timeline_loops'] = [dict(sections=['section-1','second'],loops=3)]
    window = make_window(composition=document)
    timeline = window.section_timeline
    timeline.selected_ids = {'section-1','second'}
    duplicate_key(timeline)
    groups = window.composition['timeline_loops']
    assert groups[0] == document['timeline_loops'][0]
    assert groups[1] == dict(sections=[s['id'] for s in window.composition['sections'][2:]],loops=3)
    window.undo_composition()
    timeline.selected_ids = {'section-1'}
    duplicate_key(timeline)
    assert window.composition['timeline_loops'] == document['timeline_loops']


def test_duplicate_shortcut_stays_local_and_clears_deleted_event_selection(make_window):
    first = make_window(composition=project()); second = make_window(composition=project())
    initial = copy.deepcopy(first.composition)
    duplicate_key(first.viewer)
    duplicate_key(first.composer.duration)
    assert first.composition == initial and not first.undo_compositions
    lane = first.section_timeline.automation_lane
    lane.selected = ('section-1', events(first)[0]['id'])
    first.activateWindow(); duplicate_key(lane)
    assert len(events(first)) == 2 and len(events(second)) == 1
    first.undo_composition()
    assert lane.selected is None
    duplicate_key(lane)
    assert len(events(first)) == 1 and not first.undo_compositions


def test_duplicate_section_limit_never_partially_copies(make_window):
    document = project(); prototype = document['sections'][0]
    document['sections'] = [dict(copy.deepcopy(prototype),id=f'cut-{i}') for i in range(63)]
    window = make_window(composition=document); original = copy.deepcopy(window.composition)
    window.section_timeline.selected_ids = {'cut-0','cut-1'}
    duplicate_key(window.section_timeline)
    assert window.composition == original and not window.undo_compositions
    assert '64 sections' in window.status.text()


def test_right_click_duplicate_actions_follow_the_same_undoable_paths(make_window):
    window = make_window(composition=project()); timeline = window.section_timeline
    menu = timeline.make_context_menu()
    next(a for a in menu.actions() if a.text().startswith('Duplicate')).trigger()
    assert len(window.composition['sections']) == 2 and len(window.undo_compositions) == 1
    window.undo_composition()
    lane = timeline.automation_lane
    rect = lane.rectangles()[0][0]
    lane.open_menu(lane.hits(rect.center()), lane.mapToGlobal(rect.center().toPoint()))
    submenu = lane.menu.actions()[0].menu()
    next(a for a in submenu.actions() if a.text().startswith('Duplicate')).trigger()
    lane.menu.close()
    assert len(events(window)) == 2 and len(window.undo_compositions) == 1
    assert lane.selected == ('section-1', events(window)[1]['id'])


def test_duplicate_invalid_or_overlong_selection_never_changes_index_or_document(make_window):
    window = make_window(composition=project()); panel = window.composer
    original = copy.deepcopy(window.composition); index = panel.index
    for selection in (None, 'section-1', [], ['missing'], [['section-1']]):
        assert panel.duplicate_sections(selection) is None
        assert window.composition == original and panel.index == index
    document = project(); section = document['sections'][0]
    section.update(duration=300., loops=10)
    window.set_composition(document); original = copy.deepcopy(window.composition)
    duplicate_key(window.section_timeline)
    assert window.composition == original and window.composer.index == index
    assert 'one hour' in window.status.text()
