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
from synth_sequence import render_sequence_frame, resolve_sequence_frame
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


def test_silhouette_is_optional_deterministic_and_does_not_change_rng():
    a=source(); p=defaults(); original=a.copy()
    legacy={k:v for k,v in p.items() if not k.startswith('mask_')}
    expected=render_dye_transfer(a,legacy,.2,1,53,(160,90))
    assert np.array_equal(expected,render_dye_transfer(a,p,.2,1,53,(160,90)))
    for shape in (1,2,3):
        settings=dict(p,mask_shape=shape,mask_opacity=0)
        assert np.array_equal(expected,render_dye_transfer(a,settings,.2,1,53,(160,90)))
        settings['mask_opacity']=.8
        result=render_dye_transfer(a,settings,.2,1,53,(160,90))
        assert not np.array_equal(result,expected)
        render_dye_transfer(a,settings,50,1,53,(160,90))
        assert np.array_equal(result,render_dye_transfer(a,settings,.21,1,53,(160,90)))
    assert np.array_equal(a,original)
    for key in ('mask_size','mask_aspect','mask_x','mask_y','mask_angle','mask_softness','mask_opacity'):
        assert target_parameter('dye_transfer.'+key) is not None


def test_silhouettes_geometry_opacity_and_defocus():
    # Black optical obstruction on a neutral white print. All other treatments
    # are off so silhouette geometry and darkening can be measured directly.
    p=defaults();p.update(paper_light=1,paper_saturation=0,weave=0,warp=0,
        erosion=0,grain=0,dust=0,wash=0,dye=0,softness=0,drag=0,
        mask_size=.7,mask_softness=0)
    a=np.zeros((120,200,3),np.float32)
    def draw(**settings):
        return render_dye_transfer(a,dict(p,**settings),0,1,53,(200,120))[:,:,0]
    disc=draw(mask_shape=1)
    assert disc[60,100]<.01 and disc[60,10]>.99
    assert np.allclose(disc[60,60:141],disc[20:101,100])  # circular, not canvas-stretched
    half=draw(mask_shape=1,mask_opacity=.5)
    assert np.allclose(half,(disc+1)/2)
    wedge=draw(mask_shape=2)
    assert (wedge[90]<.1).sum()>(wedge[40]<.1).sum()
    bulb=draw(mask_shape=3)
    assert bulb[10,100]<.01 and disc[10,100]>.99
    moved=draw(mask_shape=1,mask_x=.25)
    assert moved[60,150]<.01 and moved[60,60]>.99
    rotated=draw(mask_shape=2,mask_angle=180)
    assert (rotated[40]<.1).sum()>(rotated[90]<.1).sum()
    ghost=draw(mask_shape=1,mask_softness=100,mask_opacity=.6)
    assert .4<ghost[60,100]<.8 and ghost[60,10]>ghost[60,100]
    assert np.abs(np.diff(ghost[60])).max()<.02
    # Very large obstructions stay solid over the entire canvas. No blur-edge
    # fade caused by cutting the shape at the image boundary first.
    large=draw(mask_shape=1,mask_size=4)
    assert large.max()<.01


def test_first_study_revision_keeps_its_saved_appearance():
    import hashlib
    root=Path(__file__).resolve().parents[1]
    seq=compile_composition(load_composition(root/'presets/text-dye-transfer-v1.json'))
    expected=[(0.0, '828c6d7baee1b88e6e2133d847928406f951395817e622258a9e3b9bdef4a88c'), (1.3, '71e370fd206c44f78a910c157c3a9f01ccc5ac557136bd3ce143f4108b8ff978'), (11.036666666666667, 'd694791262986153d069571a08febf1b4a28757b925c04346c4b2d1ee5d94882')]
    for t,digest in expected:
        assert hashlib.sha256(render_sequence_frame(seq,t,(160,90)).tobytes()).hexdigest()==digest


def test_second_study_revision_keeps_its_saved_appearance():
    import hashlib
    root=Path(__file__).resolve().parents[1]
    seq=compile_composition(load_composition(root/'presets/text-dye-transfer-v2.json'))
    expected=[
        (0., '1ade35f1826039c00d4359c6e667faf4f03d58344f7d674c0a934993d70b3c1f'),
        (8.07, '905bc2190749ac5eb8dfa37da9a84705ab45bfa0fd0db844890869f69cdc787b'),
        (13.47, 'a1a29ea0924a9b502f6d4d1b538380115093eed944f9397bf869b3ec9b47827d'),
    ]
    for t,digest in expected:
        assert hashlib.sha256(render_sequence_frame(seq,t,(160,90)).tobytes()).hexdigest()==digest


def test_study_keeps_complete_glyphs_before_and_after_optical_placement():
    from synth_text import render_text
    seq=compile_composition(starter_composition('text-dye-transfer'))
    w,h,pad=720,406,96
    for cue in seq['cues']:
        t=cue['time'];base=resolve_sequence_frame(seq,t)[-1]
        modules={m['id']:m['params'] for m in base['modules']}
        if not modules['text']['content'].strip(): continue
        # Draw on a padded canvas with identical artwork dimensions. Any ink
        # outside the original canvas would have been lost before Dye transfer,
        # even if the subsequent transform moves its clipped edges inwards.
        large=dict(base,width=w+2*pad,height=h+2*pad,framing='preserve',
                   reference=dict(width=w,height=h,framing='native'))
        ink=render_text(np.zeros((h+2*pad,w+2*pad,3),np.float32),modules['text'],t,large)
        outside=ink.copy();outside[pad:pad+h,pad:pad+w]=0
        assert outside.max()==0, cue
        # Isolate the letter body from intentional long exposure trails. Keep
        # actual displacement, weave and local registration at each cut.
        p=dict(modules['dye_transfer'])
        p.update(paper_light=0,ink_light=1,ink_saturation=0,wash=0,halo=0,dye=0,
                 grain=0,dust=0,erosion=0,drag=0,shutter=0,softness=0,
                 focus_flutter=0,emulsion=0,streaks=0,edge_bloom=0,mask_shape=0)
        placed=render_dye_transfer(ink[pad:pad+h,pad:pad+w],p,t,1,base['seed'],(w,h))
        rows,cols=np.nonzero(placed.max(axis=2)>.1)
        assert len(rows)>0, cue
        assert min(rows.min(),cols.min(),h-1-rows.max(),w-1-cols.max())>=8, cue


def test_pale_lettering_keeps_subtle_texture_instead_of_dark_pits():
    from synth_text import render_text
    from PIL import ImageFilter
    seq=compile_composition(starter_composition('text-dye-transfer'))
    t=next(c['time'] for c in seq['cues'] if c['state'].endswith(':impression-242'));base=resolve_sequence_frame(seq,t)[-1]
    modules={m['id']:m['params'] for m in base['modules']}
    a=render_text(np.zeros((406,720,3),np.float32),modules['text'],t,base)
    p=modules['dye_transfer']
    assert modules['text']['content']=='& YOU KNOW'
    clean=render_dye_transfer(a,dict(p,erosion=0),t,1,base['seed'],(720,406)).mean(axis=2)
    result=render_dye_transfer(a,p,t,1,base['seed'],(720,406)).mean(axis=2)
    core=np.asarray(Image.fromarray(np.uint8(clean>.7)*255).filter(ImageFilter.MinFilter(9)))>0
    assert core.sum()>1000
    loss=(clean-result)[core]
    assert np.quantile(loss,.99)<.04
    # Some fine texture remains; it has not been replaced by flat white type.
    assert result[core].std()>.005


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
    assert seq['duration']==15. and seq['fps']==30
    assert (seq['canvas']['width'],seq['canvas']['height'])==(720,406)
    save_composition(tmp_path/'study.json',p)
    restored=compile_composition(load_composition(tmp_path/'study.json'))
    authored=compile_composition(dye_transfer_composition())
    for t in (0.,1.3,1.9,4.4,6.8,10.5,13.8,14.8):
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


def test_new_inserts_leave_readable_sections_unchanged():
    root=Path(__file__).resolve().parents[1]
    old=compile_composition(load_composition(root/'presets/text-dye-transfer-v3.json'))
    new=compile_composition(load_composition(root/'presets/text-dye-transfer-v6.json'))
    for cue in new['cues']:
        t=cue['time']
        if t<1.5 or 4.5<=t<434/30 or t>=446/30:
            assert render_sequence_frame(old,t,(160,90)).tobytes()==render_sequence_frame(new,t,(160,90)).tobytes()
    masks=[]
    for cue,next_cue in zip(new['cues'],new['cues'][1:]):
        base=resolve_sequence_frame(new,cue['time'])[-1]
        p=next(m['params'] for m in base['modules'] if m['id']=='dye_transfer')
        if p['mask_shape']:
            masks.append(p['mask_shape'])
            assert 1.5<=cue['time']<next_cue['time']<=4.5
            assert 1<=round((next_cue['time']-cue['time'])*30)<=3
    assert masks==[2,1,3,1,1]


def test_final_orange_ink_is_cleaner_and_other_frames_keep_their_look():
    root=Path(__file__).resolve().parents[1]
    previous=compile_composition(load_composition(root/'presets/text-dye-transfer-v4.json'))
    current=compile_composition(load_composition(root/'presets/text-dye-transfer-v6.json'))
    for frame in (0,68,71,77,98,242,433,446,472):
        assert render_sequence_frame(previous,frame/30,(160,90)).tobytes()==render_sequence_frame(current,frame/30,(160,90)).tobytes()
    for frame in range(434,446):
        old=render_sequence_frame(previous,frame/30,(720,406))
        new=render_sequence_frame(current,frame/30,(720,406))
        assert old.tobytes()!=new.tobytes()
        base=resolve_sequence_frame(current,frame/30)[-1]
        p=next(m['params'] for m in base['modules'] if m['id']=='dye_transfer')
        assert p['erosion']==.04
