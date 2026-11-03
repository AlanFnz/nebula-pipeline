"""Cached playback must not revalidate a whole study on every inspector tick."""
import math
from pathlib import Path

import pytest
from PySide6.QtCore import QSignalBlocker

from synth_composition import load_composition
from synth_effect_diagnostics import explain_effect
from synth_sequence import resolve_sequence_frame
from test_synth_composer_ui import window
from test_synth_preview_scope import settle


def test_cached_study_updates_inspector_without_renormalizing(window, monkeypatch):
    import synth_sequence
    window.auto_prepare.setChecked(False)
    monkeypatch.setattr(window, 'prepare_visual_sound', lambda: None)
    window.set_composition(load_composition(Path(__file__).parents[1]/'presets/pleated-signal-acid-v4.json'))
    settle(window)
    window.composer.effects_panel.inspect_effect('film_emulsion')
    # Resolve expected inspector facts through the existing public path first.
    expected = {t: explain_effect(window.composition, window.sequence, 'film_emulsion', t,
                                 resolved=resolve_sequence_frame(window.sequence, t))
                for t in (1., 9., 18.)}
    received = []
    monkeypatch.setattr(window.composer.effects_panel, 'set_explanations', received.append)
    def unexpected(*_args, **_kwargs):
        raise AssertionError('Cached playback must reuse the compiled sequence')
    monkeypatch.setattr(synth_sequence, 'normalize_sequence', unexpected)
    packet = ((2, 2), b'\x00'*12)
    for seconds in expected:
        window.display_frame(seconds, packet, cached=True)
        assert received[-1] == expected[seconds]
        assert window.viewer.packet == packet
    assert window.composition['generated_sound']['version'] == 3


@pytest.mark.parametrize('elapsed', [.082, .0834, .1665, 1.002, 19.999, 20.001])
def test_playback_timer_targets_next_frame_boundary(window, monkeypatch, elapsed):
    import synth_studio
    monkeypatch.setattr(window, 'preview_fps', lambda: 12)
    with QSignalBlocker(window.play): window.play.setChecked(True)
    window.play_started = 100.
    window.play_origin = 0
    monkeypatch.setattr(synth_studio.time, 'monotonic', lambda: 100.+elapsed)
    window.schedule_play_tick()
    delay = window.play_timer.interval()/1000.
    boundary = (math.floor(elapsed*12)+1)/12
    assert boundary <= elapsed+delay+1e-10 <= boundary+.001+1e-10
    window.play_timer.stop()
    with QSignalBlocker(window.play): window.play.setChecked(False)
