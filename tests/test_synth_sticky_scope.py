"""Single-click preserves editing scope; double-click explicitly edits a clip."""
import copy
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from test_synth_effect_discovery_ui import window, select
from test_synth_effect_scope import document


def click_clip(window, index):
    rectangle = window.section_timeline.rectangles()[index]
    QTest.mouseClick(window.section_timeline, Qt.MouseButton.LeftButton, pos=rectangle.center().toPoint())
    QApplication.processEvents()


@pytest.mark.parametrize('local', [False, True])
def test_timeline_click_preserves_scope_and_routes_new_effect_to_that_scope(window, local):
    window.set_composition(document()); panel = window.composer; effects = panel.effects_panel
    panel.change_scope(int(local)); effects.show_overview()
    original = copy.deepcopy(window.composition)
    click_clip(window, 1)
    assert panel.index == 1 and panel.scope == int(local)
    assert window.composition == original and not window.undo_compositions
    assert window.section_timeline.editing_section_id == (original['sections'][1]['id'] if local else None)
    assert effects.available_button.text() == ('Add clip effect…' if local else 'Add project effect…')
    assert effects.add_button.text() == effects.available_button.text()
    assert effects.clip_title.isHidden() == (not local)
    effects.available_button.click(); QApplication.processEvents()
    dialog = window.discovery_dialog
    assert dialog.session.section_id == (original['sections'][1]['id'] if local else None)
    select(dialog, 'bloom'); dialog.debounce.stop(); dialog.render_selection()
    dialog.session.accept_packet(); dialog.refresh_preview(); dialog.action.click()
    assert panel.scope == int(local) and panel.index == 1
    target = window.composition['sections'][1] if local else window.composition
    assert target['effects']['bloom']['mode'] == 'on'
    if local:
        assert window.composition['effects'] == original['effects']
    else:
        assert window.composition['sections'] == original['sections']
    window.undo_composition(); assert window.composition == original


def test_project_view_remains_shared_after_returning_from_a_clip_inspector(window):
    window.set_composition(document()); panel = window.composer; effects = panel.effects_panel
    panel.change_scope(1); effects.inspect_effect('tape@2')
    panel.change_scope(0); effects.show_overview()
    assert effects.clip_title.isHidden() and 'tape@2' not in effects.applied_ids
    assert effects.effect_choices['tape@2'].isHidden()
    click_clip(window, 2)
    assert panel.scope == 0 and 'tape@2' not in effects.applied_ids
    assert effects.project_effect_ids == ('raster',)
    panel.change_scope(1)
    assert panel.index == 2 and panel.scope == 1
    click_clip(window, 0)
    assert panel.scope == 1 and set(effects.clip_effect_ids) == {'tape@2', 'raster'}


@pytest.mark.parametrize('local', [False, True])
def test_double_click_enters_clicked_clip_without_editing_document(window, local):
    window.set_composition(document()); panel = window.composer
    panel.change_scope(int(local))
    original = copy.deepcopy(window.composition)
    timeline = window.section_timeline
    position = timeline.rectangles()[1].center().toPoint()
    # Exercise the first click and the double-click event, as native Qt does.
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=position)
    assert panel.scope == int(local)
    QTest.mouseDClick(timeline, Qt.MouseButton.LeftButton, pos=position)
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=position)
    QApplication.processEvents()
    assert panel.scope == 1 and panel.index == 1
    assert timeline.editing_section_id == original['sections'][1]['id']
    assert panel.effects_panel.available_button.text() == 'Add clip effect…'
    assert not panel.effects_panel.clip_title.isHidden()
    assert timeline._reorder is None and timeline._resize is None
    assert window.composition == original and not window.undo_compositions
    click_clip(window, 2)
    assert panel.scope == 1 and panel.index == 2


def test_double_click_loop_occurrence_edits_its_clip_and_keeps_clicked_time(window):
    doc = document()
    doc['timeline_loops'] = [{'sections': [s['id'] for s in doc['sections'][:2]], 'loops': 2}]
    window.set_composition(doc); panel = window.composer; panel.change_scope(0)
    timeline = window.section_timeline
    position = timeline.rectangles()[2].center().toPoint()
    QTest.mouseDClick(timeline, Qt.MouseButton.LeftButton, pos=position)
    QApplication.processEvents()
    assert panel.scope == 1 and panel.index == 0
    assert window.timeline.value() == round(sum(s['duration'] for s in doc['sections'][:2]) * doc['fps'])
    assert not window.undo_compositions


def test_double_click_outside_clip_does_not_enter_clip_editing(window):
    window.set_composition(document()); panel = window.composer; panel.change_scope(0)
    timeline = window.section_timeline
    position = timeline.rectangles()[1].center().toPoint(); position.setY(0)
    QTest.mouseDClick(timeline, Qt.MouseButton.LeftButton, pos=position)
    QApplication.processEvents()
    assert panel.scope == 0 and panel.index == 0
    assert not window.undo_compositions
