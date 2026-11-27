import json
import shutil

import numpy as np
import pytest

from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.documents.synth_media import render_output_frame
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.documents.synth_starting_points import new_piece
from nebula.effects.synth_effects import effect_preset
from nebula.effects.synth_photocopy import render_photocopy
from nebula.render.synth import MODULE_BY_ID
from nebula.sources.synth_fonts import FONT_ROOT, reference_for_face


def plate(width=192, seconds=0., **changes):
    settings = {p.key: p.default for p in MODULE_BY_ID['photocopy'].params}
    settings.update(process=1, softness=0., edge_wear=0., light_depth=0., threshold=.5,
                    contrast=1., black=0., white=1., cadence=0., grain=0., pinholes=0.,
                    paper_grain=0., paper_tint=0., halftone=0.)
    settings.update(changes)
    image = np.zeros((width, width, 3), np.float32)
    image[:, width // 2:] = 1.
    return render_photocopy(image, settings, seconds, 283)


@pytest.mark.parametrize('setting,paper', [('paper_grain', True), ('paper_tint', True),
                                           ('grain', False), ('pinholes', False), ('edge_fade', False)])
def test_paper_and_ink_controls_are_independent(setting, paper):
    clean = plate()
    changed = plate(**{setting: .5})
    diff = np.abs(clean - changed)
    left, right = np.hsplit(diff, 2)
    active, other = (left, right) if paper else (right, left)
    assert active.max() > .01
    assert other.max() < 1e-6


def test_screen_crosses_the_ink_edge_and_resolves_into_tone_on_small_previews():
    settings = dict(halftone=.8, screen_angle=0., dot_size=8.)
    a = plate(360, **settings) - plate(360)
    # 180 pixels is an integer number of screen periods at this resolution.
    assert np.allclose(a[:, :180], a[:, 180:], atol=2e-5)
    assert a.std() > .02
    assert np.allclose(plate(90, **settings), plate(90))
    assert np.array_equal(plate(grain=1.), plate(seconds=2., grain=1.))
    assert not np.array_equal(plate(grain=1.), plate(seconds=2., grain=1., cadence=5.))


def test_independent_type_plates_follow_effect_order_and_survive_reopen(tmp_path):
    size = (144, 180)
    doc = new_piece('text', dict(width=size[0], height=size[1]), text='M')
    for key, y in [('type_overprint', .16), ('type_overprint@2', .84)]:
        entry = effect_preset(key)
        entry['params'].update({key+'.content': 'PAPER', key+'.light': 1., key+'.height': .08, key+'.y': y})
        doc['effects'][key] = entry
    dye = effect_preset('dye_transfer')
    dye['params'].update({'dye_transfer.cadence': 0., 'dye_transfer.emulsion': .1})
    doc['effects']['dye_transfer'] = dye
    doc['effect_order'] = ['dye_transfer', 'type_overprint', 'type_overprint@2']
    path = tmp_path/'plates.nebula'
    save_composition(path, doc)
    restored = load_composition(path)
    seq = compile_composition(restored)
    original = render_output_frame(None, seq, 0, size, None)
    preview = render_sequence_frame(seq, 1., size=size)
    assert original.tobytes() == preview.tobytes()
    restored['effects']['type_overprint@2']['params']['type_overprint@2.content'] = 'EDITION'
    edited = render_output_frame(None, compile_composition(restored), 0, size, None)
    changed = np.any(np.asarray(edited) != np.asarray(original), axis=2)
    assert changed[140:164].any() and not changed[:135].any()
    restored['effect_order'] = ['type_overprint', 'dye_transfer', 'type_overprint@2']
    reordered = render_output_frame(None, compile_composition(restored), 0, size, None)
    assert not np.array_equal(np.asarray(edited)[:55], np.asarray(reordered)[:55])


def test_moving_the_project_and_font_reconnects_exact_bytes_only(tmp_path):
    first = tmp_path/'first'
    first.mkdir()
    local_font = first/'local.ttf'
    shutil.copyfile(FONT_ROOT/'Anton-Regular.ttf', local_font)
    ref = reference_for_face(dict(path=local_font, family='Anton', style='Regular', postscript='Anton-Regular'))
    doc = new_piece('text', dict(width=144, height=180), text='TYPE')
    doc['source']['states']['blank']['overrides']['text.font'] = ref
    doc['effects']['type_overprint'] = effect_preset('type_overprint')
    doc['effects']['type_overprint']['params']['type_overprint.font'] = ref
    save_composition(first/'sample.nebula', doc)
    moved = first.rename(tmp_path/'moved')
    loaded = load_composition(moved/'sample.nebula')
    source = loaded['source']['states']['blank']['overrides']['text.font']
    assert json.loads(source)['path'] == str((moved/'local.ttf').resolve())
    assert loaded['effects']['type_overprint']['params']['type_overprint.font'] == source
    shutil.copyfile(FONT_ROOT/'ArchivoBlack-Regular.ttf', moved/'local.ttf')
    unresolved = load_composition(moved/'sample.nebula')
    assert unresolved['source']['states']['blank']['overrides']['text.font'] == ref
