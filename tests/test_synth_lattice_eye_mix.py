import copy

import numpy as np
import pytest

from synth import default_synth_preset
from synth_composition import compile_composition, load_composition, save_composition
from synth_lattice import render_chromatic_lattice
from synth_lattice_eye_ripple import ripple_cells, ripple_profile, limit_cell_rotation
from synth_lattice_recipes import watching_eye_composition
from synth_sequence import render_sequence_frame
from test_synth_lattice_eye_ripple import params
from test_synth_effects_editor_integration import make_window


def frame(p, t=2.4, size=(144,256)):
    w,h=size
    preset=dict(default_synth_preset(),width=w,height=h,seed=141126,speed=1.)
    return render_chromatic_lattice(np.zeros((h,w,3),np.float32),p,t,preset)


@pytest.mark.parametrize('mode,size,position,fluid',[(0,0.,0.,100.),(1,100.,0.,0.),(2,100.,100.,0.)])
def test_mixer_can_reproduce_each_original_mode_exactly(mode,size,position,fluid):
    old=params(eye_placement=1,eye_ripple=.8,eye_ripple_response=mode)
    mixed=dict(old,eye_ripple_response=3,eye_ripple_size=size,
               eye_ripple_rotation=0.,eye_ripple_position=position,eye_ripple_fluid=fluid)
    for t in (0.,2.04,2.3,2.7,5.8):
        assert np.array_equal(frame(old,t),frame(mixed,t))


def test_each_mix_component_is_independent_and_zero_mix_is_exactly_disabled():
    p=params(eye_placement=1,eye_ripple=.8,eye_ripple_response=3,eye_ripple_size=0.,
             eye_ripple_rotation=0.,eye_ripple_position=0.,eye_ripple_fluid=0.)
    original=frame(dict(p,eye_ripple=0.))
    assert np.array_equal(frame(p),original)
    variants=[]
    for key,value in [('size',100.),('rotation',12.),('position',100.),('fluid',100.)]:
        active=dict(p,**{'eye_ripple_'+key:value})
        rendered=frame(active)
        assert not np.array_equal(rendered,original)
        assert np.array_equal(frame(dict(active,**{'eye_ripple_'+key:0.})),original)
        variants.append(rendered)
    for a,b in zip(variants,variants[1:]):
        assert not np.array_equal(a,b)


def test_rotation_rocks_whole_figures_without_scaling_or_changing_center():
    p=params(eye_ripple_response=3,eye_ripple_size=0.,eye_ripple_rotation=10.,eye_ripple_position=0.)
    u=np.array([0.,1.,-1.,0.,0.],np.float32)
    v=np.array([0.,0.,0.,1.,-1.],np.float32)
    ix=np.full(5,3.,np.float32);iy=np.full(5,.5,np.float32)
    radius=np.full(5,2.,np.float32);rounding=np.full(5,.16,np.float32)
    def transform(vibration):
        profile=(np.array([0.,10.]),np.array([.5,.5]),np.array([vibration,vibration]),np.zeros(2))
        return ripple_cells(ix,iy,u,v,radius,rounding,10.,p,profile)
    a,b,r=transform(.5);x,y,_=transform(-.5)
    assert a.dtype==b.dtype==r.dtype==np.float32
    assert a[0]==b[0]==0.
    assert np.array_equal(r,radius)
    assert np.allclose(np.hypot(a,b),np.hypot(u,v))
    assert abs(b[1])>.01 and b[1]*y[1]<0  # Opposite phases rock in opposite directions.
    assert np.allclose(a[1:3],-a[2:0:-1])


@pytest.mark.parametrize('shape',[1,2])
def test_dense_rotating_cells_stay_inside_their_tiles(shape):
    radius=np.array([2.,3.,4.,4.8],np.float32)
    rounding=np.array([0.,.16,.6,1.],np.float32)
    for base in (0.,19.,45.,89.,135.):
        for degrees in (-20.,-4.,0.,4.,20.):
            angle=np.deg2rad(base)
            turn=limit_cell_rotation(np.full(4,np.deg2rad(degrees)),angle,radius,rounding,10.,shape)
            factor=.70710678 if shape==2 else 1.
            def extent(a):
                if shape==2:a=a+np.pi/4
                return radius*factor*((abs(np.cos(a))+abs(np.sin(a)))*(1-rounding)+rounding)
            assert np.all(extent(angle+turn)<=np.maximum(4.85,extent(angle))+1e-6)
            assert np.all(np.abs(turn)<=abs(np.deg2rad(degrees))+1e-6)


def test_mix_is_periodic_seek_independent_and_saved_with_all_controls(tmp_path):
    p=params(eye_ripple=.8,eye_ripple_response=3,eye_ripple_rotation=8.,eye_ripple_fluid=15.,
             eye_ripple_position=20.,eye_ripple_size=70.,eye_blink_period=3.7,eye_blink_phase=.94)
    for t in (0.,.05,.7,1.5,2.7,3.69):
        a=ripple_profile(p,t,141126);b=ripple_profile(p,t+3.7,141126)
        ripple_profile(p,t+2,141126)
        c=ripple_profile(p,t,141126)
        assert np.array_equal(a,c) and np.allclose(a,b,atol=1e-12)
    project=watching_eye_composition()
    keys=('response','size','rotation','position','fluid','speed','width','reach')
    values={'chromatic_lattice.eye_ripple_'+k:p['eye_ripple_'+k] for k in keys}
    values['chromatic_lattice.eye_ripple']=.8
    project['effects']['chromatic_lattice']={'mode':'recipe','params':values}
    save_composition(tmp_path/'mixed.json',project)
    loaded=load_composition(tmp_path/'mixed.json')
    assert loaded==project
    a=compile_composition(project);b=compile_composition(loaded)
    assert render_sequence_frame(a,2.3,(144,256)).tobytes()==render_sequence_frame(b,2.3,(144,256)).tobytes()


def test_custom_mix_controls_are_visible_saved_and_undoable(make_window):
    w=make_window(composition=watching_eye_composition());c=w.composer;panel=c.object_panel
    c.look_tabs.setCurrentWidget(panel)
    keys=['chromatic_lattice.eye_ripple_'+k for k in ('size','rotation','position','fluid')]
    assert not any(key in panel.object_eligible for key in keys)
    panel.controls['chromatic_lattice.eye_ripple_response'].input.setCurrentIndex(3)
    assert all(key in panel.object_eligible for key in keys)
    for key,value in zip(keys,(60.,8.,12.,15.)):
        before=copy.deepcopy(c.document)
        panel.controls[key].input.setValue(value)
        after=copy.deepcopy(c.document)
        assert after['effects']['chromatic_lattice']['params'][key]==value
        w.undo_composition();assert c.document==before
        w.redo_composition();assert c.document==after
    panel.controls['chromatic_lattice.eye_ripple_response'].input.setCurrentIndex(1)
    assert not any(key in panel.object_eligible for key in keys)
