import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition


def test_tunnel_object_controls_and_undo(window):
    window.set_composition(starter_composition('spectral-tunnel'))
    composer = window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    obj = composer.object_panel
    assert obj.kind == 'tunnel'
    assert obj.controls['spectral_tunnel.sides'].isHidden()
    obj.controls['spectral_tunnel.shape'].input.setCurrentIndex(3)
    assert not obj.controls['spectral_tunnel.sides'].isHidden()
    obj.controls['spectral_tunnel.period'].input.setValue(.6)
    assert window.composition['effects']['spectral_tunnel']['params']['spectral_tunnel.period'] == .6
    window.undo_composition()
    assert obj.controls['spectral_tunnel.period'].input.value() == .3
    obj.details.click()
    assert composer.object_editor.effect_id == 'spectral_tunnel'
    wait_until(lambda: not window.render_running and not window.render_queued)
