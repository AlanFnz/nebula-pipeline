import copy
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image

from synth import MODULE_BY_ID, default_synth_preset
from synth_blender import render_blender_scene, stepped_orbit, orbital_steps
from synth_blender_parts import part_poses, parts_for
from synth_blender_recipes import orbital_rings_composition, optical_relic_composition
from synth_composition import compile_composition, save_composition, load_composition
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition


def defaults(name):return {p.key:p.default for p in MODULE_BY_ID[name].params}


def test_reference_timing_held_poses_and_repeat():
    steps=orbital_steps()
    assert len(steps)==60 and steps[0]==0 and all(b>a for a,b in zip(steps,steps[1:]))
    period=226/30
    poses=[stepped_orbit(math.tau*(frame/30)/period,60) for frame in range(226)]
    assert len(set(poses))==60
    assert len(set(poses[:4]))==1 and poses[4]!=poses[3]
    for frame in (0,4,15,75,113,222):
        assert stepped_orbit(math.tau*(frame/30)/period,60)==stepped_orbit(math.tau*((frame+226)/30)/period,60)
    assert stepped_orbit(.123,0)==.123
    assert len({stepped_orbit(math.tau*f/240,12) for f in range(240)})==12


def test_legacy_source_request_is_unchanged_and_new_parts_are_scoped(monkeypatch):
    import synth_blender_bridge as bridge
    calls=[]
    def render(p,a,size,**kw):calls.append((p,a,size,kw));return Image.new('RGB',size)
    monkeypatch.setattr(bridge,'render_frame',render)
    preset=dict(default_synth_preset(),speed=1.)
    params=defaults('blender_scene')
    render_blender_scene(np.zeros((32,24,3)),params,0,preset)
    assert set(calls[0][0])=={'scene_version','ring_width','tube_radius','hoop_bow','hoop_twist',
       'body_height','base_width','crown_size','axle_length','size','camera_yaw','camera_elevation',
       'metal_hue','metal_saturation','metallic','roughness','environment','reflection_contrast',
       'background_hue','background_saturation','light_angle','light_size','light_power','exposure',
       'framing_height','offset_x','offset_y'}
    assert part_poses(dict(params,part_ring1_position_x=1.),0)=={}
    assert part_poses(dict(params,scene=1,part_upper_position_x=1.),0)=={}
    poses=part_poses(dict(params,scene=1,part_ring2_turns_z=1,part_core_visible=0),.5)
    assert set(poses)=={'ring2','core'}
    assert len(parts_for(0))==7 and len(parts_for(1))==8


def test_new_study_roundtrip_and_exposures_use_shared_renderer(monkeypatch,tmp_path):
    import synth_blender_bridge as bridge
    calls=[]
    def render(p,a,size,**kw):
        calls.append((p,a,kw));return Image.new('RGB',size,(int(a*20)%255,130,70))
    monkeypatch.setattr(bridge,'render_frame',render)
    p=orbital_rings_composition();original=copy.deepcopy(p)
    save_composition(tmp_path/'rings.json',p)
    seq=compile_composition(load_composition(tmp_path/'rings.json'))
    assert seq['duration']==11.3 and seq['fps']==30
    out=render_sequence_frame(seq,.7,(72,90))
    assert len(calls)==2 and calls[0][0]==calls[1][0] and calls[0][1]!=calls[1][1]
    assert 'motion_exposure' not in calls[0][0]
    assert np.asarray(out).shape==(90,72,3)
    assert load_composition(tmp_path/'rings.json')==original
    assert original==json.loads((Path(__file__).parents[1]/'presets/orbital-rings-v1.json').read_text())
    assert optical_relic_composition()==starter_composition('optical-relic')


def test_film_gate_is_opt_in_and_resolution_independent():
    from synth_broadcast_detail import glass_optics
    p=dict(defaults('broadcast'),screen=1.,screen_wear=0.,screen_inset=.02,screen_radius=.06,halo=0.)
    def render(size,settings):
        w,h=size
        return glass_optics(np.ones((h,w,3),np.float32)*.5,settings,np.random.default_rng(1),1)
    old={k:v for k,v in p.items() if k not in ('screen_shape','screen_radius')}
    assert np.array_equal(render((72,90),p),render((72,90),old))
    gate=render((720,900),dict(p,screen_shape=1))
    assert gate[0,360].max()==0 and gate[450,0].max()==0
    assert np.allclose(gate[450,360],.5)
    assert gate[25,25].max()<.1 and gate[25,360].min()>.4
