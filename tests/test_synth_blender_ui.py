import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PIL import Image
from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import copy


def test_scene_controls_history_and_groups(window,monkeypatch):
    import synth_blender_bridge as bridge
    monkeypatch.setattr(bridge,'render_frame',lambda p,a,size:Image.new('RGB',size,'seagreen'))
    project=starter_composition('optical-relic')
    window.set_composition(project)
    panel=window.composer.object_panel
    window.composer.look_tabs.setCurrentWidget(panel)
    assert panel.kind=='blender'
    panel.reveal_object_group('Sculpture')
    panel.controls['blender_scene.ring_width'].input.setValue(1.2)
    assert window.composition['effects']['blender_scene']['params']['blender_scene.ring_width']==1.2
    window.undo_composition()
    assert panel.controls['blender_scene.ring_width'].input.value()==1.
    assert 'Stage & lighting' in panel.object_groups
    panel.details.click()
    assert window.composer.object_editor.effect_id=='blender_scene'
    wait_until(lambda:not window.render_running and not window.render_queued)


def test_independent_part_selection_edit_material_animation_and_undo(window,monkeypatch):
    import synth_blender_bridge as bridge
    monkeypatch.setattr(bridge,'render_frame',lambda p,a,size,**kw:Image.new('RGB',size,'seagreen'))
    window.set_composition(starter_composition('optical-relic'))
    panel=window.composer.object_panel
    window.composer.look_tabs.setCurrentWidget(panel)
    original=copy.deepcopy(window.composition)
    QTest.mouseClick(panel.part_selector, Qt.MouseButton.LeftButton)
    QTest.keyClick(panel.part_selector, Qt.Key.Key_Down)
    QTest.keyClick(panel.part_selector, Qt.Key.Key_Down)
    QTest.keyClick(panel.part_selector, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert panel.part_selector.currentData()=='upper'
    assert window.composition==original
    assert not panel.object_groups['Sculpture'].isVisible()
    assert panel.object_groups['Upper hoop / Transform'].isVisible()
    assert not panel.position_host.isVisible()
    panel.controls['blender_scene.part_upper_scale_x'].input.setValue(1.3)
    assert window.composition['effects']['blender_scene']['params']=={'blender_scene.part_upper_scale_x':1.3}
    window.undo_composition()
    assert window.composition==original
    assert panel.part_selector.currentData()=='upper'
    panel.reveal_object_group('Crown / Material')
    assert panel.part_selector.currentData()=='crown'
    assert not panel.controls['blender_scene.part_crown_hue'].isVisible()
    panel.controls['blender_scene.part_crown_inherit'].input.setChecked(False)
    assert panel.controls['blender_scene.part_crown_hue'].isVisible()
    window.undo_composition(); assert window.composition==original
    panel.object_filter.setText('Upper hoop'); QApplication.processEvents()
    assert panel.controls['blender_scene.part_upper_rotation_x'].isVisible()
    panel.object_filter.clear(); QApplication.processEvents()
    assert panel.part_selector.currentData()=='crown'
    panel.object_filter.setText('Upper hoop')
    panel.part_selector.setCurrentIndex(panel.part_selector.findData('left'))
    QApplication.processEvents()
    assert panel.part_selector.currentData()=='left'
    assert not panel.object_filter.text()
    assert panel.object_groups['Left pin / Transform'].isVisible()
    assert window.composition==original
    assert panel.reveal_control('blender_scene.part_lower_position_z')
    assert panel.part_selector.currentData()=='lower'
    control=panel.controls['blender_scene.part_lower_position_z']
    control.animate_button.click()
    dialog=window.composer.automation_dialogs[-1]
    dialog.times['start'].setValue(0.); dialog.times['attack'].setValue(.5)
    dialog.times['hold'].setValue(.5); dialog.times['recovery'].setValue(.5)
    dialog.amount.setValue(.4); dialog.apply()
    assert window.composition['sections'][0]['automations'][0]['path']==control.path
    window.undo_composition(); assert window.composition==original
    wait_until(lambda:not window.render_running and not window.render_queued)


def test_orbital_navigation_is_scoped_without_rewriting_other_studies(window,monkeypatch):
    import synth_blender_bridge as bridge
    monkeypatch.setattr(bridge,'render_frame',lambda p,a,size,**kw:Image.new('RGB',size,'seagreen'))
    project=starter_composition('orbital-rings');window.set_composition(project)
    panel=window.composer.object_panel;window.composer.look_tabs.setCurrentWidget(panel)
    original=copy.deepcopy(window.composition)
    assert [panel.part_selector.itemData(i) for i in range(1,panel.part_selector.count())]==['base','ring1','ring2','ring3','ring4','ring5','core','finial']
    assert panel.object_jump.findData('Upper hoop / Transform')==-1
    panel.reveal_control('blender_scene.part_ring3_rotation_y')
    assert panel.part_selector.currentData()=='ring3'
    assert panel.controls['blender_scene.part_ring3_rotation_y'].isVisible()
    panel.controls['blender_scene.part_ring3_rotation_y'].input.setValue(21.)
    assert window.composition['effects']['blender_scene']['params']['blender_scene.part_ring3_rotation_y']==21.
    window.undo_composition();assert window.composition==original
    panel.object_filter.setText('Orbit phase');QApplication.processEvents()
    assert panel.controls['blender_scene.orbit_phase_2'].isVisible()
    panel.object_filter.clear();QApplication.processEvents()
    assert panel.part_selector.currentData()=='ring3'
    window.set_composition(starter_composition('optical-relic'))
    panel=window.composer.object_panel
    assert panel.part_selector.findData('ring3')==-1
    assert panel.part_selector.currentData() is None
    assert panel.object_jump.findData('Ring 3 / Authored orbit')==-1
    assert panel.object_jump.findData('Upper hoop / Transform')!=-1
    wait_until(lambda:not window.render_running and not window.render_queued)
