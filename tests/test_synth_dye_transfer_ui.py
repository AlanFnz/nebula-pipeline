import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from test_synth_effects_editor_integration import make_window
from synth_composition import load_composition, save_composition
from synth_starters import starter_composition


def test_dye_controls_scope_undo_and_separate_wording(make_window,tmp_path):
    p=starter_composition('text-dye-transfer')
    second=copy.deepcopy(p['sections'][0]);second['id']='second';p['sections'].append(second)
    window=make_window(composition=p);composer=window.composer;panel=composer.effects_panel
    panel.inspect_effect('dye_transfer');QApplication.processEvents()
    before=copy.deepcopy(window.composition)
    assert composer.object_panel.kind=='text'
    assert 'text.content' not in panel.controls
    panel.controls['dye_transfer.paper_hue'].input.setValue(.7)
    assert window.composition['effects']['dye_transfer']['params']['dye_transfer.paper_hue']==.7
    window.undo_composition();assert window.composition==before
    composer.change_scope(1)
    panel.group.setCurrentIndex(panel.group.findData('Optical finish'))
    QApplication.processEvents()
    assert panel.controls['dye_transfer.drag'].isVisible()
    panel.controls['dye_transfer.drag'].input.setValue(.3)
    assert window.composition['sections'][0]['effects']['dye_transfer']['params']['dye_transfer.drag']==.3
    assert 'dye_transfer' not in window.composition['sections'][1]['effects']
    save_composition(tmp_path/'scope.json',window.composition)
    assert load_composition(tmp_path/'scope.json')==window.composition
    window.undo_composition();assert window.composition==before
