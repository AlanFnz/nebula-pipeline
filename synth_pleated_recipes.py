"""Reference-timed camera choreography, sampled at the original 12 fps.

Each frame stores ordinary editable source parameters. No source images or
motion-analysis dependencies are needed to reopen, retime or export the study.
"""
import math
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def _track(keys, frame):
    """Monotone cubic interpolation: preserve speed through interior keys.

    Unlike an ease-in/out per pose, this does not stop the camera at every
    observation. Local extrema and true holds have zero tangents. Logarithmic
    scale gives equal camera ratios equal perceptual weight.
    """
    x,y=zip(*keys)
    if frame<=x[0]: return y[0]
    if frame>=x[-1]: return y[-1]
    h=[b-a for a,b in zip(x,x[1:])]
    d=[(b-a)/step for a,b,step in zip(y,y[1:],h)]
    m=[d[0]]
    for i in range(1,len(x)-1):
        a,b=d[i-1],d[i]
        if a*b<=0: m.append(0.)
        else:
            w1=2*h[i]+h[i-1];w2=h[i]+2*h[i-1]
            m.append((w1+w2)/(w1/a+w2/b))
    m.append(d[-1])
    i=next(i for i in range(len(x)-1) if x[i+1]>=frame)
    t=(frame-x[i])/h[i]
    return (2*t**3-3*t*t+1)*y[i]+(t**3-2*t*t+t)*h[i]*m[i]+(-2*t**3+3*t*t)*y[i+1]+(t**3-t*t)*h[i]*m[i+1]


def pleated_composition(*, extended=True, motion_revision=1):
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
    common.update({'pleated_field.projection':1, 'pleated_field.profile':2,
        'pleated_field.density':6.5, 'pleated_field.depth':.52,
        'pleated_field.stagger':.08, 'pleated_field.curl':.08,
        'pleated_field.irregularity':.22, 'pleated_field.flow':0.,
        'pleated_field.shear':0., 'pleated_field.distance':1.1,
        'pleated_field.aperture':6., 'pleated_field.taper':0.,
        'pleated_field.seams':.25, 'pleated_field.softness':2.2,
        'pleated_field.light_angle':160., 'pleated_field.highlight':1.25, 'pleated_field.palette':4,
        'pleated_field.light':.98, 'pleated_field.background_motion':.85,
        'screen_mesh.exposure':.5, 'screen_mesh.strength':.40, 'screen_mesh.rows':.32, 'screen_mesh.rgb':.20,
        'screen_mesh.grain':.035, 'film_emulsion.grain':.026, 'screen_mesh.softness':.25})
    # Frame observations of the reference's opening 15 seconds. Hard cuts at
    # 42, 88, 96, 165 and 175; all other keys are continuous camera observations.
    # Each segment inherits its first pose, so unmentioned channels never snap
    # back to a generic default halfway through a move.
    segments=[
        (0,42,dict(symmetry=0,density=4.7,yaw=39.,pitch=-5.,angle=12.,size=.82,pan_x=.15,pan_y=.1),[
            (3,{}),(5,dict(size=1.18,yaw=32.)),(8,dict(size=3.5,yaw=22.,pan_x=.25)),
            (10,dict(size=3.35)),(13,dict(size=1.9,yaw=30.,pan_x=.45)),
            (18,dict(size=1.06,yaw=34.,pan_x=.7)),(23,dict(size=.82,yaw=41.,pan_x=.9,angle=16.)),
            (26,dict(size=.79,yaw=43.,angle=25.,pitch=5.)),
            (29,dict(size=.76,yaw=38.,pitch=32.,angle=45.,pan_x=1.05)),
            (32,dict(size=.85,yaw=21.,pitch=48.,angle=70.,pan_x=1.12)),
            (36,dict(size=1.01,yaw=8.,pitch=38.,angle=83.,pan_x=1.35)),
            (41,dict(size=1.2,yaw=4.,pitch=30.,angle=84.,pan_x=1.65))]),
        (42,88,dict(symmetry=1,angle=-34.,yaw=-15.,pitch=12.,size=1.13,
                   pan_x=.2,pan_y=.18,aperture=.7,edge=.3,mirror_x=0.,light_angle=20.),[
            (45,dict(size=1.25,angle=-30.,edge=.42,pan_x=.3)),
            (48,dict(size=1.22,angle=-23.,edge=.05,pan_x=.6)),
            (51,dict(size=1.2,angle=-20.,edge=-.2,pan_x=.9)),
            (54,dict(size=1.08,angle=-30.,edge=-.45,pan_x=1.15,mirror_x=-.08)),
            (58,dict(size=.82,angle=-42.,edge=-.6,pan_x=1.45,mirror_x=-.18)),
            (61,dict(size=.83,angle=-42.,edge=-.6,pan_x=1.55,mirror_x=-.16)),
            (65,dict(size=1.02,edge=-.5,pan_x=1.8,mirror_x=-.12)),
            (70,dict(size=1.45,angle=-34.,edge=-.36,pan_x=2.1,mirror_x=-.08)),
            (75,dict(size=2.0,angle=-18.,edge=-.24,pan_x=2.3,mirror_x=0.)),
            (79,dict(size=3.6,angle=-8.,edge=-.15,pan_x=2.55)),
            (82,dict(size=4.6,angle=-5.,edge=-.1,pan_x=2.7)),
            (87,dict(size=4.4,angle=-32.,pan_x=2.95))]),
        (88,96,dict(symmetry=1,angle=-40.,yaw=-15.,pitch=12.,size=.9,
                   pan_x=1.5,pan_y=.18,aperture=.7,edge=-.52,mirror_x=-.12,light_angle=20.),[
            (95,dict(size=.94,pan_x=1.61))]),
        (96,165,dict(symmetry=2,angle=-38.,yaw=-12.,pitch=4.,size=1.3,
                    pan_x=.35,pan_y=.12,aperture=.9,edge=.0,light_angle=20.),[
            (99,dict(size=1.6,angle=-20.,pan_x=.52)),
            (102,dict(size=1.5,angle=-6.,pan_x=.69,aperture=.6)),
            (104,dict(size=1.1,angle=-3.,aperture=.24)),
            (106,dict(size=.77,aperture=.10,edge=-.02)),
            (108,dict(size=.56,aperture=.09,edge=-.04)),
            (110,dict(size=.43,aperture=.01,edge=-.035)),
            (112,dict(size=.4,aperture=.0,edge=-.06)),
            (114,dict(size=.41,edge=-.035)),
            (116,dict(size=.48,aperture=.07,edge=.0,angle=-24.)),
            (119,dict(size=.67,aperture=.24,angle=-36.,pan_x=.9)),
            (122,dict(size=.93,aperture=.48,pan_x=1.1)),
            (125,dict(size=1.2,aperture=.8,pan_x=1.25,angle=-26.)),
            (129,dict(size=2.8,aperture=2.,angle=-12.,pan_x=1.5)),
            (133,dict(size=4.2,aperture=6.,angle=-6.,pan_x=1.7)),
            (136,dict(size=5.0,angle=-18.,pan_x=1.9)),
            (138,dict(size=4.2,angle=-34.,pan_x=2.08)),
            (141,dict(size=1.7,angle=-40.,pan_x=2.28)),
            (145,dict(size=1.03,angle=-42.,pan_x=2.52)),
            (148,dict(size=.83,angle=-42.,pan_x=2.72)),
            (151,dict(size=3.5,angle=-30.,pan_x=2.95)),
            (154,dict(size=3.8,angle=-35.,pan_x=3.13)),
            (158,dict(size=2.5,angle=-39.,pan_x=3.4)),
            (164,dict(size=1.5,angle=-42.,pan_x=3.8))]),
        (165,175,dict(symmetry=2,angle=-8.,yaw=-8.,pitch=10.,size=1.55,
                     pan_x=1.1,pan_y=.5,light_angle=20.),[
            (168,dict(size=1.65,angle=-16.,pan_x=1.3)),
            (171,dict(size=1.3,angle=-58.,pan_x=1.55)),
            (174,dict(size=.8,angle=-81.,pan_x=1.72))]),
        (175,180,dict(symmetry=2,angle=-37.,yaw=-12.,pitch=4.,size=1.85,
                     pan_x=2.95,pan_y=.12,light_angle=20.),[
            (180,dict(size=1.65,angle=-39.,pan_x=3.3))]),
    ]
    if extended:
        # Continue from the previous endpoint without retiming the first 180
        # frames. The added five seconds follow the next reference gestures:
        # mirrored retreat, rolling ribs, then an oblique unmirrored wall.
        segments.extend([
            (180,190,dict(symmetry=2,angle=-39.,yaw=-12.,pitch=4.,size=1.65,
                         pan_x=3.3,pan_y=.12,light_angle=20.),[
                (184,dict(size=1.43,angle=-41.,pan_x=3.56)),
                (189,dict(size=.96,angle=-44.,pan_x=3.9))]),
            (190,212,dict(symmetry=2,angle=-8.,yaw=-8.,pitch=10.,size=1.6,
                         pan_x=1.12,pan_y=.5,light_angle=20.),[
                (193,dict(size=1.8,angle=-16.,pan_x=1.31)),
                (196,dict(size=1.5,angle=-55.,pan_x=1.53)),
                (199,dict(size=1.05,angle=-78.,pan_x=1.74)),
                (202,dict(size=.9,angle=-90.,pan_x=1.9,pitch=18.)),
                (205,dict(size=1.4,angle=-48.,pan_x=2.1)),
                (208,dict(size=2.1,angle=-20.,pan_x=2.28,pitch=8.)),
                (211,dict(size=2.3,angle=-5.,pan_x=2.44))]),
            (212,215,dict(symmetry=0,density=4.7,angle=84.,yaw=4.,pitch=30.,
                         size=1.2,pan_x=1.65,pan_y=.1),[
                (214,dict(size=1.5,yaw=7.,pitch=35.,angle=82.,pan_x=1.82))]),
            (215,240,dict(symmetry=0,density=5.7,angle=45.,yaw=15.,pitch=-12.,
                         size=.98,pan_x=1.9,pan_y=.25),[
                (218,dict(size=1.07,yaw=8.,pitch=10.,pan_x=2.08)),
                (224,dict(size=1.9,yaw=-5.,angle=42.,pan_x=2.36)),
                (228,dict(size=2.15,yaw=-10.,pitch=5.,angle=55.,pan_x=2.55)),
                (232,dict(size=1.18,yaw=5.,pitch=15.,angle=60.,pan_x=2.75)),
                (235,dict(size=1.32,angle=57.,pan_x=2.9)),
                (238,dict(size=2.05,angle=52.,pan_x=3.03)),
                (239,dict(size=2.12,angle=51.5,pan_x=3.05)),
                (240,dict(size=2.12,angle=51.5,pan_x=3.05))]),
        ])
    if motion_revision == 2:
        # Observe the next reference frames, rather than returning the camera
        # to earlier poses. Begin at the existing cut (175) so the approach to
        # second 15 remains one continuous shot. The mirror roll keeps turning
        # through a half-turn; it does not reverse at 90 degrees.
        segments = [s for s in segments if s[0] < 175] + [
            (175, 190 if extended else 180,
             dict(symmetry=2, angle=-37., yaw=-12., pitch=4., size=3.1,
                  pan_x=2.95, pan_y=.12, light_angle=20.), [
                (180, dict(size=2.75, angle=-39., pan_x=3.3)),
                (183, dict(size=2.25, angle=-42., pan_x=3.52)),
                (186, dict(size=1.72, angle=-43., pan_x=3.75)),
                (189, dict(size=1.26, angle=-44., pan_x=3.98))]),
        ]
        if extended:
            segments.extend([
                (190,212,dict(symmetry=2,angle=-3.,yaw=-8.,pitch=10.,size=3.05,
                             pan_x=1.12,pan_y=.5,light_angle=20.),[
                    (192,dict(size=2.5,angle=-8.,pan_x=1.28)),
                    (195,dict(size=2.05,angle=-25.,pan_x=1.5)),
                    (197,dict(size=1.68,angle=-62.,pan_x=1.67)),
                    (199,dict(size=1.38,angle=-88.,pan_x=1.83)),
                    (201,dict(size=1.15,angle=-108.,pan_x=2.,pitch=16.)),
                    (203,dict(size=1.16,angle=-135.,pan_x=2.16)),
                    (206,dict(size=1.44,angle=-165.,pan_x=2.4,pitch=8.)),
                    (209,dict(size=1.9,angle=-177.,pan_x=2.64)),
                    (211,dict(size=2.12,angle=-181.,pan_x=2.8))]),
                (212,215,dict(symmetry=0,density=4.7,angle=84.,yaw=4.,pitch=30.,
                             size=1.9,pan_x=1.65,pan_y=.1),[
                    (214,dict(size=2.08,yaw=7.,pitch=35.,angle=82.,pan_x=1.82))]),
                (215,240,dict(symmetry=0,density=5.7,angle=45.,yaw=15.,pitch=-12.,
                             size=1.2,pan_x=1.9,pan_y=.25),[
                    (218,dict(size=1.42,yaw=8.,pitch=0.,angle=45.,pan_x=2.08)),
                    (222,dict(size=2.42,yaw=-3.,pitch=4.,angle=42.,pan_x=2.3)),
                    (225,dict(size=3.05,yaw=-8.,angle=42.,pan_x=2.49)),
                    (228,dict(size=2.96,yaw=-10.,pitch=5.,angle=55.,pan_x=2.7)),
                    (230,dict(size=2.04,yaw=-2.,pitch=10.,angle=60.,pan_x=2.85)),
                    (232,dict(size=1.2,yaw=5.,pitch=15.,angle=60.,pan_x=3.0)),
                    (234,dict(size=1.46,angle=57.,pan_x=3.13)),
                    (237,dict(size=2.8,angle=52.,pan_x=3.34)),
                    (240,dict(size=3.9,angle=49.,pan_x=3.55))]),
            ])
    # Observed optical-gate extents, in canvas-height units. These numeric
    # observations are converted to ordinary editable aperture parameters.
    side_extents={49: 0.6639, 50: 0.6639, 51: 0.6472, 52: 0.3083, 53: 0.1583, 54: 0.1306, 55: 0.1139, 56: 0.0028, 57: -0.0028, 58: -0.0083, 59: -0.0083, 60: -0.0028, 61: -0.0028, 62: -0.0083, 63: 0.0472, 64: 0.0972, 65: 0.1917, 66: 0.2583, 67: 0.3083, 68: 0.3972, 69: 0.4583, 70: 0.6639, 71: 0.6639, 88: 0.2028, 89: 0.0917, 90: 0.0417, 91: -0.0139, 92: -0.0083, 93: -0.025, 94: -0.0194, 95: -0.0139}
    center_extents={104: 0.6556, 105: 0.3111, 106: 0.1611, 107: 0.1333, 108: 0.1167, 109: 0.0056, 110: 0, 111: 0, 112: 0, 113: 0, 114: 0, 115: 0, 116: 0.05, 117: 0.1, 118: 0.2, 119: 0.2611, 120: 0.3111, 121: 0.3972, 122: 0.4583, 123: 0.6667}
    collapse_heights={104: 0.3417, 105: 0.2764, 106: 0.25, 107: 0.2153, 108: 0.2681, 109: 0.4236, 110: 0.0583}
    if motion_revision == 2:
        # A breathing central nucleus replaces the fully closed gate. Both
        # dimensions stay visible, including to the shared sound probes.
        # Values are artwork-height units, independent of camera scale.
        for frame in range(106,119):
            center_extents[frame] = _track([
                (106,.1611),(109,.135),(112,.12),(115,.135),(118,.2)],frame)
            collapse_heights[frame] = _track([
                (106,.25),(109,.22),(112,.2),(115,.22),(118,.5)],frame)
    states={};cues=[]
    for start,end,initial,observations in segments:
        pose=dict(initial);keys={k:[(start,v)] for k,v in initial.items()}
        for frame,changes in observations:
            pose.update(changes)
            for k,v in pose.items(): keys.setdefault(k,[(start,common['pleated_field.'+k])]).append((frame,v))
        for frame in range(start,end):
            values={}
            for k,track in keys.items():
                values[k]=math.exp(_track([(f,math.log(v)) for f,v in track],frame)) if k=='size' else _track(track,frame)
            if values.get('symmetry',0): values['angle'] = -values['angle']
            if frame in side_extents:
                values['aperture']=0.
                values['edge']=side_extents[frame]/values['size']-values.get('mirror_x',0.)-.035
            if frame in center_extents:
                extent=center_extents[frame]
                values['aperture']=extent/values['size']
                values['edge']=-.085 if extent==0 else -.035
                if frame in collapse_heights:
                    values['boundary']=1
                    values['taper']=extent/collapse_heights[frame]
            overrides=dict(common);overrides.update({'pleated_field.'+k:v for k,v in values.items()})
            name=f'camera-{frame:03}'
            states[name]=dict(preset='Reference blinds',enabled=['pleated_field','film_emulsion','screen_mesh'],overrides=overrides)
            cues.append(dict(time=frame/12,state=name,transition='cut'))
    sequence=normalize_sequence(dict(schema_version=1,render_version=2,
        name='Pleated signal / violet transmission',fps=12,duration=20. if extended else 15.,seed=51126,
        canvas=dict(width=960,height=720,framing='native'),states=states,cues=cues))
    project=composition_from_sequence(sequence)
    project['phrases']['custom']['name']='Pleats / camera orbit / optical mirrors'
    project['effect_order']=['film_emulsion','screen_mesh']
    return normalize_composition(project)


def pleated_sound_composition():
    """Optional audible study; the existing silent snapshot remains unchanged."""
    from synth_visual_sound import default_sound
    project=pleated_composition()
    project['name']='Pleated signal / electric motion'
    project['generated_sound']=default_sound()
    return normalize_composition(project)


def pleated_acid_composition(*,layered=True):
    """Twenty-second visual instrument; original triangle study stays frozen."""
    from synth_visual_sound import acid_sound,instrument_sound
    project=pleated_composition(motion_revision=2 if layered else 1)
    project['name']='Pleated signal / acid motion'
    project['generated_sound']=instrument_sound() if layered else acid_sound()
    if layered: project['generated_sound']['continuity']=1.
    return normalize_composition(project)
