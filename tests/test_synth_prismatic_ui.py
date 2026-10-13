import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition
from synth_parameter_presentation import presentation


def test_prismatic_controls_edit_and_undo_independent_geometry_and_finish(window):
    window.set_composition(starter_composition('prismatic-film'))
    composer=window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    assert composer.object_panel.kind=='prismatic'
    controls=composer.object_panel.controls
    shape=controls['prismatic_field.shape'].input
    assert shape.currentIndex()==1
    assert controls['prismatic_field.sides'].isHidden()
    shape.setCurrentIndex(2)
    assert window.composition['effects']['prismatic_field']['params']['prismatic_field.shape']==2
    window.undo_composition()
    assert shape.currentIndex()==1
    shape.setCurrentIndex(0)
    assert not controls['prismatic_field.sides'].isHidden()
    control=controls['prismatic_field.sides'].input
    control.setValue(5)
    assert window.composition['effects']['prismatic_field']['params']['prismatic_field.sides']==5
    window.undo_composition()
    assert control.value()==3
    window.undo_composition()
    assert shape.currentIndex()==1
    controls['prismatic_field.transition_ease'].input.setValue(.5)
    assert window.composition['effects']['prismatic_field']['params']['prismatic_field.transition_ease']==.5
    window.undo_composition()
    assert controls['prismatic_field.transition_ease'].input.value()==.9
    controls['prismatic_field.turn_settle'].input.setValue(.25)
    assert window.composition['effects']['prismatic_field']['params']['prismatic_field.turn_settle']==.25
    window.undo_composition()
    assert controls['prismatic_field.turn_settle'].input.value()==.6
    composer.object_panel.details.click()
    panel=composer.effects_panel
    assert panel.effect_id=='prismatic_field'
    panel.reveal_control('prismatic_field.fold_period')
    assert not panel.controls['prismatic_field.fold_period'].isHidden()
    panel.controls['prismatic_field.fold_period'].input.setValue(4.)
    assert window.composition['effects']['prismatic_field']['params']['prismatic_field.fold_period']==4.
    window.undo_composition()
    panel.inspect_effect('film_emulsion')
    panel.reveal_control('film_emulsion.grain')
    assert not panel.controls['film_emulsion.grain'].isHidden()
    panel.controls['film_emulsion.grain'].input.setValue(.04)
    assert window.composition['effects']['film_emulsion']['params']['film_emulsion.grain']==.04
    window.undo_composition()
    assert panel.controls['film_emulsion.grain'].input.value()==.115
    assert presentation('prismatic_field.rotation_speed').unit=='°/s'
    assert presentation('prismatic_field.fold_period').unit==' s'
    wait_until(lambda: not window.render_running and not window.render_queued)
