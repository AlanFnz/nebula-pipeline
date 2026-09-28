"""Frozen recipe/default data and explicit rendering-contract selection.

Unversioned files use v1. New operations opt into v2; original files are never
rewritten on load. The v1 phosphor implementation lives in synth_profile_v1.
Other operations retain their original algorithms, guarded by the v1 manifest.
Future algorithm changes must retain a versioned implementation before dispatch
is updated. Storage schema and rendering versions are deliberately independent.
"""
import copy
from functools import lru_cache
import json
from pathlib import Path

CURRENT_RENDER_VERSION = 2


@lru_cache(maxsize=1)
def _snapshot():
    return json.loads((Path(__file__).parent / 'presets/compat-v1.json').read_text())


def frozen_data(key):
    return copy.deepcopy(_snapshot()[key])


def starter_snapshot(identifier):
    if identifier == 'text-pressure':
        return copy.deepcopy(_pressure_snapshot())
    if identifier == 'text-transmission':
        return copy.deepcopy(_transmission_snapshot())
    if identifier.startswith('text-') and identifier.endswith('-original'):
        return copy.deepcopy(_text_snapshot()[identifier.removesuffix('-original')])
    if identifier.startswith('text-'):
        return copy.deepcopy(_refined_text_snapshot()[identifier])
    if identifier in ('profile-clear', 'profile-doryphoros'):
        return copy.deepcopy(_profile_snapshot()[identifier])
    return copy.deepcopy(_snapshot()['starters'][identifier])


@lru_cache(maxsize=1)
def _pressure_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-pressure-v2.json').read_text())


@lru_cache(maxsize=1)
def _transmission_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-transmission-v3.json').read_text())


@lru_cache(maxsize=1)
def _text_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-studies-v1.json').read_text())


@lru_cache(maxsize=1)
def _refined_text_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-studies-v2.json').read_text())


@lru_cache(maxsize=1)
def _profile_snapshot():
    return json.loads((Path(__file__).parent / 'presets/compat-profiles-v2.json').read_text())


def render_version(raw):
    value = raw.get('render_version', 1)
    if isinstance(value, bool) or not isinstance(value, int) or value not in (1, 2):
        raise ValueError(f'Unsupported render version: {value}')
    return value


def frozen_defaults(module):
    for entry in _snapshot()['default']['modules']:
        if entry['id'] == module:
            return copy.deepcopy(entry['params'])
    return {}
