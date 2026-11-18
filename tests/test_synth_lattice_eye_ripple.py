import copy

import numpy as np
import pytest

from nebula.render.synth import default_synth_preset
from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.sources.synth_lattice import render_chromatic_lattice
from nebula.sources.synth_lattice_eye import blink_opening
from nebula.sources.synth_lattice_eye_ripple import ripple_coordinates, ripple_profile, ripple_triggers, ripple_cells
from nebula.documents.synth_lattice_recipes import watching_eye_composition
from nebula.documents.synth_sequence import resolve_sequence_frame, render_sequence_frame


def params(**changes):
    preset = resolve_sequence_frame(compile_composition(watching_eye_composition()), 0)[-1]
    p = next(m['params'] for m in preset['modules'] if m['id']=='chromatic_lattice')
    return dict(p, **changes)


def test_existing_pixels_and_recipes_remain_unchanged_when_disabled():
    p=params(eye_placement=1,eye_reveal=1.)
    old={k:v for k,v in p.items() if not k.startswith('eye_ripple')}
    source=np.zeros((256,144,3),np.float32)
    preset=dict(default_synth_preset(),seed=141126,width=144,height=256,speed=1.)
    for t in (0.,2.04,2.3,2.7,5.8):
        assert np.array_equal(render_chromatic_lattice(source,p,t,preset),
                              render_chromatic_lattice(source,old,t,preset))
    assert ripple_profile(dict(p,eye_enabled=0,eye_ripple=1.),2.2) is None
    assert ripple_profile(dict(p,eye_blink_count=0,eye_ripple=1.),2.2) is None
    assert ripple_profile(dict(p,eye_opening=0,eye_ripple=1.),2.2) is None


def test_triggers_follow_visible_blinks_and_skip_unsampled_events():
    for fps in (0,1,6,12,60):
        p=params(eye_blink_fps=fps,eye_blink_period=3.7)
        events=ripple_triggers(p['eye_blink_count'],p['eye_blink_period'],p['eye_blink_duration'],
                              p['eye_blink_variation'],p['eye_double_blink'],fps,141126)
        for at,strength in events:
            assert 0 <= at < 3.7
            assert 0 < strength <= 1
            assert blink_opening(at,p,141126) <= 1-strength+1e-10
            if fps:
                assert at*fps == pytest.approx(round(at*fps))
    assert not ripple_triggers(1,1.,.12,0.,0.,1,141126)


def test_ring_moves_outward_fades_and_is_circular_at_any_aspect():
    p=params(eye_ripple=.5,eye_blink_count=1,eye_double_blink=0.,eye_blink_variation=0.,
             eye_blink_fps=0,eye_ripple_reach=10.,eye_ripple_width=.6,eye_ripple_speed=5.)
    trigger=8*.36+.38*.24
    peaks=[]; amplitudes=[]
    for age in (.3,.6,1.,1.5):
        r, displacement=ripple_profile(p,trigger+age,141126)
        peaks.append(r[np.argmax(displacement)]); amplitudes.append(displacement.max())
        assert displacement[0] == displacement[-1] == 0
    assert np.diff(peaks) == pytest.approx((1.5,2.,2.5),abs=.1)
    assert all(a>b for a,b in zip(amplitudes,amplitudes[1:]))
    profile=ripple_profile(p,trigger+.6,141126)
    # Radius stays in cell units, not fractions of either canvas dimension.
    x=np.array([130.,100.,70.,100.],np.float32)
    y=np.array([200.,230.,200.,170.],np.float32)
    u,v=ripple_coordinates(x,y,(100.,200.),10.,profile)
    shifts=np.hypot(u-x,v-y)
    assert shifts == pytest.approx([shifts[0]]*4,abs=1e-5)
    assert shifts[0]>0
    a,b=ripple_coordinates(x*2,y*2,(200.,400.),20.,profile)
    assert a == pytest.approx(u*2); assert b == pytest.approx(v*2)
    far=np.array([500.],np.float32)
    assert np.array_equal(ripple_coordinates(far,far,(0.,0.),10.,profile)[0],far)
    assert ripple_profile(p,trigger+3.,141126) is None


def test_wave_moves_surrounding_cells_without_moving_the_open_eye():
    p=params(eye_placement=1,eye_size=5.7,eye_ripple=.55,eye_blink_count=1,
             eye_double_blink=0.,eye_blink_variation=0.,eye_blink_fps=0,
             grain=0.,softness=0.,glow=0.)
    source=np.zeros((640,360,3),np.float32)
    preset=dict(default_synth_preset(),seed=141126,width=360,height=640,speed=1.)
    assert blink_opening(3.6,p,141126)==1
    a=render_chromatic_lattice(source,p,3.6,preset)
    b=render_chromatic_lattice(source,dict(p,eye_ripple=0.),3.6,preset)
    assert np.array_equal(a[305:335,165:195],b[305:335,165:195])
    assert np.max(abs(a-b))>.05
    assert np.array_equal(a[:40],b[:40])  # The wave has not reached this far.


@pytest.mark.parametrize('fps',[0,6])
def test_ripple_is_periodic_seek_independent_and_smooth_between_held_poses(fps):
    p=params(eye_ripple=.5,eye_blink_fps=fps,eye_blink_period=3.7,eye_blink_phase=.94)
    for t in (0.,.05,.7,1.5,2.7,3.69):
        a=ripple_profile(p,t,141126);b=ripple_profile(p,t+3.7,141126)
        ripple_profile(p,t+2,141126)
        c=ripple_profile(p,t,141126)
        if a is None:
            assert b is c is None
        else:
            assert np.array_equal(a[1],c[1])
            assert np.max(abs(a[1]-b[1])) < 1e-10
    if fps:
        p=params(eye_ripple=.5,eye_blink_fps=6)
        assert blink_opening(2.04,p,141126)==blink_opening(2.08,p,141126)
        assert not np.array_equal(ripple_profile(p,2.04,141126)[1],ripple_profile(p,2.08,141126)[1])


def test_saved_composition_and_extreme_overlapping_waves_render_consistently(tmp_path):
    project=watching_eye_composition()
    project['effects']['chromatic_lattice']={'mode':'recipe','params':{
        'chromatic_lattice.eye_placement':1,'chromatic_lattice.eye_ripple':.45,
        'chromatic_lattice.eye_ripple_speed':7.,'chromatic_lattice.eye_ripple_reach':10.}}
    save_composition(tmp_path/'ripple.json',project)
    loaded=load_composition(tmp_path/'ripple.json')
    assert loaded == project
    a=compile_composition(project);b=compile_composition(loaded)
    assert render_sequence_frame(a,2.3,(144,256)).tobytes()==render_sequence_frame(b,2.3,(144,256)).tobytes()
    p=params(eye_ripple=1.,eye_blink_count=12,eye_blink_period=1.,eye_double_blink=1.,
             eye_ripple_reach=20.,eye_ripple_speed=2.,eye_ripple_width=2.5)
    for size in ((144,256),(256,144),(180,180)):
        w,h=size; source=np.zeros((h,w,3),np.float32)
        preset=dict(default_synth_preset(),width=w,height=h,seed=141126,speed=1.)
        frame=render_chromatic_lattice(source,p,2.3,preset)
        assert np.isfinite(frame).all() and frame.min()>=0 and frame.max()<=1
        assert np.array_equal(frame,render_chromatic_lattice(source,dict(p),2.3,preset))


def test_ripple_controls_save_undo_and_hide_with_eye(make_window,tmp_path):
    w=make_window(composition=watching_eye_composition());c=w.composer;panel=c.object_panel
    c.look_tabs.setCurrentWidget(panel)
    path='chromatic_lattice.eye_ripple'
    original=copy.deepcopy(c.document)
    assert path in panel.object_eligible and 'Eye ripple' in panel.object_groups
    panel.controls[path].input.setValue(.45)
    changed=copy.deepcopy(c.document)
    assert changed['effects']['chromatic_lattice']['params'][path] == .45
    save_composition(tmp_path/'ui.json',changed)
    assert load_composition(tmp_path/'ui.json')==changed
    w.undo_composition();assert c.document==original
    w.redo_composition();assert c.document==changed
    panel.controls['chromatic_lattice.eye_ripple_response'].input.setCurrentIndex(1)
    pulse=copy.deepcopy(c.document)
    assert pulse['effects']['chromatic_lattice']['params']['chromatic_lattice.eye_ripple_response']==1
    save_composition(tmp_path/'pulse.json',pulse)
    assert load_composition(tmp_path/'pulse.json')==pulse
    w.undo_composition();assert c.document==changed
    w.redo_composition();assert c.document==pulse
    panel.controls['chromatic_lattice.eye_enabled'].input.setCurrentIndex(0)
    assert path not in panel.object_eligible


def test_cell_pulse_arrives_at_center_then_restores_without_a_trough():
    p=params(eye_ripple=.75,eye_ripple_response=1,eye_blink_count=1,eye_double_blink=0.,
             eye_blink_variation=0.,eye_blink_fps=0,eye_ripple_speed=5.,eye_ripple_width=1.)
    trigger=ripple_triggers(1,8.,.38,0.,0.,0,141126)[0][0]
    def response(age, radius):
        profile=ripple_profile(p,trigger+age,141126)
        return np.interp(radius,profile[0],profile[1])
    assert response(.5,3.)==0.  # Front has not reached this cell.
    assert response(.66,3.)>.3
    assert response(.81,3.)==0.  # No inward contraction after the pulse.
    assert response(.86,4.)>0
    profile=ripple_profile(p,trigger+.66,141126)
    assert profile[1].min()>=0
    for age in (.5,.66,.81):
        a=ripple_profile(p,trigger+age,141126)
        b=ripple_profile(p,trigger+age+8,141126)
        assert np.allclose(a,b,atol=1e-12)


def test_cell_response_is_rigid_circular_and_leaves_space_between_cells():
    p=params(eye_ripple_response=1,grid_x=0.,grid_y=0.)
    ix=np.array([3.,0.,-3.,0.],np.float32);iy=np.array([0.,3.,0.,-3.],np.float32)
    u=np.array([1.,2.,3.,4.],np.float32);v=-u
    radius=np.full(4,3.,np.float32); rounding=np.full(4,.16,np.float32)
    profile=(np.array([0.,3.,10.]),np.array([0.,.5,0.]),np.array([0.,.5,0.]))
    a,b,r=ripple_cells(ix,iy,u,v,radius,rounding,10.,p,profile)
    assert np.array_equal(a,u) and np.array_equal(b,v)
    assert np.allclose(r,radius*1.1)  # Whole-cell scaling, same at four directions.
    # Every pixel belonging to one cell shares its center/response.
    a,b,r=ripple_cells(np.full(4,3.,np.float32),np.zeros(4,np.float32),u,v,radius,rounding,10.,p,profile)
    assert np.allclose(r,r[0]) and np.array_equal(a,u)
    for mode in (1,2):
        for shape in (0,1,2,3):
            for rotation in (0,19,45,90):
                q=dict(p,eye_ripple_response=mode,shape=shape,rotation=rotation)
                a,b,r=ripple_cells(ix,iy,u,v,radius,rounding,10.,q,profile)
                angle=np.deg2rad(rotation)+(np.pi/4 if shape==2 else 0)
                extent=r
                if shape in (1,2):
                    extent=r*(.70710678 if shape==2 else 1.)*((abs(np.cos(angle))+abs(np.sin(angle)))*(1-rounding)+rounding)
                assert np.all(extent+np.maximum(abs(a-u),abs(b-v))<=4.85001)
    # Position is relative to the eye, including grid offsets.
    shifted=dict(p,grid_x=1.,grid_y=0.)
    assert np.allclose(ripple_cells(ix-1,iy,u,v,radius,rounding,10.,shifted,profile)[2],
                       ripple_cells(ix,iy,u,v,radius,rounding,10.,p,profile)[2])


@pytest.mark.parametrize('mode',[1,2])
def test_cell_modes_keep_eye_and_distant_cells_and_survive_random_seeks(mode):
    p=params(eye_placement=1,eye_size=5.7,eye_ripple=.75,eye_ripple_response=mode,
             eye_blink_count=1,eye_double_blink=0.,eye_blink_variation=0.,eye_blink_fps=0,
             grain=0.,softness=0.,glow=0.)
    source=np.zeros((640,360,3),np.float32)
    preset=dict(default_synth_preset(),seed=141126,width=360,height=640,speed=1.)
    a=render_chromatic_lattice(source,p,3.6,preset)
    b=render_chromatic_lattice(source,dict(p,eye_ripple=0.),3.6,preset)
    render_chromatic_lattice(source,p,5.3,preset)
    assert np.array_equal(a,render_chromatic_lattice(source,p,3.6,preset))
    assert np.array_equal(a[305:335,165:195],b[305:335,165:195])
    assert np.max(abs(a-b))>.05
    assert np.array_equal(a[:40],b[:40])


def test_old_fluid_response_is_default_and_pixel_identical():
    p=params(eye_ripple=.55)
    p.pop('eye_ripple_response',None)
    source=np.zeros((256,144,3),np.float32)
    preset=dict(default_synth_preset(),seed=141126,width=144,height=256,speed=1.)
    assert np.array_equal(render_chromatic_lattice(source,p,2.3,preset),
                          render_chromatic_lattice(source,dict(p,eye_ripple_response=0),2.3,preset))


from test_synth_effects_editor_integration import make_window
