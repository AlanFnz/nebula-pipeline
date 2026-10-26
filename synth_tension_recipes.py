"""Original study: a luminous form stretches into threads and gathers itself."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def tension_composition():
    enabled=('slab','signal_tension','signal_background','film_emulsion','broadcast')
    settings={'speed':1.,'depth':0.,'treatment_fps':24, 'object_x':0., 'object_y':0.}
    for module in enabled:
        settings.update({f'{module}.{p.key}':p.default for p in MODULE_BY_ID[module].params})
    settings.update({
        'slab.shape':2, 'slab.diameter':.40, 'slab.position_x':0.,'slab.position_y':0.,
        'slab.hollow':.50, 'slab.intensity':1.0, 'slab.edge_softness':.018,
        'slab.fill_magenta':.05, 'slab.magenta':.08, 'slab.cyan':.12,
        'slab.jitter':0., 'slab.notch':0., 'slab.ghost_opacity':0.,
        'slab.cloud_strength':0., 'slab.cloud_detail':0.,
        'signal_tension.tension':.9, 'signal_tension.cohesion':.32,
        'signal_tension.instability':.72, 'signal_tension.glow':.45,
        'signal_tension.spacing':7., 'signal_tension.bend':.8,
        'signal_background.level':.026, 'signal_background.grain':.065,
        'signal_background.tint':.25,
        'film_emulsion.grain':.045, 'film_emulsion.grain_size':.8,
        'film_emulsion.registration':1.0, 'film_emulsion.softness':.6,
        'film_emulsion.bleed':.65, 'film_emulsion.flicker':.012,
        'broadcast.field':0., 'broadcast.static':0., 'broadcast.roll':0.,
        'broadcast.curve':.055, 'broadcast.vignette':.24,
    })
    sequence=normalize_sequence(dict(schema_version=1,render_version=2,
        name='Tension / elastic signal',duration=15.,fps=24,seed=261026,
        canvas={'width':960,'height':720,'framing':'native'},
        states={'tension':{'preset':'Reference blinds','enabled':list(enabled),'overrides':settings}},
        cues=[dict(time=0.,state='tension',transition='cut')]))
    project=composition_from_sequence(sequence)
    project['phrases']['custom']['name']='Tension / pull, recoil, memory'
    project['effect_order']=['signal_tension','signal_background','film_emulsion','broadcast']
    return normalize_composition(project)
