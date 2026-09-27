"""Object selection expressed through existing source-effect overrides."""
from __future__ import annotations

from synth_composition import compile_composition, normalize_composition
from synth_effects import describe_effects, effect_preset, state_values
from synth_shared_timing import without_timing


SUBJECTS = {
    'signal': ('Geometric signal', ('forms', 'rays')),
    'ink': ('Ink stamps', ('ink_bloom',)),
    'particles': ('Particle model', ('particles',)),
    'none': ('No object', ()),
}
SOURCE_EFFECTS = ('forms', 'rays', 'ink_bloom', 'particles')


def active_subjects(summary):
    # A head with intermittent ray accents is primarily a particle object.
    return tuple(kind for kind in ('ink', 'particles', 'signal')
                 if any(summary[key]['active'] for key in SUBJECTS[kind][1]))


def scope_states(project, index=None):
    states = compile_composition(project)['states']
    prefix = project['sections'][index]['id'] + ':' if index is not None else ''
    return [state for name, state in states.items() if name.startswith(prefix)]


def _follow_sources(effects):
    for key in SOURCE_EFFECTS:
        if key in effects:
            effects[key]['mode'] = 'recipe'
            if not effects[key]['params']:
                del effects[key]


def restore_subject(project, index=None):
    result = normalize_composition(project)
    target = result if index is None else result['sections'][index]
    _follow_sources(target['effects'])
    if index is None:
        for section in result['sections']:
            _follow_sources(section['effects'])
    return result


def select_subject(project, kind, index=None):
    """Replace source families in the scope, retaining treatments and timing.

    Restoring an authored family follows its original on/off choreography.
    Parameter edits survive switching away and back. No document schema changes
    are needed: the normal compiler, history and detailed export own the result.
    """
    if kind not in SUBJECTS:
        raise ValueError('Unknown object type')
    result = restore_subject(project, index)
    baseline = describe_effects(scope_states(result, index))
    target = result if index is None else result['sections'][index]
    effects = target['effects']
    selected = SUBJECTS[kind][1]
    source_enabled = set().union(*(state_values(state)[1] for state in result['source']['states'].values()))
    for key in SOURCE_EFFECTS:
        entry = effects.setdefault(key, {'mode': 'recipe', 'params': {}})
        if key not in selected:
            entry['mode'] = 'off'
            continue
        if any(baseline[item]['active'] for item in selected):
            continue
        # A newly introduced geometric object starts as one solid form.
        if key == 'rays':
            continue
        entry['mode'] = 'on'
        module = {'forms': 'slab', 'ink_bloom': 'ink_bloom', 'particles': 'particles'}[key]
        configured = bool(entry['params'] or (index is not None and result['effects'].get(key, {}).get('params')))
        if module not in source_enabled and not configured and key != 'forms':
            initial = without_timing(effect_preset(key))
            if key == 'particles':
                initial['params'].update({'particles.attractor': 4, 'particles.occlusion': 1.,
                                          'particles.xray': 0., 'particles.neck_fade': .42})
            entry['params'].update(initial['params'])
    return normalize_composition(result)
