"""One composition-wide ink clock, separate from section appearance effects."""
from __future__ import annotations

import copy
import math

from synth import MODULE_BY_ID, curated_presets, normalize_synth
from synth_effects import apply_effects, merge_effects, state_values
from synth_ink_timing import TIMING_KEYS, stage_durations


TIMING_PATHS = tuple(f'ink_bloom.{key}' for key in TIMING_KEYS)
PROFILE_PATHS = (*TIMING_PATHS, 'ink_bloom.clock_scale')


def without_timing(entry):
    result = copy.deepcopy(entry)
    result['params'] = {key: value for key, value in result['params'].items() if key not in PROFILE_PATHS}
    return result


def _has_timing(effects):
    return any(path in effects.get('ink_bloom', {}).get('params', {}) for path in TIMING_PATHS)


def _timing_effects(project, section):
    """Bypass hides a source without replacing its authored clock profile."""
    effects = merge_effects(project['effects'], section['effects'])
    if 'ink_bloom' in effects:
        effects['ink_bloom'].pop('bypassed', None)
    return effects


def _profile(project, preferred_section=None, include_edits=True):
    """Use the first relevant ink state as the common motion path."""
    sections = project['sections']
    ordered = [preferred_section] if preferred_section is not None else []
    ordered += [s for s in sections if s is not preferred_section]
    source = project['source']
    for section in ordered:
        phrase = project['phrases'][section['phrase']]
        active = next((cue for cue in reversed(source['cues']) if cue['time'] <= phrase['start']), source['cues'][0])
        cues = [active, *(cue for cue in source['cues'] if phrase['start'] < cue['time'] < phrase['end'])]
        effects = _timing_effects(project, section)
        if not include_edits and 'ink_bloom' in effects:
            effects['ink_bloom'] = without_timing(effects['ink_bloom'])
        for cue in cues:
            state = apply_effects(source['states'][cue['state']], effects)
            values, enabled = state_values(state)
            if 'ink_bloom' not in enabled:
                continue
            params = {path.removeprefix('ink_bloom.'): value for path, value in values.items() if path.startswith('ink_bloom.')}
            profile = {f'ink_bloom.{key}': params[key] for key in TIMING_KEYS}
            profile.update({f'ink_bloom.{key}': value for key, value in stage_durations(params).items()})
            profile['ink_bloom.clock_scale'] = params['clock_scale'] if params['clock_mode'] else values.get('speed', curated_presets()[state['preset']]['speed'])
            return profile
    defaults = {spec.key: spec.default for spec in MODULE_BY_ID['ink_bloom'].params}
    return {**{f'ink_bloom.{key}': defaults[key] for key in TIMING_KEYS},
            **{f'ink_bloom.{key}': value for key, value in stage_durations(defaults).items()},
            'ink_bloom.clock_scale': 1.}


def normalize_shared_timing(project):
    """Migrate explicit timing overrides; untouched recipes keep their pixels.

    Existing whole-clip edits take precedence. Otherwise the first section with
    custom timing supplies one profile. The embedded source is never rewritten.
    """
    raw = project.get('ink_timing', {})
    migrating = not raw
    if not isinstance(raw, dict) or any(path not in PROFILE_PATHS for path in raw):
        raise ValueError('Unknown shared ink timing setting')
    if raw:
        checked = normalize_synth({'modules': [{'id': 'ink_bloom', 'params': {path.split('.')[1]: value for path, value in raw.items()}}]})
        values = checked['modules'][0]['params']
        profile = _profile(project, include_edits=False)
        profile.update({path: values[path.split('.')[1]] for path in raw})
    else:
        global_edits = _has_timing(project['effects'])
        section = next((s for s in project['sections'] if _has_timing(s['effects'])), None)
        if not global_edits and section is None:
            project['ink_timing'] = {}
            return
        if global_edits:
            # Old section overrides cannot defeat an existing whole-clip edit.
            for s in project['sections']:
                if 'ink_bloom' in s['effects']:
                    s['effects']['ink_bloom'] = without_timing(s['effects']['ink_bloom'])
        profile = _profile(project, preferred_section=None if global_edits else section)
    for effects in [project['effects'], *(s['effects'] for s in project['sections'])]:
        if 'ink_bloom' in effects:
            effects['ink_bloom'] = without_timing(effects['ink_bloom'])
            if effects['ink_bloom'] == {'mode': 'recipe', 'params': {}}:
                del effects['ink_bloom']
    # Resolve inherited stages once, so they cannot vary with a section's recipe.
    params = {path.split('.')[1]: value for path, value in profile.items()}
    profile.update({f'ink_bloom.{key}': value for key, value in stage_durations(params).items()})
    if migrating:
        retime_cycle_sections(project, _profile(project, include_edits=False), profile)
    project['ink_timing'] = profile


def edit_shared_timing(project, path, value):
    """Edit/reset one shared value on an already normalized composition copy."""
    if path not in TIMING_PATHS:
        raise ValueError('Unknown ink timing control')
    profile = copy.deepcopy(project['ink_timing'] or _profile(project, include_edits=False))
    previous = copy.deepcopy(profile)
    profile[path] = _profile(project, include_edits=False)[path] if value is None else value
    retime_cycle_sections(project, previous, profile)
    project['ink_timing'] = profile


def _loop_seconds(profile):
    params = {path.split('.')[1]: value for path, value in profile.items()}
    speed = params['motion_speed'] * params['clock_scale']
    return sum(stage_durations(params).values()) / speed if speed else float('inf')


def retime_cycle_sections(project, previous, profile):
    """Keep existing whole-cycle ink sections aligned on the export frame grid.

    Infer the cycle count instead of forcing arbitrary edited timelines into
    loops. Round cumulative boundaries so rounding errors cannot accumulate.
    """
    old_loop, new_loop = _loop_seconds(previous), _loop_seconds(profile)
    if not all(math.isfinite(value) and value > 0 for value in (old_loop, new_loop)):
        return
    fps = project['fps']; counts = []
    source = project['source']
    for section in project['sections']:
        count = round(section['duration'] / old_loop)
        if count < 1 or abs(section['duration'] - count * old_loop) > 1 / fps + 1e-8:
            return
        phrase = project['phrases'][section['phrase']]
        if any(phrase['start'] < cue['time'] < phrase['end'] for cue in source['cues']):
            return
        cue = next((cue for cue in reversed(source['cues']) if cue['time'] <= phrase['start']), source['cues'][0])
        state = apply_effects(source['states'][cue['state']], _timing_effects(project, section))
        if 'ink_bloom' not in state_values(state)[1]:
            return
        counts.append(count)
    frames = []; cycles = 0; previous_frame = 0
    for count in counts:
        cycles += count
        boundary = round(cycles * new_loop * fps)
        frames.append(boundary - previous_frame); previous_frame = boundary
    if previous_frame > 3600 * fps or any(frame < 1 or frame > 300 * fps for frame in frames):
        return
    for section, frame in zip(project['sections'], frames): section['duration'] = frame / fps


def restore_shared_timing(project):
    if project['ink_timing']:
        retime_cycle_sections(project, project['ink_timing'], _profile(project, include_edits=False))
    project['ink_timing'] = {}


def apply_shared_timing(state, profile):
    if profile:
        state.setdefault('overrides', {}).update(profile)
        state['overrides']['ink_bloom.clock_mode'] = 1
    return state
