"""Visible, single-section material for a fresh piece; existing studies stay intact."""
from synth import MODULE_BY_ID, SHAPES
from synth_canvas import normalize_canvas
from synth_compat import CURRENT_RENDER_VERSION
from synth_composition import blank_composition, normalize_composition
from synth_text import validate_text


DEFAULT_TEXT = 'REVOLUTION IS NOW'


def new_piece(kind, canvas=None, fps=25, *, text=DEFAULT_TEXT, shape='rectangle', model='silhouette'):
    if kind not in ('text', 'shape', 'model'):
        raise ValueError('Choose Text, Shape or Model for generated material.')
    if shape not in {value.lower() for value in SHAPES}:
        raise ValueError('Unknown starting shape.')
    if model not in ('silhouette', 'particles'):
        raise ValueError('Unknown model presentation.')
    if kind == 'text' and not validate_text(text).strip():
        raise ValueError('Enter some text to start with.')
    size = normalize_canvas(canvas)
    # New material is authored for this canvas, without a previous piece's crop.
    canvas = dict(width=size['width'], height=size['height'], framing='adaptive')
    module = {'text': 'text', 'shape': 'slab', 'model': model}[kind]
    project = blank_composition()
    project.update(name=f'Untitled {kind}', fps=fps, canvas=canvas,
                   render_version=CURRENT_RENDER_VERSION)
    source = project['source']
    source.update(name=project['name'], fps=fps, duration=6., canvas=canvas,
                  render_version=CURRENT_RENDER_VERSION)
    params = {f'{module}.{spec.key}': spec.default for spec in MODULE_BY_ID[module].params}
    if kind == 'text':
        params.update({'text.content': text, 'text.saturation': 0., 'text.back_brightness': 0.,
                       'text.size': .18, 'text.fit_width': .85})
    elif kind == 'shape':
        params.update({'slab.position_x': 0., 'slab.position_y': 0., 'slab.width': .48,
                       'slab.height': .45, 'slab.notch': 0., 'slab.jitter': 0.,
                       'slab.ghost_opacity': 0., 'slab.magenta': 0., 'slab.cyan': 0.})
        project['geometry'].update(shape=shape, diameter=.42)
    elif model == 'silhouette':
        # The projection scales against height; bound a new head by both axes.
        scale = .28 * min(size['width'], size['height']) / size['height']
        params.update({'silhouette.model': 2, 'silhouette.center_x': .5,
                       'silhouette.center_y': .5 - .23 * scale, 'silhouette.scale': scale,
                       'silhouette.neck_length': .25})
    else:
        params.update({'particles.attractor': 5, 'particles.assembly': 1.,
                       'particles.breathing': 0., 'particles.count': 14000,
                       'particles.yaw': -35., 'particles.scale': .68,
                       'particles.turbulence': .025, 'particles.occlusion': 1.,
                       'particles.xray': 0., 'particles.neck_fade': .42,
                       'particles.rotation_speed': 0., 'particles.dot_size': 2.,
                       'particles.intensity': 1.8, 'particles.shimmer': .15,
                       'particles.saturation': .3, 'particles.color_spread': .15})
    params.update(speed=1., depth=0., treatment_fps=fps)
    source['states']['blank'].update(enabled=[module], overrides=params)
    project['phrases']['custom'].update(name=kind.title(), start=0., end=6.)
    project['sections'][0]['duration'] = 6.
    return normalize_composition(project)
