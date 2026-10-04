import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from synth_composition import load_composition, save_composition, compile_composition
from synth_effects import effect_preset
from synth_effect_browser import EffectBrowserDialog
from test_synth_effects_editor_integration import make_window
from test_synth_instances import piece


def test_instance_ui_add_animate_remove_undo_save_and_reopen(make_window, tmp_path):
    window = make_window(composition=piece()); composer = window.composer
    panel = composer.effects_panel; original = copy.deepcopy(window.composition)
    panel.inspect_effect('tape'); panel.instance_button.click()
    QApplication.processEvents()
    assert panel.effect_id == 'tape@2'
    assert window.composition['effects']['tape'] == original['effects']['tape']
    assert panel.inspector_title.text() == 'EDIT / Tape damage · 2'
    assert len(window.undo_compositions) == 1
    assert panel.controls['tape@2.pull'].animate_button.isVisible()
    panel.controls['tape@2.pull'].animate_button.click()
    dialog = composer.automation_dialogs[-1]
    assert dialog.target.currentData() == 'tape@2.pull'
    assert 'Tape damage · 2' in dialog.target.currentText()
    dialog.times['start'].setValue(4); dialog.times['attack'].setValue(.15)
    dialog.times['hold'].setValue(0); dialog.times['recovery'].setValue(.85)
    dialog.amount.setValue(.3); dialog.apply()
    assert len(window.undo_compositions) == 2
    assert window.composition['sections'][0]['automations'][0]['path'] == 'tape@2.pull'
    panel.toggle_bypass('tape@2')
    assert window.composition['effects']['tape@2']['bypassed']
    assert window.composition['effects']['tape'] == original['effects']['tape']
    panel.remove_effect('tape@2')
    assert not window.composition['sections'][0].get('automations')
    assert 'tape' in panel.applied_ids and 'tape@2' not in panel.applied_ids
    window.undo_composition()
    assert window.composition['effects']['tape@2']['bypassed']
    assert len(window.composition['sections'][0]['automations']) == 1
    save_composition(tmp_path/'instances.json', window.composition)
    saved = load_composition(tmp_path/'instances.json')
    assert compile_composition(saved) == window.sequence
    reloaded = make_window(composition=saved)
    assert 'tape@2' in reloaded.composer.effects_panel.applied_ids
    assert 'tape' in reloaded.composer.effects_panel.applied_ids
    # Global removal of the original slot must not remove another pass's events.
    reloaded.composer.effects_panel.remove_effect('tape')
    assert len(reloaded.composition['sections'][0]['automations']) == 1


def test_add_browser_and_section_scope_allocate_unique_instances(make_window):
    p = piece(); second = copy.deepcopy(p['sections'][0]); second['id'] = 'second'
    p['sections'].append(second)
    window = make_window(composition=p); composer = window.composer
    browser = EffectBrowserDialog(('tape',), ('tape',), window)
    browser.instanceRequested.connect(composer.add_effect_instance)
    browser.show(); QApplication.processEvents()
    assert browser.instance_action.isVisible()
    browser.instance_action.click()
    assert 'tape@2' in window.composition['effects']
    composer.select_section(1); composer.add_effect_instance('tape@2')
    assert 'tape@3' in window.composition['sections'][1]['effects']
    assert 'tape@3' not in window.composition['effects']
    assert 'tape@3' not in window.composition['sections'][0]['effects']
    composer.select_section(0)
    assert 'tape@3' not in composer.effects_panel.applied_ids
    window.undo_composition(); assert 'tape@3' not in window.composition['sections'][1]['effects']
    window.redo_composition(); assert 'tape@3' in window.composition['sections'][1]['effects']


def test_audition_add_instance_closes_preview_without_overwriting_base(make_window):
    window = make_window(composition=piece())
    original = copy.deepcopy(window.composition)
    window.open_effect_discovery()
    dialog = window.discovery_dialog
    dialog.search.setText('Tape damage'); QApplication.processEvents()
    assert dialog.selected_effect_id() == 'tape'
    assert dialog.instance_action.isVisible()
    dialog.instance_action.click(); QApplication.processEvents()
    assert window.discovery_session is None
    assert window.comparison is None
    assert window.composition['effects']['tape'] == original['effects']['tape']
    assert window.composition['effects']['tape@2'] == effect_preset('tape@2', 3)
    assert len(window.undo_compositions) == 1
