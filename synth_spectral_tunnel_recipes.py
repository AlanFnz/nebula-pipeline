"""A square optical loop reconstructed from the ref-15 light lattice."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def spectral_tunnel_composition():
    overrides = {'speed': 1., 'depth': 0., 'treatment_fps': 50,
                 'object_x': 0., 'object_y': 0.}
    overrides.update({'spectral_tunnel.' + p.key: p.default
                      for p in MODULE_BY_ID['spectral_tunnel'].params if p.key != 'orientation'})
    # The original study inherits the default orientation, preserving its file.
    # Each cell advances into its neighbor's position in one reference cycle.
    overrides.update({'spectral_tunnel.motion': 1,
                      'spectral_tunnel.period': .4,
                      'spectral_tunnel.vanishing_x': 1.286,
                      'spectral_tunnel.horizon': .573,
                      'spectral_tunnel.depth': 1.006,
                      'spectral_tunnel.spacing': 3.95})
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Spectral tunnel / luminous ripple', duration=6., fps=50, seed=151026,
        canvas={'width': 500, 'height': 500, 'framing': 'native'},
        states={'ripple': {'preset': 'Reference blinds', 'enabled': ['spectral_tunnel'],
                           'overrides': overrides}},
        cues=[dict(time=0., state='ripple', transition='cut')]))
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = 'Luminous ripple / seamless loop'
    return normalize_composition(project)
