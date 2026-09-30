"""Legacy source/recipe bindings. Generic treatments never inspect presets.

Frames represent a compound source's root, not each particle/card/ray. Per-card
projection and particle deformation remain capabilities of their generators.
"""
import math

from synth_canvas import content_size, object_offset, particle_framing, source_framing
from synth_regions import DirectionalRegion, LocalFrame
from synth_render_context import RenderContext, SourceOutput

ANCHORS = ('auto', 'silhouette', 'slab', 'ink_bloom', 'particles', 'blinds', 'text')


def source_frame(preset, size, time, anchor='auto', continuous_time=None):
    sources = {m['id']: m['params'] for m in preset.get('modules', ()) if m.get('enabled', True)}
    if anchor == 'auto':
        anchor = next((key for key in ('text', 'silhouette', 'ink_bloom', 'particles', 'slab', 'blinds') if key in sources), None)
    if anchor not in sources:
        return None
    p = sources[anchor]
    w, h = size; cw, ch = content_size(preset, size); dx, dy = object_offset(preset, size)
    if anchor == 'text':
        from synth_text import text_layout
        mask, sx, sy = text_layout(p, time if continuous_time is None else continuous_time, preset['speed'], (cw, ch))
        return LocalFrame((w / 2 + dx, h / 2 + dy), max(1., mask.height * sy / 2), -p['rotation'])
    if anchor == 'silhouette':
        return LocalFrame((w / 2 + cw * (p['center_x'] - .5) + dx,
                           h / 2 + ch * (p['center_y'] - .5) + dy),
                          max(1., ch * p['scale'] * max(.3, math.cos(math.radians(p['pitch'])))), p['roll'])
    if anchor == 'slab':
        from synth import _smooth, _clock
        clock = _clock(preset, time)
        x = p['position_x'] + _smooth(preset['seed'], 'slab-shape', clock * .6, preset['variation_mode']) * p['jitter'] * .18 * preset['depth']
        y = p['position_y'] + .08 * _smooth(preset['seed'], 'slab-y', clock * .4, preset['variation_mode']) * preset['depth']
        radius = p['diameter'] if p['shape'] in (2, 3) else p['height']
        return LocalFrame(((w - cw) / 2 + (x + 1) * max(1, cw - 1) / 2 + dx,
                           (h - ch) / 2 + (y + 1) * max(1, ch - 1) / 2 + dy),
                          max(1., radius * ch / 2), -p['rotation'])
    if anchor == 'ink_bloom':
        from synth_print import bloom_phase
        if p.get('clock_mode') and continuous_time is not None:
            time = continuous_time
        _clock, phase, opening = bloom_phase(time, p, preset['speed'])
        angle = p['rotation'] + p['tumble'] * 140 * math.sin(math.tau * (phase - .30))
        unit = p['size'] * min(cw, ch) * (.94 + .06 * opening)
        return LocalFrame((w / 2 + cw * p['position_x'] * .5 + dx,
                           h / 2 + ch * p['position_y'] * .5 + dy), max(1., unit), -angle)
    if anchor == 'particles':
        unit = ch * .35 * p['scale'] * particle_framing(cw, ch, source_framing(preset))
        return LocalFrame((w / 2 + cw * p['position_x'] * .5 + dx,
                           h / 2 - ch * p['position_y'] * .5 + dy), max(1., unit))
    return LocalFrame((w / 2 + cw * p['aperture_position'] * .5 + dx,
                       h / 2 + ch * p['aperture_vertical'] * .5 + dy),
                      max(1., ch * p['aperture_height'] / 2), -p['rotation'])


def phosphor_inputs(arr, params, time, preset, seed, continuous_time=None):
    h, w = arr.shape[:2]; cw, ch = content_size(preset, (w, h))
    continuous = time if continuous_time is None else continuous_time
    context = RenderContext((w, h), (cw, ch), continuous, time, preset['speed'], seed,
                            'reference' in preset and (w > cw + .5 or h > ch + .5))
    canvas = LocalFrame((w / 2, h / 2), max(1., min(w, h) / 2))
    mode = params.get('fade_mode', 0)
    region = None
    softness = .065
    if mode == 0:
        # Compatibility recipe: anatomical placement lives in the binding,
        # while DirectionalRegion and render_phosphor remain source-agnostic.
        frame = source_frame(preset, (w, h), time, 'silhouette')
        strength = params.get('neck_dissolve', 0.)
        if frame is not None and strength:
            region = DirectionalRegion(start=.9, width=.38, strength=strength)
    else:
        frame = canvas if mode == 2 else source_frame(preset, (w, h), time, ANCHORS[params.get('fade_anchor', 0)], continuous)
        strength = params.get('fade_strength', 0.)
        if frame is not None and strength:
            region = DirectionalRegion(params.get('fade_start', 0.), params.get('fade_width', .5),
                                       params.get('fade_angle', 0.), params.get('fade_x', 0.),
                                       params.get('fade_y', 0.), strength, params.get('fade_curve', 1) == 1)
        softness = params.get('fade_softness', .065)
    return SourceOutput(arr, frame or canvas), context, region, softness
