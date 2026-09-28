from synth_composition import load_composition, save_composition
from synth_starters import starter_composition
from synth_studio import SynthControl
from synth import MODULE_BY_ID
from test_synth_composer_ui import window, wait_until


def test_native_wording_apply_undo_and_text_timing(window,tmp_path):
    window.set_composition(starter_composition('text-phosphor'))
    panel=window.composer; panel.look_tabs.setCurrentWidget(panel.object_panel)
    assert panel.object_panel.kind == 'text'
    control=panel.object_panel.controls['text.content'].input
    control.editor.setPlainText('REVOLUCIÓN\nIS NOW')
    assert 'text' not in window.composition['effects']
    control.apply.click()
    assert window.composition['effects']['text']['params']['text.content']=='REVOLUCIÓN\nIS NOW'
    wait_until(lambda: not window.render_running and not window.render_queued)
    path=tmp_path/'type.json'; save_composition(path,window.composition)
    assert load_composition(path)['effects']['text']==window.composition['effects']['text']
    window.undo_composition()
    assert panel.object_panel.controls['text.content'].input.value()=='REVOLUTION IS NOW'
    panel.object_panel.timing.click()
    assert panel.effects_panel.effect_id=='text'
    assert panel.effects_panel.parameter_tabs.currentIndex()==1
    assert not panel.effects_panel.controls['text.period'].isHidden()
    assert panel.effects_panel.controls['text.content'].isHidden()
    assert panel.scope_combo.isVisible()  # Text timing honors whole clip/section scope.
    spec=MODULE_BY_ID['text'].params[0]
    detail=SynthControl(spec,'NOW'); detail.spin.editor.setPlainText('LATER');detail.spin.apply.click()
    assert detail.value()=='LATER'
