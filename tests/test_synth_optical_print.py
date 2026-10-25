"""Portable, opt-in optical printing and semantic text readability."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFilter

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_automation import TARGETS, target_parameter
from synth_composition import compile_composition, save_composition, load_composition
from synth_effect_catalog import effect_catalog
from synth_effects import effect_preset
from synth_optical_print import render_optical_print, exposure_at
from synth_optical_recipes import dark_print_composition
from synth_reading_montage import ReadingBeat, reading_schedule
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_video import VIDEO_EFFECTS, VIDEO_MODULES


def defaults():
    return {p.key: p.default for p in MODULE_BY_ID['optical_print'].params}


def source(size=(128,96)):
    w,h=size
    a=np.zeros((h,w,3),np.float32)
    a[h//4:3*h//4,w//5:4*w//5]=1
    a[h//3:2*h//3,2*w//5:3*w//5]=0
    return a


def test_deterministic_seeking_cadence_and_input_ownership():
    a=source(); original=a.copy(); p=defaults(); saved=copy.deepcopy(p)
    first=render_optical_print(a,p,1.,1.,23,(128,96))
    render_optical_print(a,p,8.,1.,23,(128,96))
    assert np.array_equal(first,render_optical_print(a,p,1.,1.,23,(128,96)))
    assert np.array_equal(first,render_optical_print(a,p,1.001,1.,23,(128,96)))
    assert not np.array_equal(first,render_optical_print(a,p,1.1,1.,23,(128,96)))
    assert np.array_equal(a,original) and p==saved


def test_cuts_have_unequal_durations_and_zero_freezes_layout():
    cuts=[exposure_at(t,4.,42)[0] for t in np.arange(0,4,.01)]
    counts=np.unique(cuts,return_counts=True)[1]
    assert counts.max()>counts.min()*1.5
    p=dict(defaults(),cuts=0.,grain=0.,dust=0.)
    assert np.array_equal(render_optical_print(source(),p,0,1,42,(128,96)),
                          render_optical_print(source(),p,13,1,42,(128,96)))


@pytest.mark.parametrize('size',[(31,127),(131,29),(1,1)])
@pytest.mark.parametrize('high',[False,True])
def test_parameter_extremes_are_finite_and_bounded(size,high):
    p={s.key:(s.maximum if high else s.minimum) for s in MODULE_BY_ID['optical_print'].params}
    out=render_optical_print(source(size),p,2.1,1.,42,size,ReadingBeat('word',progress=.9))
    assert out.shape==source(size).shape
    assert np.isfinite(out).all() and 0<=out.min()<=out.max()<=1


@pytest.mark.parametrize('size',[(160,120),(80,180),(240,60)])
def test_protection_keeps_the_complete_impression_inside_canvas(size):
    p=dict(defaults(),reading_clarity=1,reading_hold=1,width=1.5,overprint=0,
           motion=1,registration=.035,stripes=0,spot=0,grain=0,dust=0,stock=0,
           damage=0,pale_ink=0,softness=0,focus=0)
    for t in (0.,.5,2.7):
        out=render_optical_print(source(size),p,t,1.,42,size,ReadingBeat('word',progress=.5))
        rows,cols=np.nonzero(out.max(axis=2)>.1)
        assert len(cols)>0
        assert cols.min()>0 and cols.max()<size[0]-1
        assert rows.min()>0 and rows.max()<size[1]-1


def test_footage_catalog_intensity_and_legacy_disabled():
    assert 'optical_print' in VIDEO_EFFECTS and 'optical_print' in VIDEO_MODULES
    assert 'optical_print' in {e.id for e in effect_catalog()}
    p=default_synth_preset()
    for m in p['modules']:m['enabled']=m['id']=='optical_print'
    m=next(m for m in p['modules'] if m['id']=='optical_print')
    image=Image.fromarray(np.uint8(source()*255))
    assert render_synth_frame(p,size=image.size,source_image=image).tobytes()!=image.tobytes()
    m['params']['effect_intensity']=0
    assert render_synth_frame(p,size=image.size,source_image=image).tobytes()==image.tobytes()
    for old in curated_presets().values():
        assert not any(m['enabled'] for m in old['modules'] if m['id']=='optical_print')
    for path in TARGETS:
        if path.startswith('optical_print.'): assert target_parameter(path) is not None


def test_saved_study_factory_and_replaced_wording(tmp_path):
    project=starter_composition('text-dark-print')
    seq=compile_composition(project)
    assert seq['duration']==7.5 and seq['fps']==12
    assert (seq['canvas']['width'],seq['canvas']['height'])==(956,720)
    save_composition(tmp_path/'study.json',project)
    restored=compile_composition(load_composition(tmp_path/'study.json'))
    authored=compile_composition(dark_print_composition())
    for t in (0.,.7,2.6,3.5,4.5,6.5):
        expected=render_sequence_frame(seq,t,(160,120)).tobytes()
        assert render_sequence_frame(restored,t,(160,120)).tobytes()==expected
        assert render_sequence_frame(authored,t,(160,120)).tobytes()==expected
    project['effects']['text']=effect_preset('text')
    project['effects']['text']['params']={'text.content':'MEMORIA EN MOVIMIENTO'}
    changed=compile_composition(project)
    assert render_sequence_frame(changed,1.,(160,120)).tobytes()!=render_sequence_frame(seq,1.,(160,120)).tobytes()
    events,_,_=reading_schedule(dict(content='MEMORIA EN MOVIMIENTO',reading_duration=7.5))
    assert [word for _,_,word,_,transition in events if not transition]==['MEMORIA','EN','MOVIMIENTO']


@pytest.mark.parametrize('typeface',[0,1,2])
def test_secondary_layers_preserve_foreground_and_seek_deterministically(typeface):
    p=dict(defaults(),reading_clarity=1.,reading_hold=1.,softness=0.,focus=0.,
           damage=0.,pale_ink=0.,grain=0.,dust=0.,spot=0.,stock=0.,brightness=1.)
    beat=ReadingBeat('REVOLUTION',progress=.4)
    a=source((160,120))
    wet=dict(p,fragment_mix=1.,fragment_typeface=typeface,halation=.8)
    for t in (.4,1.2,3.3):
        dry=render_optical_print(a,dict(p,overprint=0.,stripes=0.),t,1.,23,(160,120),beat)
        base=render_optical_print(a,p,t,1.,23,(160,120),beat)
        out=render_optical_print(a,wet,t,1.,23,(160,120),beat)
        # Foreground cores from a separately rendered isolated impression stay
        # identical. Only the secondary exposures may change around the word.
        cores=np.asarray(Image.fromarray(np.uint8(dry.max(axis=2)>.65)*255).filter(ImageFilter.MinFilter(5)))>0
        assert cores.sum()>30
        assert np.max(abs(base[cores]-out[cores]))<.005
        assert np.mean(abs(base-out))>.002
        render_optical_print(a,wet,19.,1.,23,(160,120),beat)
        assert np.array_equal(out,render_optical_print(a,wet,t,1.,23,(160,120),beat))


def test_secondary_font_does_not_generate_lettering_on_footage():
    p=dict(defaults(),fragment_mix=1.,halation=.8)
    a=source()
    original=render_optical_print(a,p,1.3,1.,42,(128,96))
    for font in (1,2):
        assert np.array_equal(original,render_optical_print(a,dict(p,fragment_typeface=font),1.3,1.,42,(128,96)))


def test_old_saved_settings_default_to_original_print_and_reading_is_unchanged():
    old=json.loads((Path(__file__).parents[1]/'presets/text-dark-print-v1.json').read_text())
    old_seq=compile_composition(old)
    new_seq=compile_composition(dark_print_composition())
    old_state=next(iter(old_seq['states'].values()))
    new_state=next(iter(new_seq['states'].values()))
    # Typography, semantic timing and every pre-existing main-impression control
    # are authored exactly as before; only the secondary exposures opt in.
    for key,value in old_state['overrides'].items():
        if key!='optical_print.spot': assert new_state['overrides'][key]==value
    assert old_seq['duration']==new_seq['duration'] and old_seq['fps']==new_seq['fps']
    p=defaults();a=source();beat=ReadingBeat('word',progress=.9)
    missing={k:v for k,v in p.items() if k not in ('fragment_mix','fragment_typeface','halation')}
    assert np.array_equal(render_optical_print(a,p,.8,1.,23,(128,96),beat),
                          render_optical_print(a,missing,.8,1.,23,(128,96),beat))
