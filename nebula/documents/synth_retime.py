"""Optional piecewise clocks for section stretching, shared by preview/export.

Cues stay on the timeline. Procedural effects and footage each receive their
own continuous clock; an absent map preserves the original renderer exactly.
"""
from __future__ import annotations

import math

CLOCKS = ('effects', 'video')


def normalize_time_map(raw, duration):
    if not isinstance(raw, list) or not raw or len(raw) > 65536:
        raise ValueError('Time map must contain clock segments')
    result = []
    end = 0.
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError('Invalid time map segment')
        item = {}
        for key in ('start', 'end', 'effects_start', 'effects_rate', 'video_start', 'video_rate'):
            value = entry.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'Time map {key} must be finite')
            item[key] = float(value)
        if abs(item['start'] - end) > 1e-8 or item['end'] <= item['start']:
            raise ValueError('Time map segments must be contiguous and ordered')
        for clock in CLOCKS:
            if item[f'{clock}_start'] < 0 or not 1e-12 <= item[f'{clock}_rate'] <= 1e12:
                raise ValueError('Time map clock is outside the supported range')
        end = item['end']
        result.append(item)
    if abs(end - duration) > 1e-8:
        raise ValueError('Time map must cover the sequence duration')
    return result


def clock_segment(time_map, time):
    # The final segment also defines continuation when an imported phrase is
    # extended or looped, matching the existing continuous-clock convention.
    return next((item for item in time_map if time < item['end'] - 1e-10), time_map[-1])


def mapped_time(time_map, time, clock='effects'):
    if not time_map:
        return time
    item = clock_segment(time_map, time)
    return round(item[f'{clock}_start'] + (time - item['start']) * item[f'{clock}_rate'], 12)



def resize_time_map(time_map, duration):
    """Extend/trim coverage without altering the retained clocks or their rates."""
    result = [dict(item) for item in time_map if item['start'] < duration]
    result[-1]['end'] = duration
    return result


def compose_time_maps(outer, inner):
    """Preserve clocks when a detailed sequence becomes an editable composition."""
    if not inner:
        return outer
    result = []
    for segment in outer:
        boundaries = {segment['start'], segment['end']}
        for clock in CLOCKS:
            for source in inner[:-1]:
                time = segment['start'] + (source['end'] - segment[f'{clock}_start']) / segment[f'{clock}_rate']
                if segment['start'] + 1e-9 < time < segment['end'] - 1e-9:
                    boundaries.add(time)
        boundaries = sorted(boundaries)
        for start, end in zip(boundaries, boundaries[1:]):
            item = {'start': start, 'end': end}
            for clock in CLOCKS:
                time = segment[f'{clock}_start'] + (start - segment['start']) * segment[f'{clock}_rate']
                source = clock_segment(inner, time)
                item[f'{clock}_start'] = mapped_time(inner, time, clock)
                item[f'{clock}_rate'] = segment[f'{clock}_rate'] * source[f'{clock}_rate']
            result.append(item)
    return result
