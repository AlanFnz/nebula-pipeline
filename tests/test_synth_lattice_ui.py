import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from test_synth_composer_ui import window, wait_until
from nebula.documents.synth_starters import starter_composition


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
    panel=composer.object_editor
    assert panel.effect_id=='chromatic_lattice'
    assert not panel.remove_button.isVisible()
    panel.reveal_control('chromatic_lattice.shape')
    panel.controls['chromatic_lattice.shape'].input.setCurrentIndex(0)
    assert panel.controls['chromatic_lattice.sides'].isHidden()
    wait_until(lambda:not window.render_running and not window.render_queued)


def test_timing_note_follows_the_visual_clock_and_preserves_free_periods(window):
    window.set_composition(starter_composition('chromatic-lattice'))
    obj = window.composer.object_panel
    controls = obj.controls
    group = obj.object_groups['Rhythm & timing']
    mode = controls['chromatic_lattice.color_rhythm'].input
    mode.setCurrentIndex(0)
    controls['chromatic_lattice.period'].input.setValue(7.5)
    assert 'separate periods' in group.summary.text()
    mode.setCurrentIndex(1)
    controls['chromatic_lattice.bpm'].input.setValue(96)
    controls['chromatic_lattice.phrase_bars'].input.setValue(2)
    assert '96 BPM · 2 bars of 4/4 · 5 s at 1× before retiming' in group.summary.text()
    controls['chromatic_lattice.bpm'].input.setValue(120)
    controls['chromatic_lattice.phrase_bars'].input.setValue(1)
    assert '120 BPM · 1 bar of 4/4 · 2 s' in group.summary.text()
    obj.set_automation_counts({'chromatic_lattice.bpm': 1})
    assert 'current tempo' in group.summary.text()
    assert '2 s' not in group.summary.text()
    mode.setCurrentIndex(0)
    assert 'separate periods' in group.summary.text()
    assert controls['chromatic_lattice.period'].input.value() == 7.5
    wait_until(lambda: not window.render_running and not window.render_queued)
