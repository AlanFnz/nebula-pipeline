"""Independent material and disc clocks, backwards compatibility and editable stops."""
import numpy as np
from PySide6.QtWidgets import QDialog

from nebula.documents.synth_composition import compile_composition, composition_from_sequence, stretch_section
from nebula.documents.synth_sequence import normalize_sequence, render_sequence_frame
from nebula.ui.synth_color_ui import ColorPicker
from test_synth_effects_editor_integration import make_window


def composition(**params):
    overrides = {'radial_bloom.' + key: value for key, value in params.items()}
    overrides['speed'] = 1.0
    state = dict(preset='Reference blinds', enabled=['radial_bloom'], overrides=overrides)
    sequence = normalize_sequence(dict(schema_version=1, render_version=2, name='Gradient test',
        duration=4., fps=24, states={'source': state}, cues=[dict(time=0., state='source', transition='cut')]))
    return composition_from_sequence(sequence)


def frame(project, seconds):
    return render_sequence_frame(compile_composition(project), seconds, (96, 80)).tobytes()


def test_new_controls_are_opt_in_and_extend_uses_the_same_clock():
    assert frame(composition(), .5) == frame(composition(pattern=0, pan_y=.8, copies=3), .5)
    project = composition(pattern=1, cycle=2., motion_period=2., rotation=0., disc_travel_x=.35)
    assert frame(project, 0.) == frame(project, 2.)
    assert frame(project, .25) != frame(project, 1.)
    longer = stretch_section(project, project['sections'][0]['id'], 8., 'smart')
    assert frame(longer, 3.75) == frame(project, 3.75)
    assert frame(longer, 4.25) == frame(project, .25)


def test_disc_motion_is_independent_of_color_playback_and_direction():
    settings = dict(pattern=1, cycle=2., motion_period=2., rotation=0.)
    forward = composition(**settings)
    backward = composition(direction=1, **settings)
    assert frame(forward, .25) == frame(backward, 1.75)
    held = composition(direction=2, **settings)
    assert frame(held, 0.) == frame(held, 1.)
    moving = composition(direction=2, disc_travel_y=.7, **settings)
    assert frame(moving, 0.) != frame(moving, 1.)


def test_coincident_stops_wrap_cleanly_and_last_color_wins():
    params = {f'stop_{i}_position': float(i % 2) for i in range(1, 9)}
    project = composition(pattern=1, stop_8_saturation=0., stop_8_light=.25, **params)
    pixels = np.frombuffer(frame(project, 1.), dtype=np.uint8)
    assert np.ptp(pixels) == 0
    assert 63 <= pixels[0] <= 64


def test_object_palette_edit_can_be_undone_as_one_change(make_window, monkeypatch):
    window = make_window(composition=composition(pattern=1))
    composer = window.composer
    obj = composer.object_panel
    composer.look_tabs.setCurrentWidget(obj)
    assert obj.color_panel.chip_row.isVisible()
    assert 'radial_bloom.copy_angle' in obj.object_eligible
    assert 'radial_bloom.petals' not in obj.object_eligible
    before = composer.document
    def choose(dialog):
        dialog.select_swatch((.33, .44, .55))
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ColorPicker, 'exec', choose)
    obj.color_panel.chips['radial_stop_4'].click()
    assert composer.color_context('radial_stop_4')['hsv'] == (.33, .44, .55)
    window.undo_composition()
    assert composer.document == before
