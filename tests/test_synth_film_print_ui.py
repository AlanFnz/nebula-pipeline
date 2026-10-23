import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from test_synth_composer_ui import window, wait_until
from synth_starters import starter_composition


def test_print_inspector_edits_and_undo_preserve_authored_montage(window):
    window.set_composition(starter_composition('text-film-burn'))
    panel=window.composer.effects_panel
    window.composer.look_tabs.setCurrentWidget(panel)
    panel.inspect_effect('text')
    panel.reveal_control('text.weight')
    assert not panel.controls['text.weight'].isHidden()
    panel.inspect_effect('film_burn')
    panel.reveal_control('film_burn.grain')
    assert not panel.controls['film_burn.grain'].isHidden()
    panel.controls['film_burn.grain'].input.setValue(.12)
    assert window.composition['effects']['film_burn']['params']['film_burn.grain']==.12
    assert len(window.composition['source']['cues'])==123
    window.undo_composition()
    assert panel.controls['film_burn.grain'].input.value()==.075
    panel.inspect_effect('print_collage')
    panel.reveal_control('print_collage.weave')
    panel.controls['print_collage.weave'].input.setValue(.01)
    assert window.composition['effects']['print_collage']['params']['print_collage.weave']==.01
    window.undo_composition()
    assert panel.controls['print_collage.weave'].input.value()==.003
    wait_until(lambda: not window.render_running and not window.render_queued)
