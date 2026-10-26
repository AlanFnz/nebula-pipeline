"""Reusable dye printing, editable reference montage and ordering regressions."""
import copy
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_composition import compile_composition, load_composition, save_composition
from synth_dye_transfer import render_dye_transfer
from synth_dye_recipes import dye_transfer_composition
from synth_effect_catalog import effect_catalog
from synth_effect_order import movable, resolved_order
from synth_effects import effect_preset
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_video import VIDEO_EFFECTS, VIDEO_MODULES
from synth_automation import target_parameter


def defaults():
    return {s.key:s.default for s in MODULE_BY_ID['dye_transfer'].params}


def source(size=(160,90)):
    w,h=size
    a=np.zeros((h,w,3),np.float32)
    a[h//4:3*h//4,w//4:3*w//4]=1
    return a


def test_seeks_cadence_and_no_mutation():
    a=source();p=defaults();old=a.copy();settings=copy.deepcopy(p)
    first=render_dye_transfer(a,p,.2,1,53,(160,90))
    render_dye_transfer(a,p,20,1,53,(160,90))
    assert np.array_equal(first,render_dye_transfer(a,p,.21,1,53,(160,90)))
    assert not np.array_equal(first,render_dye_transfer(a,p,.3,1,53,(160,90)))
    assert np.array_equal(a,old) and p==settings


def test_optical_finish_is_deterministic_and_optional():
    a=source(); p=defaults(); old=a.copy()
    original=render_dye_transfer(a,p,.2,1,53,(160,90))
    # Old settings dictionaries may not contain any new optional controls.
    keys=('emulsion','streaks','edge_bloom','registration','focus_flutter','shutter')
    legacy={k:v for k,v in p.items() if k not in keys}
    assert np.array_equal(original,render_dye_transfer(a,legacy,.2,1,53,(160,90)))
    p.update(emulsion=.6,streaks=.5,edge_bloom=.7,registration=.4,focus_flutter=2,shutter=-.3)
    result=render_dye_transfer(a,p,.2,1,53,(160,90))
    render_dye_transfer(a,p,91,1,53,(160,90))
    assert np.array_equal(result,render_dye_transfer(a,p,.21,1,53,(160,90)))
    assert not np.array_equal(original,result)
    assert np.array_equal(a,old)
    assert all(target_parameter('dye_transfer.'+k) is not None for k in keys)


def test_shutter_trails_follow_direction_without_opposite_edge_wrap():
    a=source((160,90));p=defaults()
    p.update(paper_light=0,ink_light=1,ink_saturation=0,weave=0,warp=0,
             erosion=0,grain=0,dust=0,wash=0,dye=0,softness=0,drag=0)
    up=render_dye_transfer(a,dict(p,shutter=-.7),0,1,53,(160,90)).mean(axis=2)
    down=render_dye_transfer(a,dict(p,shutter=.7),0,1,53,(160,90)).mean(axis=2)
    def centroid(image): return (image*np.arange(90)[:,None]).sum()/image.sum()
    assert centroid(up)<44<centroid(down)
    assert up[-1].max()==0 and down[0].max()==0
    # The exposure is continuous, not a row of translated glyph copies.
    assert np.all(up[:20].sum(axis=1)>0)
    assert np.all(down[70:].sum(axis=1)>0)


def test_first_study_revision_keeps_its_saved_appearance():
    import hashlib
    root=Path(__file__).resolve().parents[1]
    seq=compile_composition(load_composition(root/'presets/text-dye-transfer-v1.json'))
    expected=[(0.0, '828c6d7baee1b88e6e2133d847928406f951395817e622258a9e3b9bdef4a88c'), (1.3, '71e370fd206c44f78a910c157c3a9f01ccc5ac557136bd3ce143f4108b8ff978'), (11.036666666666667, 'd694791262986153d069571a08febf1b4a28757b925c04346c4b2d1ee5d94882')]
    for t,digest in expected:
        assert hashlib.sha256(render_sequence_frame(seq,t,(160,90)).tobytes()).hexdigest()==digest


@pytest.mark.parametrize('size',[(1,1),(31,127),(131,29)])
@pytest.mark.parametrize('maximum',[False,True])
def test_extremes_finite_bounded(size,maximum):
    p={s.key:s.maximum if maximum else s.minimum for s in MODULE_BY_ID['dye_transfer'].params}
    out=render_dye_transfer(source(size),p,8,1,53,size)
    assert out.shape==source(size).shape
    assert np.isfinite(out).all() and 0<=out.min()<=out.max()<=1


def test_catalog_footage_intensity_and_order():
    assert 'dye_transfer' in VIDEO_EFFECTS and 'dye_transfer' in VIDEO_MODULES
    assert 'dye_transfer' in {e.id for e in effect_catalog()}
    assert movable('dye_transfer')
    assert target_parameter('dye_transfer.drag') is not None
    p=default_synth_preset();p['speed']=1.;p['depth']=0.
    for m in p['modules']:m['enabled']=m['id']=='dye_transfer'
    m=next(m for m in p['modules'] if m['id']=='dye_transfer')
    image=Image.fromarray(np.uint8(source()*255))
    wet=np.asarray(render_synth_frame(p,time_seconds=.5,size=image.size,source_image=image)).astype(float)
    m['params']['effect_intensity']=0
    dry=np.asarray(render_synth_frame(p,time_seconds=.5,size=image.size,source_image=image)).astype(float)
    assert np.array_equal(dry,np.asarray(image))
    m['params']['effect_intensity']=50
    half=np.asarray(render_synth_frame(p,time_seconds=.5,size=image.size,source_image=image)).astype(float)
    assert np.abs(half-(wet+dry)/2).max()<=1.1
    m['params']['effect_intensity']=100
    b=next(m for m in p['modules'] if m['id']=='broadcast');b['enabled']=True
    b['params'].update(curve=.25,vignette=.5)
    p['effect_order']=['dye_transfer','broadcast']
    after=render_synth_frame(p,time_seconds=.5,size=image.size,source_image=image)
    p['effect_order']=['broadcast','dye_transfer']
    before=render_synth_frame(p,time_seconds=.5,size=image.size,source_image=image)
    assert after.tobytes()!=before.tobytes()
    p['effect_order']=resolved_order(dict(p,effect_order=[]))
    explicit=render_synth_frame(p,time_seconds=.5,size=image.size,source_image=image)
    del p['effect_order']
    assert explicit.tobytes()==render_synth_frame(p,time_seconds=.5,size=image.size,source_image=image).tobytes()


def test_frozen_study_roundtrip_timing_and_opt_in(tmp_path):
    p=starter_composition('text-dye-transfer');seq=compile_composition(p)
    assert seq['duration']==473/30 and seq['fps']==30
    assert (seq['canvas']['width'],seq['canvas']['height'])==(720,406)
    save_composition(tmp_path/'study.json',p)
    restored=compile_composition(load_composition(tmp_path/'study.json'))
    authored=compile_composition(dye_transfer_composition())
    for t in (0.,1.3,1.9,4.4,6.8,10.5,13.8,15.5):
        expected=render_sequence_frame(seq,t,(160,90)).tobytes()
        assert render_sequence_frame(restored,t,(160,90)).tobytes()==expected
        assert render_sequence_frame(authored,t,(160,90)).tobytes()==expected
    for cue in seq['cues']:
        assert render_sequence_frame(seq,cue['time'],(64,36)).size==(64,36)
    words={s['overrides']['text.content'] for s in seq['states'].values()}
    assert {'JUST\nONE\nMORE\nTRY','SOMEONE\nTO\nBELIEVE\nIN',
            'I NEED\nSOMEONE TO\nBELIEVE IN','&\nYOU\nKNOW'}<=words
    # Replacement is still the standard Text object, not baked reference pixels.
    p['effects']['text']=effect_preset('text')
    p['effects']['text']['params']={'text.content':'ANOTHER IMPRESSION'}
    assert render_sequence_frame(compile_composition(p),.2,(160,90)).tobytes()!=render_sequence_frame(seq,.2,(160,90)).tobytes()
    assert not next(m for m in default_synth_preset()['modules'] if m['id']=='dye_transfer')['enabled']
