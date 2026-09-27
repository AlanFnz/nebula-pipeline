"""Video contracts: independent clocks, exact seeking, framing and atomic audio export."""
import copy
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw
import pytest

from media import Cancellation, Cancelled, decode_frames
from synth import default_synth_preset
from synth_composition import compile_composition, load_composition, save_composition
from synth_media import export_synth_video
from synth_sequence import render_sequence_frame
from synth_video import (VideoFrameProvider, apply_treatment, check_source, frame_on_canvas,
                         inspect_video, normalize_footage, prepare_proxy, relink_footage,
                         source_index, video_composition)


@pytest.fixture(scope='module')
def clip(tmp_path_factory):
    folder = tmp_path_factory.mktemp('video')
    path = folder / 'moving image with audio.mkv'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=128x96:rate=12:duration=1',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1',
                    '-c:v', 'ffv1', '-pix_fmt', 'bgr0', '-c:a', 'pcm_s16le', str(path)], check=True)
    return inspect_video(path)


def test_proxy_random_access_matches_original_and_reuses_decoding(clip, tmp_path):
    originals = dict(decode_frames(clip, 12, 0, 12, edge=96))
    with VideoFrameProvider(preview=True, directory=tmp_path) as provider:
        for index in (0, 11, 4, 9, 1, 7, 2, 8, 3, 10, 6, 5):
            frame = provider.frame(clip, index / 12, 96)
            assert frame.tobytes() == originals[index].tobytes(), index
        count = provider.decode_count
        for index in range(12): provider.frame(clip, index / 12, 96)
        assert provider.decode_count == count
    assert not provider.cancel.processes
    assert len(list(tmp_path.glob('*.mkv'))) == 1
    with VideoFrameProvider(preview=True, directory=tmp_path) as provider:
        assert provider.frame(clip, .5, 96).tobytes() == originals[6].tobytes()


def test_trim_loop_hold_and_continuous_clock_across_sections(clip):
    project = video_composition(clip)
    project['footage'].update({'in': .25, 'out': .75, 'treatment_fps': 2})
    first = project['sections'][0]; first['duration'] = .5
    project['sections'].append(dict(copy.deepcopy(first), id='section-2'))
    seq = compile_composition(project)
    assert source_index(seq['footage'], .5) == 3
    assert source_index(seq['footage'], .49) == 8
    with VideoFrameProvider() as provider:
        for frame in range(12):
            t = frame / 12
            expected = provider.frame(seq['footage'], t)
            actual = render_sequence_frame(seq, t, frame_provider=provider, bypass=True)
            assert actual.tobytes() == expected.tobytes()
        seq['footage']['end_mode'] = 'hold'
        assert render_sequence_frame(seq, .9, frame_provider=provider, bypass=True).tobytes() == provider.frame(seq['footage'], .499).tobytes()
    # A longer source must not restart when an effect section starts.
    project['footage'].update({'in': 0., 'out': 1.})
    seq = compile_composition(project)
    with VideoFrameProvider() as provider:
        a = render_sequence_frame(seq, 0, frame_provider=provider, bypass=True)
        b = render_sequence_frame(seq, .5, frame_provider=provider, bypass=True)
        assert a.tobytes() != b.tobytes()
        assert b.tobytes() == provider.frame(clip, .5).tobytes()


def test_effect_changes_reuse_source_and_before_bypasses_all_treatment(clip, tmp_path):
    project = video_composition(clip)
    with VideoFrameProvider(preview=True, directory=tmp_path) as provider:
        clean = render_sequence_frame(compile_composition(project), .25, (96, 72), provider)
        decoded = provider.decode_count
        treated_project = apply_treatment(project, 1)
        # Fixed preview resolution here so this tests effects, not resolution changes.
        treated_project['effects'].pop('low_res')
        treated = compile_composition(treated_project)
        treated['master'].update(enabled=True, saturation=0.)
        image = render_sequence_frame(treated, .25, (96, 72), provider)
        assert provider.decode_count == decoded
        assert image.tobytes() != clean.tobytes()
        source = render_sequence_frame(treated, .25, (96, 72), provider, True)
        assert np.abs(np.asarray(source).astype(int) - np.asarray(clean)).max() <= 1


def test_uniform_canvas_framing_and_full_canvas_effects(clip):
    image = Image.new('RGB', (128, 96)); ImageDraw.Draw(image).rectangle((48, 32, 79, 63), fill='white')
    canvas = {'width': 96, 'height': 192}
    for fit in ('contain', 'cover', 'original'):
        framed = np.asarray(frame_on_canvas(image, dict(clip, fit=fit), canvas, (96, 192)))
        ys, xs = np.where(framed[..., 0] > 200)
        assert abs((xs.max() - xs.min()) - (ys.max() - ys.min())) <= 1
        assert abs((xs.min() + xs.max()) / 2 - 47.5) <= 1
    moved = np.asarray(frame_on_canvas(image, dict(clip, x=10., y=-12.), canvas, (96, 192)))
    ys, xs = np.where(moved[..., 0] > 200)
    assert abs((xs.min() + xs.max()) / 2 - 57.5) <= 1
    assert abs((ys.min() + ys.max()) / 2 - 83.5) <= 1
    p = video_composition(clip); p['canvas'] = canvas
    p['effects'] = {'raster': {'mode': 'on', 'params': {'raster.grain': .2}}}
    result = np.asarray(render_sequence_frame(compile_composition(p), .25))
    assert np.std(result[:20]) > 1 and np.std(result[-20:]) > 1


def test_saved_source_missing_relink_and_validation(clip, tmp_path):
    p = video_composition(clip); saved = tmp_path / 'composition.json'
    save_composition(saved, p)
    assert compile_composition(load_composition(saved)) == compile_composition(p)
    raw = json.loads(saved.read_text()); raw['footage']['path'] = 'missing.mkv'; saved.write_text(json.dumps(raw))
    loaded = load_composition(saved)
    assert loaded['footage']['path'] == str(tmp_path / 'missing.mkv')
    with pytest.raises(ValueError, match='missing'): check_source(loaded['footage'])
    loaded['footage'] = relink_footage(loaded['footage'], clip)
    assert render_sequence_frame(compile_composition(loaded), 0).size == (128, 96)
    with pytest.raises(ValueError, match='Out'): normalize_footage(dict(clip, out=0))
    p['effects'] = {'silhouette': {'mode': 'on', 'params': {}}}
    with pytest.raises(ValueError, match='generators'): compile_composition(p)
    changed = copy.deepcopy(clip); changed['identity']['size'] += 1
    with pytest.raises(ValueError, match='changed'): check_source(changed)


def test_treatments_are_independent_and_renderable(clip):
    p = video_composition(clip)
    with VideoFrameProvider() as provider:
        for index in range(4):
            treatment = apply_treatment(p, index)
            assert treatment['footage'] == p['footage']
            assert treatment['sections'] == p['sections']
            assert render_sequence_frame(compile_composition(treatment), .5, (96, 72), provider).size == (96, 72)
    assert p['effects'] == {}


def audio_samples(path):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-f', 'f32le', '-ac', '1', '-ar', '48000', 'pipe:1'])
    return np.frombuffer(raw, dtype='<f4')


@pytest.mark.parametrize('mode,audio,start', [('loop', 'keep', 0), ('hold', 'keep', 0), ('hold', 'keep', 9), ('loop', 'keep', 9), ('loop', 'mute', 0)])
def test_export_audio_obeys_trim_loop_hold_and_range(clip, tmp_path, mode, audio, start):
    p = video_composition(clip)
    p['sections'][0]['duration'] = 2.
    p['footage'].update({'in': .25, 'out': .75, 'end_mode': mode, 'audio': audio})
    target = tmp_path / f'{mode}-{audio}-{start}.mp4'
    sequence = compile_composition(p)
    export_synth_video(default_synth_preset(), target, start=start, sequence=sequence)
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(target)]))
    assert abs(float(info['format']['duration']) - (24 - start) / 12) < .06
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    assert int(video['nb_frames']) == 24 - start
    assert (video['width'], video['height']) == (128, 96)
    assert any(s['codec_type'] == 'audio' for s in info['streams']) == (audio == 'keep')
    if audio == 'keep':
        samples = audio_samples(target)
        late = samples[int(.9 * 48000):int(1.1 * 48000)]
        rms = np.sqrt(np.mean(late**2))
        assert rms > .05 if mode == 'loop' else rms < .001


def test_export_cancellation_and_source_protection_are_atomic(clip, tmp_path):
    seq = compile_composition(video_composition(clip))
    output = tmp_path / 'existing.mp4'; output.write_bytes(b'keep me')
    cancel = Cancellation()
    with pytest.raises(ValueError, match='cancelled'):
        export_synth_video(default_synth_preset(), output, sequence=seq, cancel=cancel,
                           progress=lambda a, b: cancel.cancel() if a == 2 else None)
    assert output.read_bytes() == b'keep me'
    assert not list(tmp_path.glob('.nebula-*'))
    assert not cancel.processes
    with pytest.raises(ValueError, match='different'):
        export_synth_video(default_synth_preset(), clip['path'], sequence=seq)
    alias = tmp_path / 'source-alias.mkv'; os.link(clip['path'], alias)
    with pytest.raises(ValueError, match='different'):
        export_synth_video(default_synth_preset(), alias, sequence=seq)


def test_cancelled_proxy_is_not_published(clip, tmp_path):
    cancel = Cancellation(); cancel.cancel()
    with pytest.raises(Cancelled): prepare_proxy(clip, cancel, tmp_path)
    assert not list(tmp_path.glob('*.mkv'))


def test_fractional_rate_proxy_scrubs_keep_sequential_frame_identity(tmp_path):
    from synth_video import _proxy_frames
    path = tmp_path / 'ntsc.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=128x96:rate=30000/1001:duration=1',
                    '-c:v', 'libx264', str(path)], check=True)
    footage = inspect_video(path)
    cache = tmp_path / 'cache'
    proxy = prepare_proxy(footage, directory=cache)
    sequential = dict(_proxy_frames(proxy, footage, 0, 96, Cancellation()))
    with VideoFrameProvider(preview=True, directory=cache) as provider:
        for index in (0, 14, 7, 29, 1, 8, 3, 27):
            assert provider.frame(footage, index / footage['sample_fps'], 96).tobytes() == sequential[index].tobytes()
