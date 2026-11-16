import numpy as np
import pytest

from synth_lattice_eye_ripple import ripple_triggers
from test_synth_lattice_eye_ripple import params
from test_synth_lattice_eye_mix import frame


def glow_params(**changes):
    return params(**dict(dict(eye_placement=1,eye_size=5.7,eye_reveal=0.,eye_ripple=.8,
        eye_ripple_response=3,eye_ripple_size=0.,eye_ripple_rotation=0.,
        eye_ripple_position=0.,eye_ripple_fluid=0.,eye_ripple_glow=90.,
        eye_ripple_glow_radius=6.,eye_blink_count=1,eye_blink_period=8.,eye_double_blink=0.,
        eye_blink_variation=0.,eye_blink_fps=0,grain=0.,softness=0.,glow=0.,
        cadence=0.,pulse=0.,color_period=8.,period=8.),**changes))


def test_glow_is_opt_in_and_master_and_old_modes_remain_respected():
    p=glow_params()
    old={k:v for k,v in p.items() if not k.startswith('eye_ripple_glow')}
    assert np.array_equal(frame(old),frame(dict(p,eye_ripple_glow=0.)))
    for mode in (0,1,2):
        assert np.array_equal(frame(dict(p,eye_ripple_response=mode)),
                              frame(dict(old,eye_ripple_response=mode)))
    for key,value in [('eye_enabled',0),('eye_ripple',0.),('eye_blink_count',0),('eye_opening',0.)]:
        assert np.array_equal(frame(dict(p,**{key:value})),frame(dict(old,**{key:value})))


def test_glow_lights_only_arriving_cells_and_does_not_flash_the_eye():
    p=glow_params()
    trigger=ripple_triggers(1,8.,.38,0.,0.,0,141126)[0][0]
    def diff(age):
        a=frame(p,trigger+age,(360,640))
        b=frame(dict(p,eye_ripple_glow=0.),trigger+age,(360,640))
        return a-b
    assert not diff(-.2).any()
    a=diff(.6)
    assert a.max()>.08 and a.min()>=0
    assert not a[:60].any()  # Distant rows have not been reached.
    assert not a[305:335,165:195].any()  # The opaque open eye covers the glow.
    assert not diff(4.).any()  # Light fully dissipates.
    y,x=np.mgrid[:640,:360]
    radius=np.hypot(x-180,y-320)
    def light_radius(d):
        light=d.sum(-1)
        return float(np.sum(light*radius)/light.sum())
    assert light_radius(diff(.9)) > light_radius(a)+10


def test_glow_softness_spreads_the_halo_without_altering_timing():
    p=glow_params()
    narrow=frame(dict(p,eye_ripple_glow_radius=1.),3.6,(360,640))
    broad=frame(dict(p,eye_ripple_glow_radius=20.),3.6,(360,640))
    base=frame(dict(p,eye_ripple_glow=0.),3.6,(360,640))
    n=(narrow-base).max(-1);b=(broad-base).max(-1)
    assert np.count_nonzero(b>.003)>np.count_nonzero(n>.003)
    assert np.max(b)>0 and np.max(n)>0
    assert np.array_equal(frame(p,0.),frame(dict(p,eye_ripple_glow_radius=20.),0.))


@pytest.mark.parametrize('size',[(144,256),(256,144),(180,180)])
def test_glow_is_periodic_seek_independent_and_finite_at_high_settings(size):
    p=glow_params(eye_ripple_glow=200.,eye_ripple_glow_radius=24.,
                  eye_ripple_rotation=20.,eye_ripple_fluid=100.,eye_ripple_size=100.)
    a=frame(p,3.6,size)
    frame(p,7.,size)
    assert np.array_equal(a,frame(p,3.6,size))
    assert np.allclose(a,frame(p,11.6,size),atol=1e-5)
    assert np.isfinite(a).all() and a.min()>=0 and a.max()<=1
