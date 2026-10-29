from scripts.create_earth_dreams_study import composition
from synth_starters import starter_composition
from test_synth_effects_editor_integration import make_window


def test_native_letterpress_controls_are_editable_and_undoable(make_window):
    project, _ = composition()
    w = make_window(composition=project)
    w.edit_shot(4)
    obj = w.composer.object_panel
    obj.text_tabs.setCurrentIndex(1)
    control = obj.controls['text.press_height']
    assert not control.isHidden()
    assert control.input.value() == .24
    control.input.setValue(.12)
    assert w.composition['sections'][4]['effects']['text']['params']['text.press_height'] == .12
    w.undo_composition()
    assert obj.controls['text.press_height'].input.value() == .24
    w.set_composition(starter_composition('text-liquid-words'), guard=False)
    obj = w.composer.object_panel
    obj.text_tabs.setCurrentIndex(1)
    assert obj.controls['text.press_height'].isHidden()
