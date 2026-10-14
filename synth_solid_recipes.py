"""Independent optical background and rotating die with a shared film finish."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def rotating_die_composition():
    enabled = ('color_field', 'solid', 'film_emulsion', 'broadcast')
    settings = {'speed': 1., 'depth': 0., 'treatment_fps': 25, 'object_x': 0., 'object_y': 0.}
    for module in enabled:
        settings.update({f'{module}.{spec.key}': spec.default for spec in MODULE_BY_ID[module].params if spec.kind != 'mesh'})
    settings.update({'solid.corner_radius': .13, 'solid.material': 1,
                     'solid.roughness': .27, 'solid.specular': .65,
                     'solid.pip_depth': .018, 'solid.pip_light': .075, 'solid.light': 1.,
                     'film_emulsion.grain': .115, 'film_emulsion.grain_size': 1.1,
                     'film_emulsion.registration': 4.2, 'film_emulsion.softness': 2.9,
                     'film_emulsion.bleed': 2.7,
                     'broadcast.field': 0., 'broadcast.static': 0., 'broadcast.roll': 0.,
                     'broadcast.curve': .07, 'broadcast.vignette': .3})
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Color film / rotating die', duration=15., fps=25, seed=13726,
        canvas={'width': 720, 'height': 1280, 'framing': 'native'},
        states={'turn': {'preset': 'Reference blinds', 'enabled': list(enabled), 'overrides': settings}},
        cues=[dict(time=0., state='turn', transition='cut', duration=0.)]))
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = 'Rotating die / color field'
    return normalize_composition(project)
