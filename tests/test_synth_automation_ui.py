import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from synth_composition import blank_composition, compile_composition, save_composition, load_composition
from synth_effects import effect_preset
from test_synth_effects_editor_integration import make_window


def clean():
    p = blank_composition(); p['sections'][0]['duration'] = 10.
    p['effects']['tape'] = effect_preset('tape', 3)
    return p


def authored(window): return window.composition['sections'][0].get('automations', [])


def apply_pull(dialog, start=4):
    dialog.times['start'].setValue(start); dialog.times['attack'].setValue(.15)
    dialog.times['hold'].setValue(0); dialog.times['recovery'].setValue(.85)
    dialog.amount.setValue(.6); dialog.apply()


def test_draft_cancel_apply_dirty_one_undo_save_reopen_and_base_restore(make_window, tmp_path):
    window = make_window(composition=clean()); panel = window.composer
    original = copy.deepcopy(window.composition); window.timeline.setValue(100)
    control_panel = panel.effects_panel; control_panel.inspect_effect('tape'); control_panel.parameter_tabs.setCurrentIndex(1)
    control = control_panel.controls['tape.pull']
    assert control.animate_button.text() == 'Animate…'
    QApplication.processEvents()
    assert control.animate_button.parent() is control and control.animate_button.isVisible()
    assert control_panel.controls['tape.rate'].animate_button is None
    from synth_inspector import control_group
    assert control_group('tape.pull') == 'Motion & timing'
    dialog = panel.open_automation('tape.pull')
    assert dialog.times['start'].value() == 4
    dialog.times['start'].setValue(5); dialog.reject()
    assert window.composition == original and not window.has_unsaved_changes()
    dialog = panel.open_automation('tape.pull'); apply_pull(dialog)
    assert len(authored(window)) == 1 and len(window.undo_compositions) == 1
    assert authored(window)[0]['start_fraction'] == .4
    assert window.has_unsaved_changes()
    assert control.animate_button.text() == 'Automations (1)…'
    assert 'Base' in control.label.text()
    panel.change_effect('tape', dict(effect_preset('tape', 3), params={**effect_preset('tape',3)['params'],'tape.pull':.1}), 'effect-param:tape.pull')
    control.reset_button.click()
    assert len(authored(window)) == 1
    window.undo_composition(); window.undo_composition(); window.undo_composition()
    assert window.composition == original
    window.redo_composition(); assert len(authored(window)) == 1
    save_composition(tmp_path/'automation.json', window.composition)
    assert compile_composition(load_composition(tmp_path/'automation.json')) == window.sequence


def test_edit_conflict_disable_reenable_remove_list_and_effect_remove(make_window):
    window = make_window(composition=clean()); panel = window.composer
    first = panel.open_automation('tape.pull'); apply_pull(first)
    second = panel.open_automation('tape.pull'); apply_pull(second)
    assert second.isVisible() and 'Overlapping' in second.error.text()
    assert len(authored(window)) == 1
    second.enabled.setChecked(False); second.apply(); assert len(authored(window)) == 2
    listing = panel.open_automation_list(); assert listing.list.count() == 2
    listing.list.setCurrentRow(1); listing.change('toggle'); assert 'Overlapping' in listing.error.text()
    assert not authored(window)[1]['enabled']
    listing.change('remove'); assert len(authored(window)) == 1
    listing.reject()
    event = authored(window)[0]
    edit = panel.open_automation(section_id='section-1', event_id=event['id'])
    edit.times['start'].setValue(6); edit.reject(); assert authored(window)[0]['start_fraction'] == .4
    edit = panel.open_automation(section_id='section-1', event_id=event['id'])
    edit.times['start'].setValue(6); edit.apply(); assert authored(window)[0]['start_fraction'] == .6
    panel.effects_panel.inspect_effect('tape'); panel.effects_panel.toggle_bypass('tape')
    assert len(authored(window)) == 1
    panel.effects_panel.remove_effect('tape'); assert not authored(window)
    window.undo_composition(); assert len(authored(window)) == 1
    assert window.composition['effects']['tape']['bypassed']


def test_section_choice_defaults_to_playhead_and_inactive_notice(make_window):
    p=clean(); second=copy.deepcopy(p['sections'][0]); second['id']='second'; p['sections'].append(second)
    p['effects']['tape']['bypassed']=True
    window=make_window(composition=p); window.timeline.setValue(25*14)
    editor=window.composer.open_automation('tape.pull')
    assert editor.section.currentData()=='second'
    assert editor.times['start'].value()==4
    assert 'inactive' in editor.notice.text()
    editor.reject()
    window.composer.select_section(0); window.timeline.setValue(249)
    editor=window.composer.open_automation('tape.pull')
    assert sum(c.value() for c in editor.times.values()) <= 10 + 1e-12
    editor.reject()
    window.composer.playhead_seconds = lambda: 10.
    editor=window.composer.open_automation('tape.pull')
    assert editor.times['start'].value() > 9.9
    assert 'Start moved inside' in editor.notice.text()
    editor.reject()


def test_lane_repeated_selection_drag_cancel_and_single_release_commit(make_window):
    p=clean(); p['sections'][0]['loops']=2
    window=make_window(composition=p); panel=window.composer
    apply_pull(panel.open_automation('tape.pull'))
    lane=window.section_timeline.automation_lane; QApplication.processEvents()
    assert not lane.isHidden() and window.section_timeline.height()==92
    assert window.section_scroll.height()==108
    assert lane.mapTo(window.section_scroll.viewport(), lane.rect().bottomRight()).y() < window.section_scroll.viewport().height()
    rects=lane.rectangles(); assert len(rects)==2 and rects[0][2]==rects[1][2]
    original=copy.deepcopy(window.composition); before=len(window.undo_compositions)
    pos=rects[1][0].center().toPoint()
    QTest.mousePress(lane,Qt.MouseButton.LeftButton,pos=pos)
    QTest.mouseMove(lane,pos+QPoint(10,0)); QTest.keyClick(lane,Qt.Key.Key_Escape)
    QTest.mouseRelease(lane,Qt.MouseButton.LeftButton,pos=pos+QPoint(10,0))
    assert window.composition==original and len(window.undo_compositions)==before
    QTest.mousePress(lane,Qt.MouseButton.LeftButton,pos=pos)
    QTest.mouseMove(lane,pos+QPoint(10,0)); QTest.mouseRelease(lane,Qt.MouseButton.LeftButton,pos=pos+QPoint(10,0))
    assert len(window.undo_compositions)==before+1
    assert authored(window)[0]['start_fraction'] > .4
    assert len(lane.rectangles())==2
    window.undo_composition(); assert window.composition==original


@pytest.mark.parametrize('size', [(1280,720),(1440,900)])
def test_compact_workspace_with_lane_and_narrow_inspector(make_window,size):
    window=make_window(composition=clean()); window.resize(*size)
    apply_pull(window.composer.open_automation('tape.pull'))
    window.splitter.setSizes([size[0]-380,370]); panel=window.composer.effects_panel
    panel.inspect_effect('tape'); QApplication.processEvents()
    assert window.height()==size[1]
    assert panel.parameter_scroll.viewport().height()>=100
    assert window.composer.automations_button.isVisible()


def test_target_notice_refreshes_and_selected_section_controls_activation(make_window):
    p=clean(); second=copy.deepcopy(p['sections'][0]); second['id']='second'
    second['effects']['tape']=dict(mode='off',params={}); p['sections'].append(second)
    window=make_window(composition=p); panel=window.composer
    editor=panel.open_automation()
    assert 'inactive' in editor.notice.text()
    editor.target.setCurrentIndex(editor.target.findData('tape.pull'))
    assert 'inactive' not in editor.notice.text()
    editor.section.setCurrentIndex(editor.section.findData('second'))
    assert 'inactive' in editor.notice.text()
    editor.reject()
