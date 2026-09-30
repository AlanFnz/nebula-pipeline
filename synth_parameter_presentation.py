"""Inspector presentation only; these annotations never change stored values."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterPresentation:
    unit: str = ''
    hue: bool = False


# Explicit paths avoid treating arbitrary angles, rates or normalized distances
# as physical units. In particular, separation.angle is a normalized direction.
SECONDS = frozenset({
    'particles.period', 'particles.expand_seconds', 'particles.gather_seconds',
    'ink_bloom.period', 'ink_bloom.unfold_seconds', 'ink_bloom.unfolded_seconds',
    'ink_bloom.fold_seconds', 'ink_bloom.folded_seconds',
    'photocopy.period', 'subject_cutout.retention_seconds',
    'text.word_seconds', 'text.period', 'broadcast.period', 'broadcast.reverse_period',
    'stretch_echo.period', 'signal_etch.period', 'signal_etch.pulse_seconds',
    'slice_echo.period', 'slice_echo.flash_period', 'slice_echo.flash_seconds',
})
DEGREES = frozenset({
    'slab.rotation', 'blinds.rotation', 'particles.yaw', 'particles.pitch',
    'silhouette.yaw', 'silhouette.pitch', 'silhouette.roll',
    'ink_bloom.shape_rotation', 'ink_bloom.rotation', 'ink_bloom.fan',
    'edge_phosphor.fade_angle', 'scan_modulation.fade_angle',
    'frame_jitter.rotation', 'print_surface.rotation_jitter',
    'photocopy.screen_angle', 'text.rotation', 'slice_echo.angle',
    'screen_mesh.angle', 'crt_capture.angle',
})
DEGREES_PER_SECOND = frozenset({'particles.rotation_speed', 'particles.orbit_speed'})
PIXELS = frozenset({'low_res.resolution'})
HUES = frozenset({
    'particles.hue', 'edge_phosphor.hue', 'edge_phosphor.fringe_hue',
    'text.hue', 'text.back_hue', 'broadcast.hue', 'broadcast.reverse_hue',
    'broadcast.edge_hue', 'broadcast.halo_hue', 'stretch_echo.hue',
    'chroma_print.mid_hue', 'chroma_print.white_hue', 'chroma_print.warm_hue',
    'slice_echo.hue', 'scan_modulation.key_hue', 'scan_modulation.hue',
})


def presentation(path):
    unit = ' s' if path in SECONDS else '°' if path in DEGREES else '°/s' if path in DEGREES_PER_SECOND else ' px' if path in PIXELS else ''
    return ParameterPresentation(unit=unit, hue=path in HUES)
