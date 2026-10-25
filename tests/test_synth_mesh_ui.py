import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from test_synth_composer_ui import window,wait_until
from test_synth_mesh import fixture_mesh
from synth_starters import starter_composition
from synth_mesh_ui import MeshControl


def test_import_replace_clear_and_undo_preserve_the_look(window,tmp_path,monkeypatch):
    import trimesh
    path=tmp_path/'box.glb';path.write_bytes(trimesh.creation.box().export(file_type='glb'))
    window.set_composition(starter_composition('color-film-die'))
    composer=window.composer;composer.look_tabs.setCurrentWidget(composer.object_panel);obj=composer.object_panel
    source=copy.deepcopy(window.composition['source'])
    assert obj.controls['solid.model_data'].isHidden()
    obj.controls['solid.shape'].input.setCurrentIndex(2)
    assert not obj.controls['solid.model_data'].isHidden()
    assert obj.controls['solid.corner_radius'].isHidden()
    assert obj.controls['solid.pip_size'].isHidden()
    importer=obj.controls['solid.model_data'].input
    monkeypatch.setattr('synth_mesh_ui.QFileDialog.getOpenFileName',lambda *a: (str(path),''))
    importer.import_button.click()
    initial=importer.value()
    assert 'embedded' in importer.status.text()
    assert window.composition['source']==source
    assert window.composition['effects']['solid']['params']['solid.model_data']==initial
    importer.setValue(fixture_mesh())
    window.undo_composition();assert importer.value()==initial
    importer.clear_button.click();assert importer.value()==''
    window.undo_composition();assert importer.value()==initial
    assert obj.controls['solid.turn_speed'].input.value()==24.
    obj.details.click();panel=composer.object_editor
    assert isinstance(panel.controls['solid.model_data'].input,MeshControl)
    panel.controls['solid.model_data'].input.setValue(fixture_mesh())
    window.undo_composition();assert panel.controls['solid.model_data'].input.value()==initial
    wait_until(lambda:not window.render_running and not window.render_queued)


def test_glass_material_and_height_controls_are_editable(window):
    window.set_composition(starter_composition('color-film-die'))
    composer=window.composer;composer.look_tabs.setCurrentWidget(composer.object_panel);obj=composer.object_panel
    obj.controls['solid.shape'].input.setCurrentIndex(2)
    obj.controls['solid.model_data'].input.setValue(fixture_mesh())
    obj.controls['solid.material'].input.setCurrentIndex(2)
    assert not obj.controls['solid.height_stretch'].isHidden()
    assert not obj.controls['solid.glass_transmission'].isHidden()
    assert obj.controls['solid.shading'].isHidden()
    obj.controls['solid.height_stretch'].input.setValue(1.8)
    assert window.composition['effects']['solid']['params']['solid.height_stretch']==1.8
    window.undo_composition()
    assert obj.controls['solid.height_stretch'].input.value()==1.
    wait_until(lambda:not window.render_running and not window.render_queued)
