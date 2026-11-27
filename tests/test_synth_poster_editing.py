"""Artwork depth, canvas gestures and the poster export entry point."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest

from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.documents.synth_poster import PosterFrame
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.documents.synth_starting_points import new_piece


def printed_words():
    doc = new_piece('poster', {'width': 200, 'height': 250}, text='O')
    key = 'type_overprint'
    doc['effects'][key] = {'mode': 'on', 'params': {key+'.content': 'Ink', key+'.height': .15,
                           key+'.y': .53, key+'.light': 1., key+'.saturation': 0.}}
    doc['effect_order'].insert(0, key)
    return doc


def test_artwork_stack_retains_print_and_visibility_across_export(tmp_path):
    doc = printed_words()
    original = copy.deepcopy(doc)
    def pixels(document):
        return np.asarray(render_sequence_frame(compile_composition(document), 0.))
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    word = 'type_overprint'
    ink = np.asarray(frame.mask(word, frame.canvas)) > 230
    plate = np.asarray(frame.mask('plate', frame.canvas, material=True)) > 249
    clean = pixels(doc)
    doc['poster']['hidden'] = [word, 'text']
    plate_only = pixels(doc)
    doc['poster']['hidden'] = ['text']
    doc['poster']['order'] = ['plate', word, 'text']
    changed = pixels(doc)
    region = ink & plate
    assert region.sum() > 30
    assert np.abs(changed[region].astype(float) - plate_only[region]).mean() < 4.
    assert np.abs(clean[region].astype(float) - changed[region]).mean() > 25.
    saved = tmp_path / 'print.nebula'
    save_composition(saved, doc)
    np.testing.assert_array_equal(changed, pixels(load_composition(saved)))
    assert doc['effect_order'] == original['effect_order']
    doc['poster'] = original['poster']
    np.testing.assert_array_equal(clean, pixels(doc))


def test_independent_copies_and_new_plate():
    doc = printed_words()
    key = 'type_overprint'
    section = doc['sections'][0]
    section['effects'][key] = {'mode': 'recipe', 'params': {key+'.height': .21}}
    frame = PosterFrame(compile_composition(doc), 0, doc['poster'])
    clone = frame.add_layer(doc, 'text', duplicate=key, above=key)
    assert section['effects'][clone]['params'][clone+'.height'] == .21
    section['effects'][clone]['params'][clone+'.height'] = .32
    after = PosterFrame(compile_composition(doc), 0, doc['poster'])
    assert after.modules[key]['height'] == .21 and after.modules[clone]['height'] == .32
    shape = after.add_layer(doc, 'plate', above=clone)
    after = PosterFrame(compile_composition(doc), 0, doc['poster'])
    assert after.by_key[shape].kind == 'plate' and after.order.index(shape) < after.order.index(clone)
    source = after.add_layer(doc, 'text', duplicate='text', above='text')
    after = PosterFrame(compile_composition(doc), 0, doc['poster'])
    assert after.mask(source, after.canvas).tobytes() == after.mask('text', after.canvas).tobytes()
    assert after.modules[source]['layout'] == 1
