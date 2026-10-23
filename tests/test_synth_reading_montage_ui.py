from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition


def test_reading_wording_timing_and_clarity_are_editable_and_undoable(window):
    window.set_composition(starter_composition('text-reading-print'))
    composer=window.composer; obj=composer.object_panel
    composer.look_tabs.setCurrentWidget(obj)
    control=obj.controls['text.content'].input
    assert control.value()=='REVOLUTION IS NOW'
    control.editor.setPlainText('OTRA FRASE')
    control.apply.click()
    assert window.composition['effects']['text']['params']['text.content']=='OTRA FRASE'
    assert not obj.controls['text.reading_final'].isHidden()
    assert not obj.controls['text.reading_breakup'].isHidden()
    assert obj.controls['text.copies'].isHidden()
    obj.controls['text.reading_final'].input.setValue(3.)
    assert window.composition['effects']['text']['params']['text.reading_final']==3.
    window.undo_composition()
    assert obj.controls['text.reading_final'].input.value()==2.
    obj.timing.click()
    panel=composer.effects_panel
    assert not panel.controls['text.reading_duration'].isHidden()
    assert panel.controls['text.morph_hold'].isHidden()
    assert panel.controls['text.word_seconds'].isHidden()
    panel.inspect_effect('film_burn');panel.reveal_control('film_burn.reading_clarity')
    panel.controls['film_burn.reading_clarity'].input.setValue(.8)
    assert window.composition['effects']['film_burn']['params']['film_burn.reading_clarity']==.8
    window.undo_composition()
    assert panel.controls['film_burn.reading_clarity'].input.value()==1.
    wait_until(lambda: not window.render_running and not window.render_queued)


def test_old_text_modes_keep_reading_controls_hidden(window):
    window.set_composition(starter_composition('text-transmission'))
    obj=window.composer.object_panel
    assert 'text.reading_duration' not in obj.controls
    obj.timing.click()
    panel=window.composer.effects_panel
    assert panel.controls['text.reading_duration'].isHidden()
    assert not panel.controls['text.word_seconds'].isHidden()
    wait_until(lambda: not window.render_running and not window.render_queued)
