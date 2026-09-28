"""Text remains editable and portable while using the existing effect pipeline."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset, normalize_synth, render_synth_frame
from synth_broadcast import render_broadcast
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_effects import normalize_effects
from synth_sequence import render_sequence_frame
from synth_source_adapters import source_frame
from synth_starters import starter_composition
from synth_subject import select_subject, restore_subject
from synth_text import glyph_mask, validate_text, text_pose


def source(**changes):
    p = default_synth_preset(); p.update(width=400, height=300, speed=1.)
    for m in p['modules']:
        m['enabled'] = m['id'] == 'text'
        if m['id'] == 'text': m['params'].update(back_brightness=0., saturation=0., content='NOW', size=.12, **changes)
    return p


def extent(image):
    y,x = np.where(np.asarray(image).max(axis=2) > 100)
    return (int(x.min()), int(y.min()), int(x.max()), int(y.max()))


def test_fonts_have_pinned_bytes_and_bundled_licenses():
    root = Path('assets/fonts'); manifest = json.loads((root/'sources.json').read_text())
    for name, item in manifest['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == item['sha256']
    assert len(list(root.glob('*OFL.txt'))) == 3
    masks = [glyph_mask('REVOLUCIÓN\nis now?', font, .02, 1., 1) for font in range(3)]
    assert len({m.tobytes() for m in masks}) == 3
    assert all(m.getbbox() and max(m.size) <= 4096 for m in masks)


@pytest.mark.parametrize('value', [123, 'a' * 513, '\n' * 8, 'a\x00b', '\ud800'])
def test_invalid_text_is_rejected_in_documents_and_effects(value):
    with pytest.raises(ValueError): validate_text(value)
    p=source(); next(m for m in p['modules'] if m['id']=='text')['params']['content']=value
    with pytest.raises(ValueError): normalize_synth(p)
    with pytest.raises(ValueError): normalize_effects({'text': {'params': {'text.content': value}}})


def test_reveal_keeps_full_phrase_layout_and_blank_text_is_valid():
    args=('REVOLUTION\nIS NOW', 0, .01, .9, 1)
    full=glyph_mask(*args); partial=glyph_mask(*args, 4); empty=glyph_mask(*args, 0)
    assert full.size == partial.size == empty.size
    assert 0 < np.asarray(partial).sum() < np.asarray(full).sum()
    assert not empty.getbbox()
    assert validate_text('') == ''
    p=source(); next(m for m in p['modules'] if m['id']=='text')['params']['content']=''
    assert not np.asarray(render_synth_frame(p)).any()


def test_text_resize_preserves_size_and_position_moves_subject_pixels():
    p=source(); initial=extent(render_synth_frame(p))
    q=copy.deepcopy(p); q.update(resize_canvas(p, {'width': 600, 'height': 800}))
    reframed=extent(render_synth_frame(q))
    assert reframed == tuple(v+d for v,d in zip(initial,(100,250,100,250)))
    q.update(object_x=40.,object_y=-30.)
    moved=extent(render_synth_frame(q))
    assert moved == tuple(v+d for v,d in zip(reframed,(40,-30,40,-30)))
    anchor=source_frame(q,(600,800),.5)
    assert anchor.origin == (340.,370.)


def test_text_motion_has_its_own_cadence_and_preserves_random_seeking():
    p=source(motion=1,cadence=12.,period=2.,zoom_start=2.,zoom_end=.5,ease=3.)
    spec=next(m['params'] for m in p['modules'] if m['id']=='text')
    assert text_pose(spec,.01,1) == text_pose(spec,.07,1)
    first=render_synth_frame(p,time_seconds=.3)
    render_synth_frame(p,time_seconds=4.2)
    assert first.tobytes() == render_synth_frame(p,time_seconds=.3).tobytes()
    assert first.tobytes() != render_synth_frame(p,time_seconds=.5).tobytes()
    assert text_pose(spec,0,1)[1]-text_pose(spec,.5,1)[1] > text_pose(spec,1,1)[1]-text_pose(spec,1.5,1)[1]


@pytest.mark.parametrize('look', ('phosphor','pressure','transmission','night'))
def test_text_study_round_trip_and_editable_source(look,tmp_path):
    p=starter_composition('text-'+look); original=copy.deepcopy(p)
    p['effects']['text']={'mode':'recipe','params':{'text.content':'REVOLUCIÓN\nES AHORA'}}
    seq=compile_composition(p); path=tmp_path/'text.json'; save_composition(path,p)
    a=render_sequence_frame(seq,.45,(180,135))
    assert render_sequence_frame(compile_composition(load_composition(path)),.45,(180,135)).tobytes()==a.tobytes()
    assert render_sequence_frame(compile_composition(original),.45,(180,135)).tobytes()!=a.tobytes()
    assert starter_composition('text-'+look)==original


def test_text_is_a_reversible_object_choice_in_an_existing_study():
    original=starter_composition('refined'); changed=select_subject(original,'text')
    assert changed['sections']==select_subject(original,'text')['sections']
    seq=compile_composition(changed)
    assert all('text' in s['enabled'] and 'slab' not in s['enabled'] for s in seq['states'].values())
    restored=compile_composition(restore_subject(changed))
    assert render_sequence_frame(restored,.5,(120,96)).tobytes()==render_sequence_frame(compile_composition(original),.5,(120,96)).tobytes()


def test_broadcast_is_source_independent_and_stateless():
    p={s.key:s.default for s in MODULE_BY_ID['broadcast'].params}
    image=np.full((80,100,3),.15,dtype=np.float32)
    assert render_broadcast(image,dict(p,mix=0.),1.,1.,7) is image
    a=render_broadcast(image,p,.4,1.,7)
    assert not np.array_equal(a,image)
    assert np.array_equal(a,render_broadcast(image,p,.4,1.,7))
    p.update(field=0.,curve=0.,vignette=0.,static=1.,phase=0.,duration=.2,period=2.)
    assert np.array_equal(render_broadcast(image,p,.5,1.,7),image)
    assert not np.array_equal(render_broadcast(image,p,.1,1.,7),image)
