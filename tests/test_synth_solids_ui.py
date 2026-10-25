import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition
from synth_parameter_presentation import presentation


def test_die_and_background_controls_can_be_edited_and_undone(window):
    window.set_composition(starter_composition('color-film-die'))
    composer=window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    obj=composer.object_panel
    assert obj.kind=='solid'
    assert obj.controls['solid.material'].input.currentIndex()==1
    assert obj.controls['solid.palette'].isHidden()
    assert not obj.controls['solid.roughness'].isHidden()
    obj.controls['solid.corner_radius'].input.setValue(.18)
    assert window.composition['effects']['solid']['params']['solid.corner_radius']==.18
    window.undo_composition()
    assert obj.controls['solid.corner_radius'].input.value()==.13
    obj.controls['solid.material'].input.setCurrentIndex(0)
    assert obj.controls['solid.roughness'].isHidden()
    assert not obj.controls['solid.palette'].isHidden()
    window.undo_composition()
    shape=obj.controls['solid.shape'].input
    assert not obj.controls['solid.pip_size'].isHidden()
    shape.setCurrentIndex(1)
    assert obj.controls['solid.pip_size'].isHidden()
    assert obj.controls['solid.pip_depth'].isHidden()
    window.undo_composition()
    assert shape.currentIndex()==0 and not obj.controls['solid.pip_size'].isHidden()
    obj.controls['solid.turn_speed'].input.setValue(42.)
    assert window.composition['effects']['solid']['params']['solid.turn_speed']==42.
    window.undo_composition()
    assert obj.controls['solid.turn_speed'].input.value()==24.
    obj.details.click()
    panel=composer.object_editor
    assert panel.effect_id=='solid'
    panel=composer.effects_panel
    panel.inspect_effect('color_field')
    panel.reveal_control('color_field.flow')
    panel.controls['color_field.flow'].input.setValue(.8)
    assert window.composition['effects']['color_field']['params']['color_field.flow']==.8
    window.undo_composition()
    assert panel.controls['color_field.flow'].input.value()==.43
    assert presentation('solid.turn_speed').unit=='°/s'
    obj.selector.setCurrentIndex(obj.selector.findData('none'))
    assert obj.kind=='none'
    window.undo_composition()
    assert obj.kind=='solid'
    wait_until(lambda:not window.render_running and not window.render_queued)
