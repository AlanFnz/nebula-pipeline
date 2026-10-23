"""Semantic reading beats shared explicitly by text and opt-in print treatments.

All decisions use absolute source time. No wording, study cues, frame history,
or rendered-image crop coordinates are baked into the scheduler.
"""
from dataclasses import dataclass
import math
import unicodedata


@dataclass(frozen=True)
class ReadingBeat:
    text: str
    burst: float = 0.
    progress: float = 0.
    index: int = 0
    final: bool = False


def letters(word):
    """Keep combining accents with their base character when making inserts."""
    result = []
    for character in word:
        if result and unicodedata.combining(character): result[-1] += character
        else: result.append(character)
    return result


def reading_schedule(p):
    words = p['content'].split()
    duration = p.get('reading_duration', 7.)
    final = min(p.get('reading_final', 2.), duration * .8)
    available = duration - final
    # Dense wording always retains a reading interval; lengthen the cycle for
    # more comfortable reading. Cap interruptions at 30% of the word sequence.
    transition = min(p.get('reading_transition', .25), available * .3 / (len(words) + 1))
    weights = [max(1, len(letters(word))) ** p.get('reading_weight', .65) for word in words]
    reading = max(0., available - transition * (len(words) + 1))
    total = sum(weights) or 1.
    cursor = 0.; events = []
    for index, (word, weight) in enumerate(zip(words, weights)):
        events.append((cursor, cursor + transition, word, index, True))
        cursor += transition
        span = reading * weight / total
        events.append((cursor, cursor + span, word, index, False))
        cursor += span
    return events, available, transition


def reading_beat(p, clock):
    duration = p.get('reading_duration', 7.)
    if p.get('reading_loop', 0): clock = max(0., clock) % duration
    else: clock = max(0., clock)
    events, final_start, transition = reading_schedule(p)
    if not p['content'].strip() or clock >= final_start:
        return ReadingBeat(p['content'], final=True)
    for start, end, word, index, is_transition in events:
        if start <= clock < end:
            if not is_transition: return ReadingBeat(word, index=index)
            progress = (clock - start) / max(.001, end - start)
            # Each interruption selects a complete unit, never slices glyphs.
            kind = p.get('reading_fragments', 2)
            if p.get('reading_breakup', .85) > 0 and (kind == 1 or (kind == 2 and int(progress * 3) != 1)):
                units = letters(word)
                word = units[(index + int(progress * 3)) % len(units)]
            return ReadingBeat(word, p.get('reading_breakup', .85), progress, index)
    # Last transition reveals the entire phrase before its protected hold.
    progress = max(0., min(1., (clock - (final_start - transition)) / max(.001, transition)))
    return ReadingBeat(p['content'], p.get('reading_breakup', .85), progress, len(p['content'].split()), True)


def film_reading_params(p, beat):
    """Reduce occlusion on reading beats; use the same protection on any print."""
    amount = p.get('reading_clarity', 0.)
    if beat is None or amount <= 0: return p
    result = dict(p)
    b = beat.burst
    # A bounded optical burst, not a regularly repeating black blink.
    flash = (.5 + .5 * math.sin((beat.progress * 2.6 + beat.index * .43) * math.tau)) if b else 0.
    targets = {
        'opening': 1.1 - b * (.1 + .55 * flash), 'gate_x': .5,
        'exposure': .28 + b * (1.1 + .8 * flash),
        'reversal': b * (1.1 if beat.index % 2 else .15),
        'halo': .14 + b * (.6 + flash),
        'softness': .85 + b * 2.6, 'ink_spread': .7 + b * 3.,
        'melt': .6 + b * 6., 'damage': .04 + b * .55,
    }
    for key, target in targets.items():
        # Optical controls remain meaningful while protected. Scaling around
        # their configured value preserves parameter edits and automation.
        if key in ('softness', 'ink_spread', 'melt', 'halo', 'damage', 'exposure'):
            baseline = {'softness': 3.2, 'ink_spread': 4.5, 'melt': 3.8,
                        'halo': 1.15, 'damage': .5, 'exposure': 1.3}[key]
            target *= p[key] / baseline
        result[key] = p[key] * (1 - amount) + target * amount
    return result


def collage_reading_params(p, beat):
    amount = p.get('reading_layout', 0.)
    if beat is None or amount <= 0: return p
    b = beat.burst
    # The source already contains the chosen word/letter. Use complete bounds
    # for both impressions; copies and extreme enlargements live in bursts.
    scale = (1.25, .62, 1.75)[min(2, int(beat.progress * 3))]
    targets = {'start': 0., 'end': 1., 'poster_start': 0., 'poster_end': 1.,
               'width': p['width'] * (1 + b * (scale - 1)),
               'height': 1 + b * (p['height'] - 1),
               'x': p['x'] * b, 'y': p['y'] * b,
               'copies': 1, 'poster': p['poster'] * b,
               'echo': p['echo'] * b, 'bars': p['bars'] * b,
               'weave': p['weave'] * (.2 + .8 * b)}
    result = dict(p)
    for key, target in targets.items(): result[key] = p[key] * (1 - amount) + target * amount
    result['copies'] = max(1, round(result['copies']))
    return result
