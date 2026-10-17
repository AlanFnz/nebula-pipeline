"""Inspector presentation only; these annotations never change stored values."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterPresentation:
    unit: str = ''
    hue: bool = False


# Explicit paths avoid treating arbitrary angles, rates or normalized distances
# as physical units. In particular, separation.angle is a normalized direction.
SECONDS = frozenset({
    'image_memory.persistence', 'image_memory.period',
    'chromatic_lattice.period', 'chromatic_lattice.color_period',
    'prismatic_field.fold_period',
    'particles.period', 'particles.expand_seconds', 'particles.gather_seconds',
    'ink_bloom.period', 'ink_bloom.unfold_seconds', 'ink_bloom.unfolded_seconds',
    'ink_bloom.fold_seconds', 'ink_bloom.folded_seconds',
    'photocopy.period', 'subject_cutout.retention_seconds',
    'text.morph_hold', 'text.morph_seconds', 'contour_melt.period',
    'text.word_seconds', 'text.period', 'broadcast.period', 'broadcast.reverse_period',
    'broadcast.band_interval', 'broadcast.band_travel',
    'stretch_echo.period', 'signal_etch.period', 'signal_etch.pulse_seconds',
    'slice_echo.period', 'slice_echo.flash_period', 'slice_echo.flash_seconds',
})
DEGREES = frozenset({
    'image_memory.rotation', 'image_memory.drift_angle',
    'chromatic_lattice.rotation', 'chromatic_lattice.angle',
    'solid.yaw', 'solid.pitch', 'solid.roll',
    'prismatic_field.rotation',
    'slab.rotation', 'blinds.rotation', 'particles.yaw', 'particles.pitch',
    'silhouette.yaw', 'silhouette.pitch', 'silhouette.roll',
    'ink_bloom.shape_rotation', 'ink_bloom.rotation', 'ink_bloom.fan',
    'edge_phosphor.fade_angle', 'scan_modulation.fade_angle',
    'frame_jitter.rotation', 'print_surface.rotation_jitter',
    'photocopy.screen_angle', 'text.rotation', 'slice_echo.angle',
    'screen_mesh.angle', 'crt_capture.angle',
})
DEGREES_PER_SECOND = frozenset({'image_memory.spin', 'particles.rotation_speed', 'particles.orbit_speed', 'prismatic_field.rotation_speed', 'solid.turn_speed', 'solid.tumble_speed', 'solid.roll_speed'})
PIXELS = frozenset({'low_res.resolution'})
PERCENTAGES = frozenset({'image_memory.amplitude_x', 'image_memory.amplitude_y'})
HUES = frozenset({
    'signal_repetition.key_hue', 'signal_repetition.hue', 'signal_repetition.fringe_hue', 'signal_repetition.outside_hue',
    'particles.hue', 'edge_phosphor.hue', 'edge_phosphor.fringe_hue',
    'text.hue', 'text.back_hue', 'broadcast.hue', 'broadcast.reverse_hue',
    'broadcast.edge_hue', 'broadcast.halo_hue', 'stretch_echo.hue',
    'chroma_print.mid_hue', 'chroma_print.white_hue', 'chroma_print.warm_hue',
    'slice_echo.hue', 'scan_modulation.key_hue', 'scan_modulation.hue',
})


def presentation(path):
    from synth_instances import base_path
    from synth_intensity import PATHS
    if base_path(path) in PATHS.values() or path in PERCENTAGES: return ParameterPresentation(unit=' %')
    unit = ' s' if path in SECONDS else '°' if path in DEGREES else '°/s' if path in DEGREES_PER_SECOND else ' px' if path in PIXELS else ''
    return ParameterPresentation(unit=unit, hue=path in HUES)
