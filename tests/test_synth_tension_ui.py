import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from test_synth_effects_editor_integration import make_window
from synth_composition import load_composition, save_composition
from synth_starters import starter_composition


def test_main_controls_edit_scopes_undo_and_roundtrip(make_window,tmp_path):
    project=starter_composition('tension')
    other=copy.deepcopy(project['sections'][0]);other['id']='second';project['sections'].append(other)
    window=make_window(composition=project);composer=window.composer;panel=composer.effects_panel
    panel.inspect_effect('signal_tension');QApplication.processEvents()
    for key in ('tension','cohesion','persistence','instability','texture'):
        assert panel.controls['signal_tension.'+key].isVisible()
    assert panel.controls['signal_tension.persistence'].input.suffix()==' s'
    original=copy.deepcopy(window.composition)
    panel.controls['signal_tension.tension'].input.setValue(.55)
    assert window.composition['effects']['signal_tension']['params']['signal_tension.tension']==.55
    window.undo_composition();assert window.composition==original
    composer.change_scope(1)
    panel.controls['signal_tension.cohesion'].input.setValue(.9)
    assert window.composition['sections'][0]['effects']['signal_tension']['params']['signal_tension.cohesion']==.9
    assert 'signal_tension' not in window.composition['sections'][1]['effects']
    save_composition(tmp_path/'scope.json',window.composition)
    assert load_composition(tmp_path/'scope.json')==window.composition
    window.undo_composition();assert window.composition==original


def test_tension_editor_fits_narrow_inspector_and_keeps_image_effects_separate(make_window,tmp_path):
    window=make_window(composition=starter_composition('tension'))
    window.splitter.setSizes([850,410]);panel=window.composer.effects_panel
    panel.inspect_effect('signal_tension');QApplication.processEvents()
    assert panel.group.itemText(1)=='Gesture'
    assert not panel.parameter_scroll.horizontalScrollBar().isVisible()
    assert window.composer.object_panel.kind=='signal'
    window.grab().save(str(tmp_path/'tension-inspector.png'))
