"""Optional slice exposures preserve legacy cuts and every source adapter."""
import hashlib
import math

import numpy as np
import pytest
from PIL import Image

import synth_chroma
from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_chroma import render_slice_echo, slice_envelope, slice_events


NEW_CONTROLS = ('angle', 'highlight_protect', 'luma_mask', 'envelope')


def params(**changes):
    return dict({s.key: s.default for s in MODULE_BY_ID['slice_echo'].params}, **changes)


def render(image, p, time=.25, speed=1., seed=31):
    return render_slice_echo(image, p, time, speed, seed, (image.shape[1], image.shape[0]))


@pytest.mark.parametrize('width,height,time,seed,expected', [
    (97,61,.21,7,'3abda70c03f5305d8f595338c5b832a7badd87373b674415d79602f5c2e26e38'),
    (64,96,1.37,412,'87994ac1c2bc200b3c3a2a11b229e4392ba53aa7976d3b41331d4387db1ccafb'),
    (80,80,2.04,9,'f5abc424fed9a545d347cb73662c6fb5e7dfd6dc554be4bdbca58125f1f1d9d1'),
])
def test_default_and_missing_controls_match_pre_refinement_pixels(width,height,time,seed,expected):
    # Captured from the preceding renderer, before introducing the controls.
    p = params(activity=1.,count=5,cadence=12.,color_chance=.7,screen=.35,scale=.21)
    assert all(p[key] == 0 for key in NEW_CONTROLS)
    image = np.random.default_rng(912).random((height,width,3),dtype=np.float32)
    image[:height//3,:width//3] = 0
    for settings in (p, {k:v for k,v in p.items() if k not in NEW_CONTROLS}):
        result = render(image,settings,time,.85,seed)
        assert hashlib.sha256(result.tobytes()).hexdigest() == expected


def test_envelope_follows_held_event_clock_and_freezes_with_speed():
    p = params(envelope=.2,period=1.,cadence=10.,phase=0.)
    assert slice_envelope(p,0.,1.) == 0
    assert slice_envelope(p,.1,1.) == pytest.approx(.5)
    assert slice_envelope(p,.2,1.) == 1
    assert slice_envelope(p,.8,1.) == pytest.approx(1)
    assert slice_envelope(p,.9,1.) == pytest.approx(.5)
    assert slice_envelope(p,1.,1.) == 0
    assert slice_envelope(p,.11,1.) == slice_envelope(p,.19,1.)
    assert slice_envelope(p,100.,0.) == slice_envelope(p,0.,0.)
    assert slice_envelope(dict(p,envelope=0.),.1,1.) == 1
    assert slice_envelope(dict(p,cadence=0.),.11,1.) != slice_envelope(dict(p,cadence=0.),.12,1.)
    assert slice_envelope(dict(p,phase=.1),0.,1.) == pytest.approx(.5)


def test_all_new_controls_hold_together_without_changing_event_layout():
    image = np.random.default_rng(9).random((73,119,3),dtype=np.float32)
    old = params(activity=1.,cadence=10.,period=.7)
    new = dict(old,angle=-12.,highlight_protect=.8,luma_mask=.7,envelope=.2)
    assert slice_events(old,.21,1.,7) == slice_events(new,.21,1.,7)
    first = render(image,new,.21)
    assert np.array_equal(first,render(image,new,.29))
    assert not np.array_equal(first,render(image,new,.31))
    assert np.array_equal(render(image,new,0.,0.),render(image,new,4.,0.))
    # Out-of-order preview requests never change the event or its envelope.
    render(image,new,90.)
    assert np.array_equal(first,render(image,new,.21))


@pytest.mark.parametrize('width,height', [(180,90),(90,180),(120,120)])
def test_seam_angle_uses_pixels_without_stretching_the_source(monkeypatch,width,height):
    monkeypatch.setattr(synth_chroma,'slice_events',lambda *args: ((.5,.16,0.,0.,1.,True),))
    image = np.full((height,width,3),.5,dtype=np.float32)
    p = params(angle=27.,hue=0.,saturation=1.,color_mix=1.,opacity=1.,screen=0.,softness=0.)
    out = render(image,p)
    x0,x1 = int(width*.3),int(width*.7)
    weights = image[...,1]-out[...,1]
    ys = np.arange(height)
    centers = [(weights[:,x]*ys).sum()/weights[:,x].sum() for x in (x0,x1)]
    assert (centers[1]-centers[0])/(x1-x0) == pytest.approx(math.tan(math.radians(27.)),abs=.025)

    # The boundary rotates while source coordinates stay intact: fully exposed
    # pixels common to both seam angles retain identical image detail.
    image = np.random.default_rng(12).random((height,width,3),dtype=np.float32)
    angled = render(image,p)
    straight = render(image,dict(p,angle=0.))
    common = (angled[...,1] == 0) & (straight[...,1] == 0)
    assert common.sum() > width
    assert np.array_equal(angled[common],straight[common])
    assert not np.array_equal(angled,straight)


def test_tint_keeps_bright_highlights_pale_without_lifting_black(monkeypatch):
    monkeypatch.setattr(synth_chroma,'slice_events',lambda *args: ((.5,3.,0.,0.,1.,True),))
    image = np.repeat(np.linspace(0,1,256,dtype=np.float32)[None,:,None],3,axis=2)
    p = params(hue=.9,saturation=1.,color_mix=1.,screen=0.,opacity=1.,highlight_protect=1.)
    protected = render(image,p)
    tinted = render(image,dict(p,highlight_protect=0.))
    assert not protected[0,0].any()
    assert np.allclose(protected[0,-1],1.)
    assert np.ptp(tinted[0,-1]) > .8
    assert np.array_equal(protected[0,40],tinted[0,40])
    assert np.ptp(protected[0,220]) < np.ptp(tinted[0,220])
    assert np.isfinite(protected).all()


def test_image_mask_reveals_underlying_image_where_shifted_source_is_black(monkeypatch):
    monkeypatch.setattr(synth_chroma,'slice_events',lambda *args: ((.5,3.,1.,0.,1.,False),))
    image = np.full((60,90,3),.5,dtype=np.float32)
    p = params(luma_mask=1.,screen=0.,opacity=1.)
    assert np.array_equal(render(image,p),image)
    assert not render(image,dict(p,luma_mask=0.)).any()
    assert np.allclose(render(image,dict(p,luma_mask=.5)),image*.5)


@pytest.mark.parametrize('angle', [-90.,-12.,0.,90.])
def test_extreme_options_are_finite_and_black_never_emits_light(angle):
    p = params(angle=angle,highlight_protect=1.,luma_mask=1.,envelope=.5,
               exposure=2.,screen=1.,count=12,activity=1.,shift_x=1.,shift_y=1.,scale=.7)
    black = np.zeros((83,47,3),dtype=np.float32)
    assert not render(black,p).any()
    image = np.random.default_rng(71).uniform(-.1,1.5,black.shape).astype(np.float32)
    out = render(image,p)
    assert out.shape == image.shape
    assert np.isfinite(out).all()
    assert np.array_equal(render(image,dict(p,mix=0.)),image)


@pytest.mark.parametrize('source', ['video','text','slab'])
def test_refinements_work_through_video_text_and_geometry_adapters(source):
    p = default_synth_preset()
    p.update(width=120,height=90,speed=1.)
    for module in p['modules']:
        module['enabled'] = module['id'] in (source,'slice_echo')
        if module['id'] == 'slice_echo':
            module['params'].update(activity=1.,count=12,angle=-11.,
                                    highlight_protect=.8,luma_mask=.6,envelope=.12)
    image = Image.new('RGB',(120,90),(0,0,0))
    image.paste((240,150,110),(20,20,100,70))
    kwargs = {'source_image':image} if source == 'video' else {}
    out = render_synth_frame(p,time_seconds=.31,**kwargs)
    assert out.size == (120,90)
    assert out.tobytes() == render_synth_frame(p,time_seconds=.31,**kwargs).tobytes()
    next(m for m in p['modules'] if m['id']=='slice_echo')['params']['mix'] = 0.
    assert out.tobytes() != render_synth_frame(p,time_seconds=.31,**kwargs).tobytes()
