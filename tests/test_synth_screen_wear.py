import hashlib

import numpy as np

from synth import MODULE_BY_ID
from synth_chroma import render_screen_mesh


def params(**changes):
    return dict({s.key:s.default for s in MODULE_BY_ID['screen_mesh'].params}, **changes)


def render(image, p, time=.43, speed=1., seed=97):
    return render_screen_mesh(image,p,time,speed,seed,(image.shape[1],image.shape[0]))


def test_zero_or_missing_wear_preserves_the_previous_screen_pixels():
    image = np.random.default_rng(219).random((97,121,3),dtype=np.float32)
    p = params()
    assert p['wear'] == 0
    for settings in (p,{k:v for k,v in p.items() if k!='wear'}):
        assert hashlib.sha256(render(image,settings).tobytes()).hexdigest() == '6fb26ec756cb4070078465fedd29cebb74ff3c1838fb492c2bbbb6e4a4451c74'


def test_phosphor_wear_is_held_seeded_and_preserves_black():
    image = np.full((180,240,3),.5,dtype=np.float32)
    p = params(wear=.6,grain=0.,softness=0.,cadence=10.)
    first = render(image,p,.21)
    assert np.array_equal(first,render(image,p,.29))
    assert not np.array_equal(first,render(image,p,.31))
    assert not np.array_equal(first,render(image,p,.21,seed=98))
    assert np.array_equal(render(image,p,0.,speed=0.),render(image,p,10.,speed=0.))
    assert np.array_equal(render(image,dict(p,cadence=0.),0.),render(image,dict(p,cadence=0.),10.))
    assert not render(np.zeros_like(image),p).any()
    assert np.array_equal(render(image,dict(p,mix=0.)),image)


def test_wear_changes_surface_variation_without_shifting_mean_exposure():
    image = np.full((360,360,3),.5,dtype=np.float32)
    clean = render(image,params(grain=0.,softness=0.))
    worn = render(image,params(wear=1.,grain=0.,softness=0.))
    assert not np.array_equal(clean,worn)
    assert np.isfinite(worn).all()
    assert abs(worn.mean(dtype=np.float64)-clean.mean(dtype=np.float64)) < .005
