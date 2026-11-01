"""Regression coverage for the audible study's continuous visual ending."""
from pathlib import Path

import numpy as np

from synth_composition import compile_composition, load_composition
from synth_pleated_recipes import pleated_acid_composition, pleated_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_starters import starter_composition
from synth_visual_sound import pcm_blocks, visual_signals, RATE


def test_latest_starter_retains_earlier_studies_and_unedited_frames():
    project = pleated_acid_composition()
    assert starter_composition('pleated-signal-acid') == project
    seq = compile_composition(project)
    previous = compile_composition(load_composition(
        Path(__file__).parents[1] / 'presets/pleated-signal-acid-v2.json'))
    assert seq['duration'] == 20 and seq['fps'] == 12 and len(seq['cues']) == 240
    assert project['generated_sound'] == previous['generated_sound']
    changed = set(range(106, 119)) | set(range(175, 240))
    for frame in set(range(240)) - changed:
        assert resolve_sequence_frame(seq, frame / 12)[-1] == resolve_sequence_frame(previous, frame / 12)[-1]
    # The original triangle recipe still uses the original visual choreography.
    original = compile_composition(pleated_acid_composition(layered=False))
    silent = compile_composition(pleated_composition())
    for frame in (0, 112, 180, 199, 239):
        assert resolve_sequence_frame(original, frame / 12)[-1] == resolve_sequence_frame(silent, frame / 12)[-1]


def test_contraction_stays_visible_and_audible_without_an_audio_floor():
    seq = compile_composition(pleated_acid_composition())
    for frame in range(106, 119):
        rgb = np.asarray(render_sequence_frame(seq, frame / 12, (160, 120))).astype(float)
        violet = rgb[:, :, 2] > rgb[:, :, 0] + 25
        assert violet.mean() > .025, f'Empty central figure at frame {frame}'
    signals = visual_signals(seq)
    center = (signals['time'] >= 9) & (signals['time'] < 9.75)
    assert signals['presence'][center].min() >= .04
    audio = np.concatenate(list(pcm_blocks(seq, signals=signals)))
    # Check each 100 ms window through the previous silent stretch.
    for start in np.arange(9.1, 9.6, .1):
        chunk = audio[round(start * RATE):round((start + .1) * RATE)]
        assert np.sqrt(np.mean(chunk ** 2)) > .001
    assert np.isfinite(audio).all()


def test_tail_rotates_onward_then_leaves_mirrors_for_the_reference_pass():
    seq = compile_composition(pleated_acid_composition())
    def params(frame):
        return next(m['params'] for m in resolve_sequence_frame(seq, frame / 12)[-1]['modules']
                    if m['id'] == 'pleated_field')
    # Continuing past the quarter-turn avoids repeating the earlier return.
    angles = [params(f)['angle'] for f in range(190, 212)]
    assert np.all(np.diff(angles) > 0) and angles[-1] - angles[0] > 170
    assert all(params(f)['symmetry'] == 2 for f in range(175, 212))
    assert all(params(f)['symmetry'] == 0 for f in range(212, 240))
    # Reference pass: approach, brief retreat, then renewed approach.
    scale = lambda f: params(f)['size']
    assert scale(225) > scale(215) * 2
    assert scale(232) < scale(225) * .5
    assert scale(239) > scale(232) * 2.5
    assert scale(239) > scale(238)  # No unrelated freeze at the end.
