import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import pytest

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_blender import render_optical_diffusion, rotation
from synth_blender_recipes import optical_relic_composition
from synth_composition import compile_composition, save_composition, load_composition
from synth_sequence import render_sequence_frame


def defaults(name):
    return {p.key:p.default for p in MODULE_BY_ID[name].params}


@pytest.fixture
def bridge(monkeypatch,tmp_path):
    import synth_blender_bridge as b
    executable = tmp_path/'blender'; executable.write_text('fake executable')
    monkeypatch.setattr(b,'blender_executable',lambda:executable)
    monkeypatch.setattr(b,'CACHE',tmp_path/'frames')
    calls=[]
    def request(payload,exe):
        calls.append(copy.deepcopy(payload))
        time.sleep(.01)
        Image.new('RGB',tuple(payload['size']),(60,120,80)).save(payload['output'])
        return {'ok':True}
    monkeypatch.setattr(b.worker,'request',request)
    return b,calls,executable


def test_cache_reuse_resolution_geometry_and_corruption(bridge):
    b,calls,exe = bridge
    p=defaults('blender_scene')
    with ThreadPoolExecutor(4) as pool:
        frames=list(pool.map(lambda _:b.render_frame(p,0.,(48,64)),range(4)))
    assert len(calls)==1 and all(f.size==(48,64) for f in frames)
    b.render_frame(p,0.,(96,128)); b.render_frame(dict(p,ring_width=1.2),0.,(48,64))
    b.render_frame(p,.5,(48,64))
    assert len(calls)==4
    path=b.CACHE/(b.cache_key(p,0.,(48,64),exe)+'.png')
    path.write_bytes(b'incomplete')
    b.render_frame(p,0.,(48,64))
    assert len(calls)==5 and not list(b.CACHE.glob('*.part.png'))


def test_failed_render_is_never_cached_and_retry_succeeds(bridge,monkeypatch):
    b,calls,exe=bridge
    request=b.worker.request
    def fail(payload,exe):
        Path(payload['output']).write_bytes(b'partial')
        raise RuntimeError('device unavailable')
    monkeypatch.setattr(b.worker,'request',fail)
    with pytest.raises(RuntimeError,match='device unavailable'):
        b.render_frame(defaults('blender_scene'),0.,(32,48))
    assert not list(b.CACHE.glob('*.png'))
    monkeypatch.setattr(b.worker,'request',request)
    assert b.render_frame(defaults('blender_scene'),0.,(32,48)).size==(32,48)


def test_project_roundtrip_and_optical_edits_reuse_clean_scene(bridge,tmp_path):
    b,calls,exe=bridge
    project=optical_relic_composition();before=copy.deepcopy(project)
    seq=compile_composition(project)
    a=render_sequence_frame(seq,0.,(72,96)).tobytes()
    save_composition(tmp_path/'scene.json',project)
    restored=compile_composition(load_composition(tmp_path/'scene.json'))
    assert a==render_sequence_frame(restored,0.,(72,96)).tobytes()
    project['effects']['optical_diffusion']={'mode':'on','params':{'optical_diffusion.grain':.07}}
    different=render_sequence_frame(compile_composition(project),0.,(72,96)).tobytes()
    assert different!=a and len(calls)==1
    assert before==load_composition(tmp_path/'scene.json')


def test_scene_cycle_matches_70_reference_frames_and_is_smooth():
    p=dict(defaults('blender_scene'),period=35/6)
    for frame in range(70):
        t=frame/24
        assert rotation(t,p)==rotation(t+70/24,p)==rotation(t+140/24,p)
    angles=[rotation(t/240,p) for t in range(699)]
    assert np.min(np.diff(angles))>0
    assert rotation(0,p)==rotation(8.75,p)


def test_optical_finish_loop_bypass_and_intensity():
    p=dict(defaults('optical_diffusion'),period=8.75)
    preset=dict(default_synth_preset(),speed=1.)
    a=np.full((96,72,3),.5,np.float32)
    out=render_optical_diffusion(a,p,.5,preset)
    assert np.array_equal(out,render_optical_diffusion(a,p,9.25,preset))
    assert render_optical_diffusion(a,dict(p,mix=0.),.5,preset) is a
    assert np.isfinite(out).all() and out.max()<=1 and out.min()>=0
    assert np.all(a==.5)


def test_existing_studies_never_start_blender(monkeypatch):
    import synth_blender_bridge as b
    def fail(): raise AssertionError('Legacy source requested Blender')
    monkeypatch.setattr(b,'blender_executable',fail)
    for preset in curated_presets().values():
        assert not next(m for m in preset['modules'] if m['id']=='blender_scene')['enabled']
        assert not next(m for m in preset['modules'] if m['id']=='optical_diffusion')['enabled']
    render_synth_frame(default_synth_preset(),size=(64,64))


def test_missing_blender_has_actionable_error(monkeypatch):
    import synth_blender_bridge as b
    monkeypatch.setattr(b.shutil,'which',lambda _:None)
    monkeypatch.setattr(Path,'is_file',lambda _:False)
    with pytest.raises(ValueError,match='Install Blender in Applications'):
        b.blender_executable()


def test_saved_study_is_frozen_and_new_sources_are_not_effects():
    from synth_starters import starter_composition
    from synth_effect_catalog import effect_catalog
    from synth_subject import active_subjects,scope_states,select_subject
    from synth_effects import describe_effects
    project=starter_composition('optical-relic')
    assert project==optical_relic_composition()
    assert active_subjects(describe_effects(scope_states(project)))==('blender',)
    assert active_subjects(describe_effects(scope_states(select_subject(project,'none'))))==()
    assert 'blender_scene' not in {e.id for e in effect_catalog()}
    assert 'optical_diffusion' in {e.id for e in effect_catalog()}
