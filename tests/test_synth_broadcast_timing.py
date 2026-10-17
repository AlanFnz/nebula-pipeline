"""Irregular signal loss stays seekable and leaves old documents unchanged."""
import hashlib
import json
from pathlib import Path

import numpy as np
from synth import MODULE_BY_ID
from synth_broadcast import interruption_gate, render_broadcast
from synth_composition import compile_composition, load_composition, save_composition
from synth_effect_discovery import effect_candidate
from synth_effects import effect_preset
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from test_synth_video import clip


def params(**changes):
    return dict({p.key: p.default for p in MODULE_BY_ID['broadcast'].params}, **changes)


def test_regular_and_missing_timing_retain_exact_old_pixels():
    fixtures = json.loads((Path(__file__).parent/'fixtures/broadcast-regular-v1-hashes.json').read_text())
    image = np.random.default_rng(120).random((53, 71, 3), dtype=np.float32)
    for case in fixtures:
        p = params(**case['changes'])
        for settings in (p, {k: v for k, v in p.items() if k not in ('timing', 'duration_variation', 'band_motion', 'band_interval', 'band_travel', 'band_variation')}):
            frame = render_broadcast(image, settings, case['time'], 1., 17)
            assert hashlib.sha256(frame.tobytes()).hexdigest() == case['hash']


def test_random_intervals_have_clusters_and_long_gaps_without_a_repeating_beat():
    p = params(timing=1, period=1., duration=.04)
    times = np.arange(0., 180., .01)
    gates = np.array([interruption_gate(p, t, 17) for t in times])
    starts = times[1:][np.diff(gates) > 0]
    gaps = np.diff(starts)
    assert .7 < gaps.mean() < 1.3  # Average interval remains useful.
    assert gaps.min() < .25 and gaps.max() > 3.
    assert gaps.std() > .6
    assert not np.array_equal(gates[:100], gates[100:200])
    assert np.array_equal(gates, [interruption_gate(p, t, 17) for t in reversed(times)][::-1])
    assert not np.array_equal(gates, [interruption_gate(p, t, 18) for t in times])


def test_random_gate_keeps_events_across_boundaries_and_handles_overlaps(monkeypatch):
    monkeypatch.setattr('synth_broadcast._interruption_events',
                        lambda seed, cell: ((.9, 1.),) if cell in (-1, 2) else ())
    p = params(timing=1, period=1., phase=0., duration=.2, duration_variation=0.)
    assert interruption_gate(p, 0., 17) == 1  # Event began before time zero.
    assert interruption_gate(p, .11, 17) == 0
    assert interruption_gate(p, 3.05, 17) == 1  # Crosses the cell boundary.
    assert interruption_gate(p, 3.11, 17) == 0
    assert interruption_gate(dict(p, duration_variation=1.), 3.2, 17) == 1
    assert interruption_gate(dict(p, duration_variation=1.), 3.3, 17) == 0
    assert interruption_gate(dict(p, duration=3.), 5.8, 17) == 1
    assert interruption_gate(dict(p, duration=0.), 3., 17) == 0


def test_random_events_are_independent_of_resolution_texture_and_static_fps():
    p = params(timing=1, duration_variation=.65, field=0., band=0.,
               curve=0., vignette=0., duration=.15, period=.8, static=1.)
    timelines = []
    for shape, changes in (((12, 16, 3), {}), ((18, 30, 3), dict(rate=7., static_style=1)),
                           ((10, 20, 3), dict(rate=0., screen=1., halo=2.))):
        image = np.zeros(shape, dtype=np.float32)
        times = np.arange(0., 5., .04)
        frames = [render_broadcast(image, dict(p, **changes), t, 1., 14) for t in times]
        timelines.append([frame.max() > .3 for frame in frames])
    assert timelines[0] == timelines[1] == timelines[2]
    assert 0 < sum(timelines[0]) < len(times)
    assert timelines[0] == [bool(interruption_gate(p, t, 14)) for t in times]


def test_random_wear_honors_speed_bypass_and_duration_zero():
    image = np.random.default_rng(1).random((20, 30, 3), dtype=np.float32)
    p = params(timing=1, duration_variation=.6)
    assert render_broadcast(image, dict(p, mix=0.), 2., 1., 8) is image
    assert np.array_equal(render_broadcast(image, p, 2., .5, 8), render_broadcast(image, p, 1., 1., 8))
    assert np.array_equal(render_broadcast(image, p, 2., 0., 8), render_broadcast(image, p, 0., 1., 8))
    silent = dict(p, duration=0., field=0., curve=0., vignette=0.)
    assert np.array_equal(render_broadcast(image, silent, 2., 1., 8), image)
    assert not np.array_equal(render_broadcast(image, dict(silent, outages=1.), 2., 1., 8), image)


def test_new_effect_uses_random_but_keeps_study_and_survives_save_reload(tmp_path):
    original = starter_composition('prismatic-film')
    updated = effect_candidate(original, None, 'broadcast')
    assert updated['effects']['broadcast']['params']['broadcast.timing'] == 1
    assert original['source'] == updated['source']
    assert original['sections'] == updated['sections']
    assert effect_preset('broadcast', 1)['params']['broadcast.timing'] == 0
    assert all(state.get('overrides', {}).get('broadcast.timing', 0) == 0 for state in original['source']['states'].values())
    path = tmp_path/'random.json'
    save_composition(path, updated)
    first, reloaded = compile_composition(updated), compile_composition(load_composition(path))
    for t in (.3, 2.7, 10.):
        assert render_sequence_frame(first, t, (72, 128)).tobytes() == render_sequence_frame(reloaded, t, (72, 128)).tobytes()


def test_existing_video_treatment_recipes_keep_regular_interruptions(clip):
    from synth_modulation_recipes import modulated_crt_composition
    from synth_video import TREATMENTS, apply_treatment, video_composition
    projects = [modulated_crt_composition(clip)]
    projects.extend(apply_treatment(video_composition(clip), i) for i in range(len(TREATMENTS)))
    for project in projects:
        broadcast = project['effects'].get('broadcast')
        if broadcast:
            assert broadcast['params']['broadcast.timing'] == 0
            assert broadcast['params']['broadcast.duration_variation'] == 0.
