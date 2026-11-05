"""A fifteen-second optical fold study, authored from reference-14 motifs."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def pleated_composition():
    common = {'speed':1., 'depth':0., 'treatment_fps':12, 'object_x':0., 'object_y':0.}
    for module in ('pleated_field','film_emulsion','screen_mesh'):
        common.update({module+'.'+p.key:p.default for p in MODULE_BY_ID[module].params})
    common.update({
        'film_emulsion.softness':.6, 'film_emulsion.bleed':1.4,
        'film_emulsion.registration':1.7, 'film_emulsion.edge_ink':.17,
        'film_emulsion.grain':.026, 'film_emulsion.grain_size':.65,
        'film_emulsion.chroma':.4, 'film_emulsion.flicker':.035,
        'film_emulsion.cadence':12.,
        'screen_mesh.pitch':3.6, 'screen_mesh.row_pitch':3.25,
        'screen_mesh.angle':-12., 'screen_mesh.strength':.46,
        'screen_mesh.rows':.43, 'screen_mesh.rgb':.32,
        'screen_mesh.exposure':1., 'screen_mesh.grain':.035,
        'screen_mesh.wear':.28, 'screen_mesh.softness':.1,
        'screen_mesh.cadence':12., 'screen_mesh.jitter':.018,
    })
    states={};cues=[]
    def pose(frame, *, cut=False, **values):
        key=f'pose-{len(states)+1:02}'
        overrides=dict(common)
        overrides.update({'pleated_field.'+k:v for k,v in values.items()})
        states[key]=dict(preset='Reference blinds',enabled=['pleated_field','film_emulsion','screen_mesh'],overrides=overrides)
        # Each new target begins at the preceding key. This exposes authored
        # camera moves as normal sequence morphs, editable through automation.
        if not cues: cues.append(dict(time=0.,state=key,transition='cut'))
        elif cut: cues.append(dict(time=frame/12,state=key,transition='cut'))
        else:
            start=pose.last/12
            # A cut already at this timestamp must be visible for one frame.
            if cues[-1]['time'] >= start: start+=1/12
            cues.append(dict(time=start,state=key,transition='morph',duration=frame/12-start))
        pose.last=frame
    pose.last=0
    pose(0,size=1.25,angle=18.,perspective=.62,density=5.,pan_x=.15)
    pose(8,size=1.7,angle=16.,perspective=.5,density=4.7,pan_x=.28)
    pose(23,size=.82,angle=23.,perspective=.72,density=6.,pan_x=.9)
    pose(30,size=.95,angle=72.,perspective=.5,density=7.,pan_x=1.3,tilt_x=-.4,tilt_y=.8,depth=.8)
    pose(31,cut=True,symmetry=1,size=.9,angle=0.,shear=-1.15,aperture=.22,edge=-.15,pan_x=.6,density=7.,highlight=.72)
    pose(43,symmetry=1,size=.7,angle=0.,shear=-1.05,aperture=.08,edge=-.12,pan_x=1.15,density=8.,perspective=.6,highlight=.72)
    pose(49,symmetry=1,size=1.5,angle=0.,shear=-1.25,aperture=.38,edge=.1,pan_x=1.4,density=6.)
    pose(50,cut=True,symmetry=2,size=.9,angle=0.,shear=.8,perspective=0.,pan_x=.2,pan_y=.25,density=5.)
    pose(60,symmetry=2,size=2.2,angle=0.,shear=.55,perspective=0.,pan_x=.4,pan_y=.38,density=3.8)
    pose(65,cut=True,symmetry=1,size=.8,angle=0.,shear=-1.15,aperture=.15,edge=-.25,density=8.)
    pose(72,symmetry=1,size=1.1,angle=0.,shear=-1.1,aperture=.1,edge=-.2,density=8.,pan_x=.5)
    pose(73,cut=True,symmetry=2,size=.8,angle=0.,shear=.8,perspective=0.,aperture=.7,taper=.3,density=7.)
    pose(81,symmetry=2,size=.14,angle=0.,shear=.8,perspective=0.,aperture=.24,taper=.2,density=7.)
    pose(85,symmetry=2,size=.05,angle=0.,shear=.8,perspective=0.,aperture=.14,taper=.2,density=7.)
    pose(90,symmetry=2,size=.8,angle=0.,shear=.6,perspective=0.,aperture=.55,taper=.2,density=7.,pan_x=.4)
    pose(104,symmetry=2,size=1.4,angle=0.,shear=.7,perspective=0.,aperture=3.,density=4.5,pan_x=.9,pan_y=.2)
    pose(115,symmetry=2,size=1.1,angle=0.,shear=1.2,perspective=0.,density=5.5,pan_x=1.3,pan_y=.5)
    pose(125,symmetry=2,size=.62,angle=0.,shear=.85,perspective=0.,density=6.,pan_x=1.5,pan_y=.85)
    pose(126,cut=True,size=.95,angle=-10.,density=5.5,perspective=.55,pan_x=.5)
    pose(139,size=1.55,angle=35.,density=4.8,perspective=.7,pan_x=1.1)
    pose(150,size=.7,angle=76.,density=7.5,perspective=.6,pan_x=1.5)
    pose(151,cut=True,symmetry=1,size=1.,angle=0.,shear=-1.15,aperture=.13,edge=-.1,density=7.,pan_x=.8)
    pose(160,symmetry=1,size=.85,angle=0.,shear=-.9,aperture=.25,edge=-.2,density=7.5,pan_x=1.3)
    pose(161,cut=True,symmetry=2,size=.8,angle=0.,shear=.8,perspective=0.,density=6.,pan_x=.9,pan_y=.4)
    pose(171,symmetry=2,size=1.4,angle=0.,shear=.6,perspective=0.,density=5.,pan_x=1.2,pan_y=.7)
    pose(172,cut=True,size=1.35,angle=18.,perspective=.62,density=5.,pan_x=.2)
    pose(180,size=1.25,angle=18.,perspective=.62,density=5.,pan_x=.15)
    sequence=normalize_sequence(dict(schema_version=1,render_version=2,
        name='Pleated signal / violet transmission',fps=12,duration=15.,seed=51126,
        canvas=dict(width=960,height=720,framing='native'),states=states,cues=cues))
    project=composition_from_sequence(sequence)
    project['phrases']['custom']['name']='Pleats / mirrors / collapse'
    project['effect_order']=['film_emulsion','screen_mesh']
    return normalize_composition(project)
