"""Editable radial study; soundtrack demos add user-selected media separately."""
from synth import MODULE_BY_ID
from synth_sequence import normalize_sequence
from synth_composition import composition_from_sequence, normalize_composition


def radial_composition(duration=12.):
    overrides = {'speed': 1., 'depth': 0., 'treatment_fps': 30}
    for spec in MODULE_BY_ID['radial_bloom'].params:
        overrides['radial_bloom.'+spec.key] = spec.default
    overrides.update({'radial_bloom.phase':0., 'radial_bloom.expansion':1.2, 'radial_bloom.light':.97})
    sequence = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Radial / chromatic bloom', duration=duration, fps=30, seed=11026,
        canvas={'width':720, 'height':1280, 'framing':'native'},
        states={'bloom': {'preset':'Reference blinds', 'enabled':['radial_bloom'],
                          'overrides':overrides}},
        cues=[{'time':0., 'state':'bloom', 'transition':'cut'}]))
    project = composition_from_sequence(sequence)
    project['phrases']['custom']['name'] = 'Expanding crowns'
    return normalize_composition(project)
