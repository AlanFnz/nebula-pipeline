"""Poster navigation and canvas gestures edit the same native parameters as export."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest

from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.documents.synth_poster import PosterFrame
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.documents.synth_starting_points import new_piece
from nebula.effects.synth_effects import effect_preset


def poster():
    doc = new_piece('poster', {'width': 320, 'height': 400}, text='O')
    for key, x in [('type_overprint', .25), ('type_overprint@2', .75)]:
        entry = effect_preset(key)
        entry['params'].update({key + '.x': x, key + '.content': 'caption'})
        doc['effects'][key] = entry
    doc['effect_order'] += ['type_overprint', 'type_overprint@2']
    doc['poster']['footer'] = ['type_overprint', 'type_overprint@2']
    return doc


def test_opt_in_keeps_pixels_and_lands_in_real_shapes(tmp_path):
    doc = poster()
    seq = compile_composition(doc)
    legacy = copy.deepcopy(doc)
    del legacy['poster']
    assert compile_composition(legacy) == seq
    path = tmp_path / 'edition.nebula'
    save_composition(path, doc)
    assert load_composition(path)['poster'] == doc['poster']
    frame = PosterFrame(seq, 0, doc['poster'])
    size = frame.canvas
    mask = frame.mask('text', size)
    assert mask.getbbox()
    l, t, r, b = mask.getbbox()
    center = ((l + r) / (2 * size[0]), (t + b) / (2 * size[1]))
    assert frame.pick(center, size) == 'plate'  # inside the O
    assert frame.pick((.02, .02), size) == 'paper'
    assert frame.pick((-.0001, .5), size) is None
    y, x = np.argwhere(np.asarray(mask) > 200)[0]
    assert frame.pick(((x+.5)/size[0], (y+.5)/size[1]), size) == 'text'
    for time in (0, 1.5):
        assert render_sequence_frame(seq, time, (160, 200)).tobytes() == render_sequence_frame(
            compile_composition(load_composition(path)), time, (160, 200)).tobytes()


def test_move_on_reframed_canvas_and_group_transaction():
    from nebula.core.synth_canvas import resize_canvas
    doc = poster()
    doc['canvas'] = resize_canvas(doc['canvas'], {'width': 480, 'height': 600}, fit=True)
    params = doc['effects']['dye_transfer']['params']
    params['dye_transfer.angle'] = 32.
    params['dye_transfer.scale'] = 1.2
    for key in ('plate', 'text', 'footer'):
        changed = copy.deepcopy(doc)
        frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
        frame.move(changed, key, -18., 11.)
        moved = PosterFrame(compile_composition(changed), 0., changed['poster'])
        for member in frame.footer if key == 'footer' else (key,):
            x, y = frame.center(member)
            assert moved.center(member) == pytest.approx((x-18, y+11))
        assert changed['sections'] == doc['sections']
    assert new_piece('text').get('poster') is None


def test_individual_caption_grain_survives_reload_and_leaves_other_ink_alone(tmp_path):
    doc = poster()
    key = 'type_overprint@2'
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    before = np.asarray(render_sequence_frame(compile_composition(doc), 0.))
    doc['effects'][key]['params'][key + '.ink_pinholes'] = 1.
    doc['effects'][key]['params'][key + '.ink_grain'] = .8
    path = tmp_path / 'print.nebula'
    save_composition(path, doc)
    seq = compile_composition(load_composition(path))
    after = np.asarray(render_sequence_frame(seq, 0.))
    changed = np.any(before != after, axis=2)
    assert changed.sum() > 12
    assert not changed[np.asarray(frame.mask(key, frame.canvas)) == 0].any()
    assert not changed[np.asarray(frame.mask('type_overprint', frame.canvas)) > 0].any()
    np.testing.assert_array_equal(after, np.asarray(render_sequence_frame(seq, 0.)))


def test_texture_controls_track_print_order():
    doc = poster()
    doc['effects']['photocopy'] = effect_preset('photocopy')
    doc['effects']['photocopy']['params']['photocopy.process'] = 1
    doc['effect_order'] = ['type_overprint', 'photocopy', 'dye_transfer', 'type_overprint@2']
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    assert 'photocopy.paper_grain' in frame.texture_paths('paper')[0]
    assert 'dye_transfer.dry_ink' in frame.texture_paths('type_overprint')[1]
    assert 'photocopy.pinholes' in frame.texture_paths('text')[1]
    assert frame.texture_paths('type_overprint@2')[1] == ()
    assert frame.texture_paths('footer') == ((), ())
    doc['effects']['dye_transfer']['bypassed'] = True
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    assert 'text.paper_grain' in frame.texture_paths('paper')[0]
    assert 'dye_transfer.dry_ink' not in frame.texture_paths('text')[1]


@pytest.mark.parametrize('reveal', [0, 5])
def test_source_ink_grain_moves_with_the_type_and_exposes_its_background(reveal):
    from nebula.sources.synth_text import placed_text_mask, render_text
    doc = poster()
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    params = dict(frame.modules['text'], content='PRINT', reveal=reveal, scroll_position=1.,
                  scroll_rate=0., size=.19, rotation=0., motion=0, opacity=1., brightness=1.,
                  saturation=0., back_brightness=.15, back_saturation=0.)
    width, height = frame.canvas
    pixels = np.zeros((height, width, 3), np.float32)
    preset = dict(frame.preset, object_x=0., object_y=0.)
    clean = render_text(pixels, params, 0., preset)
    params.update(ink_grain=.85, ink_pinholes=.7, ink_grain_size=2.4)
    dry = render_text(pixels, params, 0., preset)
    mask = np.asarray(placed_text_mask(params, 0., preset, frame.canvas))
    np.testing.assert_array_equal(dry[mask == 0], clean[mask == 0])
    assert np.max(clean - dry) > .1
    moved = render_text(pixels, params, 0., dict(preset, object_x=8.))
    np.testing.assert_allclose(moved[:, 8:], dry[:, :-8], atol=1e-6)
