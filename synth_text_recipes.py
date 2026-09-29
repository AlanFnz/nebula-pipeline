"""Authoring recipes for the text studies; shipped copies are frozen in presets."""
import copy

from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def opium_composition():
    common = {
        'text': {'content': 'OPIUM', 'font': 0, 'size': .115, 'fit': 2,
                 'block_width': .70, 'tracking': -.01, 'saturation': 0.,
                 'brightness': 1.05, 'back_brightness': 0.},
        'stretch_echo': {'stretch_y': 3.85, 'minimum': 1.2, 'ease': 6.,
                         'typeface': 4, 'outline': 0., 'opacity': .9, 'stroke': 1., 'period': 1.5},
        'signal_etch': {'grain': .24, 'grain_size': 2., 'streak': 3., 'erosion': .3, 'roughness': 6., 'core': .9,
                        'scatter': .9, 'spread_x': 30., 'spread_y': 4.,
                        'pulse': 12., 'pulse_spread': 35., 'pulse_stretch': 2.8, 'pulse_focus': 1., 'pulse_seconds': .17, 'period': 1.5},
        'raster': {'softness': .85, 'lines': 0., 'grain': .035, 'chroma': 0., 'line_noise': .05},
    }
    settings = {'speed': 1., 'depth': 0., 'treatment_fps': 24}
    for module, changes in common.items():
        settings.update({f'{module}.{spec.key}': spec.default for spec in MODULE_BY_ID[module].params})
        settings.update({f'{module}.{key}': value for key, value in changes.items()})
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Text / opium', duration=4.5, fps=24, seed=5826,
        canvas={'width':720, 'height':900, 'framing':'native'},
        states={'title': {'preset':'Reference blinds', 'enabled':list(common), 'overrides':settings}},
        cues=[{'time':0., 'state':'title', 'transition':'cut'}]))
    project = composition_from_sequence(source)
    project['render_version'] = 2
    project['phrases']['custom']['name'] = 'Contour / open / exposure'
    return normalize_composition(project)


def text_composition(look='phosphor'):
    duration = 6.
    common = {
        'text': {'content': 'REVOLUTION IS NOW'},
        'bloom': {'threshold': .3, 'radius': 7., 'strength': .9},
        'raster': {'softness': 2.2, 'lines': .15, 'grain': .12, 'chroma': .022, 'line_noise': .07},
        'tape': {'tracking': .004, 'jitter': .0007, 'dropouts': .09, 'chroma_delay': .003, 'bleed': .008, 'head_switch': .15, 'rate': 20., 'mix': 1.},
        'frame_jitter': {'x': 1.2, 'y': 1., 'rotation': .08, 'scale': .07, 'rate': 15},
        'broadcast': {'field': .24, 'hue': .52, 'hue_spread': .17, 'drift': .6, 'static': .85, 'duration': .12, 'period': 3., 'phase': .2, 'curve': .018, 'vignette': .2},
        'low_res': {'resolution': 480},
    }
    if look == 'phosphor':
        name = 'Text / phosphor drift'
        common['text'].update(hue=.22, saturation=.38, brightness=1.02, size=.135,
                              back_hue=.55, back_saturation=.8, back_brightness=.17)
        common['bloom'].update(radius=3.5, strength=.5)
        common['raster'].update(softness=1.7, grain=.12, chroma=.022, lines=.11, line_noise=.10)
        common['broadcast'].update(field=.14, hue=.57, hue_spread=.15, static=1., static_style=1,
            duration=.38, period=2.56, phase=.15625, drift=.9, wash=.12, static_chroma=.3,
            sync_tear=.15, curve=.005, vignette=.12, halo=.12, halo_radius=.018, halo_hue=.22, rate=12.)
        common['tape'].update(tracking=.001, jitter=.0004, dropouts=.04, bleed=.003, head_switch=.05)
        common['frame_jitter'].update(x=.75, y=.55, rotation=.02, scale=.025, rate=12.)
        common['low_res'].update(resolution=500)
    elif look == 'pressure':
        name = 'Text / pressure'
        common['text'].update(font=1, size=1.05, fit=2, block_width=.62, tracking=-.035,
            hue=.026, saturation=.88, brightness=1.04, back_saturation=.1, back_brightness=.075,
            reveal=1, word_seconds=.48, motion=3, zoom_start=1.14, zoom_end=.34, period=.48, ease=1.4, cadence=0.)
        common['bloom'].update(radius=2., strength=.13)
        common['raster'].update(softness=1.1, grain=.12, lines=.18, chroma=.035, line_noise=.08)
        common['broadcast'].update(field=0., static=0., duration=0., reverse=1.,
            reverse_period=.12, reverse_hue=.026, reverse_saturation=.87, reverse_phase=.75,
            reverse_blend=.85, field_spread=.11, reverse_stage=1, edge_fringe=.65, edge_width=.005, edge_hue=.7, curve=.008, vignette=.08)
        common['tape'].update(tracking=.001, jitter=.0004, chroma_delay=.003, bleed=.004, head_switch=.05, dropouts=.04, rate=30.)
        common['frame_jitter'].update(x=.4, y=.5, rotation=.02, rate=30.)
        common['separation'] = {'amount': .004, 'angle': .1, 'green': .95}
        common['signal_background'] = {'level': .065, 'grain': .11, 'chroma': .03, 'threshold': .25}
        common['low_res'].update(resolution=500)
    elif look == 'transmission':
        name = 'Text / lost transmission'
        common['text'].update(font=1, reveal=1, word_seconds=.65, fit_width=.94, size=.34, hue=.40,
            saturation=.7, brightness=.72, back_brightness=.004, tracking=-.035, copies=2, copy_gap=.22,
            wrap_columns=0, copy_floor=.92, leading=.96, stretch_x=.85)
        common['bloom'].update(radius=4., strength=.22, threshold=.15)
        common['raster'].update(softness=4.1, lines=.06, grain=.06, chroma=.009, line_noise=.05)
        common['tape'].update(tracking=.013, jitter=.0012, chroma_delay=.01, bleed=.009, head_switch=.08, dropouts=.015)
        common['broadcast'].update(field=.005, static=.97, band=0., duration=0., period=1.35,
            phase=0., curve=.007, static_style=1, outages=.27, sync_tear=.9, static_chroma=.55,
            halo=1.9, halo_hue=.64, halo_radius=.028, vignette=.1, rate=20.)
        common['separation'] = {'amount': .007, 'angle': .08, 'green': .9}
        common['smear'] = {'amount': .02, 'direction': -.8, 'ghosts': 1}
        common['frame_jitter'].update(x=1.1, y=.8, rotation=.35, scale=.15, rate=20.)
        common['low_res'].update(resolution=500)
    elif look == 'night':
        name = 'Text / night monitor'
        common['text'].update(size=.05, hue=.56, saturation=.08, brightness=1.1,
                              back_hue=.62, back_saturation=.86, back_brightness=.025)
        common['bloom'].update(radius=2., strength=.27, threshold=.3)
        common['raster'].update(softness=.95, grain=.09, lines=.08, chroma=.002, line_noise=.10)
        common['broadcast'].update(field=.018, hue=.61, hue_spread=-.03, static=0., duration=0.,
            curve=.10, vignette=.9, drift=.25, screen=1., screen_inset=.04, screen_wear=.85,
            halo=2.6, halo_hue=.61, halo_radius=.05, halo_threshold=.25, rate=30.)
        common['tape'].update(tracking=.0006, jitter=.0002, chroma_delay=.0006, bleed=.001, head_switch=.02, dropouts=.015)
        common['frame_jitter'].update(x=.7, y=.6, rotation=.025, scale=.025, rate=30)
        common['low_res'].update(resolution=500)
    else: raise ValueError('Unknown text study')
    # All effect values are stored in the recipe so inspector ranges and section
    # overrides use the same values as the renderer.
    if 'drift' in common:
        values = common.pop('drift'); common['warp'] = {k.split('.')[1]: v for k,v in values.items()}
    fps = {'phosphor':24, 'pressure':30, 'transmission':20, 'night':30}[look]
    settings = {'speed': 1., 'depth': 0., 'treatment_fps': 12 if look == 'phosphor' else fps}
    if look == 'night': settings['object_y'] = 36.
    if look == 'transmission': settings['object_x'] = 0.
    for module, changes in common.items():
        settings.update({f'{module}.{spec.key}': spec.default for spec in MODULE_BY_ID[module].params})
        settings.update({f'{module}.{key}': value for key, value in changes.items()})
    source = normalize_sequence(dict(schema_version=1, render_version=2, name=name, duration=duration, fps=fps, seed=2826,
        canvas={'width': 720, 'height': 424 if look == 'phosphor' else 504 if look == 'transmission' else 540, 'framing': 'native'},
        states={'title': {'preset': 'Reference blinds', 'enabled': list(common), 'overrides': settings}},
        cues=[{'time': 0., 'state': 'title', 'transition': 'cut'}]))
    def variant(name, changes):
        source['states'][name] = copy.deepcopy(source['states']['title'])
        source['states'][name]['overrides'].update(changes)

    if look == 'phosphor':
        variant('wash', {'broadcast.wash': .85, 'broadcast.field': .22, 'text.brightness':1.3})
        variant('green', {'broadcast.wash': .4, 'broadcast.hue': .40, 'text.hue':.20})
        for t, state, span in ((.8, 'wash', .16), (1.3, 'green', .08), (1.5, 'title', .16),
                               (2.08, 'wash', 0.), (2.16, 'title', 0.),
                               (3.6, 'wash', .16), (4.1, 'green', .08), (4.4, 'title', .16)):
            source['cues'].append({'time':t, 'state':state, 'transition':'morph' if span else 'cut', 'duration':span})
    if look == 'transmission':
        variant('red', {'text.copies':1, 'text.fit_width':.94, 'text.hue':.12, 'text.saturation':.05,
            'text.back_hue':.975, 'text.back_brightness':.43, 'text.back_saturation':.82,
            'broadcast.field':0., 'broadcast.outages':0., 'broadcast.halo':.5, 'object_x':0.})
        variant('cream', {'text.copies':3, 'text.fit_width':.94, 'object_x':0., 'text.hue':.90, 'text.saturation':.86, 'text.brightness':.48,
            'text.back_hue':.12, 'text.back_brightness':.82, 'text.back_saturation':.08,
            'broadcast.halo':0., 'broadcast.outages':0., 'broadcast.field':0.,
            'raster.chroma':.005, 'raster.grain':.025, 'raster.line_noise':.02, 'tape.tracking':.003, 'separation.amount':.003})
        variant('warm', {'text.hue':.07, 'broadcast.halo_hue':.19, 'broadcast.outages':0.})
        variant('magenta', {'text.hue':.91, 'broadcast.halo_hue':.09, 'broadcast.halo':.4, 'broadcast.outages':0.})
        variant('rupture', {'broadcast.outages':1., 'broadcast.halo':.12})
        source['cues'] = [{'time':t, 'state':state, 'transition':'cut'} for t, state in
            ((0.,'red'), (.20,'rupture'), (.25,'title'), (.35,'rupture'), (.45,'title'), (.55,'warm'), (.60,'magenta'), (.70,'rupture'), (.75,'title'), (.80,'rupture'), (.85,'title'), (.90,'rupture'), (.95,'title'),
             (1.10,'cream'), (1.30,'title'), (2.10,'red'), (2.35,'title'), (2.9,'warm'),
             (3.,'magenta'), (3.15,'title'), (3.65,'cream'), (3.90,'title'), (4.7,'warm'),
             (4.8,'title'), (5.4,'cream'), (5.7,'title'))]
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = {'phosphor':'Phosphor / drift / signal loss', 'pressure':'Recede / reverse',
        'transmission':'Words / echoes / interruption', 'night':'Quiet night signal'}[look]
    return normalize_composition(project)
