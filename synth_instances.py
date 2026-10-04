"""Stable identities for additional image passes, without altering legacy slots.

Only Tape damage is currently repeatable. New passes run in creation order
after the established image chain; the original module order/seeds stay intact.
"""
from collections.abc import Mapping
from dataclasses import replace
import re

REPEATABLE = frozenset({'tape'})
MAX_INSTANCES = 64


def instance_base(identifier):
    if not isinstance(identifier, str) or '@' not in identifier: return None
    match = re.fullmatch(r'(tape)@([2-9]|[1-5][0-9]|6[0-4])', identifier)
    return match[1] if match else None


def base_id(identifier):
    return instance_base(identifier) or identifier


def base_path(path):
    module, key = path.split('.', 1)
    return base_id(module) + '.' + key


def instance_ids(keys):
    return sorted({key for key in keys if instance_base(key)}, key=lambda key: int(key.split('@')[1]))


def state_instance_ids(state):
    return instance_ids([*state.get('enabled', ()), *(p.split('.')[0] for p in state.get('overrides', {}) if '@' in p)])


def document_instance_ids(document):
    keys = list(document.get('effects', {}))
    for section in document.get('sections', ()):
        keys.extend(section.get('effects', {}))
        keys.extend(e['path'].split('.')[0] for e in section.get('automations', ()))
    for state in document.get('source', document).get('states', {}).values():
        keys.extend(state_instance_ids(state))
    return instance_ids(keys)


class InstanceRegistry(Mapping):
    """Resolve aliases on demand. Iteration remains the unchanged base catalog."""
    def __init__(self, definitions, *, effects=False):
        self.definitions = definitions
        self.effects = effects

    def __iter__(self): return iter(self.definitions)
    def __len__(self): return len(self.definitions)

    def __getitem__(self, key):
        if key in self.definitions: return self.definitions[key]
        base = instance_base(key)
        if base is None: raise KeyError(key)
        original = self.definitions[base]
        changes = dict(id=key, label=f'{original.label} · {key.split("@")[1]}')
        if self.effects:
            remap = lambda path: key + path[len(base):]
            changes.update(paths=tuple(map(remap, original.paths)), modules=(key,),
                           looks=tuple((label, {remap(p): v for p, v in values.items()}) for label, values in original.looks),
                           description=original.description + ' Independent pass after the existing image effects. Each pass has its own settings and automation.')
        return replace(original, **changes)
