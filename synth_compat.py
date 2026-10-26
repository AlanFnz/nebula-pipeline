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
    if identifier == 'tension':
        return copy.deepcopy(_tension_snapshot())
    if identifier == 'text-contact-film':
        return copy.deepcopy(_contact_film_snapshot())
    if identifier == 'text-contact-film-original':
        return copy.deepcopy(_contact_film_snapshot(1))
    if identifier == 'text-dark-print':
        return copy.deepcopy(_dark_print_snapshot())
    if identifier == 'text-reading-print':
        return copy.deepcopy(_reading_print_snapshot())
    if identifier == 'text-film-burn':
        return copy.deepcopy(_film_print_snapshot())
    if identifier == 'image-memory':
        return copy.deepcopy(_memory_snapshot())
    if identifier == 'chromatic-lattice':
        return copy.deepcopy(_lattice_snapshot())
    if identifier == 'color-film-die':
        return copy.deepcopy(_solid_snapshot())
    if identifier == 'color-film-die-original':
        return copy.deepcopy(_solid_snapshot(1))
    if identifier == 'prismatic-film-original':
        return copy.deepcopy(_prismatic_snapshot(1))
    if identifier == 'prismatic-film':
        return copy.deepcopy(_prismatic_snapshot())
    if identifier == 'text-liquid-words':
        return copy.deepcopy(_word_morph_snapshot())
    if identifier == 'text-liquid-words-original':
        return copy.deepcopy(_word_morph_snapshot(1))
    if identifier == 'text-liquid-words-soft':
        return copy.deepcopy(_word_morph_snapshot(2))
    if identifier == 'text-opium':
        return copy.deepcopy(_opium_snapshot())
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
def _dark_print_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-dark-print-v2.json').read_text())


@lru_cache(maxsize=1)
def _reading_print_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-reading-print-v2.json').read_text())


@lru_cache(maxsize=1)
def _film_print_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-film-burn-v1.json').read_text())


@lru_cache(maxsize=1)
def _memory_snapshot():
    return json.loads((Path(__file__).parent / 'presets/image-memory-v1.json').read_text())


@lru_cache(maxsize=1)
def _lattice_snapshot():
    return json.loads((Path(__file__).parent / 'presets/chromatic-lattice-v1.json').read_text())


@lru_cache(maxsize=2)
def _solid_snapshot(version=2):
    return json.loads((Path(__file__).parent / f'presets/color-film-die-v{version}.json').read_text())


@lru_cache(maxsize=3)
def _word_morph_snapshot(version=3):
    return json.loads((Path(__file__).parent / f'presets/text-liquid-words-v{version}.json').read_text())


@lru_cache(maxsize=2)
def _prismatic_snapshot(version=2):
    return json.loads((Path(__file__).parent / f'presets/prismatic-film-v{version}.json').read_text())


@lru_cache(maxsize=1)
def _opium_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-opium-v1.json').read_text())


@lru_cache(maxsize=1)
def _pressure_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-pressure-v2.json').read_text())


@lru_cache(maxsize=1)
def _transmission_snapshot():
    return json.loads((Path(__file__).parent / 'presets/text-transmission-v4.json').read_text())


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


@lru_cache(maxsize=2)
def _contact_film_snapshot(version=2):
    return json.loads((Path(__file__).parent / f'presets/text-contact-film-v{version}.json').read_text())


@lru_cache(maxsize=1)
def _tension_snapshot():
    return json.loads((Path(__file__).parent / 'presets/tension-v2.json').read_text())
