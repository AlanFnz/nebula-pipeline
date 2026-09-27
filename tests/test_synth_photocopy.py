"""Reusable copy treatment, source masking and independent video hold clocks."""
import io
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
import pytest

from media import Cancellation, Cancelled
from synth import MODULE_BY_ID, curated_presets, render_synth_frame
from synth_compat import frozen_data
from synth_composition import blank_composition, compile_composition, load_composition, save_composition
from synth_cutout import render_cutout, subject_mask
from synth_effects import effect_preset
from synth_photocopy import render_photocopy
from synth_sequence import render_sequence_frame
from synth_video import VideoFrameProvider, source_index, video_composition
from test_synth_video import clip


def defaults(module): return {param.key: param.default for param in MODULE_BY_ID[module].params}


def test_new_modules_are_opt_in_and_keep_legacy_indices():
    for name, legacy in frozen_data('presets').items():
        current = curated_presets()[name]
        assert [m['id'] for m in current['modules'][:len(legacy['modules'])]] == [m['id'] for m in legacy['modules']]
        assert all(not m['enabled'] for m in current['modules'][len(legacy['modules']):])
        for t in (0, .37):
            assert render_synth_frame(current, time_seconds=t, size=(64, 80)).tobytes() == render_synth_frame(legacy, time_seconds=t, size=(64, 80)).tobytes()


def test_copy_is_stateless_and_has_its_own_grain_clock():
    source = np.full((100, 80, 3), .8, dtype=np.float32)
    source[20:90, 30:50] = .03
    p = defaults('photocopy')
    p.update(light_drift=0., tint_drift=0., blackout=0., cadence=10.)
    a = render_photocopy(source, p, .21, 52)
    assert np.array_equal(a, render_photocopy(source, p, .29, 52))
    assert not np.array_equal(a, render_photocopy(source, p, .31, 52))
    assert np.array_equal(a, render_photocopy(source, p, .21, 52))
    assert a[40:70, 33:47].mean() < a[:15].mean() * .2
    assert render_photocopy(source, dict(p, mix=0.), .21, 52) is source
    p.update(cadence=0.)
    assert np.array_equal(render_photocopy(source, p, .2, 52), render_photocopy(source, p, .8, 52))


def test_cutout_composites_without_changing_figure_proportions():
    source = Image.new('RGB', (120, 200), (150, 40, 20))
    mask = Image.new('L', source.size); ImageDraw.Draw(mask).ellipse((40, 60, 80, 100), fill=255)
    p = defaults('subject_cutout'); p.update(silhouette=1., feather=0.)
    result = np.asarray(render_cutout(source, mask, p))
    y, x = np.where(result[..., 0] < 10)
    assert x.max() - x.min() == y.max() - y.min() == 40
    assert np.all(result[0] == 255)
    assert render_cutout(source, mask, dict(p, mix=0.)) is source
    inverse = np.asarray(render_cutout(source, mask, dict(p, invert=1)))
    assert np.all(inverse[0] == 0) and np.all(inverse[80, 60] == 255)
    assert not np.array_equal(result, np.asarray(render_cutout(source, mask, dict(p, shadow=1., ground=.5))))


def test_video_hold_clock_and_effect_toggle_round_trip(clip, tmp_path, monkeypatch):
    project = video_composition(clip)
    project['footage']['motion_fps'] = 3.
    assert source_index(project['footage'], .1) == source_index(project['footage'], .3) == 0
    assert source_index(project['footage'], .34) == 4
    project['effects'] = {key: effect_preset(key) for key in ('subject_cutout', 'photocopy')}
    requested = []
    def mask(self, footage, t, canvas, mode):
        requested.append((t, mode))
        result = Image.new('L', (96, 72)); ImageDraw.Draw(result).rectangle((30, 10, 60, 70), fill=255)
        return result
    monkeypatch.setattr(VideoFrameProvider, 'mask', mask)
    path = tmp_path / 'copy.json'; save_composition(path, project)
    sequence = compile_composition(load_composition(path))
    with VideoFrameProvider() as provider:
        treated = render_sequence_frame(sequence, .25, (96, 72), provider)
        assert requested == [(.25, 0)]
        clean = render_sequence_frame(sequence, .25, (96, 72), provider, bypass=True)
        assert requested == [(.25, 0)]
        assert clean.tobytes() != treated.tobytes()
        project['effects']['subject_cutout']['mode'] = 'off'
        without_mask = render_sequence_frame(compile_composition(project), .25, (96, 72), provider)
        assert requested == [(.25, 0)] and without_mask.tobytes() != treated.tobytes()
    generated = blank_composition(); generated['effects']['subject_cutout'] = effect_preset('subject_cutout')
    with pytest.raises(ValueError, match='imported video'): compile_composition(generated)


def test_canonical_masks_ignore_preview_resolution_and_reuse_cache(clip, tmp_path, monkeypatch):
    import synth_cutout
    seen = []
    def acquire(image, mode, cancel, directory):
        seen.append(image.tobytes())
        return Image.new('L', image.size, 255)
    monkeypatch.setattr(synth_cutout, 'subject_mask', acquire)
    canvas = {'width': 1080, 'height': 1920}
    with VideoFrameProvider(preview=True, directory=tmp_path) as preview, VideoFrameProvider(directory=tmp_path) as export:
        assert preview.mask(clip, .25, canvas, 0).size == (405, 720)
        assert export.mask(clip, .25, canvas, 0).size == (405, 720)
        assert seen[0] == seen[1]
    assert not preview.cancel.processes and not export.cancel.processes


def test_mask_cache_cancellation_and_modes(tmp_path, monkeypatch):
    import synth_cutout
    calls = []
    png = io.BytesIO(); Image.new('L', (8, 8), 200).save(png, format='PNG')
    class Process:
        returncode = 0
        def __init__(self, args, **kwargs): calls.append(args)
        def communicate(self, *args, **kwargs): return png.getvalue(), b''
        def poll(self): return 0
        def wait(self): return 0
    monkeypatch.setattr(synth_cutout, 'mask_helper', lambda: Path('/fake/helper'))
    monkeypatch.setattr(synth_cutout.subprocess, 'Popen', Process)
    image = Image.new('RGB', (16, 24), 'red'); cancel = Cancellation()
    first = subject_mask(image, 0, cancel, tmp_path)
    assert first.size == image.size
    assert subject_mask(image, 0, cancel, tmp_path).tobytes() == first.tobytes() and len(calls) == 1
    subject_mask(image, 1, cancel, tmp_path)
    assert len(calls) == 2 and calls[-1][-1] == 'people'
    cancel.cancel()
    with pytest.raises(Cancelled): subject_mask(image, 0, cancel, tmp_path)
    assert not cancel.processes


@pytest.mark.skipif(sys.platform != 'darwin' or not Path('build/native/nebula-mask').is_file(), reason='optional native helper not built')
def test_native_mask_helper_empty_frame(tmp_path):
    # Actual native protocol, including the no-object path; no private assets.
    mask = subject_mask(Image.new('RGB', (160, 240), 'white'), 0, Cancellation(), tmp_path)
    assert mask.mode == 'L' and mask.size == (160, 240)
    assert np.asarray(mask).mean() < 1
