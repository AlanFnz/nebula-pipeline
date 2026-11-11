import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PIL import Image
from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition


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
