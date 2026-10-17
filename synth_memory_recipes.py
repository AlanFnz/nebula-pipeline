"""Portable original study: a luminous object leaves an evolving pigment history."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def memory_composition():
    enabled = ('image_memory', 'film_emulsion', 'broadcast')
    settings = {'speed': 1., 'depth': 0., 'treatment_fps': 24, 'object_x': 0., 'object_y': 0.}
    for module in enabled:
        settings.update({f'{module}.{spec.key}': spec.default for spec in MODULE_BY_ID[module].params})
    settings.update({
        'film_emulsion.grain': .045, 'film_emulsion.grain_size': 1.1,
        'film_emulsion.registration': 1.3, 'film_emulsion.softness': .5,
        'film_emulsion.bleed': 1.2, 'film_emulsion.flicker': .012,
        'broadcast.field': 0., 'broadcast.static': 0., 'broadcast.roll': 0.,
        'broadcast.curve': .035, 'broadcast.vignette': .22,
    })
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Memory / afterimage garden', duration=15., fps=24, seed=171026,
        canvas={'width': 720, 'height': 960, 'framing': 'native'},
        states={'memory': {'preset': 'Reference blinds', 'enabled': list(enabled), 'overrides': settings}},
        cues=[dict(time=0., state='memory', transition='cut')]))
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = 'Memory / drifting traces'
    return normalize_composition(project)
