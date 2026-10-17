import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import pytest
from PySide6.QtWidgets import QApplication
from synth_composition import blank_composition
from synth_effects import effect_preset
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
    assert panel.intensity_host.isHidden() and not control.isVisible()
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
