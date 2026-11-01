import copy
import json
import subprocess
import wave

import numpy as np
import pytest

from media import Cancellation, Cancelled
from synth import default_synth_preset
from synth_composition import compile_composition, composition_from_sequence, load_composition, save_composition
from synth_pleated_recipes import pleated_composition, pleated_sound_composition
from synth_sequence import normalize_sequence, render_sequence_frame
from synth_visual_sound import (RATE, audio_output, default_sound, acid_sound, instrument_sound, normalize_sound,
    pcm_blocks, visual_signals, write_sound, sound_key)


@pytest.fixture(scope='module',params=[1,2,3])
def study(request):
    seq=compile_composition(pleated_sound_composition())
    if request.param==2: seq['generated_sound']=acid_sound()
    if request.param==3: seq['generated_sound']=instrument_sound()
    return seq


def short_study(study, duration=2.):
    seq=copy.deepcopy(study);seq['duration']=duration
    seq['cues']=[c for c in seq['cues'] if c['time']<duration]
    seq.pop('time_map',None)
    return normalize_sequence(seq)


def pcm(seq):
    return np.concatenate(list(pcm_blocks(seq)))


def test_optional_versioned_data_roundtrips_and_does_not_change_pixels(tmp_path):
    silent=pleated_composition();audible=pleated_sound_composition()
    save_composition(tmp_path/'sound.json',audible)
    loaded=load_composition(tmp_path/'sound.json')
    assert loaded==audible
    seq=compile_composition(loaded)
    assert composition_from_sequence(seq)['generated_sound']==audible['generated_sound']
    before=compile_composition(silent)
    for t in (0,.75,4.75,9.25,10.25,18.):
        assert render_sequence_frame(seq,t,(96,72)).tobytes()==render_sequence_frame(before,t,(96,72)).tobytes()
    assert 'generated_sound' not in silent and 'generated_sound' not in before


@pytest.mark.parametrize('field,value', [('gain',float('nan')),('pitch',0),('smoothing',True),('version',True),('output','mix'),('source','text')])
def test_invalid_settings_fail(field,value):
    config=default_sound();config[field]=value
    with pytest.raises(ValueError): normalize_sound(config)


def test_deterministic_bounded_pcm_independent_of_preview_fps(study):
    seq=short_study(study)
    a=pcm(seq);b=pcm(seq)
    assert np.array_equal(a,b)
    assert a.shape==(2*RATE,2) and np.isfinite(a).all()
    assert .03<np.sqrt(np.mean(a*a))<.3 and np.max(np.abs(a))<.8
    seq['fps']=60
    assert np.array_equal(a,pcm(seq))
    assert sound_key(seq)==sound_key(dict(seq,fps=12))
    assert np.max(np.abs(a[0]))==0
    assert np.max(np.abs(a[-1]))<.001
    # Bounded sample jumps across one-second processing blocks.
    assert np.max(np.abs(a[RATE]-a[RATE-1]))<.03


def test_disabled_connections_and_removed_source_are_silent(study):
    seq=short_study(study,.4)
    for entry in seq['generated_sound']['connections'].values(): entry['enabled']=False
    assert np.count_nonzero(pcm(seq))==0
    seq['generated_sound']=default_sound()
    for state in seq['states'].values():
        state['enabled']=[key for key in state['enabled'] if key!='pleated_field']
    assert np.count_nonzero(pcm(seq))==0
    assert not visual_signals(seq)['opening'].any()


def test_collapse_silence_and_reopening_attack_come_from_gate(study):
    signals=visual_signals(study)
    closed=(signals['time']>9.3)&(signals['time']<9.55)
    assert signals['presence'][closed].max()<.025
    events=signals['time'][signals['opening']>0]
    assert any(9.5<t<10.2 for t in events)
    assert all(signals['presence'][signals['opening']>0]>.12)
    altered=copy.deepcopy(study)
    for state in altered['states'].values():
        state['overrides'].update({'pleated_field.aperture':6.,'pleated_field.edge':0.,'pleated_field.boundary':0})
    changed=visual_signals(altered)
    assert changed['presence'][closed].min()>.5
    assert not any(9.5<t<10.2 for t in changed['time'][changed['opening']>0])


def test_constant_slider_flow_is_still_motion_and_bypass_stops_it(study):
    seq=short_study(study,1.)
    state=copy.deepcopy(next(iter(seq['states'].values())))
    state['overrides'].update({'pleated_field.flow':1.,'pleated_field.irregularity':0.})
    seq['states']={'held':state};seq['cues']=[dict(time=0.,state='held',transition='cut',duration=0.)]
    assert visual_signals(seq)['motion'].max()>.1
    state['overrides']['pleated_field.flow']=0.
    assert visual_signals(seq)['motion'].max()==0
    state['overrides']['pleated_field.mix']=0.
    assert not visual_signals(seq)['presence'].any()


def test_changing_connection_changes_audio_and_preserves_undo_input(study):
    seq=short_study(study,.5);before=copy.deepcopy(seq)
    first=pcm(seq);seq['generated_sound']['pitch']=110.
    assert not np.array_equal(first,pcm(seq))
    assert np.array_equal(first,pcm(before))
    assert seq['states']==before['states']


def test_cancellation_keeps_destination_and_cleans_partial_files(tmp_path,study):
    destination=tmp_path/'sound.wav';destination.write_bytes(b'original')
    cancel=Cancellation();cancel.cancel()
    with pytest.raises(Cancelled): write_sound(study,destination,cancel)
    assert destination.read_bytes()==b'original'
    assert list(tmp_path.iterdir())==[destination]


def test_wav_full_timeline_is_exact_seek_source(tmp_path,study):
    seq=short_study(study)
    path=write_sound(seq,tmp_path/'sound.wav')
    path2=write_sound(seq,tmp_path/'again.wav')
    assert path.read_bytes()==path2.read_bytes()
    with wave.open(str(path)) as f:
        assert f.getnframes()==2*RATE and f.getframerate()==RATE and f.getsampwidth()==3
        whole=f.readframes(f.getnframes())
        f.setpos(round(.73*RATE));part=f.readframes(12000)
    assert part==whole[round(.73*RATE)*6:(round(.73*RATE)+12000)*6]


def test_export_has_sound_silence_choice_and_partial_project_clock(tmp_path,study):
    from synth_media import export_synth_video
    seq=short_study(study,1.)
    full=tmp_path/'full.mp4';part=tmp_path/'part.mp4'
    export_synth_video(default_synth_preset(),full,sequence=seq,size=(64,48))
    export_synth_video(default_synth_preset(),part,sequence=seq,size=(64,48),start=6,count=6)
    def decode(path):
        return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ac','2','-ar',str(RATE),'-']),dtype='<f4').reshape(-1,2)
    full_audio=decode(full);part_audio=decode(part)
    # AAC boundary padding differs; compare the interior to the same timeline.
    a=full_audio[24000+2048:48000-2048,0];b=part_audio[2048:24000-2048,0]
    assert np.corrcoef(a,b)[0,1]>.99
    seq['generated_sound']['output']='silent'
    silent=tmp_path/'silent.mp4'
    export_synth_video(default_synth_preset(),silent,sequence=seq,size=(64,48))
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(silent)]))['streams']
    assert [s['codec_type'] for s in streams]==['video']
    seq['generated_sound']['output']='existing'
    seq['soundtrack']={'export_audio':'soundtrack'}
    assert audio_output(seq)=='soundtrack'
    seq['generated_sound']['output']='generated'
    assert audio_output(seq)=='generated'
    seq['generated_sound']['enabled']=False
    assert audio_output(seq)=='silent'
