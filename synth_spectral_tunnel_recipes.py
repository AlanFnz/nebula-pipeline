"""A square optical loop reconstructed from the ref-15 light lattice."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def spectral_tunnel_composition():
    overrides = {'speed': 1., 'depth': 0., 'treatment_fps': 100,
                 'object_x': 0., 'object_y': 0.}
    overrides.update({'spectral_tunnel.' + p.key: p.default
                      for p in MODULE_BY_ID['spectral_tunnel'].params})
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Spectral tunnel / luminous ripple', duration=6., fps=100, seed=151026,
        canvas={'width': 500, 'height': 500, 'framing': 'native'},
        states={'ripple': {'preset': 'Reference blinds', 'enabled': ['spectral_tunnel'],
                           'overrides': overrides}},
        cues=[dict(time=0., state='ripple', transition='cut')]))
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = 'Luminous ripple / seamless loop'
    return normalize_composition(project)
