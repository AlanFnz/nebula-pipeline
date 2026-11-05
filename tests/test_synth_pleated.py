import copy
import json
import subprocess

import numpy as np
import pytest

from synth import MODULE_BY_ID, curated_presets, default_synth_preset
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_effect_catalog import effect_catalog
from synth_effects import describe_effects
from synth_pleated import render_pleated_field
from synth_pleated_recipes import pleated_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_source_adapters import source_frame
from synth_starters import starter_composition
from synth_studies import composition_category
from synth_subject import active_subjects, scope_states, select_subject


def defaults():
    return {s.key:s.default for s in MODULE_BY_ID['pleated_field'].params}


def test_study_is_portable_and_seek_order_independent(tmp_path):
    project=starter_composition('pleated-signal')
    assert project == pleated_composition()
    assert composition_category(project)=='Signals'
    assert active_subjects(describe_effects(scope_states(project)))==('pleated',)
    assert 'pleated_field' not in {e.id for e in effect_catalog()}
    from synth_effect_order import movable
    assert not movable('pleated_field')
    sequence=compile_composition(project)
    assert sequence['duration']==15 and sequence['fps']==12
    assert (sequence['canvas']['width'],sequence['canvas']['height'])==(960,720)
    a=render_sequence_frame(sequence,4.5,(160,120)).tobytes()
    assert render_sequence_frame(sequence,7.,(160,120)).tobytes()!=a
    assert render_sequence_frame(sequence,4.5,(160,120)).tobytes()==a
    save_composition(tmp_path/'study.json',project)
    reopened=compile_composition(load_composition(tmp_path/'study.json'))
    assert render_sequence_frame(reopened,4.5,(160,120)).tobytes()==a
    empty=select_subject(project,'none')
    assert active_subjects(describe_effects(scope_states(empty)))==()
    assert active_subjects(describe_effects(scope_states(select_subject(empty,'text'))))==('text',)
    assert active_subjects(describe_effects(scope_states(select_subject(empty,'pleated'))))==('pleated',)


@pytest.mark.parametrize('profile',[0,1,2])
@pytest.mark.parametrize('symmetry',[0,1,2,3])
def test_bounded_surface_across_profiles_mirrors_and_extreme_views(profile,symmetry):
    arr=np.full((72,96,3),.2,np.float32)
    preset=dict(default_synth_preset(),width=96,height=72)
    p=dict(defaults(),profile=profile,symmetry=symmetry,depth=1.4,curl=.4,
           density=18,size=.02,perspective=.9,tilt_x=1.5,tilt_y=-1.5)
    for boundary in (0,1,2):
        result=render_pleated_field(arr,dict(p,boundary=boundary),2.3,preset)
        assert result.shape==arr.shape and np.isfinite(result).all()
        assert 0<=result.min()<=result.max()<=1
    assert np.all(arr==np.float32(.2))
    assert render_pleated_field(arr,dict(p,mix=0),0,preset) is arr


def test_cadence_freeze_opacity_and_controls():
    arr=np.full((120,160,3),.2,np.float32)
    preset=dict(default_synth_preset(),width=160,height=120,speed=1.)
    p=defaults()
    a=render_pleated_field(arr,p,1.,preset)
    assert np.array_equal(a,render_pleated_field(arr,p,1.02,preset))
    assert not np.array_equal(a,render_pleated_field(arr,p,1.1,preset))
    frozen=dict(preset,speed=0)
    assert np.array_equal(render_pleated_field(arr,p,0,frozen),render_pleated_field(arr,p,10,frozen))
    assert np.allclose(render_pleated_field(arr,dict(p,mix=.5),1.,preset),(a+arr)*.5)
    for change in (dict(palette=1),dict(palette=2),dict(palette=3),dict(hue_shift=.2),
                   dict(profile=1),dict(profile=2),dict(density=8),dict(symmetry=2),
                   dict(aperture=.2),dict(depth=0),dict(angle=65),dict(seams=0)):
        assert np.mean(np.abs(a-render_pleated_field(arr,dict(p,**change),1.,preset)))>.0001


def test_reframing_does_not_stretch_folds_and_anchor_is_source_center():
    preset=resolve_sequence_frame(compile_composition(pleated_composition()),0)[-1]
    preset.update(width=160,height=120)
    p=dict(defaults(),softness=0)
    a=render_pleated_field(np.zeros((120,160,3),np.float32),p,0,preset)
    wide=copy.deepcopy(preset);wide.update(resize_canvas(preset,dict(width=240,height=120)))
    b=render_pleated_field(np.zeros((120,240,3),np.float32),p,0,wide)
    assert np.array_equal(a,b[:,40:200])
    assert source_frame(preset,(160,120),0).origin==(80.,60.)
    assert source_frame(dict(preset,object_x=10,object_y=-5),(160,120),0).origin==(90.,55.)


def test_new_source_is_disabled_in_existing_presets():
    for preset in curated_presets().values():
        assert not next(m for m in preset['modules'] if m['id']=='pleated_field')['enabled']


def test_native_export_is_exactly_fifteen_seconds(tmp_path):
    from synth_media import export_synth_video
    seq=compile_composition(pleated_composition())
    output=tmp_path/'folds.mp4'
    export_synth_video(default_synth_preset(),output,size=(96,72),sequence=seq)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'stream=nb_frames,r_frame_rate,width,height:format=duration','-of','json',str(output)]))
    assert float(info['format']['duration'])==15.
    assert info['streams'][0]['nb_frames']=='180'
    assert info['streams'][0]['r_frame_rate']=='12/1'
