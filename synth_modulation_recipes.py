"""Reusable signal recipe; footage and personal Study files remain local."""
import copy


MODULATED_CRT_EFFECTS = {
    'subject_cutout': {'subject_cutout.silhouette': 1., 'subject_cutout.paper': .55,
        'subject_cutout.feather': .7, 'subject_cutout.threshold': .18},
    'chroma_print': {'chroma_print.exposure': .1, 'chroma_print.black': .025,
        'chroma_print.white': .7, 'chroma_print.gamma': 1.,
        'chroma_print.mid_hue': .505, 'chroma_print.mid_saturation': .72,
        'chroma_print.white_saturation': .55, 'chroma_print.warm_color': 0.},
    'scan_modulation': {'scan_modulation.input': 1, 'scan_modulation.region': 2,
        'scan_modulation.key_hue': .055, 'scan_modulation.key_width': .085,
        'scan_modulation.key_floor': .09, 'scan_modulation.key_softness': .1,
        'scan_modulation.fade': 1., 'scan_modulation.fade_start': .72,
        'scan_modulation.fade_width': .17, 'scan_modulation.row_pitch': 6.5,
        'scan_modulation.wave': 20., 'scan_modulation.tear': 50.,
        'scan_modulation.streak': 35., 'scan_modulation.depth': .6,
        'scan_modulation.irregularity': .8,
        'scan_modulation.dropout': .55, 'scan_modulation.exposure': 1.,
        'scan_modulation.white': .55, 'scan_modulation.saturation': .72,
        'scan_modulation.color_faults': .4, 'scan_modulation.rate': 1.2,
        'scan_modulation.sparks': .65, 'scan_modulation.spark_threshold': .44,
        'scan_modulation.spark_size': 3.25, 'scan_modulation.spark_gain': 3.,
        'scan_modulation.spark_fade': 1., 'scan_modulation.spark_end': .19},
    'tape': {'tape.tracking': .015, 'tape.jitter': .0007,
        'tape.dropouts': .08, 'tape.chroma_delay': .002,
        'tape.bleed': .002, 'tape.head_switch': .025, 'tape.mix': .4},
    'crt_capture': {'crt_capture.moire': .065, 'crt_capture.moire_pitch': 80.,
        'crt_capture.phosphor': .27, 'crt_capture.pitch': 3.5,
        'crt_capture.curvature': 1.2, 'crt_capture.weave': .7,
        'crt_capture.field': .22, 'crt_capture.softness': .7,
        'crt_capture.focus_drift': 1.2, 'crt_capture.exposure': .4,
        'crt_capture.grain': .12, 'crt_capture.halation': .3},
}


# Separate recipe: saved and generated copies of the first modulation Study
# retain their quieter scan structure and original curved screen field.
GRAIN_CRT_EFFECTS = copy.deepcopy(MODULATED_CRT_EFFECTS)
GRAIN_CRT_EFFECTS['crt_capture'].update({
    'crt_capture.moire': 0., 'crt_capture.field': 0.,
    'crt_capture.weave': 0., 'crt_capture.curvature': 0.,
    'crt_capture.bend': .1, 'crt_capture.phosphor': 0.,
    'crt_capture.exposure': .35, 'crt_capture.grain': .1,
    'crt_capture.softness': .45, 'crt_capture.focus_drift': .7})
GRAIN_CRT_EFFECTS['screen_mesh'] = {
    'screen_mesh.pitch': 7., 'screen_mesh.strength': .16,
    'screen_mesh.rgb': .05, 'screen_mesh.row_pitch': 7.5,
    'screen_mesh.rows': .6, 'screen_mesh.angle': 0.,
    'screen_mesh.exposure': .25, 'screen_mesh.jitter': .025,
    'screen_mesh.bend': 0., 'screen_mesh.wear': .28,
    'screen_mesh.grain': .08, 'screen_mesh.softness': 0.}
GRAIN_CRT_EFFECTS['raster'] = {
    'raster.softness': 0., 'raster.lines': 0.,
    'raster.grain': .1, 'raster.chroma': .01, 'raster.line_noise': .05}
GRAIN_CRT_EFFECTS['signal_background'] = {
    'signal_background.level': .035, 'signal_background.grain': .07,
    'signal_background.line_noise': .028, 'signal_background.chroma': .004,
    'signal_background.tint': .9, 'signal_background.lines': .09,
    'signal_background.rate': 25., 'signal_background.threshold': .15}


def modulated_crt_composition(footage, *, effects=None):
    from synth_composition import normalize_composition
    from synth_effects import effect_preset
    from synth_video import video_composition
    media = copy.deepcopy(footage)
    media['out'] = min(media['out'], media['in']+10.)
    project = video_composition(media)
    project['name'] = 'Portrait / modulated CRT'
    project['canvas'] = {'width':720, 'height':480, 'framing':'native'}
    project['footage'].update(fit='cover', zoom=1., x=0., y=0., rotation=0.,
        end_mode='hold', audio='mute', motion_fps=0., treatment_fps=25.)
    project['seed'] = 4297
    project['phrases']['custom']['name'] = 'Cyan / modulated CRT'
    for effect, changes in (MODULATED_CRT_EFFECTS if effects is None else effects).items():
        entry = effect_preset(effect)
        entry['params'].update(changes)
        project['effects'][effect] = entry
    return normalize_composition(project)


def grain_crt_composition(footage):
    project = modulated_crt_composition(footage, effects=GRAIN_CRT_EFFECTS)
    project['name'] = 'Portrait / grain CRT'
    project['phrases']['custom']['name'] = 'Cyan / grain / scanlines'
    return project
