"""A procedural 3D reference study, with its scene settings stored in the project."""
from synth import MODULE_BY_ID
from synth_blender import ORBITAL_KEYS
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def optical_relic_composition():
    overrides = {'speed':1., 'depth':0., 'treatment_fps':24, 'object_x':0., 'object_y':0.}
    for name in ('blender_scene','optical_diffusion'):
        overrides.update({name+'.'+p.key:p.default for p in MODULE_BY_ID[name].params if not p.key.startswith('part_') and p.key not in ORBITAL_KEYS and p.key not in ('scene','motion_exposure','exposure_delay')})
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


def orbital_rings_composition():
    """A painted armillary assembly; shares source, parts and optical treatments."""
    overrides={'speed':1.,'depth':0.,'treatment_fps':30,'object_x':0.,'object_y':0.}
    enabled=['blender_scene','optical_diffusion','film_burn','broadcast']
    for name in enabled:
        overrides.update({name+'.'+p.key:p.default for p in MODULE_BY_ID[name].params if not p.key.startswith('part_')})
    settings={
        'blender_scene':dict(scene=1,period=226/30,phase=0.,ease=0.,size=1.02,motion_exposure=.13,exposure_delay=.125,
            band_width=.26,band_depth=.29,edge_radius=.065,ring_gap=.045,
            metal_hue=.020,metal_saturation=.76,paint_light=.73,metallic=0.,roughness=.85,
            accent_light=.88,surface_grain=.85,background_hue=.565,background_saturation=.53,
            sky_light=.50,ground_hue=.195,ground_saturation=.52,ground_light=.49,stage_bands=.28,horizon_depth=8.25,
            light_angle=48.,light_size=3.,light_power=650.,environment=.4,exposure=0.,camera_elevation=10.),
        'optical_diffusion':dict(softness=1.1,bloom=.03,grain=0.,vignette=.11,period=226/30),
        'film_burn':dict(print_mix=0.,exposure=0.,damage=0.,reversal=0.,halo=0.,melt=.5,
                         grain=.09,dust=.015,softness=.5,opening=1.3,roughness=0.,cadence=8.),
        'broadcast':dict(field=0.,static=0.,duration=0.,reverse=0.,band=0.,curve=0.,vignette=0.,
                         screen=1.,screen_shape=1,screen_radius=.06,screen_inset=.021,screen_wear=.02),
    }
    for name,values in settings.items():overrides.update({name+'.'+k:v for k,v in values.items()})
    source=normalize_sequence(dict(schema_version=1,render_version=2,
        name='Orbital rings / painted motion',duration=11.3,fps=30,seed=181126,
        canvas={'width':720,'height':900,'framing':'native'},
        states={'rings':{'preset':'Reference blinds','enabled':enabled,'overrides':overrides}},
        cues=[dict(time=0.,state='rings',transition='cut')]))
    project=composition_from_sequence(source)
    project['phrases']['custom']['name']='Five nested rings / Blender scene'
    return normalize_composition(project)


def orbital_painted_composition():
    """Second finish; keep the first sculpture, choreography and recipe intact."""
    from synth_effects import effect_preset
    project=orbital_rings_composition()
    settings={
        'print_surface':dict(surface=1,paint_flatten=.85,paint_tones=5,paint_wash=.6,
            paint_drift=1.6,paint_registration=3.,paint_outline=.36,
            paint_outline_width=1.2,paint_rim=.65,paint_period=226/30,
            cadence=8,ink_grain=1.,ink_wear=.3,grain_size=1.3,boil=.85,
            paper_motion=.05,registration=.0004,rotation_jitter=.035,softness=.15,mix=1.),
        'optical_diffusion':dict(softness=.45),
        'film_burn':dict(grain=.025,melt=.4,softness=.2),
    }
    for name, values in settings.items():
        entry=effect_preset(name)
        # Preserve every existing authored setting before applying this finish.
        entry['params']={key:value for key,value in project['source']['states']['rings']['overrides'].items()
                         if key.startswith(name+'.')}
        entry['params'].update({name+'.'+key:value for key,value in values.items()})
        project['effects'][name]=entry
    project['effect_order']=['print_surface','optical_diffusion','film_burn','broadcast']
    return normalize_composition(project)


def orbital_clean_painted_composition():
    """Approved finer pigment finish; previous recipes remain reproducible."""
    project=orbital_painted_composition()
    project['effects']['print_surface']['params'].update({
        'print_surface.paint_wash':.10, 'print_surface.ink_wear':.03,
        'print_surface.grain_size':.8, 'print_surface.ink_grain':.8})
    project['effects']['film_burn']['params']['film_burn.dust']=0.
    return normalize_composition(project)
