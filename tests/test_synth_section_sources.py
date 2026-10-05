"""Independent media, local clocks, saves, studies and real audio exports."""
import copy
from pathlib import Path
import subprocess

import numpy as np
import pytest

from synth import default_synth_preset
from synth_composition import (compile_composition, composition_from_sequence,
    load_composition, normalize_composition, save_composition, stretch_section)
from synth_media import export_synth_video
from synth_preview import preview_context
from synth_section_sources import video_source_at
from synth_sequence import normalize_sequence, render_sequence_frame
from synth_studies import save_study, study_composition
from synth_video import inspect_video, video_composition, VideoFrameProvider
from test_synth_video import clip, audio_samples
from test_synth_video_audio_retiming import frequency, rms


@pytest.fixture(scope='module')
def other_clip(tmp_path_factory):
    path = tmp_path_factory.mktemp('second source') / 'blue with tone.mkv'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:size=128x96:rate=12:duration=1',
        '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=1',
        '-c:v','ffv1','-c:a','pcm_s16le',str(path)],check=True)
    return inspect_video(path)


def two_sources(clip, other):
    p = video_composition(clip)
    p['sections'][0]['duration'] = .5
    second = copy.deepcopy(p['sections'][0]); second.update(id='second', footage=copy.deepcopy(other))
    p['sections'].append(second)
    return normalize_composition(p)


def test_legacy_shared_clock_is_unchanged_and_local_source_starts_at_its_in(clip, other_clip):
    p = two_sources(clip, other_clip); seq = compile_composition(p)
    with VideoFrameProvider() as provider:
        for t in (0., .25, .5, .75):
            source, seconds = video_source_at(seq, t)
            assert source['path'] == (clip['path'] if t < .5 else other_clip['path'])
            assert seconds == pytest.approx(t if t < .5 else t-.5)
            image = render_sequence_frame(seq,t,frame_provider=provider,bypass=True)
            assert image.tobytes() == provider.frame(source,seconds).tobytes()
    p['sections'][1].pop('footage')
    shared = compile_composition(p)
    assert 'video_segments' not in shared
    assert video_source_at(shared,.75) == (p['footage'],.75)


def test_local_loop_restart_shared_resume_and_speed_clocks(clip, other_clip):
    p = two_sources(clip,other_clip); p['sections'][1].update(loops=2,video_rate=2.)
    third = copy.deepcopy(p['sections'][0]); third['id']='third'; p['sections'].append(third)
    seq = compile_composition(p)
    for t, expected in ((.5,0.),(.75,.5),(1.,0.),(1.25,.5)):
        source, seconds = video_source_at(seq,t)
        assert source['path'] == other_clip['path']; assert seconds == pytest.approx(expected)
    assert video_source_at(seq,1.5)[1] == 2.5  # Retains the shared continuous clock.
    sped = compile_composition(stretch_section(p,'second',.25,'video'))
    assert video_source_at(sped,.625)[1] == .5


def test_detailed_roundtrip_and_retime_preserve_all_media(clip,other_clip):
    p = two_sources(clip,other_clip); p['sections'][1]['video_rate']=2.
    original = compile_composition(p)
    detailed = composition_from_sequence(original)
    rebuilt = compile_composition(detailed)
    for t in (0.,.25,.5,.75): assert video_source_at(rebuilt,t) == video_source_at(original,t)
    shortened = compile_composition(stretch_section(detailed,'section-1',.5,'video'))
    for t in (0.,.125,.25,.375): assert video_source_at(shortened,t) == video_source_at(original,t*2)


def test_personal_study_copies_every_video_and_snapshot_and_resolves_relative_paths(clip,other_clip,tmp_path):
    p = two_sources(clip,other_clip)
    # Reuse the shared asset independently: copies should still deduplicate.
    p['sections'][0]['footage']=copy.deepcopy(clip)
    from synth_exploration import capture_snapshot
    p, _identifier = capture_snapshot(p,'Two sources')
    original = copy.deepcopy(p)
    identifier = save_study(p,'Multi source',directory=tmp_path)
    loaded = study_composition(identifier,directory=tmp_path)
    from synth_section_sources import footage_references
    references = list(footage_references(loaded))
    assert all(Path(f['path']).is_absolute() and Path(f['path']).is_file() for f in references)
    assert len(set(f['path'] for f in references)) == 2
    assert len(list(tmp_path.glob('*/media/*'))) == 2
    assert p == original
    path=tmp_path/'roundtrip.json'; save_composition(path,loaded)
    assert compile_composition(load_composition(path)) == compile_composition(loaded)


@pytest.mark.parametrize('change', [dict(video_rate=0),dict(start=.2),dict(end=.3),dict(video_start=-1),dict(video_rate=float('nan'))])
def test_invalid_media_segments_are_rejected(clip,other_clip,change):
    seq=compile_composition(two_sources(clip,other_clip)); seq['video_segments'][0].update(change)
    with pytest.raises(ValueError): normalize_sequence(seq)


def test_preview_context_tracks_second_asset_changes(clip,other_clip,tmp_path):
    p=two_sources(clip,other_clip); seq=compile_composition(p)
    first=preview_context(seq,(96,72),False)
    replacement=tmp_path/'replacement.mkv'; replacement.write_bytes(Path(other_clip['path']).read_bytes())
    p['sections'][1]['footage']=inspect_video(replacement)
    assert first != preview_context(compile_composition(p),(96,72),False)


@pytest.mark.parametrize('start,count', [(0,12),(6,6)])
def test_mp4_export_switches_images_and_audio_and_preserves_pitch(clip,other_clip,tmp_path,start,count):
    p=two_sources(clip,other_clip); p['sections'][1]['video_rate']=2.
    seq=compile_composition(p)
    output=export_synth_video(default_synth_preset(),tmp_path/f'multi-{start}.mp4',start=start,count=count,sequence=seq,size=(128,96))
    samples=audio_samples(output)
    if start == 0:
        assert frequency(samples,.1,.4) == pytest.approx(440,abs=20)
        assert frequency(samples,.6,.9) == pytest.approx(880,abs=20)
    else: assert frequency(samples,.1,.4) == pytest.approx(880,abs=20)
    assert rms(samples,.1,.4) > .04
    from media import decode_frames
    info=inspect_video(output); frames=dict(decode_frames(info,12,0,count))
    blue=np.asarray(frames[count-1],float).mean(axis=(0,1))
    assert blue[2] > blue[0]+150 and blue[2] > blue[1]+150
    assert info['duration'] == pytest.approx(count/12,abs=.04)


def test_export_protects_every_source_even_when_muted(clip,other_clip):
    p=two_sources(clip,other_clip); p['sections'][1]['footage']['audio']='mute'
    with pytest.raises(ValueError,match='different from the source'):
        export_synth_video(default_synth_preset(),other_clip['path'],sequence=compile_composition(p))


def test_muted_section_exports_silence_between_sources(clip,other_clip,tmp_path):
    p=two_sources(clip,other_clip); p['sections'][1]['footage']['audio']='mute'
    p['sections'].append(dict(copy.deepcopy(p['sections'][0]),id='third'))
    output=export_synth_video(default_synth_preset(),tmp_path/'muted.mp4',sequence=compile_composition(p),size=(96,72))
    samples=audio_samples(output)
    assert rms(samples,.1,.4) > .04
    assert rms(samples,.6,.9) < .003
    assert rms(samples,1.1,1.4) > .04


def test_unused_missing_shared_source_does_not_block_independent_export(clip,other_clip,tmp_path):
    p=video_composition(clip); p['footage']['path']=str(tmp_path/'missing.mkv')
    p['sections'][0]['footage']=copy.deepcopy(other_clip)
    output=export_synth_video(default_synth_preset(),tmp_path/'independent.mp4',sequence=compile_composition(p),size=(96,72))
    assert output.is_file()


def test_local_trim_frame_and_mask_inputs_follow_the_section(clip):
    p=two_sources(clip,clip)
    p['sections'][1]['footage'].update({'in':.25,'out':.75,'x':20.,'treatment_fps':3.})
    p['effects']['subject_cutout']={'mode':'on','params':{'subject_cutout.mix':1.}}
    seq=compile_composition(p)
    from PIL import Image
    class Provider:
        def __init__(self): self.calls=[]
        def frame(self,footage,time_seconds,**kwargs):
            self.calls.append(('frame',footage,time_seconds)); return Image.new('RGB',(128,96),'white')
        def mask(self,footage,time_seconds,canvas,mode,**kwargs):
            self.calls.append(('mask',footage,time_seconds)); return Image.new('L',(128,96),255)
    provider=Provider()
    render_sequence_frame(seq,.75,(128,96),provider)
    assert [c[0] for c in provider.calls]==['frame','mask']
    assert all(c[1]['in']==.25 and c[1]['x']==20. and c[2]==.25 for c in provider.calls)


def test_new_documents_use_schema_three_legacy_stays_two(clip,other_clip):
    p=two_sources(clip,other_clip)
    assert p['schema_version']==3
    assert compile_composition(p)['schema_version']==3
    legacy=video_composition(clip)
    assert legacy['schema_version']==compile_composition(legacy)['schema_version']==2
