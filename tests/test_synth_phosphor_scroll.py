"""Line timing, seek reproducibility and opt-in treatment contracts."""
import copy
import hashlib

import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_composition import compile_composition, load_composition, save_composition
from synth_curved_screen import render_curved_screen
from synth_echo import render_signal_etch
from synth_phosphor_recipes import PAGES, phosphor_scroll_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_starters import starter_composition
from synth_text import validate_text, wrapped_text, glyph_mask
from synth_text_scroll import scroll_mask


def params(module, **values):
    return dict({p.key:p.default for p in MODULE_BY_ID[module].params}, **values)


def test_scroll_advances_rows_without_resizing_previous_words():
    p = params('text', content='ONE\nTWO\nTHREE', reveal=5, scroll_rate=0.,
               size=.08, leading=1.25, fit=0, scroll_window=3, scroll_edge=0.)
    def mask(position):
        return np.asarray(scroll_mask(dict(p, scroll_position=position), 0, 1, (400,300), (400,300), (0,0)))
    assert not mask(0).any()
    first, second = mask(1), mask(2)
    # ONE shifts one stride (30 pixels), keeping its exact raster size.
    y = np.where(first.max(axis=1)>0)[0]
    assert np.array_equal(first[y[0]:y[-1]+1], second[y[0]-30:y[-1]+1-30])
    assert second.sum() > first.sum()
    assert not mask(3)[:int(246-90)].any()


def test_manual_lines_are_bounded_and_wrapping_terminates():
    text='\n'.join('ROW' for _ in range(32))
    assert validate_text(text)==text
    assert max(glyph_mask(text,0,0,1,1).size)<=4096
    wrapped, _ = wrapped_text(text,1)
    assert len(wrapped.splitlines())==32
    with pytest.raises(ValueError): validate_text(text+'\nROW')


def test_curved_screen_can_be_neutral_and_supports_other_canvas_shapes():
    arr=np.random.default_rng(4).random((60,80,3)).astype(np.float32)
    p=params('curved_screen', angle=0., curve=0., grid=0., background=0., patina=0., grain=0., drift=0.)
    assert np.allclose(render_curved_screen(arr,p,0,1,42,(80,60)),arr)
    for shape in ((120,40,3),(40,120,3)):
        out=render_curved_screen(np.zeros(shape,np.float32),params('curved_screen'),.3,1,5,(shape[1],shape[0]))
        assert out.shape==shape and np.isfinite(out).all() and out.max()>0


def test_curved_screen_without_new_motion_retains_0115_pixels():
    arr=np.random.default_rng(42).random((64,80,3),dtype=np.float32)
    out=render_curved_screen(arr,params('curved_screen'),.7,1,71,(80,64))
    # Captured from the 0.115.0 renderer before adding surface motion.
    assert hashlib.sha256(out.tobytes()).hexdigest() == '575aae0259c82b1e33ad3643f77b6c8ad51608f4fa71de1d25b2319fc34b240b'


@pytest.mark.parametrize('motion', ['vibration','flutter','breathing','boil'])
def test_surface_motion_animates_a_held_frame_and_seeks_repeatably(motion):
    arr=np.zeros((120,160,3),np.float32)
    arr[45:75,55:105]=.8
    p=params('curved_screen',grain=0.,drift=0.,rate=1.)
    p[motion]={'vibration':3.,'flutter':4.,'breathing':.12,'boil':1.}[motion]
    def render(t, speed=1.):
        return render_curved_screen(arr,p,t,speed,71,(160,120))
    first=render(.7)
    assert not np.array_equal(first,render(.7+1/24))
    assert not np.array_equal(first[:35,100:],render(.7+1/24)[:35,100:])
    render(10.)
    assert np.array_equal(first,render(.7))
    assert np.array_equal(render(.7,0.),render(10.,0.))
    p['rate']=0.
    assert np.array_equal(render(.7),render(10.))


def test_new_etch_controls_are_opt_in_and_random_seek_is_repeatable():
    arr=np.random.default_rng(4).random((60,80,3)).astype(np.float32)
    p=params('signal_etch')
    legacy={k:v for k,v in p.items() if not k.startswith(('organic','glint'))}
    baseline=render_signal_etch(arr,legacy,.4,1,71,(80,60))
    assert np.array_equal(baseline,render_signal_etch(arr,p,.4,1,71,(80,60)))
    p.update(organic=5.,glints=2.)
    first=render_signal_etch(arr,p,.4,1,71,(80,60))
    render_signal_etch(arr,p,8.,1,71,(80,60))
    assert np.array_equal(first,render_signal_etch(arr,p,.4,1,71,(80,60)))
    assert not np.array_equal(first,baseline)


def test_study_words_duration_cuts_roundtrip_and_editability(tmp_path):
    project=starter_composition('text-phosphor-scroll')
    assert project==phosphor_scroll_composition()
    sequence=compile_composition(project)
    assert round(sequence['duration']*sequence['fps'])==395
    assert not any(k in sequence for k in ('footage','soundtrack','generated_sound'))
    for time, wording in ((8.,PAGES[0]),(16.,PAGES[1])):
        source=next(m for m in resolve_sequence_frame(sequence,time)[-1]['modules'] if m['id']=='text')
        assert source['params']['content']==wording
    save_composition(tmp_path/'study.json',project)
    first=render_sequence_frame(sequence,8.,(240,180))
    assert first.tobytes()==render_sequence_frame(compile_composition(load_composition(tmp_path/'study.json')),8.,(240,180)).tobytes()
    changed=copy.deepcopy(project)
    changed['sections'][0]['effects']['text']={'mode':'recipe','params':{'text.content':'A\nNEW\nPHRASE'}}
    altered=compile_composition(changed)
    assert render_sequence_frame(altered,8.,(240,180)).tobytes()!=first.tobytes()
    assert render_sequence_frame(altered,16.,(240,180)).tobytes()==render_sequence_frame(sequence,16.,(240,180)).tobytes()


def test_curved_screen_accepts_video_and_zero_intensity_is_bypass():
    from PIL import Image
    p=default_synth_preset();p.update(width=80,height=64)
    for m in p['modules']:
        m['enabled']=m['id']=='curved_screen'
        if m['enabled']:m['params']['effect_intensity']=0.
    source=Image.new('RGB',(80,64),(50,100,150))
    assert render_synth_frame(p,source_image=source).tobytes()==source.tobytes()
