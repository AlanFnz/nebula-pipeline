"""A procedural 3D reference study, with its scene settings stored in the project."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def optical_relic_composition():
    overrides = {'speed':1., 'depth':0., 'treatment_fps':24, 'object_x':0., 'object_y':0.}
    for name in ('blender_scene','optical_diffusion'):
        overrides.update({name+'.'+p.key:p.default for p in MODULE_BY_ID[name].params if not p.key.startswith('part_')})
    overrides.update({'blender_scene.roughness':.24,
                      'blender_scene.metallic':1.,
                      'blender_scene.tube_radius':.125,
                      'blender_scene.hoop_bow':.10,
                      'blender_scene.hoop_twist':0.,
                      'blender_scene.crown_size':1.1,
                      'blender_scene.light_power':400.,
                      'blender_scene.light_size':8.,
                      'blender_scene.light_angle':-50.,
                      'blender_scene.environment':.65,
                      'blender_scene.period':35/6,
                      'blender_scene.phase':.9366666667,
                      'blender_scene.ease':.26,
                      'optical_diffusion.period':8.75,
                      'blender_scene.background_saturation':.52,
                      'optical_diffusion.softness':3.8})
    source = normalize_sequence(dict(schema_version=1,render_version=2,
        name='Optical relic / green reverie',duration=8.75,fps=24,seed=161126,
        canvas={'width':720,'height':960,'framing':'native'},
        states={'relic':{'preset':'Reference blinds',
                         'enabled':['blender_scene','optical_diffusion'], 'overrides':overrides}},
        cues=[dict(time=0.,state='relic',transition='cut')]))
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = 'Rotating relic / Blender scene'
    return normalize_composition(project)
