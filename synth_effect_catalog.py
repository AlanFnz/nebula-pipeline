"""Presentation-only discovery metadata for image treatments."""
from __future__ import annotations

from dataclasses import dataclass

from synth_effects import EFFECTS


SOURCE_EFFECT_IDS = frozenset(('forms', 'rays', 'ink_bloom', 'particles', 'silhouette', 'text'))
CATEGORIES = ('Distortion', 'Texture', 'Light & color', 'Motion & echoes', 'Cutout', 'Finishing', 'Other')
EFFECT_CATEGORIES = {
    'scan_modulation': 'Distortion',
    'crt_capture': 'Texture',
    'stretch_echo': 'Motion & echoes',
    'signal_etch': 'Texture',
    'chroma_print': 'Light & color',
    'slice_echo': 'Motion & echoes',
    'screen_mesh': 'Texture',
    'broadcast': 'Distortion',
    'subject_cutout': 'Cutout',
    'photocopy': 'Texture',
    'signal_background': 'Texture',
    'edge_phosphor': 'Light & color',
    'scan_drag': 'Motion & echoes',
    'ghosts': 'Motion & echoes',
    'breakup': 'Distortion',
    'tape': 'Distortion',
    'drift': 'Distortion',
    'cloud': 'Light & color',
    'flare': 'Light & color',
    'separation': 'Light & color',
    'interference': 'Distortion',
    'frame_jitter': 'Motion & echoes',
    'bloom': 'Light & color',
    'raster': 'Texture',
    'print_surface': 'Texture',
    'low_res': 'Finishing',
}


@dataclass(frozen=True)
class CatalogEffect:
    id: str
    label: str
    category: str
    description: str
    presets: tuple[str, ...]


EFFECT_CATALOG = tuple(sorted((
    CatalogEffect(effect.id, effect.label, EFFECT_CATEGORIES.get(effect.id, 'Other'), effect.description,
                  tuple(label for label, _values in effect.looks) or ('Default settings',))
    for effect in EFFECTS if effect.id not in SOURCE_EFFECT_IDS
), key=lambda effect: effect.label.casefold()))


def effect_catalog(allowed_effects=None, *, query='', category=''):
    """Search names, descriptions, categories and existing preset labels.

    The caller supplies compatibility for the current document. None leaves
    compatibility unrestricted; an empty collection permits no treatments.
    Returned metadata contains no mutable renderer settings.
    """
    allowed = None if allowed_effects is None else frozenset(allowed_effects)
    words = query.casefold().split()
    result = []
    for effect in EFFECT_CATALOG:
        if allowed is not None and effect.id not in allowed:
            continue
        if category and effect.category != category:
            continue
        searchable = ' '.join((effect.id.replace('_', ' '), effect.label, effect.category,
                               effect.description, *effect.presets)).casefold()
        if all(word in searchable for word in words):
            result.append(effect)
    return tuple(result)
