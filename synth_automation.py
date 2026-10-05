"""Bounded section gestures, evaluated against the resolved moving base.

Section IDs scope authored event IDs. Compiled IDs are unique per occurrence.
Automation uses output timeline time, never the procedural/media time maps.
"""
from __future__ import annotations

import copy
import math
import hashlib
import uuid
from synth import MODULE_BY_ID
from synth_instances import base_path

TARGETS = frozenset({
    'signal_repetition.spacing', 'signal_repetition.wave', 'signal_repetition.mix',
    'signal_repetition.fringe', 'signal_repetition.exposure',
    'signal_repetition.band_flow', 'signal_repetition.sync_loss', 'signal_repetition.line_flutter',
    'tape.pull', 'tape.tracking', 'tape.jitter', 'warp.amount',
    'breakup.amount', 'separation.amount', 'smear.amount', 'smear.opacity',
    'bloom.strength', 'crt_capture.bend', 'raster.grain', 'raster.lines',
    'raster.chroma', 'raster.line_noise', 'chroma_print.exposure',
    'chroma_print.mid_saturation', 'chroma_print.warm_color', 'chroma_print.mix',
})
STAGES = ('start', 'attack', 'hold', 'recovery')
MAX_SECTION_EVENTS = 131072
MAX_SEQUENCE_EVENTS = 131072


def target_parameter(path):
    if base_path(path) not in TARGETS:
        raise ValueError(f'Unsupported automation target: {path}')
    module, key = path.split('.')
    return next(p for p in MODULE_BY_ID[module].params if p.key == key)


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def normalize_automations(raw, *, duration=1., fractions=True):
    """Validate half-open, nonoverlapping enabled intervals on each target."""
    if not isinstance(raw, list) or len(raw) > (MAX_SECTION_EVENTS if fractions else MAX_SEQUENCE_EVENTS):
        raise ValueError('Automation must be a bounded list of events')
    suffix = '_fraction' if fractions else ''
    limit = 1. if fractions else duration
    ids = set(); result = []
    for event in raw:
        if not isinstance(event, dict): raise ValueError('Automation event must be an object')
        identifier = event.get('id')
        if not isinstance(identifier, str) or not identifier or len(identifier) > 256 or identifier in ids:
            raise ValueError('Automation identifiers must be unique within their clip/sequence')
        ids.add(identifier)
        path = event.get('path')
        if not isinstance(path, str): raise ValueError('Automation needs a parameter path')
        spec = target_parameter(path)
        amount = _number(event.get('amount'), 'Change amount')
        if abs(amount) > spec.maximum - spec.minimum:
            raise ValueError(f'{path} change amount exceeds its parameter range')
        enabled = event.get('enabled', True)
        if not isinstance(enabled, bool): raise ValueError('Automation enabled must be a boolean')
        easing = event.get('easing', 'smooth')
        if easing not in ('smooth', 'linear'): raise ValueError('Automation easing must be smooth or linear')
        stages = {key + suffix: _number(event.get(key + suffix), key.title()) for key in STAGES}
        if any(value < 0 or value > limit for value in stages.values()):
            raise ValueError('Automation start and stages must be within the clip')
        total = sum(stages[key + suffix] for key in STAGES[1:])
        if total <= 0 or stages['start' + suffix] + total > limit + 1e-12:
            raise ValueError('Automation needs a positive duration and must end inside its clip')
        result.append(dict(id=identifier, path=path, amount=amount, enabled=enabled, easing=easing, **stages))
    intervals = {}
    for event in result:
        if event['enabled']:
            start = event['start' + suffix]
            end = start + sum(event[key + suffix] for key in STAGES[1:])
            intervals.setdefault(event['path'], []).append((start, end, event['id']))
    for path, events in intervals.items():
        events.sort()
        for previous, current in zip(events, events[1:]):
            if current[0] < previous[1] - 1e-12:
                raise ValueError(f'Overlapping automation on {path}: {previous[2]} and {current[2]}')
    return result


def duplicate_automation(events, event_id):
    """Copy a gesture into the first free interval after it, within its section."""
    original = next((event for event in events if event['id'] == event_id), None)
    if original is None: raise ValueError('Select an automation to duplicate.')
    length = sum(original[key + '_fraction'] for key in STAGES[1:])
    start = original['start_fraction'] + length
    # Reserve disabled gestures too: their copies should still be safe to enable.
    intervals = sorted((event['start_fraction'], event['start_fraction'] +
                        sum(event[key + '_fraction'] for key in STAGES[1:]))
                       for event in events if event['path'] == original['path'])
    for left, right in intervals:
        if right <= start + 1e-12: continue
        if start + length <= left + 1e-12: break
        start = right
    if start + length > 1 + 1e-12:
        raise ValueError('No room after this automation. Lengthen the clip or move its gestures to make space, then duplicate again.')
    duplicate = copy.deepcopy(original)
    duplicate.update(id='gesture-' + uuid.uuid4().hex, start_fraction=min(start, 1-length))
    return duplicate


def envelope(event, seconds):
    """Continuous rise/hold/recover. Zero stages are explicit steps."""
    if not event.get('enabled', True): return 0.
    local = seconds - event['start']
    attack, hold, recovery = (event[key] for key in STAGES[1:])
    # Fractions and frame times may reach the same endpoint by different
    # floating-point operations. A few ULPs suppress only arithmetic residue,
    # preventing a nearly-zero pull from resampling an otherwise neutral frame.
    end = event['start'] + attack + hold + recovery
    tolerance = 8 * math.ulp(max(abs(end), abs(event['start'])))
    if seconds < event['start'] - tolerance or seconds >= end - tolerance: return 0.
    if abs(local) <= tolerance: local = 0.
    def ease(x):
        x = max(0., min(1., x))
        return x * x * (3 - 2 * x) if event.get('easing', 'smooth') == 'smooth' else x
    if attack > 0 and local < attack: return ease(local / attack)
    if local < attack + hold: return 1.
    return 1. - ease((local - attack - hold) / recovery) if recovery > 0 else 1.


def absolute_event(event, duration, start=0., identifier=None):
    result = {key: event[key] for key in ('id', 'path', 'amount', 'enabled', 'easing')}
    result.update({key: event[key + '_fraction'] * duration for key in STAGES})
    result['start'] += start
    if identifier is not None: result['id'] = identifier
    return result


def section_event(event, duration):
    result = {key: event[key] for key in ('id', 'path', 'amount', 'enabled', 'easing')}
    result.update({key + '_fraction': event[key] / duration for key in STAGES})
    return result


def apply_automations(preset, events, seconds):
    """Copy only for nonzero contributions; never normalize or enable effects."""
    result = preset
    modules = None
    for event in events:
        delta = event['amount'] * envelope(event, seconds)
        if delta == 0: continue
        module, key = event['path'].split('.')
        original = next((m for m in preset['modules'] if m['id'] == module), None)
        if original is None or not original.get('enabled', True): continue
        if result is preset:
            result = copy.deepcopy(preset)
            modules = {m['id']: m for m in result['modules']}
        spec = target_parameter(event['path'])
        modules[module]['params'][key] = max(spec.minimum, min(spec.maximum, original['params'][key] + delta))
    return result


def compiled_id(section_id, event_id, occurrence, loop):
    """Bounded identities survive repeated detailed/composition conversions."""
    payload = repr((section_id, event_id, occurrence, loop)).encode()
    return "event-" + hashlib.sha256(payload).hexdigest()[:32]
