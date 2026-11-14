"""Color bindings for the existing 3D materials and their scene-specific channels."""
from synth_color_ui import ColorSpec, COLORS
from synth_blender_parts import PARTS
from synth_lattice_colors import LATTICE_COLORS


def color(key, label, *channels):
    return ColorSpec('blender_' + key, label, channels, 'blender_scene')


BLENDER_COLORS = (
    color('background', 'Background color', 'background_hue', 'background_saturation', 'background_light'),
    color('metal', 'Material color', 'metal_hue', 'metal_saturation', 'metal_light'),
    color('sky', 'Sky color', 'background_hue', 'background_saturation', 'sky_light'),
    color('ground', 'Ground color', 'ground_hue', 'ground_saturation', 'ground_light'),
    color('paint', 'Paint color', 'metal_hue', 'metal_saturation', 'paint_light'),
    color('accent', 'Accent color', 'accent_hue', 'accent_saturation', 'accent_light'),
    *(color('part_' + part, label + ' color', *(f'part_{part}_{c}' for c in ('hue', 'saturation', 'light')))
      for part, label, _ in PARTS),
)


def color_spec(key):
    return next(spec for spec in (*COLORS, *BLENDER_COLORS, *LATTICE_COLORS) if spec.key == key)


def scene_colors(params, part=None):
    if part:
        return () if params.get(f'part_{part}_inherit', 1) else ('blender_part_' + part,)
    painted = params.get('scene', 0) == 1 and params.get('orbital_finish', 0) == 0
    return (('blender_sky', 'blender_ground', 'blender_paint', 'blender_accent') if painted
            else ('blender_background', 'blender_metal'))
