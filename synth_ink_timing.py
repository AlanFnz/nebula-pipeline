"""Editable stage durations over the ink gesture's authored motion path."""
from __future__ import annotations

import math

import numpy as np


DURATION_KEYS = ('unfold_seconds', 'unfolded_seconds', 'fold_seconds', 'folded_seconds')
TIMING_KEYS = ('motion_speed', *DURATION_KEYS, 'cadence', 'cycle', 'phase',
               'period', 'open_start', 'open_duration', 'close_start', 'close_duration')


def stage_knots(p):
    """Ordered recipe landmarks, with overlapping legacy stages bounded."""
    start = p['open_start'] / 100
    opened = min(1., start + p['open_duration'] / 100)
    close = min(1., max(opened, p['close_start'] / 100))
    closed = min(1., max(close, (p['close_start'] + p['close_duration']) / 100))
    return (0., start, opened, close, closed, 1.)


def stage_durations(p):
    """Resolve seconds independently, retaining unspecified recipe stages."""
    _, start, opened, close, closed, _ = stage_knots(p)
    durations = dict(zip(DURATION_KEYS, (
        (opened - start) * p['period'], (close - opened) * p['period'],
        (closed - close) * p['period'], (start + 1 - closed) * p['period'],
    )))
    for key in DURATION_KEYS:
        if p.get(key, -1.) >= 0:
            durations[key] = p[key]
    return durations


def gesture_phase(time, p, speed=1.):
    """Return held clock, authored turn phase, opening and closing envelopes.

    With no duration overrides the old arithmetic stays exact. Custom seconds
    retime the authored turn along with opening, so a fast unfold still passes
    through the same edge-on views. The closed rest straddles the loop seam in
    the recipe's original proportion, keeping its initial pause.
    """
    if p.get('clock_mode', 0):
        speed = p.get('clock_scale', 1.)
    clock = math.floor(time * speed * p.get('motion_speed', 1.) * p['cadence'] + 1e-8) / p['cadence']
    if all(p.get(key, -1.) < 0 for key in DURATION_KEYS):
        phase = (clock / p['period'] + p['phase']) % 1.
        opening = np.clip((phase * 100 - p['open_start']) / p['open_duration'], 0., 1.)
        closing = np.clip((phase * 100 - p['close_start']) / p['close_duration'], 0., 1.)
        return clock, phase, opening * opening * (3 - 2 * opening), 1 - closing * closing * (3 - 2 * closing)
    stages = stage_durations(p)
    total = sum(stages.values())
    if total <= 0:
        return clock, 0., 0., 1.
    authored = stage_knots(p)
    closed_share = authored[1] + 1 - authored[-2]
    lead = stages['folded_seconds'] * (authored[1] / closed_share if closed_share else .5)
    opened = lead + stages['unfold_seconds']
    close = opened + stages['unfolded_seconds']
    closed = close + stages['fold_seconds']
    elapsed = (clock + p['phase'] * total) % total
    phase = float(np.interp(elapsed, (0., lead, opened, close, closed, total), authored))
    if elapsed < lead or elapsed >= closed:
        envelope = 0.
    elif elapsed < opened:
        amount = (elapsed - lead) / stages['unfold_seconds']
        envelope = amount * amount * (3 - 2 * amount)
    elif elapsed < close:
        envelope = 1.
    else:
        amount = (elapsed - close) / stages['fold_seconds']
        envelope = 1 - amount * amount * (3 - 2 * amount)
    return clock, phase, envelope, 1.
