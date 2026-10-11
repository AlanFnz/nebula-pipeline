"""Frequency, project-clock, bypass and source-safety contracts for B2."""
import copy
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from media import Cancellation, Cancelled
from synth import default_synth_preset
from synth_audio_reactivity import (apply_reactivity, cached_responses, normalize_reactivity,
    prepare_reactivity, target_parameter)
from synth_composition import (blank_composition, compile_composition, composition_from_sequence,
    load_composition, normalize_composition, save_composition)
from synth_media import export_synth_video
from synth_sequence import normalize_sequence, render_sequence_frame, resolve_sequence_frame
from synth_soundtrack import probe_soundtrack


def mapping(track, identifier='low', path='bloom.strength', **settings):
    return dict(id=identifier, track_id=track['id'], path=path, low_hz=100., high_hz=700.,
        amount=.3, sensitivity=1., attack=0., release=0., enabled=True, **settings)


def document(track, maps=None, duration=4.):
    project = blank_composition()
    project['soundtrack'] = copy.deepcopy(track)
    project['sections'][0]['duration'] = duration
    project['source']['states'][next(iter(project['source']['states']))]['enabled'] = ['bloom']
    project['audio_reactivity'] = {'enabled': True, 'mappings': maps or [mapping(track)]}
    return compile_composition(project)


@pytest.fixture(scope='module')
def tones(tmp_path_factory):
    path = tmp_path_factory.mktemp('bands') / 'bands.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
        'sine=frequency=300:sample_rate=48000:duration=1', '-f', 'lavfi', '-i',
        'sine=frequency=3000:sample_rate=48000:duration=1', '-f', 'lavfi', '-i',
        'anullsrc=r=48000:cl=mono:d=1', '-filter_complex',
        '[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]', '-map', '[a]', str(path)], check=True)
    return probe_soundtrack(path)


def response(sequence, time):
    result = cached_responses(sequence, time)
    assert result is not None
    return result


def test_frequency_separation_and_silence_do_not_normalize_noise(tones):
    low = mapping(tones)
    high = mapping(tones, 'high'); high.update(low_hz=2000., high_hz=4000.)
    sequence = document(tones, [low, high])
    prepare_reactivity(sequence)
    assert response(sequence, .5)['low'] > .6
    assert response(sequence, .5)['high'] == 0.
    assert response(sequence, 1.5)['high'] > .6
    assert response(sequence, 1.5)['low'] == 0.
    assert response(sequence, 2.5) == {'low': 0., 'high': 0.}
    assert response(sequence, 3.5) == {'low': 0., 'high': 0.}


def test_full_range_and_antiphase_stereo_preserve_energy(tones, tmp_path):
    path = tmp_path / 'opposite.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tones['path'], '-af',
        'pan=stereo|c0=c0|c1=-1*c0', str(path)], check=True)
    stereo = probe_soundtrack(path)
    full = mapping(stereo); full.update(low_hz=0., high_hz=stereo['sample_rate'] / 2)
    sequence = document(stereo, [full])
    prepare_reactivity(sequence)
    assert response(sequence, .5)['low'] > .6


def test_microscopic_tone_stays_zero_even_at_maximum_sensitivity(tmp_path):
    path = tmp_path / 'tiny.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
        'sine=frequency=300:sample_rate=48000:duration=1', '-af', 'volume=0.0001',
        '-c:a', 'pcm_f32le', str(path)], check=True)
    track = probe_soundtrack(path)
    settings = mapping(track); settings['sensitivity'] = 16.
    sequence = document(track, [settings], duration=1.)
    prepare_reactivity(sequence)
    assert response(sequence, .5)['low'] == 0.


def test_project_trim_offset_loop_and_release_follow_absolute_clock(tones):
    track = dict(tones, **{'in': .5, 'out': 2., 'offset': .405, 'end_mode': 'loop'})
    settings = mapping(track); settings.update(attack=.1, release=.15)
    sequence = document(track, [settings], duration=4.)
    analysis = prepare_reactivity(sequence)
    assert response(sequence, .404)['low'] == 0.
    assert response(sequence, .5)['low'] > .2
    assert response(sequence, 1.6)['low'] < .04
    assert response(sequence, 2.2)['low'] > .4
    ordered = {float(t): response(sequence, float(t)) for t in np.arange(0., 4., .037)}
    for t in reversed(list(ordered)):
        assert response(sequence, t) == ordered[t]
    preset = resolve_sequence_frame(sequence, .6)[-1]
    first = apply_reactivity(preset, sequence, .6, analysis=analysis)
    for t in (3.2, .1, 1.1, 2.6): apply_reactivity(preset, sequence, t, analysis=analysis)
    assert apply_reactivity(preset, sequence, .6, analysis=analysis) == first
    # Changing the section clocks never changes a project-time response.
    changed = copy.deepcopy(sequence)
    changed['time_map'] = [{'start': 0., 'end': 4., 'effects_start': 0., 'effects_rate': 2., 'video_start': 0., 'video_rate': 1.}]
    assert prepare_reactivity(changed) is analysis
    assert response(changed, .6) == response(sequence, .6)


def test_output_gain_and_choice_do_not_change_analysis(tones):
    sequence = document(tones)
    original = prepare_reactivity(sequence)
    changed = copy.deepcopy(sequence)
    changed['soundtrack'].update(gain=0., export_audio='silent')
    assert prepare_reactivity(changed) is original
    assert response(changed, .5) == response(sequence, .5)


@pytest.mark.parametrize('changes', [
    {'low_hz': -1.}, {'high_hz': 24001.}, {'high_hz': 100.}, {'sensitivity': float('nan')},
    {'attack': float('inf')}, {'release': -1.}, {'amount': True}, {'enabled': 1},
    {'track_id': 'different'}, {'path': 'bloom.enabled'}, {'path': 'raster.mode'},
])
def test_invalid_mappings_reject(tones, changes):
    item = mapping(tones); item.update(changes)
    with pytest.raises(ValueError): normalize_reactivity({'enabled': True, 'mappings': [item]}, tones)


def test_bounded_ids_and_active_missing_track_validation(tones):
    item = mapping(tones)
    with pytest.raises(ValueError, match='unique'):
        normalize_reactivity({'mappings': [item, item]}, tones)
    with pytest.raises(ValueError, match='16'):
        normalize_reactivity({'mappings': [dict(item, id=str(i)) for i in range(17)]}, tones)
    with pytest.raises(ValueError, match='soundtrack'):
        normalize_reactivity({'mappings': [item]})
    assert normalize_reactivity({'enabled': False, 'mappings': [item]})['mappings']


def test_same_target_adds_before_clamping_and_preserves_animated_base(tones):
    plus = mapping(tones)
    minus = mapping(tones, 'minus'); minus['amount'] = -.2
    sequence = document(tones, [plus, minus])
    analysis = prepare_reactivity(sequence)
    preset = resolve_sequence_frame(sequence, .5)[-1]
    base = copy.deepcopy(preset)
    bloom = next(m for m in preset['modules'] if m['id'] == 'bloom')
    spec = target_parameter('bloom.strength')
    bloom['params']['strength'] = spec.maximum - .01
    result = apply_reactivity(preset, sequence, .5, analysis=analysis)
    amount = response(sequence, .5)['low'] * .1
    assert next(m for m in result['modules'] if m['id'] == 'bloom')['params']['strength'] == pytest.approx(min(spec.maximum, bloom['params']['strength'] + amount))
    # Reverse mapping order gives identical pixels/parameters, including mixed signs.
    reversed_sequence = document(tones, [minus, plus])
    reversed_analysis = prepare_reactivity(reversed_sequence)
    assert apply_reactivity(preset, reversed_sequence, .5, analysis=reversed_analysis) == result
    bloom['params']['strength'] = .3
    result = apply_reactivity(preset, sequence, .5, analysis=analysis)
    assert next(m for m in result['modules'] if m['id'] == 'bloom')['params']['strength'] == pytest.approx(.3 + amount)
    assert base != preset and preset['modules'] != result['modules']


@pytest.mark.parametrize('kind', ['global', 'individual', 'zero', 'module'])
def test_bypass_missing_media_restores_exact_pixels_without_io(tones, kind, monkeypatch):
    import synth_audio_reactivity
    sequence = document(tones)
    neutral = copy.deepcopy(sequence); neutral.pop('audio_reactivity')
    if kind == 'global': sequence['audio_reactivity']['enabled'] = False
    elif kind == 'individual': sequence['audio_reactivity']['mappings'][0]['enabled'] = False
    elif kind == 'zero': sequence['audio_reactivity']['mappings'][0]['amount'] = 0.
    else:
        for state in sequence['states'].values(): state['enabled'] = []
        for state in neutral['states'].values(): state['enabled'] = []
    sequence['soundtrack']['path'] = '/missing/audio.wav'
    monkeypatch.setattr(synth_audio_reactivity, 'check_soundtrack', lambda *_: pytest.fail('bypass opened source'))
    assert render_sequence_frame(sequence, .5, (64, 48)).tobytes() == render_sequence_frame(neutral, .5, (64, 48)).tobytes()
    assert not prepare_reactivity(sequence).responses


def test_missing_changed_and_cancelled_analysis_error_and_leave_no_processes(tones, tmp_path):
    missing = document(dict(tones, path=str(tmp_path / 'missing.wav')))
    with pytest.raises(ValueError, match='missing.*Relink'): prepare_reactivity(missing)
    with pytest.raises(ValueError, match='missing.*Relink'): render_sequence_frame(missing, .5, (64, 48))
    changed = document(dict(tones, identity={'size': 1, 'mtime_ns': 0}))
    with pytest.raises(ValueError, match='changed.*Relink'): prepare_reactivity(changed)
    class Interrupt(Cancellation):
        def __init__(self): super().__init__(); self.checks = 0
        def check(self):
            self.checks += 1
            if self.checks == 7: self.cancel()
            super().check()
    sequence = document(tones); sequence['audio_reactivity']['mappings'][0]['sensitivity'] = 1.123
    cancel = Interrupt()
    with pytest.raises(Cancelled): prepare_reactivity(sequence, cancel)
    assert not cancel.processes
    assert cached_responses(sequence, .5) is None


def test_schema_compile_detailed_roundtrip_and_removal_do_not_resurrect(tones, tmp_path):
    sequence = document(tones)
    assert sequence['schema_version'] == 5
    project = composition_from_sequence(sequence)
    assert project['schema_version'] == 5 and 'audio_reactivity' not in project['source']
    path = tmp_path / 'piece.json'; save_composition(path, project)
    assert load_composition(path) == normalize_composition(project)
    assert compile_composition(project)['audio_reactivity'] == sequence['audio_reactivity']
    project.pop('audio_reactivity')
    assert normalize_composition(project)['schema_version'] == 4
    project['source'] = sequence
    assert 'audio_reactivity' not in compile_composition(project)
    sequence.pop('audio_reactivity')
    assert normalize_sequence(sequence)['schema_version'] == 4
    sequence.pop('soundtrack')
    assert normalize_sequence(sequence)['schema_version'] == 1


def test_export_preflight_fails_before_video_encode_and_preserves_destination(tones, tmp_path, monkeypatch):
    import synth_media
    sequence = document(dict(tones, path=str(tmp_path / 'missing.wav'), export_audio='silent'))
    output = tmp_path / 'existing.mp4'; output.write_bytes(b'previous')
    monkeypatch.setattr(synth_media.subprocess, 'Popen', lambda *_args, **_kwargs: pytest.fail('encoded before analysis'))
    with pytest.raises(ValueError, match='missing.*Relink'):
        export_synth_video(default_synth_preset(), output, count=5, size=(64, 48), sequence=sequence)
    assert output.read_bytes() == b'previous'
    assert not list(tmp_path.glob('.nebula-synth-*'))


def test_cached_meter_does_no_io_and_bounded_cache_evicts(tones, monkeypatch):
    import synth_audio_reactivity as audio
    first = document(tones); prepare_reactivity(first)
    expected = response(first, .5)
    with monkeypatch.context() as patch:
        patch.setattr(audio, 'check_soundtrack', lambda *_: pytest.fail('meter touched media'))
        patch.setattr(Path, 'stat', lambda *_a, **_k: pytest.fail('meter statted media'))
        assert cached_responses(first, .5) == expected
    monkeypatch.setattr(audio, 'CACHE_ENTRIES', 2)
    for sensitivity in (1.41, 1.42, 1.43):
        sequence = document(tones)
        sequence['audio_reactivity']['mappings'][0]['sensitivity'] = sensitivity
        prepare_reactivity(sequence)
    assert len(audio._cache) == 2
    assert cached_responses(first, .5) is None


def test_cached_render_rejects_changed_source_and_rebuilds_untracked_identity(tones, tmp_path):
    path = tmp_path / 'copied.wav'; path.write_bytes(Path(tones['path']).read_bytes())
    track = probe_soundtrack(path)
    sequence = document(track); analysis = prepare_reactivity(sequence)
    preset = resolve_sequence_frame(sequence, .5)[-1]
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='changed.*Relink'):
        apply_reactivity(preset, sequence, .5)
    with pytest.raises(ValueError, match='changed.*Relink'):
        apply_reactivity(preset, sequence, .5, analysis=analysis)
    # Without authored identity, actual stat still prevents cache reuse.
    sequence['soundtrack'].pop('identity')
    fresh = prepare_reactivity(sequence)
    path.write_bytes(path.read_bytes() + b'more')
    with pytest.raises(ValueError, match='stale'):
        apply_reactivity(preset, sequence, .5, analysis=fresh)
    assert prepare_reactivity(sequence) is not fresh


def test_instance_targets_are_independent_and_do_not_enable_slot(tones):
    from synth import normalize_synth
    item = mapping(tones, path='tape@2.pull'); item['amount'] = .1
    sequence = document(tones, [item])
    for state in sequence['states'].values():
        state['enabled'] = ['tape@2']
    sequence = normalize_sequence(sequence)
    preset = resolve_sequence_frame(sequence, .5)[-1]
    result = apply_reactivity(preset, sequence, .5)
    original = next(m for m in preset['modules'] if m['id'] == 'tape@2')
    edited = next(m for m in result['modules'] if m['id'] == 'tape@2')
    assert edited['params']['pull'] > original['params']['pull']
    assert next(m for m in result['modules'] if m['id'] == 'tape') == next(m for m in preset['modules'] if m['id'] == 'tape')
    original['enabled'] = False
    assert apply_reactivity(preset, sequence, .5) is preset


def test_partial_export_matches_full_project_clock(tones, tmp_path, monkeypatch):
    import synth_sequence
    sequence = document(tones)
    sequence['soundtrack']['export_audio'] = 'silent'
    full = []; partial = []
    original_render = synth_sequence.render_sequence_frame
    captured = full
    def capture(seq, seconds, *args, **kwargs):
        image = original_render(seq, seconds, *args, **kwargs)
        captured.append((seconds, image.tobytes(), response(seq, seconds)))
        return image
    monkeypatch.setattr(synth_sequence, 'render_sequence_frame', capture)
    export_synth_video(default_synth_preset(), tmp_path / 'full.mp4', count=35, size=(64, 48), sequence=sequence)
    captured = partial
    export_synth_video(default_synth_preset(), tmp_path / 'partial.mp4', start=12, count=13, size=(64, 48), sequence=sequence)
    assert partial == full[12:25]


@pytest.mark.parametrize('parameter,amount', [('expansion', .6), ('detail', -.5), ('light', .7)])
def test_radial_targets_affect_pixels_and_zero_amount_matches_original(tones, parameter, amount):
    item = mapping(tones, path='radial_bloom.' + parameter); item['amount'] = amount
    sequence = document(tones, [item])
    for state in sequence['states'].values(): state['enabled'] = ['radial_bloom']
    sequence = normalize_sequence(sequence)
    baseline = copy.deepcopy(sequence); baseline.pop('audio_reactivity')
    original = render_sequence_frame(baseline, .5, (96, 72)).tobytes()
    assert render_sequence_frame(sequence, .5, (96, 72)).tobytes() != original
    sequence['audio_reactivity']['mappings'][0]['amount'] = 0.
    assert render_sequence_frame(sequence, .5, (96, 72)).tobytes() == original
    assert target_parameter(item['path']).kind == 'float'


@pytest.mark.parametrize('path', ['frame_jitter.strength', 'tape.mix', 'tape@2.mix'])
def test_disruption_targets_recover_in_silence_and_respect_bypass(tones, path):
    module = path.split('.')[0]
    item = mapping(tones, path=path); item['amount'] = 1.
    sequence = document(tones, [item])
    for state in sequence['states'].values():
        state['enabled'] = ['radial_bloom', module]
        state['overrides'][path] = 0.
    sequence = normalize_sequence(sequence)
    baseline = copy.deepcopy(sequence); baseline.pop('audio_reactivity')
    original = render_sequence_frame(baseline, .5, (96, 72)).tobytes()
    active = render_sequence_frame(sequence, .5, (96, 72)).tobytes()
    assert active != original
    assert render_sequence_frame(sequence, 2.5, (96, 72)).tobytes() == render_sequence_frame(baseline, 2.5, (96, 72)).tobytes()
    assert render_sequence_frame(sequence, .5, (96, 72)).tobytes() == active
    sequence['audio_reactivity']['enabled'] = False
    assert render_sequence_frame(sequence, .5, (96, 72)).tobytes() == original
    sequence['audio_reactivity']['enabled'] = True
    for state in sequence['states'].values():
        state['enabled'].remove(module)
    preset = resolve_sequence_frame(sequence, .5)[-1]
    assert apply_reactivity(preset, sequence, .5) is preset


def test_portable_study_preserves_mapping_and_track_ids_after_library_move(tones, tmp_path):
    from synth_studies import save_study, study_composition
    copied = tmp_path / 'original.wav'; copied.write_bytes(Path(tones['path']).read_bytes())
    track = probe_soundtrack(copied)
    item = mapping(track, path='radial_bloom.expansion')
    sequence = document(track, [item])
    for state in sequence['states'].values(): state['enabled'] = ['radial_bloom']
    project = composition_from_sequence(sequence)
    before = copy.deepcopy(project)
    root = tmp_path / 'Studies'; identifier = save_study(project, 'Reactive radial', root)
    assert project == before
    saved = root / identifier.split(':')[1] / 'study.json'
    raw = json.loads(saved.read_text())
    assert raw['schema_version'] == 5
    assert not Path(raw['soundtrack']['path']).is_absolute()
    assert raw['audio_reactivity']['mappings'][0]['track_id'] == track['id']
    copied.unlink()
    moved = tmp_path / 'Moved'; root.rename(moved)
    loaded = study_composition(identifier, moved)
    assert loaded['soundtrack']['id'] == track['id']
    assert loaded['audio_reactivity']['mappings'] == project['audio_reactivity']['mappings']
    compiled = compile_composition(loaded)
    prepare_reactivity(compiled)
    assert response(compiled, .5)['low'] > .6
    assert render_sequence_frame(compiled, .5, (64, 48)).size == (64, 48)


def test_concurrent_preparation_derives_once_and_waiting_cancellation_returns(tones, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import synth_audio_reactivity as audio
    sequence = document(tones)
    sequence['audio_reactivity']['mappings'][0]['sensitivity'] = 1.6789
    entered = threading.Event(); proceed = threading.Event(); cancelled_waiting = threading.Event()
    original = audio._source_energy
    calls = []
    def block(*args):
        calls.append(1); entered.set()
        assert proceed.wait(timeout=3.)
        return original(*args)
    monkeypatch.setattr(audio, '_source_energy', block)
    waiting = Cancellation()
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(prepare_reactivity, sequence)
        assert entered.wait(timeout=2.)
        second = pool.submit(prepare_reactivity, sequence)
        third = pool.submit(prepare_reactivity, sequence, waiting)
        waiting.cancel()
        try:
            with pytest.raises(Cancelled): third.result(timeout=2.)
        finally:
            proceed.set()
        assert first.result(timeout=3.) is second.result(timeout=3.)
    assert calls == [1] and not waiting.processes


def test_same_size_overwrite_with_restored_mtime_invalidates_actual_analysis(tones, tmp_path):
    import os
    path = tmp_path / 'restored.wav'; path.write_bytes(Path(tones['path']).read_bytes())
    track = probe_soundtrack(path)
    sequence = document(track)
    first = prepare_reactivity(sequence)
    preset = resolve_sequence_frame(sequence, .5)[-1]
    old_response = response(sequence, .5)['low']
    stat = path.stat()
    content = bytearray(path.read_bytes())
    offset = content.index(b'data') + 8
    count = int.from_bytes(content[offset - 4:offset], 'little')
    audio = np.frombuffer(content, dtype='<i2', offset=offset, count=count // 2)
    audio[:] = (audio.astype(np.float32) * .5).astype('<i2')
    path.write_bytes(content)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    after = path.stat()
    assert (after.st_size, after.st_mtime_ns) == (stat.st_size, stat.st_mtime_ns)
    with pytest.raises(ValueError, match='stale'):
        apply_reactivity(preset, sequence, .5, analysis=first)
    second = prepare_reactivity(sequence)
    assert second is not first
    assert response(sequence, .5)['low'] < old_response * .6
