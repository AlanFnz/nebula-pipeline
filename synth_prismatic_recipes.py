"""Authored optical planes, folding into a triangle; no external media needed."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def prismatic_composition():
    settings={'speed':1.,'depth':0.,'treatment_fps':25,'object_x':0.,'object_y':0.}
    # Keep the published recipe sparse; later controls use their neutral defaults.
    for module in ('prismatic_field','film_emulsion'):
        settings.update({f'{module}.{spec.key}':spec.default for spec in MODULE_BY_ID[module].params if spec.key != 'effect_intensity'})
    settings.update({'prismatic_field.rotation_speed':0.,'prismatic_field.shape':1,
                     'prismatic_field.center_shape':1,'prismatic_field.transition_ease':.9,
                     'prismatic_field.turn_settle':.6,'prismatic_field.fold_depth':.25,
                     'prismatic_field.drift':.06,'prismatic_field.color_phase':.02,
                     'prismatic_field.wash':.85,'film_emulsion.grain':.115,
                     'film_emulsion.grain_size':1.1,'film_emulsion.registration':4.2,'film_emulsion.softness':3.8})
    poses=(
        ('crossed',0.,0.,dict(rotation=55.,opening=.7,gather=0.)),
        ('spread',.2,1.65,dict(rotation=68.,opening=.84,gather=0.)),
        ('edge',2.2,.8,dict(rotation=96.,opening=.055,gather=0.)),
        ('turn',3.55,.95,dict(rotation=175.,opening=.11,gather=0.)),
        ('open',5.1,1.45,dict(rotation=208.,opening=.9,gather=0.)),
        ('planes',7.15,1.1,dict(rotation=284.,opening=1.3,gather=.28)),
        ('gather',8.92,1.8,dict(rotation=335.,opening=.7,gather=.65)),
        ('shape',11.16,1.44,dict(rotation=360.,opening=.7,gather=1.,drift=0.,
                                color_speed=.025,color_phase=.64,light=1.10,saturation=.95,shading=.25,
                                object_x=0.,object_y=0.)),
    )
    states={}
    for name,_,_,pose in poses:
        overrides=dict(settings)
        overrides.update({key if key.startswith('object_') else 'prismatic_field.'+key:value for key,value in pose.items()})
        states[name]={'preset':'Reference blinds','enabled':['prismatic_field','film_emulsion'],'overrides':overrides}
    source=normalize_sequence(dict(schema_version=1,render_version=2,
        name='Prismatic / color film',duration=15.,fps=25,seed=13726,
        canvas={'width':720,'height':1280,'framing':'native'},states=states,
        cues=[dict(time=t,state=name,transition='morph' if duration else 'cut',duration=duration)
              for name,t,duration,_ in poses]))
    project=composition_from_sequence(source)
    project['phrases']['custom']['name']='Planes / folds / shape'
    return normalize_composition(project)
