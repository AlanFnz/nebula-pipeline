import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from nebula.documents.synth_composition import blank_composition, load_composition, save_composition
from nebula.effects.synth_effects import effect_preset
from test_synth_effects_editor_integration import make_window


def document():
    p=blank_composition()
    p['effects']['forms']=effect_preset('forms')
    p['effects']['broadcast']=effect_preset('broadcast')
    return p


def test_intensity_is_always_visible_and_survives_navigation(make_window):
    window=make_window(composition=document()); panel=window.composer.effects_panel
    panel.inspect_effect('broadcast'); QApplication.processEvents()
    control=panel.controls['broadcast.effect_intensity']
    assert control.isVisible() and control.input.value()==100
    assert control.input.suffix()==' %'
    assert panel.intensity_layout.indexOf(control)==0
    assert panel.parameter_layout.indexOf(control)==-1
    assert control.animate_button is not None
    for index in range(4):
        panel.parameter_tabs.setCurrentIndex(index); panel.filter.setText('nothing matches')
        QApplication.processEvents()
        assert control.isVisible()
    panel.inspect_effect('text'); QApplication.processEvents()
    assert window.composer.look_tabs.currentWidget() is window.composer.object_panel
    assert not control.isVisible()
    window.composer.look_tabs.setCurrentWidget(panel)
    panel.inspect_effect('broadcast'); QApplication.processEvents()
    assert panel.controls['broadcast.effect_intensity'] is control and control.isVisible()
    panel.inspect_effect('tape'); QApplication.processEvents()
    assert panel.controls['tape.effect_intensity'].isVisible() # Creative tab too


def test_zero_bypass_restore_and_clip_override_participate_in_undo(make_window):
    p=document(); second=copy.deepcopy(p['sections'][0]); second['id']='second'; p['sections'].append(second)
    window=make_window(composition=p); composer=window.composer; panel=composer.effects_panel
    panel.inspect_effect('broadcast')
    control=panel.controls['broadcast.effect_intensity']
    original=copy.deepcopy(window.composition)
    control.input.setValue(0)
    assert window.composition['effects']['broadcast']['params']['broadcast.effect_intensity']==0
    assert 'broadcast' in panel.browser_applied_ids()
    panel.toggle_bypass('broadcast')
    assert control.input.value()==0
    panel.toggle_bypass('broadcast')
    assert control.input.value()==0
    composer.change_scope(1)
    control.input.setValue(45)
    assert window.composition['sections'][0]['effects']['broadcast']['params']['broadcast.effect_intensity']==45
    assert window.composition['effects']['broadcast']['params']['broadcast.effect_intensity']==0
    control.reset_button.click()
    assert control.input.value()==0
    for _ in range(5): window.undo_composition()
    assert window.composition==original


def test_intensity_automation_defaults_to_a_visible_reduction(make_window):
    window=make_window(composition=document())
    panel=window.composer.effects_panel; panel.inspect_effect('broadcast')
    dialog=window.composer.open_automation('broadcast.effect_intensity')
    assert dialog.target.currentData()=='broadcast.effect_intensity'
    assert dialog.amount.value()==-30 and dialog.amount.suffix()==' %'
    dialog.times['start'].setValue(0); dialog.apply()
    event=window.composition['sections'][0]['automations'][0]
    assert event['path']=='broadcast.effect_intensity' and event['amount']==-30
    assert panel.controls['broadcast.effect_intensity'].animate_button.text()=='Automations (1)…'
    window.undo_composition()
    assert not window.composition['sections'][0].get('automations')


def test_selected_intensities_drag_type_undo_and_reopen(make_window, tmp_path):
    project = document()
    path = 'broadcast.effect_intensity'
    project['effects']['broadcast']['params'][path] = 7
    template = project['sections'][0]
    for name, intensity in [('second', 30), ('third', 50), ('fourth', 90)]:
        clip = dict(copy.deepcopy(template), id=name)
        clip['effects']['broadcast'] = {'mode': 'recipe', 'params': {path: intensity}}
        project['sections'].append(clip)
    project['sections'][1]['automations'] = [dict(
        id='fade', path=path, amount=-5, enabled=True, easing='smooth',
        start_fraction=0, attack_fraction=.1, hold_fraction=.2, recovery_fraction=.1)]
    window = make_window(composition=project)
    original = copy.deepcopy(window.composition)
    timeline = window.section_timeline
    panel = window.composer.effects_panel
    panel.inspect_effect('broadcast')
    batch = panel.selection_intensity
    assert not batch.toggle.isVisible()
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=timeline.rectangles()[0].center().toPoint())
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier,
                     timeline.rectangles()[2].center().toPoint())
    assert batch.toggle.text() == 'Edit 3 clips' and not batch.toggle.isChecked()
    assert window.composition == original and panel.intensity_host.isVisible()
    batch.toggle.click()
    assert batch.summary.text() == 'Mixed values · 7–50 %' and not panel.intensity_host.isVisible()
    assert batch.number.placeholderText() == 'Mixed' and not batch.number.text()
    assert batch.slider.minimum() == -70 and batch.slider.maximum() == 500
    batch.slider.setSliderDown(True)
    for position in (25, 60, 100):
        batch.slider.setSliderPosition(position)
    assert window.composition == original and batch.summary.text() == 'Mixed values · 17–60 %'
    batch.slider.setSliderDown(False)
    relative = copy.deepcopy(original)
    for clip, value in zip(relative['sections'], (17, 40, 60)):
        clip['effects'].setdefault('broadcast', {'mode': 'recipe', 'params': {}})['params'][path] = value
    assert window.composition == relative and len(window.undo_compositions) == 1
    assert batch.slider.value() == 0
    window.activateWindow()
    batch.number.setFocus()
    QTest.keyClicks(batch.number, '40')
    assert window.composition == relative
    QTest.keyClick(batch.number, Qt.Key.Key_Return)
    absolute = copy.deepcopy(relative)
    for clip in absolute['sections'][:3]:
        clip['effects']['broadcast']['params'][path] = 40
    assert window.composition == absolute and len(window.undo_compositions) == 2
    assert batch.summary.text() == '40 %'
    saved = tmp_path / 'batch.nebula'
    save_composition(saved, window.composition)
    assert load_composition(saved) == absolute
    for expected in (relative, original):
        QTest.keySequence(window.focusWidget(), QKeySequence(QKeySequence.StandardKey.Undo))
        QApplication.processEvents()
        assert window.composition == expected
    assert batch.summary.text() == 'Mixed values · 7–50 %'
    window.redo_composition()
    assert window.composition == relative
    timeline.select_at(0)
    assert not batch.isVisible() and panel.intensity_host.isVisible()


def test_batch_select_all_follows_study_and_respects_common_limit(make_window):
    project = document()
    path = 'broadcast.effect_intensity'
    project['effects']['broadcast']['params'].pop(path, None)
    state = next(iter(project['source']['states'].values()))
    state['overrides'][path] = 18.25
    second = dict(copy.deepcopy(project['sections'][0]), id='second')
    second['effects']['broadcast'] = {'mode': 'recipe', 'bypassed': True, 'params': {path: 93.75}}
    project['sections'].append(second)
    window = make_window(composition=project)
    timeline = window.section_timeline
    panel = window.composer.effects_panel
    panel.inspect_effect('broadcast')
    timeline.setFocus()
    QTest.keySequence(timeline, QKeySequence(QKeySequence.StandardKey.SelectAll))
    batch = panel.selection_intensity
    batch.toggle.click()
    batch.slider.setValue(batch.slider.maximum())
    local = [clip['effects']['broadcast'] for clip in window.composition['sections']]
    assert [entry['params'][path] for entry in local] == [24.5, 100.]
    assert local[1]['bypassed'] and batch.slider.maximum() == 0
    panel.inspect_effect('tape')
    assert not batch.toggle.isChecked() and panel.intensity_host.isVisible()
