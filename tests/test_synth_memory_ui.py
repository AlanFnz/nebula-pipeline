import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from test_synth_effects_editor_integration import make_window
from synth_starters import starter_composition
from synth_composition import load_composition, save_composition


def test_memory_controls_are_discoverable_scoped_and_undoable(make_window,tmp_path):
    project=starter_composition('image-memory')
    second=copy.deepcopy(project['sections'][0]);second['id']='second';project['sections'].append(second)
    window=make_window(composition=project);composer=window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    obj=composer.object_panel
    assert obj.kind=='memory'
    assert obj.layout().indexOf(obj.control_host)<obj.layout().indexOf(obj.position_host)
    assert list(obj.controls)[:3]==['image_memory.persistence','image_memory.drift','image_memory.dissolve']
    assert obj.controls['image_memory.persistence'].input.suffix()==' s'
    obj.controls['image_memory.persistence'].input.setValue(4.)
    assert window.composition['effects']['image_memory']['params']['image_memory.persistence']==4.
    composer.change_scope(1)
    obj.controls['image_memory.drift'].input.setValue(.6)
    assert window.composition['sections'][0]['effects']['image_memory']['params']['image_memory.drift']==.6
    assert 'image_memory' not in window.composition['sections'][1]['effects']
    assert 'image_memory.drift' not in window.composition['effects']['image_memory']['params']
    window.undo_composition()
    assert obj.controls['image_memory.drift'].input.value()==.13
    obj.controls['image_memory.shape'].input.setCurrentIndex(2)
    assert not obj.controls['image_memory.sides'].isHidden()
    obj.controls['image_memory.sides'].input.setValue(3)
    save_composition(tmp_path/'memory.json',window.composition)
    assert load_composition(tmp_path/'memory.json')==window.composition
    obj.details.click()
    panel=composer.effects_panel
    assert panel.effect_id=='image_memory' and panel.intensity_host.isHidden()
    panel.reveal_control('image_memory.shape')
    panel.controls['image_memory.shape'].input.setCurrentIndex(1)
    assert panel.controls['image_memory.sides'].isHidden()
    panel.reveal_control('image_memory.dissolve')
    assert panel.controls['image_memory.dissolve'].isVisible()
