import copy
import json
from pathlib import Path

import numpy as np
from PIL import Image

from synth import MODULE_BY_ID, default_synth_preset
from synth_blender import ORBITAL_VARIANT_KEYS, render_blender_scene
from synth_blender_recipes import (yin_yang_composition, yin_yang_flowing_composition,
    yin_yang_drifting_composition, orbital_clean_painted_composition,
    orbital_smooth_painted_composition, optical_relic_composition)
from synth_composition import compile_composition, save_composition, load_composition
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition


def test_yin_yang_roundtrip_retains_only_two_moving_pieces(monkeypatch,tmp_path):
    import synth_blender_bridge as bridge
    calls=[]
    def render(params,angle,size,**kwargs):
        calls.append((params,angle,kwargs));return Image.new('RGB',size,'seagreen')
    monkeypatch.setattr(bridge,'render_frame',render)
    project=starter_composition('yin-yang'); original=copy.deepcopy(project)
    save_composition(tmp_path/'yin.json',project)
    seq=compile_composition(load_composition(tmp_path/'yin.json'))
    render_sequence_frame(seq,1.,(72,90))
    assert seq['duration']==15. and seq['fps']==30
    assert len(calls)==1  # no delayed exposure obscuring the symbol
    params,_,kwargs=calls[0]
    assert params['scene']==1 and params['orbital_finish']==1 and params['orbit_shape_2']==1
    assert params['orbit_smooth_2']==1.
    assert all(params[f'orbit_shape_{i}']==0 for i in (1,3,4,5))
    assert set(kwargs['parts'])=={'ring3','ring4','ring5','core'}
    assert all(not edit['visible'] for edit in kwargs['parts'].values())
    assert project==original==load_composition(tmp_path/'yin.json')==yin_yang_drifting_composition()
    assert project['source']['states']['rings']['enabled']==['blender_scene','optical_diffusion']
    settings=project['source']['states']['rings']['overrides']
    assert settings['blender_scene.period']==settings['optical_diffusion.period']==15.
    assert params['orbit_pace_2']>0. and params['orbit_drift_2']>0.
    for seconds in (0.,7.5,15.):
        render_sequence_frame(seq,seconds,(72,90))
    assert calls[-1]==calls[-3] and calls[-2]!=calls[-1]


def test_neutral_variants_preserve_original_requests_and_frozen_recipes(monkeypatch):
    import synth_blender_bridge as bridge
    requests=[]
    monkeypatch.setattr(bridge,'render_frame',lambda p,a,size,**kw:requests.append(p) or Image.new('RGB',size))
    p={p.key:p.default for p in MODULE_BY_ID['blender_scene'].params}
    p['scene']=1
    arr=np.zeros((32,24,3))
    render_blender_scene(arr,p,0,default_synth_preset())
    assert not ORBITAL_VARIANT_KEYS.intersection(requests[-1])
    p['orbit_pattern']=17
    render_blender_scene(arr,p,0,default_synth_preset())
    assert not ORBITAL_VARIANT_KEYS.intersection(requests[-1])
    p['orbit_pace_3']=.4;p['orbit_drift_3']=12.
    render_blender_scene(arr,p,0,default_synth_preset())
    assert ORBITAL_VARIANT_KEYS.intersection(requests[-1])=={'orbit_pattern','orbit_pace_3','orbit_drift_3'}
    p['orbit_pace_3']=p['orbit_drift_3']=0.
    p['orbit_smooth_2']=1.
    render_blender_scene(arr,p,0,default_synth_preset())
    assert ORBITAL_VARIANT_KEYS.intersection(requests[-1])=={'orbit_smooth_2'}
    p['orbit_smooth_2']=0.
    p['orbital_finish']=1
    render_blender_scene(arr,p,0,default_synth_preset())
    assert ORBITAL_VARIANT_KEYS.intersection(requests[-1])=={'orbital_finish'}
    p['scene']=0;p['orbit_shape_2']=1
    render_blender_scene(arr,p,0,default_synth_preset())
    assert not ORBITAL_VARIANT_KEYS.intersection(requests[-1])
    root=Path(__file__).parents[1]/'presets'
    assert orbital_clean_painted_composition()==json.loads((root/'orbital-rings-v3.json').read_text())
    assert optical_relic_composition()==json.loads((root/'optical-relic-v1.json').read_text())
    assert yin_yang_composition()==json.loads((root/'yin-yang-v1.json').read_text())
    assert yin_yang_flowing_composition()==json.loads((root/'yin-yang-v2.json').read_text())


def test_painted_study_only_smooths_white_ring():
    original=orbital_clean_painted_composition()
    updated=orbital_smooth_painted_composition()
    expected=copy.deepcopy(original)
    expected['source']['states']['rings']['overrides']['blender_scene.orbit_smooth_2']=1.
    assert updated==expected==starter_composition('orbital-rings')
    assert compile_composition(updated)['duration']==11.3
