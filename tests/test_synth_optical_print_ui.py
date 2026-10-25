from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition


def test_dark_print_wording_and_reading_protection_are_editable(window):
    window.set_composition(starter_composition('text-dark-print'))
    composer=window.composer
    obj=composer.object_panel
    composer.look_tabs.setCurrentWidget(obj)
    wording=obj.controls['text.content'].input
    wording.editor.setPlainText('MEMORIA EN MOVIMIENTO')
    wording.apply.click()
    assert window.composition['effects']['text']['params']['text.content']=='MEMORIA EN MOVIMIENTO'
    panel=composer.effects_panel
    panel.inspect_effect('optical_print')
    for path,value,original in [('optical_print.reading_hold',.9,.65),
                                ('optical_print.cuts',4.,6.),
                                ('optical_print.effect_intensity',50.,100.)]:
        panel.reveal_control(path)
        assert not panel.controls[path].isHidden()
        panel.controls[path].input.setValue(value)
        assert window.composition['effects']['optical_print']['params'][path]==value
        window.undo_composition()
        assert panel.controls[path].input.value()==original
    wait_until(lambda: not window.render_running and not window.render_queued)
