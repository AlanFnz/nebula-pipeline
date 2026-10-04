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

# Capability sentences, separate from frozen recipes and measured visibility.
CONTRIBUTIONS = {
    'forms': 'Luminous forms provide the geometric source.',
    'rays': 'Rays provide a striped light source.',
    'text': 'Text provides the lettering.',
    'silhouette': 'Model silhouette provides the head.',
    'ink_bloom': 'Ink bloom provides overlapping stamps.',
    'particles': 'Particles provide the moving point source.',
    'edge_phosphor': 'Edge phosphor creates a colored contour.',
    'scan_drag': 'Scan drag pulls highlights into streaks.',
    'signal_background': 'Signal background textures dark areas.',
    'ghosts': 'Ghosts add shifted copies and a luminous companion.',
    'cloud': 'Granular halo surrounds luminous forms with noise.',
    'tape': 'Tape damage resamples the picture with horizontal pull, tracking faults and color bleed.',
    'frame_jitter': 'Frame jitter varies the source registration.',
    'bloom': 'Bloom spreads light from bright source areas.',
}


def contribution_sentence(effect_id):
    from synth_effects import EFFECT_BY_ID
    return CONTRIBUTIONS.get(effect_id, EFFECT_BY_ID[effect_id].description.split('. ')[0].rstrip('.') + '.')


def composition_contributions(summary, entries, parent_entries, video=False):
    """Follow the current scope, including authored off and bypassed entries."""
    ids = [effect.id for effect in EFFECTS if summary[effect.id]['active'] or effect.id in entries or effect.id in parent_entries]
    return tuple((identifier, contribution_sentence(identifier), identifier in SOURCE_EFFECT_IDS) for identifier in ids)
