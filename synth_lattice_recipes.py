"""Editable luminous lattice study; no external media required."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence
from synth_lattice_relief import RELIEF_KEYS
from synth_lattice_eye import EYE_KEYS


def lattice_composition():
    overrides={'speed':1.,'depth':0.,'treatment_fps':30,'object_x':0.,'object_y':0.}
    # Keep the original study snapshot unchanged; musical phrasing is opt-in.
    overrides.update({'chromatic_lattice.'+p.key:p.default for p in MODULE_BY_ID['chromatic_lattice'].params
                      if p.key not in RELIEF_KEYS | EYE_KEYS | {'color_rhythm','bpm','phrase_bars'}})
    source=normalize_sequence(dict(schema_version=1,render_version=2,
        name='Lattice / chromatic pulse',duration=20.,fps=30,seed=171026,
        canvas={'width':720,'height':1280,'framing':'native'},
        states={'pulse':{'preset':'Reference blinds','enabled':['chromatic_lattice'],'overrides':overrides}},
        cues=[dict(time=0.,state='pulse',transition='cut')]))
    project=composition_from_sequence(source)
    project['phrases']['custom']['name']='Luminous cells / traveling waves'
    return normalize_composition(project)


def printed_orbit_composition():
    overrides = {'speed':1., 'depth':0., 'treatment_fps':12, 'object_x':0., 'object_y':0.}
    values = dict(surface=1, shape=1, spacing=81.7, size=.919, minimum=.3257,
                  wave_shape=3, period=4., phase=0., angle=0., color_period=4.,
                  color_phase=.80548, color_spread=.33, grid_x=.03, grid_y=-.058,
                  softness=.25, glow=0., rim=1., bevel=1.55, edge_width=4.8, grain=.085)
    overrides.update({'chromatic_lattice.'+p.key:values.get(p.key,p.default)
                      for p in MODULE_BY_ID['chromatic_lattice'].params if p.key not in EYE_KEYS})
    paint = dict(surface=1, paint_flatten=0., paint_wash=.10, paint_drift=.65,
                 paint_registration=.25, paint_outline=0., paint_rim=0.,
                 cadence=12., paint_period=8., ink_grain=.12, ink_wear=.04,
                 grain_size=.8, boil=.7, paper_motion=0., registration=0.,
                 rotation_jitter=0., softness=0.)
    overrides.update({'print_surface.'+p.key:paint.get(p.key,p.default)
                      for p in MODULE_BY_ID['print_surface'].params})
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Lattice / printed orbit', duration=8., fps=24, seed=141126,
        canvas={'width':720,'height':1280,'framing':'native'},
        states={'orbit':{'preset':'Reference blinds',
                         'enabled':['chromatic_lattice','print_surface'], 'overrides':overrides}},
        cues=[dict(time=0.,state='orbit',transition='cut')]))
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = 'Printed cells / opposing sweeps'
    return normalize_composition(project)


def watching_eye_composition():
    project = printed_orbit_composition()
    project['name'] = 'Lattice / watching eye'
    project['phrases']['custom']['name'] = 'Printed cells / watching eye'
    project['source']['name'] = project['name']
    params = project['source']['states']['orbit']['overrides']
    # Preserve the first version's frozen recipe; later controls are opt-in.
    params.update({'chromatic_lattice.'+p.key: p.default for p in MODULE_BY_ID['chromatic_lattice'].params if p.key in EYE_KEYS-{'eye_blink_fps','eye_placement'}})
    params['chromatic_lattice.eye_enabled'] = 1
    return normalize_composition(project)
