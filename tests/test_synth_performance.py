import copy
import json
import numpy as np
import pytest
from PIL import Image, ImageDraw
from synth_performance import (defaults, normalize_performance, values_at, source_time,
    base_document, apply_frame, apply_surface, apply_signals, available_controls)
from synth_composition import compile_composition, normalize_composition, composition_from_sequence
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_pleated_recipes import pleated_composition


@pytest.fixture(scope='module')
def sequence():
    return compile_composition(pleated_composition())


def test_optional_config_roundtrips_project_and_sequence(sequence):
    project = composition_from_sequence(sequence)
    original = normalize_composition(project)
    config = defaults(); config['values']['twist'] = 35
    config['tracks']['scale'] = [[0, 100], [.3, 125], [1, 80]]
    project['visual_performance'] = config
    loaded = normalize_composition(json.loads(json.dumps(project)))
    assert loaded['schema_version'] == 7
    compiled = compile_composition(loaded)
    assert compiled['visual_performance'] == config
    promoted = composition_from_sequence(compiled)
    assert promoted['visual_performance'] == config
    assert 'visual_performance' not in promoted['source']
    assert base_document(loaded) == original


@pytest.mark.parametrize('bad', [
    dict(version=2), dict(version=True), dict(version=1, enabled=1),
    dict(version=1, values={'pace':0}), dict(version=1, values={'x':float('nan')}),
    dict(version=1, values={'unknown':3}), dict(version=1, tracks={'scale':[[.2,100],[.1,110]]}),
    dict(version=1, tracks={'scale':[[0,100],[0,110]]}),
])
def test_validation_rejects_bad_automation(bad):
    with pytest.raises(ValueError): normalize_performance(bad)


@pytest.mark.parametrize('time', [0, 2.3, 9.3, 18])
def test_neutral_and_disabled_are_pixel_exact(sequence, time):
    original = render_sequence_frame(sequence, time, (96,72))
    performed = dict(sequence, visual_performance=defaults())
    assert render_sequence_frame(performed,time,(96,72)).tobytes() == original.tobytes()
    performed['visual_performance']['enabled'] = False
    performed['visual_performance']['values'].update(scale=150, opening=70)
    assert render_sequence_frame(performed,time,(96,72)).tobytes() == original.tobytes()


def test_recording_interpolation_and_integrated_pace():
    config=defaults(); config['tracks']={'scale':[[.2,80],[.8,140]], 'pace':[[0,50],[1,150]]}
    assert values_at(config,0,10)['scale']==80
    assert values_at(config,5,10)['scale']==110
    assert values_at(config,10,10)['scale']==140
    assert source_time(config,5,10,100)==3.75
    config['tracks']={}; config['values']['pace']=200
    assert source_time(config,6,10,30)==2
    config['values']['fluidity']=100
    assert source_time(config,.125,10,120)<.25


def test_rotation_preserves_aspect_ratio():
    image=Image.new('RGB',(160,90)); d=ImageDraw.Draw(image); d.rectangle((65,35,94,54),fill='white')
    config=defaults();config['values']['rotation']=90
    a=np.asarray(apply_frame(image,config,0,10))[:,:,0]>128
    ys,xs=np.where(a)
    assert (xs.max()-xs.min()+1,ys.max()-ys.min()+1)==(20,30)


def test_preview_stage_matches_export_and_is_deterministic(sequence):
    config=defaults(); config['values'].update(scale=120, twist=37, texture=20, color=30, pace=125)
    config['tracks']['x']=[[0,-5],[1,5]]
    performed=dict(sequence,visual_performance=config)
    time=3.2
    raw=render_sequence_frame(base_document(performed), source_time(config,time,sequence['duration'],sequence['fps']),(96,72))
    expected=apply_frame(raw,config,time,sequence['duration'],sequence['seed'])
    actual=render_sequence_frame(performed,time,(96,72))
    assert actual.tobytes()==expected.tobytes()
    assert render_sequence_frame(performed,time,(96,72)).tobytes()==actual.tobytes()


def test_surface_adapter_is_relative_and_keeps_original(sequence):
    preset=resolve_sequence_frame(sequence,1)[-1]; original=copy.deepcopy(preset)
    config=defaults();config['values'].update(opening=50,relief=150,density=150)
    changed=apply_surface(preset,config,1,sequence['duration'])
    assert preset==original
    before=next(m for m in preset['modules'] if m['id']=='pleated_field')['params']
    after=next(m for m in changed['modules'] if m['id']=='pleated_field')['params']
    assert after['aperture']==min(6,before['aperture']+1.25)
    assert after['density']>before['density']
    assert {'opening','relief','density'} <= {c.key for c in available_controls(sequence)}
    performed=dict(sequence,visual_performance=config)
    base=base_document(performed)
    assert base['visual_performance']['values']['opening']==50
    assert render_sequence_frame(performed,1,(96,72)).tobytes()!=render_sequence_frame(sequence,1,(96,72)).tobytes()


def test_audio_neutral_identity_and_shared_visual_clock():
    t=np.linspace(0,10,1201)
    signals=dict(time=t,presence=np.ones_like(t),expansion=t/10,motion=t/20,opening=np.zeros_like(t))
    assert apply_signals(signals,None,10,30) is signals
    assert apply_signals(signals,defaults(),10,30) is signals
    config=defaults();config['values']['pace']=200
    changed=apply_signals(signals,config,10,30)
    assert changed['expansion'][240]==pytest.approx(.4)
    config['values'].update(scale=50,x=20)
    changed=apply_signals(signals,config,10,30)
    assert changed['presence'][240]==pytest.approx(.25)
    config['tracks']['rotation']=[[0,0],[1,180]]
    assert apply_signals(signals,config,10,30)['motion'][500]>changed['motion'][500]


def test_sound_cache_includes_frame_rate_for_performed_timing(sequence):
    from synth_visual_sound import sound_key
    performed=dict(sequence,visual_performance=defaults())
    performed['visual_performance']['values']['pace']=123
    assert sound_key(performed)!=sound_key(dict(performed,fps=24))
    assert sound_key(sequence)==sound_key(dict(sequence,fps=24))
