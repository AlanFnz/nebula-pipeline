"""Circular control envelopes and note releases for the layered instrument."""
import math
import numpy as np
from synth_visual_sound import CONTROL_RATE, _smooth


def smooth_cycle(values, seconds):
    """Solve the one-pole's periodic initial state; last sample duplicates first."""
    cycle = np.asarray(values[:-1])
    if not len(cycle): return np.asarray(values).copy()
    coefficient = 1 - math.exp(-1 / (CONTROL_RATE * seconds))
    settled = _smooth(cycle, seconds)
    last = settled[-1] / -math.expm1(-len(cycle) / (CONTROL_RATE * seconds))
    result = np.empty_like(values)
    for i, value in enumerate(cycle):
        last += coefficient * (value - last)
        result[i] = last
    result[-1] = result[0]
    return result


def cyclic_notes(notes, period, duration):
    """Include releases from the previous turn, retaining each oscillator seed."""
    result = []
    for index, note in enumerate(notes):
        if note['time'] >= period: continue
        result.append(dict(note, loop_index=index))
        offset = period
        while note['time'] + duration(note) > offset:
            result.append(dict(note, time=note['time'] - offset, loop_index=index))
            offset += period
    return sorted(result, key=lambda note: note['time'])
