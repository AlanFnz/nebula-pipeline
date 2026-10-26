"""Per-effect dry/wet controls, independent of each effect's authored recipe.

Legacy image operations keep their order and seeds. Most effects blend at one
stage. Ghosts and early Broadcast exposure span several stages; their dry
branches receive the intervening treatments before rejoining the wet signal.
"""
from dataclasses import replace

from PIL import Image

from synth_instances import base_id


IMAGE_MODULES = (
    'dye_transfer', 'signal_tension', 'contact_print', 'film_emulsion', 'film_burn', 'print_collage', 'optical_print', 'contour_melt', 'scan_modulation', 'signal_repetition',
    'crt_capture', 'stretch_echo', 'signal_etch', 'chroma_print', 'slice_echo',
    'screen_mesh', 'broadcast', 'subject_cutout', 'photocopy', 'signal_background',
    'edge_phosphor', 'scan_drag', 'breakup', 'tape', 'flare', 'separation',
    'interference', 'frame_jitter', 'bloom', 'raster', 'print_surface', 'low_res',
    'color_field',
)
PATHS = {key: key + '.effect_intensity' for key in IMAGE_MODULES}
PATHS.update(ghosts='smear.effect_intensity', drift='warp.effect_intensity', cloud='slab.cloud_intensity')


def intensity_path(effect_id):
    path = PATHS.get(base_id(effect_id))
    if path and base_id(effect_id) != effect_id:
        return effect_id + '.' + path.split('.')[1]
    return path


def add_parameters(modules, P):
    """Append only, preserving all existing module and parameter indices."""
    keys = {path.split('.')[0]: path.split('.')[1] for path in PATHS.values()}
    return tuple(replace(module, params=(*module.params,
        P(keys[module.id], 'Intensity', 100., 0, 100, 1,
          'Blend this effect with the image without it. 0% removes its contribution; 100% keeps the configured result. Other settings stay intact.')))
        if module.id in keys else module for module in modules)


def amount(params):
    return params.get('effect_intensity', 100.) / 100.


def blend_pass(image, strength, render):
    if strength <= 0: return image
    # Several legacy generators operate in place and return None.
    wet = image if strength >= 1 else image.copy()
    result = render(wet)
    if result is not None: wet = result
    return wet if strength >= 1 else image * (1-strength) + wet * strength


def blend_images(dry, wet, strength):
    return dry if strength <= 0 else wet if strength >= 1 else Image.blend(dry, wet, strength)


def low_res_strength(preset):
    return next((amount(m['params']) for m in preset['modules']
                 if m['id'] == 'low_res' and m.get('enabled', True)), 1.)


def with_low_res(preset, enabled):
    # Shallow copy of immutable inputs; never rewrite the caller's recipe.
    return dict(preset, modules=[dict(m, enabled=enabled,
        params=dict(m['params'], effect_intensity=100.)) if m['id']=='low_res' else m
        for m in preset['modules']])


class SignalBranches:
    """Fork only while a partially mixed compound effect is in flight."""
    def __init__(self, image):
        self.signals = {frozenset(): image}
        self.active = {}

    def begin(self, effect, strength):
        if effect in self.active: return
        self.active[effect] = strength
        if strength >= 1: return
        signals = {}
        for omitted, image in self.signals.items():
            signals[omitted | {effect}] = image
            if strength > 0: signals[omitted] = image.copy()
        self.signals = signals

    def apply(self, render):
        for omitted, image in self.signals.items():
            result = render(image, omitted)
            if result is not None: self.signals[omitted] = result

    def end(self, effect):
        if effect not in self.active: return
        strength = self.active.pop(effect)
        if strength >= 1: return
        signals = {}
        for omitted, dry in self.signals.items():
            if effect not in omitted: continue
            key = omitted - {effect}
            signals[key] = dry if strength <= 0 else dry*(1-strength) + self.signals[key]*strength
        self.signals = signals

    def result(self):
        for effect in tuple(self.active): self.end(effect)
        return self.signals[frozenset()]

    def snapshot(self):
        """Read the mixed source without closing compound effects in flight."""
        branch = SignalBranches(None)
        branch.signals = self.signals.copy()
        branch.active = self.active.copy()
        return branch.result().copy()
