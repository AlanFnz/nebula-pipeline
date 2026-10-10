"""Imported audio contracts verified with actual tones and rendered video packets."""
import copy
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
import pytest

from media import Cancellation, Cancelled
from synth import default_synth_preset
from synth_composition import (blank_composition, compile_composition, composition_from_sequence,
                               load_composition, normalize_composition, save_composition)
from synth_media import export_synth_video
from synth_sequence import load_sequence, normalize_sequence, render_sequence_frame, save_sequence
from synth_soundtrack import (check_soundtrack, mux_soundtrack_audio, normalize_soundtrack,
                              probe_soundtrack, soundtrack_source_time, waveform_peaks)
from synth_video import inspect_video, video_composition


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', *map(str, args)], check=True)


@pytest.fixture(scope='module')
def tones(tmp_path_factory):
    path = tmp_path_factory.mktemp('soundtrack') / 'two tones.wav'
    ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1',
           '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=1',
           '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[a]', '-map', '[a]', path)
    return probe_soundtrack(path)


def silent_video(path, duration):
    ffmpeg('-f', 'lavfi', '-i', f'color=size=96x64:rate=20:duration={duration}',
           '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', path)
    return path


def samples(path):
    return np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
        '-map', '0:a:0', '-ar', '48000', '-ac', '1', '-f', 'f32le', 'pipe:1']), dtype='<f4')


def rms(data, left, right):
    window = data[round(left * 48000):round(right * 48000)]
    return float(np.sqrt(np.mean(window ** 2)))


def frequency(data, left, right):
    window = data[round(left * 48000):round(right * 48000)]
    return np.argmax(np.abs(np.fft.rfft(window * np.hanning(len(window))))) * 48000 / len(window)


def audio_streams(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams',
        'a', '-show_streams', '-of', 'json', str(path)]))['streams']


def test_probe_defaults_and_normalization_are_independent(tones):
    assert tones['duration'] == pytest.approx(2.)
    assert tones['sample_rate'] == 48000 and tones['channels'] == 1
    assert tones['offset'] == tones['in'] == 0.
    assert tones['out'] == tones['duration'] and tones['gain'] == 1.
    assert tones['end_mode'] == 'silence' and tones['export_audio'] == 'soundtrack'
    assert Path(tones['path']).is_absolute() and tones['id']
    result = normalize_soundtrack(tones)
    result['identity']['size'] += 1
    assert result != tones
    assert normalize_soundtrack(tones) == tones


@pytest.mark.parametrize('key,value', [
    ('duration', 0.), ('duration', 10 ** 1000), ('duration', float('nan')), ('in', float('inf')), ('out', -1.),
    ('offset', -1.), ('offset', float('inf')), ('gain', True), ('gain', 1.01),
    ('sample_rate', 1.5), ('channels', 0), ('channels', float('nan')),
    ('id', ''), ('path', 'x\0y'), ('end_mode', 'hold'), ('export_audio', 'mix'),
])
def test_malformed_authored_settings_reject(tones, key, value):
    with pytest.raises(ValueError):
        normalize_soundtrack(dict(tones, **{key: value}))


def test_clock_trim_offset_silence_and_loop(tones):
    track = dict(tones, **{'in': .25, 'out': 1.75, 'offset': .5})
    assert soundtrack_source_time(track, -.1) is None
    assert soundtrack_source_time(track, .49) is None
    assert soundtrack_source_time(track, .5) == .25
    assert soundtrack_source_time(track, 1.) == .75
    assert soundtrack_source_time(track, 2.) is None
    track['end_mode'] = 'loop'
    assert soundtrack_source_time(track, 2.) == .25
    assert soundtrack_source_time(track, 200.) == pytest.approx(.25)
    with pytest.raises(ValueError): soundtrack_source_time(track, float('nan'))


def test_soundtrack_roundtrips_compile_and_removal_keep_generated_pixels(tones, tmp_path):
    project = blank_composition()
    baseline = compile_composition(project)
    project['soundtrack'] = dict(tones, offset=1.5, gain=.4, end_mode='loop')
    saved = copy.deepcopy(project)
    normalized = normalize_composition(project)
    detailed = compile_composition(project)
    assert project == saved
    assert normalized['schema_version'] == detailed['schema_version'] == 4
    assert 'footage' not in normalized and 'footage' not in detailed
    for time in (0., .6, 5.):
        assert render_sequence_frame(detailed, time, (64, 48)).tobytes() == render_sequence_frame(baseline, time, (64, 48)).tobytes()
    imported = composition_from_sequence(detailed)
    assert imported['soundtrack'] == normalized['soundtrack']
    assert 'soundtrack' not in imported['source']
    assert compile_composition(imported)['soundtrack'] == detailed['soundtrack']
    save_composition(tmp_path / 'piece.json', normalized)
    assert load_composition(tmp_path / 'piece.json') == normalized
    save_sequence(tmp_path / 'detail.json', detailed)
    assert load_sequence(tmp_path / 'detail.json') == detailed
    normalized.pop('soundtrack')
    assert normalize_composition(normalized)['schema_version'] == 1
    assert 'soundtrack' not in compile_composition(normalized)
    # A detailed source embedded by older editing code cannot resurrect removal.
    normalized['source'] = detailed
    assert 'soundtrack' not in compile_composition(normalized)
    assert normalize_sequence(dict(baseline, schema_version=4))['schema_version'] == 1


def test_missing_changed_and_cancelled_media_are_actionable(tones, tmp_path):
    with pytest.raises(ValueError, match='missing.*Relink'):
        check_soundtrack(dict(tones, path=str(tmp_path / 'missing.wav')))
    with pytest.raises(ValueError, match='changed.*Relink'):
        check_soundtrack(dict(tones, identity={'size': 0, 'mtime_ns': 0}))
    cancelled = Cancellation(); cancelled.cancel()
    for operation in (lambda: probe_soundtrack(tones['path'], cancelled),
                      lambda: waveform_peaks(tones, cancelled)):
        with pytest.raises(Cancelled): operation()
    assert not cancelled.processes
    with pytest.raises(ValueError, match='No audio'):
        probe_soundtrack(silent_video(tmp_path / 'no-audio.mp4', .2))


def test_waveform_uses_full_source_all_channels_and_ignores_trim_gain(tones, tmp_path):
    peaks = waveform_peaks(tones, bins=32)
    assert len(peaks) == 32 and min(peaks) > .1 and max(peaks) < .14
    assert waveform_peaks(dict(tones, **{'in': 1., 'out': 1.1, 'gain': 0.}), bins=32) == peaks
    opposite = tmp_path / 'opposite.wav'
    ffmpeg('-i', tones['path'], '-af', 'pan=stereo|c0=c0|c1=-1*c0', opposite)
    assert min(waveform_peaks(probe_soundtrack(opposite), bins=32)) > .1


def test_waveform_mid_decode_cancellation_releases_process(tones):
    class CancelAfterRead(Cancellation):
        def __init__(self):
            super().__init__(); self.checks = 0
        def check(self):
            self.checks += 1
            if self.checks == 4: self.cancel()
            super().check()
    cancel = CancelAfterRead()
    with pytest.raises(Cancelled): waveform_peaks(tones, cancel)
    assert not cancel.processes


@pytest.mark.parametrize('mode,start,duration,windows', [
    ('silence', 0., 2.6, [(.1, .25, None), (.55, .75, 440), (1.3, 1.5, 880), (2.1, 2.4, None)]),
    ('loop', 0., 2.6, [(.1, .25, None), (.55, .75, 440), (1.3, 1.5, 880), (2.1, 2.4, 440)]),
    ('loop', 1.6, .9, [(.05, .2, 880), (.5, .7, 440)]),
    ('silence', 2.2, .6, [(.1, .4, None)]),
    ('loop', 100.2, .6, [(.1, .3, 880)]),
])
def test_mux_trim_offset_end_and_partial_exports(tones, tmp_path, mode, start, duration, windows):
    track = dict(tones, **{'in': .25, 'out': 1.75, 'offset': .4, 'end_mode': mode})
    original = copy.deepcopy(track)
    video = silent_video(tmp_path / 'video.mp4', duration)
    destination = tmp_path / 'result.mp4'
    mux_soundtrack_audio(video, destination, track, start, duration)
    data = samples(destination)
    for left, right, tone in windows:
        if tone is None:
            assert rms(data, left, right) < .001
        else:
            assert rms(data, left, right) > .04
            assert frequency(data, left, right) == pytest.approx(tone, abs=12)
    assert track == original
    video_hash = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(video), '-map', '0:v', '-c:v', 'copy', '-f', 'hash', 'pipe:1'])
    result_hash = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(destination), '-map', '0:v', '-c:v', 'copy', '-f', 'hash', 'pipe:1'])
    assert result_hash == video_hash
    assert not list(tmp_path.glob('.nebula-soundtrack-*'))


@pytest.mark.parametrize('cancel_phase', ['trim.wav', 'mux.mp4'])
def test_gain_and_atomic_cancellation_protect_existing_destination(tones, tmp_path, monkeypatch, cancel_phase):
    import synth_soundtrack
    video = silent_video(tmp_path / 'video.mp4', .6)
    full = tmp_path / 'full.mp4'; half = tmp_path / 'half.mp4'
    mux_soundtrack_audio(video, full, tones, 0., .6)
    mux_soundtrack_audio(video, half, dict(tones, gain=.5), 0., .6)
    assert rms(samples(half), .1, .5) / rms(samples(full), .1, .5) == pytest.approx(.5, abs=.02)
    existing = tmp_path / 'existing.mp4'; existing.write_bytes(b'existing export')
    cancel = Cancellation()
    original = synth_soundtrack.run_ffmpeg
    def cancel_after_trim(args, token):
        original(args, token)
        if Path(args[-1]).name == cancel_phase: token.cancel()
    monkeypatch.setattr(synth_soundtrack, 'run_ffmpeg', cancel_after_trim)
    with pytest.raises(Cancelled):
        mux_soundtrack_audio(video, existing, dict(tones, end_mode='loop'), 0., .6, cancel)
    assert existing.read_bytes() == b'existing export'
    assert not cancel.processes and not list(tmp_path.glob('.nebula-soundtrack-*'))


def test_mux_refuses_source_and_hardlink_overwrite(tones, tmp_path):
    video = silent_video(tmp_path / 'video.mp4', .2)
    linked = tmp_path / 'source-alias.mp4'; os.link(tones['path'], linked)
    for destination in (tones['path'], linked, video):
        with pytest.raises(ValueError, match='overwrite'):
            mux_soundtrack_audio(video, destination, tones, 0., .2)


@pytest.mark.parametrize('choice,expected', [('soundtrack', 880), ('footage', 440), ('silent', None)])
def test_export_audio_selection_overrides_footage_and_preserves_video(tones, tmp_path, monkeypatch, choice, expected):
    import synth_media
    clip = tmp_path / 'footage.mkv'
    ffmpeg('-f', 'lavfi', '-i', 'color=size=96x64:rate=20:duration=1',
           '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1',
           '-c:v', 'ffv1', '-c:a', 'pcm_s16le', clip)
    project = video_composition(inspect_video(clip))
    project['soundtrack'] = dict(tones, **{'in': 1., 'out': 2., 'export_audio': choice})
    sequence = compile_composition(project)
    monkeypatch.setattr('synth_sequence.render_sequence_frame', lambda *a, **k: Image.new('RGB', (96, 64)))
    destination = tmp_path / f'{choice}.mp4'
    export_synth_video(default_synth_preset(), destination, count=10, size=(96, 64), sequence=sequence)
    if expected is None:
        assert not audio_streams(destination)
    else:
        assert frequency(samples(destination), .1, .4) == pytest.approx(expected, abs=8)
    # Authored audio stays protected even when it is not the chosen export audio.
    with pytest.raises(ValueError, match='source soundtrack'):
        export_synth_video(default_synth_preset(), tones['path'], count=10, sequence=sequence)


def test_legacy_export_and_missing_soundtrack_with_silent_choice(tones, tmp_path, monkeypatch):
    monkeypatch.setattr('synth_sequence.render_sequence_frame', lambda *a, **k: Image.new('RGB', (96, 64)))
    sequence = compile_composition(blank_composition())
    output = tmp_path / 'legacy.mp4'
    export_synth_video(default_synth_preset(), output, count=3, size=(96, 64), sequence=sequence)
    assert sequence['schema_version'] == 1 and not audio_streams(output)
    sequence['soundtrack'] = dict(tones, path=str(tmp_path / 'missing.wav'), export_audio='silent')
    export_synth_video(default_synth_preset(), output, count=3, size=(96, 64), sequence=sequence)
    assert not audio_streams(output)
    sequence['soundtrack']['export_audio'] = 'soundtrack'
    before = output.read_bytes()
    with pytest.raises(ValueError, match='missing.*Relink'):
        export_synth_video(default_synth_preset(), output, count=3, size=(96, 64), sequence=sequence)
    assert output.read_bytes() == before


def test_partial_video_export_uses_absolute_audio_clock(tones, tmp_path, monkeypatch):
    monkeypatch.setattr('synth_sequence.render_sequence_frame', lambda *a, **k: Image.new('RGB', (96, 64)))
    project = blank_composition()
    project['soundtrack'] = dict(tones, **{'in': .25, 'out': 1.75, 'offset': .4, 'end_mode': 'loop'})
    sequence = compile_composition(project)
    output = tmp_path / 'partial.mp4'
    export_synth_video(default_synth_preset(), output, start=40, count=23, size=(96, 64), sequence=sequence)
    data = samples(output)
    assert frequency(data, .05, .2) == pytest.approx(880, abs=10)
    assert frequency(data, .5, .7) == pytest.approx(440, abs=10)


def test_removed_audio_restores_video_schema_and_timing_edits_do_not_retime_track(tones, tmp_path):
    clip = tmp_path / 'source.mkv'
    ffmpeg('-f', 'lavfi', '-i', 'color=size=96x64:rate=20:duration=1', '-c:v', 'ffv1', clip)
    project = video_composition(inspect_video(clip))
    project['soundtrack'] = dict(tones, offset=.8)
    project = normalize_composition(project)
    project['sections'][0].update(duration=2., loops=2)
    assert compile_composition(project)['soundtrack'] == project['soundtrack']
    project.pop('soundtrack')
    removed = normalize_composition(project)
    assert removed['schema_version'] == 2
    assert 'soundtrack' not in compile_composition(removed)
