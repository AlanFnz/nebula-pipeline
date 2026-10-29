"""Editable printed type, optical finish, and the isolated Earth study."""
import copy

import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_composition import compile_composition, load_composition, save_composition
from synth_dye_transfer import render_dye_transfer
from synth_sequence import render_sequence_frame
from synth_text import badge_mask, glyph_mask, letterpress_settings
from scripts.create_earth_dreams_study import composition


def defaults(module):
    return {p.key: p.default for p in MODULE_BY_ID[module].params}


def test_letterpress_is_opt_in_and_seekable_with_held_reprints():
    args = ('THE EARTH', 1, .02, 1., 1)
    plain = glyph_mask(*args)
    p = defaults('text')
    assert not letterpress_settings(p, 100)
    assert glyph_mask(*args, press=letterpress_settings(p, 100)).tobytes() == plain.tobytes()
    p.update(press_height=.2, press_width=.1, press_angle=5, press_baseline=.04,
             press_seed=83, press_rate=10)
    at = lambda t: glyph_mask(*args, press=letterpress_settings(p, t))
    first = at(.21)
    at(19)
    assert first.tobytes() == at(.29).tobytes()
    assert first.tobytes() != at(.31).tobytes()
    assert first.tobytes() != plain.tobytes()
    p['press_rate'] = 0
    assert at(0).tobytes() == at(100).tobytes()
    previous = at(0).tobytes()
    p['press_seed'] += 1
    assert previous != at(0).tobytes()


@pytest.mark.parametrize('text', ['EARTH\nDREAMS', 'TIE\u0301RRA\nÉVEIL', 'W'*512])
def test_letterpress_reveal_keeps_layout_and_diacritics(text):
    press = (.5, .4, 15., .25, 35, 0)
    args = (text, 1, .01, 1.1, 1)
    full = glyph_mask(*args, press=press)
    partial = glyph_mask(*args, visible=2, press=press)
    empty = glyph_mask(*args, visible=0, press=press)
    assert full.size == partial.size == empty.size
    assert max(full.size) <= 4096
    assert 0 < np.asarray(partial).sum() < np.asarray(full).sum()
    assert np.all(np.asarray(partial) <= np.asarray(full))
    assert not empty.getbbox()


@pytest.mark.parametrize('mode', [0, 1, 2, 4])
def test_letterpress_is_used_by_supported_text_modes(mode):
    preset = default_synth_preset()
    for module in preset['modules']:
        module['enabled'] = module['id'] == 'text'
        if module['id'] == 'text':
            p = module['params']
            p.update(content='THE EARTH DREAMS THROUGH US', reveal=mode, word_seconds=.03)
    plain = render_synth_frame(preset, time_seconds=.45, size=(240,160))
    p.update(press_height=.35, press_angle=12, press_seed=77)
    printed = render_synth_frame(preset, time_seconds=.45, size=(240,160))
    assert plain.tobytes() != printed.tobytes()


def test_subtitle_width_keeps_legacy_alignment_and_anchors_word_builds():
    main = glyph_mask('THE EARTH', 1, .01, 1., 1)
    common = dict(shape=5, padding_x=0, padding_y=0, gap=5, subtitle_scale=.59)
    old = badge_mask(main, 'DREAMS', 1, 400, 0, **common)
    assert old.tobytes() == badge_mask(main, 'DREAMS', 1, 400, 0, subtitle_width=.975, **common).tobytes()
    left = badge_mask(main, 'DREAMS', 1, 400, 0, subtitle_width=.34, alignment=0, **common)
    right = badge_mask(main, 'DREAMS', 1, 400, 0, subtitle_width=.34, alignment=2, **common)
    assert np.array_equal(np.asarray(left)[:210], np.asarray(right)[:210])
    assert left.crop((0,215,left.width,left.height)).getbbox()[0] < 20
    assert right.crop((0,215,right.width,right.height)).getbbox()[0] > 500


def test_optical_controls_preserve_old_pixels_and_do_not_mutate_inputs():
    p = defaults('dye_transfer')
    a = np.zeros((90,160,3), np.float32); a[25:65,40:120] = 1
    keys = ('edge_leak','edge_leak_hue','edge_leak_width','edge_leak_x','tooth','ink_density')
    old = render_dye_transfer(a, {k:v for k,v in p.items() if k not in keys}, .2, 1, 53, (160,90))
    assert np.array_equal(old, render_dye_transfer(a,p,.2,1,53,(160,90)))
    original = a.copy()
    for key, value in [('edge_leak', .8), ('tooth', 2.), ('ink_density', 1.)]:
        settings = dict(p, **{key:value}); saved = copy.deepcopy(settings)
        result = render_dye_transfer(a,settings,.2,1,53,(160,90))
        assert not np.array_equal(result, old), key
        render_dye_transfer(a,settings,99,1,53,(160,90))
        assert np.array_equal(result, render_dye_transfer(a,settings,.21,1,53,(160,90)))
        assert np.array_equal(a,original) and settings == saved


def test_earth_study_shots_timing_and_independent_wording_round_trip(tmp_path):
    project, shots = composition()
    seq = compile_composition(project)
    assert seq['duration'] == 7.6 and seq['fps'] == 30
    assert seq['canvas'] == dict(width=720,height=406,framing='native')
    assert len(shots) == len(project['sections']) == 40
    assert [round(c['time']*30) for c in seq['cues']] == [s['frame'] for s in shots]
    assert not seq.get('footage') and not seq.get('soundtrack')
    first = render_sequence_frame(seq, .5, (180,102)).tobytes()
    project['sections'][4]['effects']['text'] = {'mode':'recipe','params':{'text.content':'WATER'}}
    changed = compile_composition(project)
    assert first != render_sequence_frame(changed, .5, (180,102)).tobytes()
    assert render_sequence_frame(seq, 2., (180,102)).tobytes() == render_sequence_frame(changed, 2., (180,102)).tobytes()
    save_composition(tmp_path/'earth.json',project)
    assert load_composition(tmp_path/'earth.json') == project

