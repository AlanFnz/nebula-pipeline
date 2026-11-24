"""Independent material and disc clocks, backwards compatibility and editable stops."""
import copy
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


def test_disc_wiggle_is_delayed_radius_relative_and_loopable():
    from nebula.sources.synth_radial_gradients import _wiggle_offsets
    p = dict(copies=5, wiggle_amount=2., wiggle_lag_ms=50, motion_period=6., motion_phase=.25)
    offsets = _wiggle_offsets(p, .875)
    assert offsets[0] == (0., 0.)
    assert offsets[1] != offsets[2]
    np.testing.assert_allclose(offsets[2:], _wiggle_offsets(p, .825)[1:-1], atol=1e-12)
    np.testing.assert_allclose(offsets, _wiggle_offsets(p, 6.875), atol=1e-12)
    np.testing.assert_allclose(np.asarray(offsets) * 2, _wiggle_offsets(dict(p, wiggle_amount=4.), .875))
    assert len(set(_wiggle_offsets(dict(p, wiggle_lag_ms=0), .875)[1:])) == 1


def test_wiggle_moves_inner_discs_with_a_held_palette_and_survives_extend():
    params = dict(pattern=1, direction=2, rotation=0., motion_period=2., expansion=.6)
    original = composition(**params)
    assert frame(original, .25) == frame(composition(**params, wiggle_amount=0., wiggle_lag_ms=200), .25)
    one_disc = composition(**params, copies=1, wiggle_amount=8.)
    assert frame(one_disc, .25) == frame(composition(**params, copies=1), .25)
    project = composition(**params, wiggle_amount=3., wiggle_lag_ms=50)
    first = frame(project, .25)
    assert first != frame(original, .25)
    assert first != frame(project, .75)
    assert first == frame(project, 2.25)
    longer = stretch_section(project, project['sections'][0]['id'], 8., 'smart')
    assert first == frame(longer, 4.25)


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


def test_palette_menu_preserves_geometry_and_restores_authored_colors(make_window, tmp_path):
    from nebula.documents.synth_composition import load_composition, save_composition
    from nebula.sources.synth_radial_palettes import PALETTES, palette_values
    doc = composition(pattern=1)
    doc['effects']['radial_bloom'] = dict(mode='recipe', params={
        'radial_bloom.center_x': -.5, 'radial_bloom.stop_3_position': .41})
    window = make_window(composition=doc)
    composer = window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    menu = composer.object_panel.palette_selector.combo
    before = copy.deepcopy(composer.document)
    assert menu.currentText() == 'Study colors'
    assert menu.count() == len(PALETTES) + 2
    for palette in PALETTES:
        menu.activated.emit(menu.findData(palette.key))
        expected = copy.deepcopy(before)
        expected['effects']['radial_bloom']['params'].update(palette_values(palette))
        assert composer.document == expected
        assert menu.currentData() == palette.key
    path = tmp_path / 'palette.nebula'
    save_composition(path, composer.document)
    assert load_composition(path) == composer.document
    composer.change_color('radial_stop_4', (.3, .4, .5), None)
    assert menu.currentData() is None
    window.undo_composition()
    assert menu.currentData() == PALETTES[-1].key
    menu.activated.emit(menu.findData('inherit'))
    assert composer.document == before
    window.undo_composition()
    assert composer.document == expected


def test_clip_palette_inheritance_and_crowns_visibility(make_window):
    doc = composition(pattern=1)
    other = copy.deepcopy(doc['sections'][0])
    other['id'] = 'other'
    doc['sections'].append(other)
    window = make_window(composition=doc)
    composer = window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    menu = composer.object_panel.palette_selector.combo
    menu.activated.emit(menu.findData('jade'))
    shared = copy.deepcopy(composer.document)
    composer.select_section(1)
    assert menu.currentText() == 'Composition colors'
    menu.activated.emit(menu.findData('ember'))
    assert composer.document['sections'][0] == shared['sections'][0]
    assert composer.document['effects'] == shared['effects']
    menu.activated.emit(menu.findData('inherit'))
    assert composer.document == shared
    crowns = make_window(composition=composition(pattern=0)).composer
    crowns.look_tabs.setCurrentWidget(crowns.object_panel)
    assert crowns.object_panel.palette_selector.isHidden()
