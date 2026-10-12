"""Whole-word morphs remain readable, seekable and compatible with old studies."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_contour import render_contour_melt
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_text import text_layout
from synth_word_morph import word_state, word_field, morph_progress


def params(**changes):
    return dict({s.key: s.default for s in MODULE_BY_ID['text'].params},
                **dict(reveal=3, morph_flow=0., morph_hold=1., morph_seconds=1., **changes))


def test_phrase_reads_in_order_and_final_word_holds_until_clip_end():
    assert word_state('REVOLUTION IS NOW', .9, 1., 1., False) == ('REVOLUTION', 'IS', 0.)
    assert word_state('REVOLUTION IS NOW', 1.5, 1., 1., False) == ('REVOLUTION', 'IS', .5)
    assert word_state('REVOLUTION IS NOW', 2., 1., 1., False) == ('IS', 'NOW', 0.)
    assert word_state('REVOLUTION IS NOW', 99., 1., 1., False) == ('NOW', 'NOW', 0.)
    assert word_state('REVOLUTION IS NOW', 5.5, 1., 1., True) == ('NOW', 'REVOLUTION', .5)
    assert word_state('REVOLUTION IS NOW', 6., 1., 1., True) == ('REVOLUTION', 'IS', 0.)


@pytest.mark.parametrize('content', ('', '   ', 'NOW', 'I REVOLUTION', 'REVOLUCIÓN ES AHORA', 'W' * 512))
def test_bounded_layout_handles_empty_unicode_single_and_long_words(content):
    p = params(content=content)
    image, sx, sy = text_layout(p, 1.5, 1., (720, 900))
    assert max(image.size) <= 576 and sx > 0 and sy > 0
    assert bool(image.getbbox()) == bool(content.strip())
    assert word_field.cache_info().maxsize == 24


def test_morph_transports_ink_instead_of_dissolving_between_two_pictures():
    p = params(content='REVOLUTION IS', font=3, weight=800)
    first = np.asarray(text_layout(p, 0., 1., (720, 900))[0]) / 255.
    middle = np.asarray(text_layout(p, 1.5, 1., (720, 900))[0]) / 255.
    last = np.asarray(text_layout(p, 2., 1., (720, 900))[0]) / 255.
    assert np.mean(np.abs(middle - (first + last) / 2)) > .01
    # A crisp moving silhouette, rather than two faint superimposed words.
    assert np.mean(middle[middle > .05] > .8) > .7
    assert middle.sum() > min(first.sum(), last.sum()) * .5
    before_boundary = np.asarray(text_layout(p, 1.99999, 1., (720, 900))[0]).astype(float)
    assert np.mean(abs(before_boundary - last * 255)) < .05


def test_morph_easing_speed_and_cadence_have_independent_clocks():
    p = params(content='ONE TWO', cadence=10.)
    assert text_layout(p, 1.21, 1., (300, 400))[0].tobytes() == text_layout(p, 1.29, 1., (300, 400))[0].tobytes()
    assert text_layout(p, .61, 2., (300, 400))[0].tobytes() == text_layout(p, 1.22, 1., (300, 400))[0].tobytes()
    linear = dict(p, morph_ease=0.)
    assert text_layout(p, 1.2, 1., (300, 400))[0].tobytes() != text_layout(linear, 1.2, 1., (300, 400))[0].tobytes()


def test_study_is_editable_roundtrips_and_is_independent_of_seek_order(tmp_path):
    project = starter_composition('text-liquid-words')
    original = copy.deepcopy(project)
    project['effects']['text'] = {'mode': 'recipe', 'params': {'text.content': 'WE ARE HERE', 'text.morph_seconds': .45}}
    path = tmp_path / 'words.json'; save_composition(path, project)
    seq = compile_composition(load_composition(path))
    a = render_sequence_frame(seq, 1.5, (240, 300))
    render_sequence_frame(seq, 5., (240, 300))
    assert render_sequence_frame(seq, 1.5, (240, 300)).tobytes() == a.tobytes()
    assert render_sequence_frame(compile_composition(original), 1.5, (240, 300)).tobytes() != a.tobytes()
    assert starter_composition('text-liquid-words') == original


def test_morph_canvas_resize_preserves_letter_proportions_and_position():
    p = default_synth_preset(); p.update(width=400, height=300, speed=1.)
    p['modules'] = [dict(id='text', enabled=True, params=params(content='IS NOW'))]
    before = np.asarray(render_synth_frame(p, time_seconds=1.5))
    p.update(resize_canvas(p, {'width':600, 'height':800}))
    p.update(object_x=30., object_y=-20.)
    after = np.asarray(render_synth_frame(p, time_seconds=1.5))
    assert np.array_equal(before, after[230:530, 130:530])


def test_contours_bypass_exactly_and_work_on_non_text_sources():
    p = {s.key:s.default for s in MODULE_BY_ID['contour_melt'].params}
    black = np.zeros((180, 240, 3), dtype=np.float32)
    assert not render_contour_melt(black, p, .5, 1., 17, (240,180)).any()
    image = black.copy(); image[35:140, 55:180] = .9
    assert render_contour_melt(image, dict(p, mix=0.), .5, 1., 17, (240,180)) is image
    a = render_contour_melt(image, p, .5, 1., 17, (240,180))
    assert not np.array_equal(a, image)
    assert np.array_equal(a, render_contour_melt(image, p, .5, 1., 17, (240,180)))
    preset = default_synth_preset(); preset.update(width=240, height=180)
    preset['modules'] = [dict(id='contour_melt', enabled=True, params=p)]
    rendered = render_synth_frame(preset, time_seconds=.5, source_image=Image.fromarray(np.uint8(image * 255)))
    assert rendered.size == (240,180)


def test_first_liquid_words_keeps_012_pixels():
    hashes = json.loads(Path('tests/fixtures/text-liquid-words-v1-hashes.json').read_text())
    seq = compile_composition(starter_composition('text-liquid-words-original'))
    for time, expected in hashes.items():
        assert hashlib.sha256(render_sequence_frame(seq, float(time), (288,360)).tobytes()).hexdigest() == expected


def test_soft_motion_liquid_words_keeps_013_pixels():
    hashes = json.loads(Path('tests/fixtures/text-liquid-words-v2-hashes.json').read_text())
    seq = compile_composition(starter_composition('text-liquid-words-soft'))
    for time, expected in hashes.items():
        assert hashlib.sha256(render_sequence_frame(seq, float(time), (288,360)).tobytes()).hexdigest() == expected


def test_fast_attack_moves_early_then_decelerates_without_progress_reversal():
    for snap in (0., .3, .8, 1.):
        curve = np.array([morph_progress(t, 1., snap) for t in np.linspace(0,1,101)])
        assert curve[0] == 0. and curve[-1] == 1.
        assert np.min(np.diff(curve)) >= -1e-12
        assert curve[1] < .001 and 1 - curve[-2] < .001
    assert morph_progress(.3, 1., .8) > .65
    assert morph_progress(.3, 1., 0.) < .2
    assert morph_progress(.37, 0., 1.) == .37  # no easing means linear


def test_liquid_words_holds_keep_a_lit_body_under_the_moving_contours():
    project = starter_composition('text-liquid-words')
    plain = copy.deepcopy(project)
    plain['source']['states']['words']['enabled'] = ['text']
    sequence, bare = compile_composition(project), compile_composition(plain)
    # Sample both the long word and NOW through their exposure cycle. Most of
    # the letter body must remain lit, rather than reducing to faint outlines.
    for time in (0., .4, .8, 1.2, 4., 4.4, 4.8, 5.2, 5.6, 5.96):
        image = np.asarray(render_sequence_frame(sequence,time,(500,400))).max(axis=2)
        mask = np.asarray(render_sequence_frame(bare,time,(500,400))).max(axis=2) > 128
        assert (image[mask] > 75).mean() > .8


def test_elastic_strokes_land_continuously_and_seek_without_history():
    p = params(content='REVOLUTION IS NOW', font=4, weight=900,
               morph_snap=.8, morph_settle=.65, morph_roundness=.45)
    def ink(time, settings=p):
        return np.asarray(text_layout(settings, time, 1., (1000,800))[0]).astype(float)
    plain = dict(p, morph_settle=0.)
    assert np.mean(abs(ink(1.3) - ink(1.3,plain))) > .1
    for boundary in (1., 2., 3., 4.):
        assert np.mean(abs(ink(boundary-1e-6) - ink(boundary))) < .05
    middle = ink(1.3)
    ink(100.)
    assert np.array_equal(ink(1.3),middle)
    assert np.array_equal(ink(0.),ink(0.,plain))
    assert np.array_equal(ink(4.),ink(4.,plain))


def test_living_words_remain_continuous_at_transition_end_and_seekable():
    p = params(content='REVOLUTION IS NOW', font=4, weight=800, morph_roundness=.45, morph_living=.55)
    first = np.asarray(text_layout(p, .1, 1., (720,900))[0]).astype(float)
    later = np.asarray(text_layout(p, .8, 1., (720,900))[0]).astype(float)
    assert np.mean(abs(first - later)) > .1  # holds remain alive
    before = np.asarray(text_layout(p, 1.999999, 1., (720,900))[0]).astype(float)
    after = np.asarray(text_layout(p, 2., 1., (720,900))[0]).astype(float)
    assert np.mean(abs(before - after)) < .05
    assert text_layout(p, .1, 1., (720,900))[0].tobytes() == first.astype('uint8').tobytes()


def test_refined_words_canvas_resize_preserves_rounded_animated_geometry():
    p = default_synth_preset(); p.update(width=400, height=300, speed=1.)
    p['modules'] = [dict(id='text', enabled=True, params=params(content='IS NOW', font=4,
        weight=800, morph_roundness=.7, morph_living=.8, morph_snap=.8, morph_settle=.65))]
    before = np.asarray(render_synth_frame(p, time_seconds=1.5))
    p.update(resize_canvas(p, {'width':600, 'height':800}))
    after = np.asarray(render_synth_frame(p, time_seconds=1.5))
    assert np.array_equal(before, after[250:550, 100:500])


def test_inset_ink_preserves_black_and_letter_gaps_and_has_editable_groove():
    p = {s.key:s.default for s in MODULE_BY_ID['contour_melt'].params}
    p.update(style=1, hollow=0., fill=1., glow=0., softness=0., grain=0., groove=1.)
    blank = np.zeros((160,240,3), dtype=np.float32)
    assert not render_contour_melt(blank,p,0.,1.,17,(720,480)).any()
    ink = blank.copy(); ink[30:130,40:110] = 1.; ink[30:130,116:186] = 1.
    out = render_contour_melt(ink,p,.3,1.,17,(720,480))
    assert out[80,113].max() < .01  # preserve the six-pixel gap
    plain = render_contour_melt(ink,dict(p,groove=0.),.3,1.,17,(720,480))
    assert (plain - out)[ink[...,0] > 0].mean() > .05
    assert not (plain - out)[ink[...,0] == 0].any()
    hollow = render_contour_melt(ink,dict(p,fill=0.),.3,1.,17,(720,480))
    assert hollow[80,75].max() < .001 and hollow.max() > .5
    assert np.array_equal(out,render_contour_melt(ink,p,.3,1.,17,(720,480)))
    assert render_contour_melt(ink,dict(p,mix=0.),.3,1.,17,(720,480)) is ink
    preset = default_synth_preset(); preset.update(width=240,height=160)
    preset['modules'] = [dict(id='contour_melt',enabled=True,params=p)]
    footage = Image.fromarray(np.uint8(ink * 255))
    rendered = render_synth_frame(preset,time_seconds=.3,source_image=footage)
    assert rendered.size == footage.size and rendered.tobytes() != footage.tobytes()
