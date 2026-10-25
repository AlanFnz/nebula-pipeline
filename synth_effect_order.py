"""Explicit image-pass order; serialized module slots remain seed identities.

No order field means the original study renderer. A custom order renders the
objects first, then image passes from top to bottom. Source-only controls and
working resolution retain their original jobs rather than becoming fake layers.
"""
from synth_instances import base_id

SOURCES = frozenset(('slab', 'blinds', 'particles', 'silhouette', 'ink_bloom',
    'text', 'radial_bloom', 'prismatic_field', 'solid', 'chromatic_lattice', 'image_memory'))
SOURCE_PASSES = ('optical_print', 'print_collage', 'chroma_print', 'slice_echo',
                 'contour_melt', 'stretch_echo', 'signal_etch', 'scan_modulation', 'signal_repetition')
FIXED = {
    'color_field': 'Source background · stays behind generated objects.',
    'cloud': 'Source detail · the halo is part of Luminous forms.',
    'subject_cutout': 'Source preparation · isolates footage before image effects.',
    'low_res': 'Output resolution · sets the working resolution for the whole image.',
}
ALIASES = {'smear': 'ghosts', 'warp': 'drift'}


def movable(identifier):
    from synth_effects import EFFECT_BY_ID
    effect = EFFECT_BY_ID.get(identifier)
    return bool(effect and identifier not in FIXED and effect.modules and
                all(base_id(module) not in SOURCES for module in effect.modules))


def normalize_order(raw):
    if not isinstance(raw, list) or len(raw) > 128:
        raise ValueError('Effect order must be a list of image effects')
    if any(not isinstance(key, str) or not movable(key) for key in raw):
        raise ValueError('Only movable image effects can appear in effect order')
    if len(raw) != len(set(raw)):
        raise ValueError('Effect order cannot contain duplicate identities')
    return list(raw)


def legacy_order(preset):
    """Actual image-pass sequence, including disabled slots for future edits."""
    modules = preset['modules']
    # Text and the newer generators run before the loop, irrespective of slots.
    boundary = max((i for i, m in enumerate(modules) if m.get('enabled', True)
                    and m['id'] in {'slab', 'blinds', 'particles', 'silhouette', 'ink_bloom', 'flare'}), default=-1) + 1
    order = []
    for index in range(len(modules) + 1):
        if index == boundary: order.extend(SOURCE_PASSES)
        if index == len(modules): break
        key = ALIASES.get(modules[index]['id'], modules[index]['id'])
        if key not in SOURCE_PASSES and movable(key): order.append(key)
    return list(dict.fromkeys(order))


def resolved_order(preset):
    default = legacy_order(preset)
    custom = preset.get('effect_order', ())
    return list(custom) + [key for key in default if key not in custom]


def order_for_states(states, custom=None):
    from synth import curated_presets
    from synth_effects import state_values
    from synth_instances import state_instance_ids
    states = list(states)
    if not states: return []
    preset = dict(curated_presets()[states[0]['preset']])
    enabled = set().union(*(state_values(state)[1] for state in states))
    preset['modules'] = [dict(m, enabled=m['id'] in enabled) for m in preset['modules']]
    instances = sorted(set().union(*(state_instance_ids(state) for state in states)))
    preset['modules'].extend(dict(id=key, enabled=key in enabled) for key in instances)
    if custom: preset['effect_order'] = custom
    return resolved_order(preset)


def move_before(order, identifier, before=None):
    if identifier not in order or before == identifier or (before is not None and before not in order):
        return list(order)
    result = [key for key in order if key != identifier]
    result.insert(result.index(before) if before else len(result), identifier)
    return result
