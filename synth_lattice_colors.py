"""Palette swatches bound to the printed lattice's existing HSV channels."""
from synth_color_ui import ColorSpec

LATTICE_COLORS = tuple(
    ColorSpec('lattice_'+key, label, tuple(key+'_'+c for c in ('hue','saturation','light')), 'chromatic_lattice')
    for key,label in (('face_a','First cell color'), ('face_b','Second cell color'), ('paper','Background color'),
                      ('eye','Eye color'), ('eye_ink','Eye ink')))


def lattice_colors(params):
    if params.get('surface',0) != 1: return ()
    return tuple(s.key for s in LATTICE_COLORS[:5 if params.get('eye_enabled',0) else 3])
