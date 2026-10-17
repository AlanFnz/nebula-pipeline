"""Editable luminous lattice study; no external media required."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def lattice_composition():
    overrides={'speed':1.,'depth':0.,'treatment_fps':30,'object_x':0.,'object_y':0.}
    overrides.update({'chromatic_lattice.'+p.key:p.default for p in MODULE_BY_ID['chromatic_lattice'].params})
    source=normalize_sequence(dict(schema_version=1,render_version=2,
        name='Lattice / chromatic pulse',duration=20.,fps=30,seed=171026,
        canvas={'width':720,'height':1280,'framing':'native'},
        states={'pulse':{'preset':'Reference blinds','enabled':['chromatic_lattice'],'overrides':overrides}},
        cues=[dict(time=0.,state='pulse',transition='cut')]))
    project=composition_from_sequence(source)
    project['phrases']['custom']['name']='Luminous cells / traveling waves'
    return normalize_composition(project)
