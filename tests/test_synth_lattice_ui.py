import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition


def test_lattice_shapes_palettes_timing_and_undo_are_editable(window):
    window.set_composition(starter_composition('chromatic-lattice'))
    composer=window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    obj=composer.object_panel
    assert obj.kind=='lattice'
    assert obj.controls['chromatic_lattice.sides'].isHidden()
    assert obj.controls['chromatic_lattice.angle'].isHidden()
    obj.controls['chromatic_lattice.shape'].input.setCurrentIndex(3)
    assert not obj.controls['chromatic_lattice.sides'].isHidden()
    obj.controls['chromatic_lattice.sides'].input.setValue(5)
    assert window.composition['effects']['chromatic_lattice']['params']['chromatic_lattice.sides']==5
    window.undo_composition()
    assert obj.controls['chromatic_lattice.sides'].input.value()==6
    obj.controls['chromatic_lattice.palette'].input.setCurrentIndex(2)
    assert window.composition['effects']['chromatic_lattice']['params']['chromatic_lattice.palette']==2
    obj.controls['chromatic_lattice.period'].input.setValue(3.)
    assert window.composition['effects']['chromatic_lattice']['params']['chromatic_lattice.period']==3.
    obj.controls['chromatic_lattice.wave_shape'].input.setCurrentIndex(2)
    assert not obj.controls['chromatic_lattice.angle'].isHidden()
    obj.details.click()
    panel=composer.effects_panel
    assert panel.effect_id=='chromatic_lattice'
    assert not panel.remove_button.isVisible()
    panel.reveal_control('chromatic_lattice.shape')
    panel.controls['chromatic_lattice.shape'].input.setCurrentIndex(0)
    assert panel.controls['chromatic_lattice.sides'].isHidden()
    wait_until(lambda:not window.render_running and not window.render_queued)
