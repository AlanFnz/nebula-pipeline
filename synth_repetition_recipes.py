"""Local footage recipe: moving fragments inside a filmed CRT portrait."""
import copy

FRAGMENT_EFFECTS = {
    'signal_repetition': dict(region=3, spacing=32.,sample_width=720.,sample_center=.5,
        contour=.55,row_height=32.,row_breakup=.92,row_lines=.9,wave=5.,drift=10.,
        instability=.65,rate=1.5,relief=2.2,edge_width=.4,fringe=1.05,detail=.035,
        hue=.615,saturation=.8,exposure=.4,color_slips=.38,
        outline_warp=3.5,edge_echo=.6,edge_distance=9.,
        outside_mix=.95,outside_level=.76,outside_hue=.63,outside_saturation=.18),
    'crt_capture': dict(phosphor=.38,pitch=3.1,moire=.035,moire_pitch=65.,
        field=.18,angle=.15,curvature=.2,softness=.55,focus_drift=.8,
        bend=.7,exposure=.22,grain=.065,halation=.12,radius=2.,flicker=.15),
    'tape': dict(tracking=.012,jitter=.0006,dropouts=.1,chroma_delay=.0018,
        bleed=.0012,head_switch=.035,mix=.4),
    'raster': dict(softness=.35,lines=.07,grain=.02,chroma=.006,line_noise=.02),
}


def temporal_fragments_composition(footage):
    """A ten-second, non-looping source passage with two editable signal releases."""
    from synth import MODULE_BY_ID
    from synth_composition import normalize_composition
    from synth_effects import effect_preset
    from synth_video import video_composition
    media = copy.deepcopy(footage)
    media['out'] = min(media['out'],media['in']+10.)
    project = video_composition(media)
    project.update(name='Portrait / temporal fragments',seed=4301,fps=25,
                   canvas=dict(width=900,height=900,framing='native'))
    project['footage'].update(fit='cover',zoom=1.,x=0.,y=0.,end_mode='hold',
                               audio='mute',motion_fps=0.,treatment_fps=25.)
    project['phrases']['custom']['name']='Fragmented signal'
    for effect,changes in FRAGMENT_EFFECTS.items():
        entry = effect_preset(effect)
        entry['params'] = {f'{effect}.{s.key}':s.default for s in MODULE_BY_ID[effect].params}
        entry['params'].update({f'{effect}.{key}':value for key,value in changes.items()})
        project['effects'][effect]=entry
    project['sections'][0]['automations']=[
        dict(id='signal-opening',path='signal_repetition.spacing',amount=124.,enabled=True,
             easing='smooth',start_fraction=0.,attack_fraction=0.,hold_fraction=.012,recovery_fraction=.10),
        dict(id='signal-release',path='signal_repetition.spacing',amount=80.,enabled=True,
             easing='smooth',start_fraction=.65,attack_fraction=.015,hold_fraction=.012,recovery_fraction=.07),
    ]
    return normalize_composition(project)
