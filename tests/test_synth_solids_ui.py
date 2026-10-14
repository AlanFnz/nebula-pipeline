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
    shape=obj.controls['solid.shape'].input
    assert not obj.controls['solid.pip_size'].isHidden()
    shape.setCurrentIndex(1)
    assert obj.controls['solid.pip_size'].isHidden()
    window.undo_composition()
    assert shape.currentIndex()==0 and not obj.controls['solid.pip_size'].isHidden()
    obj.controls['solid.turn_speed'].input.setValue(42.)
    assert window.composition['effects']['solid']['params']['solid.turn_speed']==42.
    window.undo_composition()
    assert obj.controls['solid.turn_speed'].input.value()==24.
    obj.details.click()
    panel=composer.effects_panel
    assert panel.effect_id=='solid'
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
