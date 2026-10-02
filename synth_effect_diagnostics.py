"""Presentation facts and conditional guidance; never infer stage luminance."""
from dataclasses import dataclass
from pathlib import Path
from synth_effects import EFFECT_BY_ID, merge_effects, state_values
from synth_sequence import resolve_sequence_frame


@dataclass(frozen=True)
class EffectExplanation:
    code: str
    scope: str
    evidence: str
    message: str
    target: str | None = None


def explain_effect(document, sequence, effect_id, seconds, section_id=None, resolved=None):
    effect = EFFECT_BY_ID[effect_id]
    local = next((s for s in document['sections'] if s['id'] == section_id), None)
    entries = merge_effects(document['effects'], local['effects']) if local else document['effects']
    entry = entries.get(effect_id, {})
    scope = 'selected section' if local else 'Whole clip'
    result = []
    def fact(code, message, target=None, evidence='resolved', where='At this frame'):
        if target and target not in effect.paths and target not in ('activation', 'resume', 'object', 'source'):
            raise ValueError('Explanation points to an unavailable control.')
        result.append(EffectExplanation(code, where, evidence, message, target))
    if entry.get('bypassed'):
        fact('bypassed', 'Bypassed. Your settings are retained.', 'resume', where='In this scope')
    elif entry.get('mode') == 'off':
        fact('off', f'Off in {scope}.', 'activation', where='In this scope')
    if 'footage' in document and not Path(document['footage']['path']).is_file():
        fact('missing-media', 'Source video is missing.', 'source')
        return tuple(result)
    _, _, _, _, _, transition, amount, base = resolved or resolve_sequence_frame(sequence, seconds)
    values = {f"{m['id']}.{k}": v for m in base['modules'] for k, v in m['params'].items()}
    enabled = {m['id'] for m in base['modules'] if m['enabled']}
    p = lambda path: values[path]
    relevant = effect.modules
    active = any(m in enabled for m in relevant)
    if effect_id == 'ghosts': active = 'smear' in enabled or ('slab' in enabled and p('slab.ghost_opacity') > 0)
    if effect_id == 'cloud': active = 'slab' in enabled
    if not active:
        message = f'Inactive at {seconds:.2f}s; its resolved modules are disabled.'
        if effect_id == 'cloud': message = 'Granular halo needs Luminous forms at this frame.'
        fact('dependency' if effect_id == 'cloud' else 'disabled', message, 'object' if effect_id == 'cloud' else 'activation')
        return tuple(result)
    zero = None
    if effect_id == 'edge_phosphor' and p('edge_phosphor.mix') == 0: zero = 'edge_phosphor.mix'
    elif effect_id == 'bloom' and p('bloom.strength') == 0: zero = 'bloom.strength'
    elif effect_id == 'cloud' and p('slab.cloud_strength') == 0: zero = 'slab.cloud_strength'
    elif effect_id == 'tape':
        if p('tape.mix') == 0: zero = 'tape.mix'
        elif all(p('tape.'+k) == 0 for k in ('tracking','jitter','dropouts','chroma_delay','bleed','head_switch')): zero = 'tape.tracking'
    elif effect_id == 'frame_jitter':
        if p('frame_jitter.strength') == 0: zero = 'frame_jitter.strength'
        elif all(p('frame_jitter.'+k) == 0 for k in ('x','y','rotation','scale')): zero = 'frame_jitter.x'
    elif effect_id == 'scan_drag':
        if p('scan_drag.mix') == 0: zero = 'scan_drag.mix'
        elif p('scan_drag.window') == 1 and all(p('scan_drag.'+k)==0 for k in ('amount','jitter','tearing','overload')): zero = 'scan_drag.amount'
    elif effect_id == 'ghosts':
        smear = 'smear' in enabled and p('smear.amount') > 0 and p('smear.opacity') > 0
        companion = 'slab' in enabled and p('slab.ghost_opacity') > 0
        if not smear and not companion: zero = 'smear.amount'
    if zero:
        fact('zero', f'{effect.label} has zero contributing strength at this frame.', zero)
    elif not result:
        fact('configured', f'{effect.label} is configured at {seconds:.2f}s. Visibility depends on the source and other treatments.')
    threshold = {'bloom':'bloom.threshold', 'edge_phosphor':'edge_phosphor.threshold', 'scan_drag':'scan_drag.threshold'}.get(effect_id)
    # Edge phosphor has no threshold path: retain description rather than inventing one.
    if threshold in effect.paths:
        fact('brightness-guidance', 'This treatment needs bright source areas. Threshold controls which areas contribute.', threshold, 'guidance')
    elif effect_id == 'edge_phosphor':
        fact('capability', effect.description, evidence='guidance')
    if transition != 'cut' and amount < 1:
        fact('transition', 'An authored transition also contributes at this frame.', evidence='resolved')
    return tuple(result)
