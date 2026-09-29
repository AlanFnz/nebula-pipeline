"""Editable video treatment; source media is supplied locally by the user."""

import copy

PORTRAIT_EFFECTS = {
    'chroma_print': {'chroma_print.exposure': .3, 'chroma_print.black': .15,
        'chroma_print.white': .9, 'chroma_print.gamma': 1.05, 'chroma_print.detail': 1.,
        'chroma_print.detail_radius': 50., 'chroma_print.white_saturation': .09,
        'chroma_print.mid_hue': .53, 'chroma_print.mid_saturation': .6,
        'chroma_print.warm_color': .65, 'chroma_print.warm_threshold': .16},
    'slice_echo': {'slice_echo.count': 2, 'slice_echo.height': .22,
        'slice_echo.shift_x': .12, 'slice_echo.shift_y': .2,
        'slice_echo.scale': .18, 'slice_echo.period': .4,
        'slice_echo.activity': 1., 'slice_echo.travel': .35,
        'slice_echo.cadence': 12., 'slice_echo.color_chance': .7,
        'slice_echo.color_mix': .95, 'slice_echo.saturation': .5, 'slice_echo.screen': .15,
        'slice_echo.exposure': .2,
        'slice_echo.opacity': .85},
    'screen_mesh': {'screen_mesh.pitch': 4., 'screen_mesh.strength': .55,
        'screen_mesh.rgb': .3, 'screen_mesh.exposure': .6,
        'screen_mesh.grain': .04, 'screen_mesh.angle': 7., 'screen_mesh.bend': 2.},
    'separation': {'separation.amount': .003, 'separation.angle': 0., 'separation.green': .9},
    'bloom': {'bloom.threshold': .5, 'bloom.radius': 2., 'bloom.strength': .25},
    'raster': {'raster.softness': 1.15, 'raster.lines': 0., 'raster.grain': .035,
        'raster.chroma': .008, 'raster.line_noise': .025},
    'frame_jitter': {'frame_jitter.x': 1.2, 'frame_jitter.y': .8,
        'frame_jitter.rotation': .06, 'frame_jitter.scale': .15, 'frame_jitter.rate': 25.},
}


# A separate treatment keeps the first recipe and saved Studies intact.
EXPOSURE_EFFECTS = copy.deepcopy(PORTRAIT_EFFECTS)
for _effect, _values in {
    'chroma_print': {'exposure': .49, 'black': .22, 'detail': .72,
        'mid_hue': .51, 'mid_saturation': .92, 'white_saturation': .03,
        'warm_color': .25},
    'slice_echo': {'height': .3, 'shift_x': .06, 'shift_y': .075, 'scale': .09,
        'period': .45, 'activity': .88, 'travel': .16, 'cadence': 25.,
        'color_chance': .68, 'color_mix': .95, 'saturation': .75,
        'screen': .15, 'exposure': .1, 'opacity': .88, 'softness': .006,
        'angle': -9., 'highlight_protect': .35, 'luma_mask': .35, 'envelope': .14},
    'screen_mesh': {'rgb': .17, 'strength': .48, 'exposure': .85,
        'softness': .45, 'grain': .025, 'wear': .4},
    'bloom': {'strength': .42, 'radius': 3.4, 'threshold': .55},
    'raster': {'softness': 1.5, 'grain': .022},
}.items():
    EXPOSURE_EFFECTS[_effect].update({f'{_effect}.{key}': value for key,value in _values.items()})


def exposure_composition(footage):
    """Luminous, gently misregistered exposures; the first portrait is unchanged."""
    project = portrait_composition(footage, effects=EXPOSURE_EFFECTS)
    project['name'] = 'Portrait / cyan exposures'
    project['footage'].update(rotation=-14.,zoom=1.48,x=90.,y=-120.)
    project['phrases']['custom']['name'] = 'Cyan / filmed exposures'
    return project


def portrait_composition(footage, *, effects=None):
    """Author a local portrait Study without committing a source path or video."""
    from synth import MODULE_BY_ID
    from synth_composition import normalize_composition
    from synth_effects import effect_preset
    from synth_video import video_composition
    project = video_composition(footage)
    project['name'] = 'Portrait / cyan signal'
    project['canvas'] = {'width':720, 'height':720, 'framing':'native'}
    project['footage'].update(fit='cover',zoom=1.4,x=90.,y=-140.,
                              end_mode='hold',audio='mute',motion_fps=0.,treatment_fps=25.)
    project['seed'] = 4296
    project['phrases']['custom']['name'] = 'Cyan / slices / phosphor'
    for effect, changes in (PORTRAIT_EFFECTS if effects is None else effects).items():
        entry = effect_preset(effect)
        # Save every value in the Study to decouple it from future defaults.
        entry['params'] = {f'{effect}.{s.key}':s.default for s in MODULE_BY_ID[effect].params}
        entry['params'].update(changes)
        project['effects'][effect] = entry
    return normalize_composition(project)
