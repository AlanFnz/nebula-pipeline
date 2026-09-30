"""Mapped source audio follows video clocks without changing pitch or source files."""
import copy
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from media import Cancellation, Cancelled
from synth_video import inspect_video
from synth_video_audio import _tempo_filters, mux_source_audio
from test_synth_video import audio_samples, clip


@pytest.fixture(scope='module')
def tones(tmp_path_factory):
    folder = tmp_path_factory.mktemp("audio's clock")
    path = folder/'two-tone.mkv'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=size=96x64:rate=20:duration=2',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1',
        '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=1',
        '-filter_complex','[1:a][2:a]concat=n=2:v=0:a=1[a]', '-map','0:v','-map','[a]',
        '-c:v','ffv1','-c:a','pcm_s16le',str(path)],check=True)
    return inspect_video(path)


def video(path,duration):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
        f'color=size=96x64:rate=20:duration={duration}','-an','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
    return path


def segment(start,end,video_start,rate):
    return dict(start=start,end=end,effects_start=0.,effects_rate=1.,video_start=video_start,video_rate=rate)


def frequency(samples,left,right):
    chunk = samples[round(left*48000):round(right*48000)]
    power = np.abs(np.fft.rfft(chunk*np.hanning(len(chunk))))
    return np.argmax(power)*48000/len(chunk)


def rms(samples,left,right):
    chunk = samples[round(left*48000):round(right*48000)]
    return float(np.sqrt(np.mean(chunk**2)))


def duration(path):
    data = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(path)]))
    return float(data['format']['duration'])


@pytest.mark.parametrize('rate',[.125,.5,1.,2.,8.])
def test_atempo_chain_preserves_rate_and_uses_supported_factors(rate):
    factors = [float(part.split('=')[1]) for part in _tempo_filters(rate).split(',')]
    assert all(.5 <= factor <= 2. for factor in factors)
    assert np.prod(factors) == pytest.approx(rate)


@pytest.mark.parametrize('start,length,windows',[
    (0.,1.5,[(.12,.25,440),(.41,.48,880),(.7,.9,880)]),
    (.25,.75,[(.025,.09,440),(.18,.24,880),(.45,.6,880)]),
])
def test_piecewise_rate_and_partial_export_follow_source_clock_with_pitch_preserved(tones,tmp_path,start,length,windows):
    footage = copy.deepcopy(tones)
    footage.update({'in':.25,'out':1.75,'end_mode':'hold'})
    original = copy.deepcopy(footage)
    stat = Path(footage['path']).stat()
    mapping = [segment(0.,.5,0.,2.),segment(.5,1.5,1.,.5)]
    frozen = copy.deepcopy(mapping)
    source_video = video(tmp_path/'silent.mp4',length)
    destination = tmp_path/'mapped.mp4'
    mux_source_audio(source_video,destination,footage,start,length,Cancellation(),time_map=mapping)
    samples = audio_samples(destination)
    assert duration(destination) == pytest.approx(length,abs=.025)
    for left,right,tone in windows:
        assert frequency(samples,left,right) == pytest.approx(tone,abs=20)
        assert rms(samples,left,right) > .04
    assert footage == original and mapping == frozen
    after = Path(footage['path']).stat()
    assert (after.st_size,after.st_mtime_ns) == (stat.st_size,stat.st_mtime_ns)
    assert not list(tmp_path.glob('.nebula-audio-*'))


@pytest.mark.parametrize('mode',['loop','hold'])
def test_fast_source_clock_loops_trim_or_pads_hold_with_silence(tones,tmp_path,mode):
    footage = copy.deepcopy(tones)
    footage.update({'in':.25,'out':1.75,'end_mode':mode})
    destination = tmp_path/f'{mode}.mp4'
    mux_source_audio(video(tmp_path/'silent.mp4',1.2),destination,footage,0.,1.2,Cancellation(),
                     time_map=[segment(0.,1.2,0.,2.)])
    samples = audio_samples(destination)
    assert rms(samples,.1,.25) > .04
    late = rms(samples,.95,1.1)
    assert late > .04 if mode == 'loop' else late < .001
    assert duration(destination) == pytest.approx(1.2,abs=.025)


@pytest.mark.parametrize('mode',['loop','hold'])
def test_late_video_offset_uses_loop_modulo_or_immediate_hold_silence(tones,tmp_path,mode):
    footage = copy.deepcopy(tones)
    footage.update({'in':.25,'out':1.75,'end_mode':mode})
    destination = tmp_path/f'late-{mode}.mp4'
    mux_source_audio(video(tmp_path/'silent.mp4',.4),destination,footage,2.,.4,Cancellation(),
                     time_map=[segment(0.,3.,100.,.5)])
    samples = audio_samples(destination)
    assert rms(samples,.05,.3) > .04 if mode == 'loop' else rms(samples,.05,.3) < .001


@pytest.mark.parametrize('rate',[.25,4.])
def test_chained_tempo_has_correct_pitch_and_padded_duration(clip,tmp_path,rate):
    footage = copy.deepcopy(clip)
    footage.update({'in':.25,'out':.75,'end_mode':'loop'})
    destination = tmp_path/f'rate-{rate}.mp4'
    mux_source_audio(video(tmp_path/'silent.mp4',.8),destination,footage,0.,.8,Cancellation(),
                     time_map=[segment(0.,.8,0.,rate)])
    samples = audio_samples(destination)
    assert frequency(samples,.1,.6) == pytest.approx(440,abs=4)
    assert rms(samples,.1,.6) > .04
    assert duration(destination) == pytest.approx(.8,abs=.025)


def test_mapped_audio_cancellation_cleans_temporary_files(tones,tmp_path):
    source_video = video(tmp_path/'silent.mp4',.4)
    destination = tmp_path/'cancelled.mp4'
    cancel = Cancellation()
    cancel.cancel()
    with pytest.raises(Cancelled):
        mux_source_audio(source_video,destination,tones,0.,.4,cancel,time_map=[segment(0.,.4,0.,1.)])
    assert not destination.exists()
    assert not cancel.processes
    assert not list(tmp_path.glob('.nebula-audio-*'))


def test_mapped_audio_refuses_source_overwrite(tones,tmp_path):
    source_video = video(tmp_path/'silent.mp4',.4)
    with pytest.raises(ValueError,match='overwrite'):
        mux_source_audio(source_video,tones['path'],tones,0.,.4,Cancellation(),time_map=[segment(0.,.4,0.,1.)])


def test_cancel_between_pieces_removes_all_intermediates(tones,tmp_path,monkeypatch):
    import synth_video_audio
    original_run = synth_video_audio.run_ffmpeg
    cancel = Cancellation()
    source_video = video(tmp_path/'silent.mp4',.6)
    destination = tmp_path/'cancelled.mp4'
    def run_then_cancel(args,token):
        original_run(args,token)
        if Path(args[-1]).name == 'piece-0.wav': token.cancel()
    monkeypatch.setattr(synth_video_audio,'run_ffmpeg',run_then_cancel)
    with pytest.raises(Cancelled):
        mux_source_audio(source_video,destination,tones,0.,.6,cancel,
                         time_map=[segment(0.,.3,0.,2.),segment(.3,.6,.6,2.)])
    assert not destination.exists()
    assert not cancel.processes
    assert not list(tmp_path.glob('.nebula-audio-*'))


def test_effects_only_clock_map_uses_exact_legacy_ffmpeg_commands(tones,tmp_path,monkeypatch):
    import synth_video_audio
    calls = []
    monkeypatch.setattr(synth_video_audio,'run_ffmpeg',lambda args,cancel:calls.append(args))
    source_video = tmp_path/'silent.mp4'
    destination = tmp_path/'result.mp4'
    mapping = [segment(i*.01,(i+1)*.01,i*.01,1.) for i in range(100)]
    for entry in mapping: entry['effects_rate'] = 3.
    mux_source_audio(source_video,destination,tones,.2,.6,Cancellation(),time_map=mapping)
    assert len(calls) == 2
    mapped_commands = [[str(arg).replace(str(Path(arg).parent),'TEMP') if str(arg).endswith('trim.wav') else arg for arg in call] for call in calls]
    calls.clear()
    mux_source_audio(source_video,destination,tones,.2,.6,Cancellation())
    legacy_commands = [[str(arg).replace(str(Path(arg).parent),'TEMP') if str(arg).endswith('trim.wav') else arg for arg in call] for call in calls]
    assert mapped_commands == legacy_commands


def test_continuous_same_rate_sections_share_one_audio_piece(tones,tmp_path,monkeypatch):
    import synth_video_audio
    calls = []
    monkeypatch.setattr(synth_video_audio,'run_ffmpeg',lambda args,cancel:calls.append(args))
    mapping = [segment(i*.01,(i+1)*.01,i*.02,2.) for i in range(100)]
    frozen = copy.deepcopy(mapping)
    mux_source_audio(tmp_path/'silent.mp4',tmp_path/'result.mp4',tones,0.,1.,Cancellation(),time_map=mapping)
    assert len(calls) == 3  # One trim, one tempo pass, one mux.
    assert Path(calls[1][-1]).name == 'piece-0.wav'
    assert 'atempo=2' in calls[1][calls[1].index('-af')+1]
    assert mapping == frozen


def test_audio_coalescence_retains_source_jumps_and_rate_changes():
    from synth_video_audio import _coalesce_video_segments
    mapping = [segment(0.,1.,0.,2.),segment(1.,2.,2.,2.),
               segment(2.,3.,0.,2.),segment(3.,4.,2.,.5)]
    joined = _coalesce_video_segments(mapping)
    assert len(joined) == 3
    assert joined[0]['start'] == 0. and joined[0]['end'] == 2.
    assert joined[1]['video_start'] == 0.
    assert joined[2]['video_rate'] == .5
