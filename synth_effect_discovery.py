"""Validated, scoped effect edits shared by temporary auditions and Apply."""
import copy
import hashlib
import json

from synth_composition import compile_composition, normalize_composition
from synth_creative import CREATIVE_CONTROLS
from synth_effect_catalog import SOURCE_EFFECT_IDS
from synth_effects import EFFECT_BY_ID, effect_preset, is_removed_effect
from synth_exploration import comparison_problem
from synth_video import VIDEO_EFFECTS


def document_fingerprint(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def preset_entry(effect_id, preset, previous=None, parent=None, local=False):
    """The established replacement semantics, including inherited bypass."""
    effect = EFFECT_BY_ID.get(effect_id)
    if effect is None or type(preset) is not int or not 0 <= preset < max(1, len(effect.looks)):
        raise ValueError('Choose an available effect preset.')
    entry = effect_preset(effect_id, preset)
    previous, parent = previous or {}, parent or {}
    if 'bypassed' in previous:
        entry['bypassed'] = previous['bypassed']
    if local and 'creative' in parent:
        entry['creative'] = {'version': 1, 'values': {spec.key: spec.neutral for spec in CREATIVE_CONTROLS.get(effect_id, ())}}
    return entry


def effect_candidate(document, section_id, effect_id, operation='add', preset=0):
    """Return a complete normalized candidate without modifying the original.

    A stable section ID freezes the edit target; None targets the whole clip.
    All unrelated fields (including snapshots) are retained.
    """
    original = normalize_composition(document)
    if effect_id not in EFFECT_BY_ID or effect_id in SOURCE_EFFECT_IDS:
        raise ValueError('Choose an image treatment, not an Object source.')
    allowed = VIDEO_EFFECTS if 'footage' in original else tuple(e for e in EFFECT_BY_ID if e != 'subject_cutout')
    if effect_id not in allowed:
        raise ValueError('This treatment is unavailable for the current source.')
    if operation not in ('add', 'replace', 'without'):
        raise ValueError('Unknown effect operation.')
    result = copy.deepcopy(original)
    target = result if section_id is None else next((s for s in result['sections'] if s['id'] == section_id), None)
    if target is None:
        raise ValueError('The selected section no longer exists. Open a fresh preview.')
    previous = target['effects'].get(effect_id, {})
    parent = result['effects'].get(effect_id, {}) if section_id is not None else {}
    if operation == 'without':
        entry = copy.deepcopy(previous or {'mode': 'recipe', 'params': {}})
        entry['bypassed'] = True
    else:
        if operation == 'add' and ((previous and not is_removed_effect(previous)) or
                                   (parent and not is_removed_effect(parent) and not is_removed_effect(previous))):
            raise ValueError('This effect is already authored. Inspect it to keep its settings.')
        entry = preset_entry(effect_id, preset, previous, parent, section_id is not None)
    target['effects'][effect_id] = entry
    result = normalize_composition(result)
    problem = comparison_problem(compile_composition(original), compile_composition(result))
    if problem:
        raise ValueError(problem)
    # Comparing the complete document after removing the sole permitted edit
    # also guards source identity, seed, timing and the snapshot library.
    check = copy.deepcopy(result)
    checked_target = check if section_id is None else next(s for s in check['sections'] if s['id'] == section_id)
    if effect_id in (original if section_id is None else next(s for s in original['sections'] if s['id'] == section_id))['effects']:
        checked_target['effects'][effect_id] = copy.deepcopy(previous)
    else:
        checked_target['effects'].pop(effect_id)
    if check != original:
        raise ValueError('An effect candidate changed unrelated composition settings.')
    return result
