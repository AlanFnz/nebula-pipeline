"""Portable composition snapshots and deterministic, effect-scoped auditions."""
import copy
from datetime import datetime, timezone
import random
import uuid

from synth_creative import CREATIVE_CONTROLS

MAX_SNAPSHOTS = 32
VARIATION_AMOUNTS = {'subtle': .10, 'moderate': .25, 'strong': .50}
TIMING_CONTROLS = {'cadence', 'outward', 'return'}


def content(document):
    """A complete artistic document without its snapshot library."""
    return copy.deepcopy({key: value for key, value in document.items() if key != 'snapshots'})


def normalize_snapshots(raw):
    from synth_composition import normalize_composition
    if not isinstance(raw, list) or len(raw) > MAX_SNAPSHOTS:
        raise ValueError(f'Use at most {MAX_SNAPSHOTS} snapshots')
    result = []; identifiers = set()
    for item in raw:
        if not isinstance(item, dict) or type(item.get('version')) is not int or item['version'] != 1:
            raise ValueError('Unsupported snapshot version')
        identifier, name, stamp = item.get('id'), item.get('name'), item.get('created_at')
        if not isinstance(identifier, str) or not identifier or len(identifier) > 64 or identifier in identifiers:
            raise ValueError('Snapshot identifiers must be unique')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError('Use a snapshot name between 1 and 80 characters')
        try:
            date = datetime.fromisoformat(stamp)
            if date.tzinfo is None: raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('Snapshot date must include its timezone') from None
        document = item.get('document')
        if not isinstance(document, dict) or 'snapshots' in document:
            raise ValueError('Snapshot documents cannot contain a snapshot library')
        result.append(dict(version=1, id=identifier, name=name.strip(), created_at=stamp,
                           document=normalize_composition(document)))
        identifiers.add(identifier)
    return result


def capture_snapshot(project, name):
    from synth_composition import normalize_composition
    result = normalize_composition(project)
    if len(result.get('snapshots', [])) >= MAX_SNAPSHOTS:
        raise ValueError(f'The library has {MAX_SNAPSHOTS} snapshots. Remove one before capturing another.')
    item = dict(version=1, id=uuid.uuid4().hex, name=name,
                created_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), document=content(result))
    result.setdefault('snapshots', []).append(item)
    return normalize_composition(result), item['id']


def snapshot_by_id(project, identifier):
    item = next((item for item in project.get('snapshots', []) if item['id'] == identifier), None)
    if item is None: raise ValueError('This snapshot is no longer available')
    return item


def restore_snapshot(project, identifier):
    from synth_composition import normalize_composition
    result = content(snapshot_by_id(project, identifier)['document'])
    if project.get('snapshots'): result['snapshots'] = copy.deepcopy(project['snapshots'])
    return normalize_composition(result)


def remove_snapshot(project, identifier):
    result = copy.deepcopy(project); snapshot_by_id(result, identifier)
    result['snapshots'] = [item for item in result['snapshots'] if item['id'] != identifier]
    if not result['snapshots']: result.pop('snapshots')
    return result


def comparison_problem(first, second):
    """Compare rendered sequences only when frame coordinates mean the same thing."""
    if first['canvas'] != second['canvas']: return 'The canvas or framing differs. Restore the snapshot to use its canvas.'
    if first['fps'] != second['fps']: return 'Timeline FPS differs. Restore the snapshot to use its frame rate.'
    if first['duration'] != second['duration'] or first.get('time_map') != second.get('time_map'):
        return 'Timeline duration or source/effect clocks differ. Restore the snapshot to use its timing.'
    return ''


def vary_effect(project, effect_id, amount, keys, seed, section_id=None):
    """Change only selected creative adjustments; keep noise seed and source intact.

    Every audition starts from its captured base, so Try again does not accumulate
    random edits. The values and exploration seed travel with the saved effect.
    """
    from synth_composition import normalize_composition
    controls = {spec.key: spec for spec in CREATIVE_CONTROLS.get(effect_id, ())}
    if amount not in VARIATION_AMOUNTS or not keys or set(keys) - controls.keys():
        raise ValueError('Choose supported creative controls and a variation amount')
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**31:
        raise ValueError('Invalid exploration seed')
    result = normalize_composition(project)
    target = result
    if section_id is not None:
        target = next((section for section in result['sections'] if section['id'] == section_id), None)
        if target is None: raise ValueError('The selected section no longer exists')
    parent = result['effects'].get(effect_id, {}) if section_id else {}
    entry = target['effects'].setdefault(effect_id, {'mode': 'recipe', 'params': {}})
    inherited = parent.get('creative', {}).get('values', {})
    creative = entry.setdefault('creative', {'version': 1, 'values': {}})
    rng = random.Random(seed); span = VARIATION_AMOUNTS[amount]
    for key in sorted(set(keys)):
        spec = controls[key]; original = creative['values'].get(key, inherited.get(key, spec.neutral))
        delta = rng.choice((-1, 1)) * rng.uniform(span * .4, span)
        if spec.operation == 'offset': delta = (1 if delta > 0 else -1) * {'subtle': 1, 'moderate': 2, 'strong': 4}[amount]
        adjusted = max(spec.minimum, min(spec.maximum, original + delta))
        if adjusted == original: adjusted = max(spec.minimum, min(spec.maximum, original - delta))
        creative['values'][key] = int(adjusted) if spec.operation == 'offset' else round(adjusted, 4)
    creative['variation'] = dict(seed=seed, amount=amount, controls=sorted(set(keys)))
    return normalize_composition(result)
