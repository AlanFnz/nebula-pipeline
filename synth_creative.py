"""Bounded, reversible adjustments to authored effect values, before rendering."""
from dataclasses import dataclass
import math

from synth import MODULE_BY_ID


@dataclass(frozen=True)
class CreativeControl:
    key: str
    label: str
    paths: tuple[str, ...]
    hint: str
    minimum: float = 0.
    maximum: float = 2.
    neutral: float = 1.
    operation: str = 'scale'


CREATIVE_CONTROLS = {
    'tape': (
        CreativeControl('damage', 'Tracking & dropout strength',
                        ('tape.tracking', 'tape.jitter', 'tape.dropouts', 'tape.head_switch'),
                        'Scale tracking slips, scan jitter, missing scanlines and head-switch wear. Color bleed stays separate.'),
        CreativeControl('cadence', 'Pattern change speed', ('tape.rate',),
                        'Scale how often the tape pattern changes at global speed 1. This is pattern cadence, not fault probability or export FPS.'),
        CreativeControl('color', 'Color bleed', ('tape.chroma_delay', 'tape.bleed'),
                        'Scale the delay and spread of color without changing the tracking/dropout amplitudes.'),
    ),
    'frame_jitter': (
        CreativeControl('distance', 'Movement distance', ('frame_jitter.x', 'frame_jitter.y'),
                        'Scale horizontal and vertical registration together, preserving their balance and random pose sequence.'),
        CreativeControl('rotation', 'Turn jitter', ('frame_jitter.rotation',),
                        'Scale the held rotation. Translation and scale jitter stay separate.'),
        CreativeControl('cadence', 'Pose change speed', ('frame_jitter.rate',),
                        'Scale changes per second at global speed 1. A slower cadence holds poses longer; it does not change Timeline FPS.'),
    ),
    'ghosts': (
        CreativeControl('copies', 'Add / remove copies', ('smear.ghosts',),
                        'Add or remove copies from each authored count, bounded to 1–10. The luminous form companion remains a single ghost.',
                        -6, 6, 0, 'offset'),
        CreativeControl('distance', 'Trail distance', ('smear.amount', 'slab.ghost_offset'),
                        'Scale the whole-image trail reach and the luminous form companion offset. Does not change their direction.'),
        CreativeControl('brightness', 'Trail brightness', ('smear.opacity', 'slab.ghost_opacity'),
                        'Scale shifted-copy brightness and the luminous form companion opacity. Existing fading along the trail is retained.'),
    ),
    'particles': (
        CreativeControl('distance', 'Expansion distance', ('particles.dispersion',),
                        'Scale the released cloud around the same center. Requires a released cloud or Assembly cycle; it does not trigger an expansion.'),
        CreativeControl('outward', 'Outward time', ('particles.expand_seconds',),
                        'Scale Impulse expansion duration. The engine caps it at one quarter of Cycle seconds; cycle length and burst start phase stay unchanged.', .25),
        CreativeControl('return', 'Return time', ('particles.gather_seconds',),
                        'Scale Impulse gathering duration, capped at one fifth of Cycle seconds. This does not change cycle length.', .25),
        CreativeControl('disorder', 'Path disorder', ('particles.chaos', 'particles.turbulence'),
                        'Scale wandering and, in Surges/Impulse, staggered curved arrivals. Does not change the release center or model size.'),
    ),
}


def normalize_creative(effect_id, raw):
    controls = {control.key: control for control in CREATIVE_CONTROLS.get(effect_id, ())}
    if not controls or not isinstance(raw, dict):
        raise ValueError(f'Creative controls are unavailable for {effect_id}')
    if type(raw.get('version')) is not int or raw['version'] != 1:
        raise ValueError('Unsupported creative controls version')
    values = raw.get('values')
    if not isinstance(values, dict): raise ValueError('Creative values must be an object')
    result = {}
    for key, value in values.items():
        control = controls.get(key)
        if control is None: raise ValueError(f'Unknown {effect_id} creative control: {key}')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not control.minimum <= value <= control.maximum:
            raise ValueError(f'{key} must be between {control.minimum} and {control.maximum}')
        if control.operation == 'offset' and not float(value).is_integer():
            raise ValueError(f'{key} must be an integer')
        result[key] = int(value) if control.operation == 'offset' else float(value)
    normalized = {'version': 1, 'values': result}
    if 'variation' in raw:
        variation = raw['variation']
        if (not isinstance(variation, dict) or type(variation.get('seed')) is not int or
            not 0 <= variation['seed'] < 2**31 or variation.get('amount') not in ('subtle', 'moderate', 'strong') or
            not isinstance(variation.get('controls'), list) or not variation['controls'] or
            not all(isinstance(key, str) and key in controls for key in variation['controls'])):
            raise ValueError('Invalid creative variation record')
        normalized['variation'] = dict(seed=variation['seed'], amount=variation['amount'], controls=sorted(set(variation['controls'])))
    return normalized


def merged_creative(parent, local):
    """Local keys override their parent; explicit neutral cancels a parent key."""
    values = dict(parent.get('creative', {}).get('values', {}))
    values.update(local.get('creative', {}).get('values', {}))
    result = {'version': 1, 'values': values}
    variation = local.get('creative', {}).get('variation', parent.get('creative', {}).get('variation'))
    if variation is not None: result['variation'] = dict(variation)
    return result


def creative_overrides(effect_id, values, creative):
    result = {}
    for control in CREATIVE_CONTROLS.get(effect_id, ()):
        value = creative.get('values', {}).get(control.key, control.neutral)
        if value == control.neutral: continue
        for path in control.paths:
            module, key = path.split('.')
            spec = next(spec for spec in MODULE_BY_ID[module].params if spec.key == key)
            base = values[path]
            adjusted = base + value if control.operation == 'offset' else base * value
            adjusted = max(spec.minimum, min(spec.maximum, adjusted))
            result[path] = int(round(adjusted)) if spec.kind == 'int' else adjusted
    return result
