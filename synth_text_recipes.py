"""Authoring recipes for the text studies; shipped copies are frozen in presets."""
import copy

from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


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
        common['text'].update(hue=.22, saturation=.42, brightness=.95, size=.15,
                              back_hue=.55, back_saturation=.85, back_brightness=.13)
        common['bloom'].update(radius=9., strength=1.3)
        common['raster'].update(softness=3.1, grain=.15, chroma=.034)
        common['broadcast'].update(field=.3, hue=.48, hue_spread=.19, phase=.18, drift=1.2)
    elif look == 'pressure':
        name = 'Text / pressure'
        common['text'].update(content='REVOLUTION\nIS NOW', font=1, size=.3, stretch_y=1.65, leading=.86, tracking=.01,
            hue=.025, saturation=.95, brightness=.98, back_brightness=.02,
            motion=1, zoom_start=1.1, zoom_end=.24, period=1.2, ease=1.5, cadence=24.)
        common['bloom'].update(radius=2., strength=.18)
        common['raster'].update(softness=.9, grain=.12, lines=.15, chroma=.02)
        common['broadcast'].update(field=0., static=0., duration=0., reverse=1., reverse_period=.6,
            reverse_hue=.025, reverse_saturation=.95, curve=.008, vignette=.18)
        common['drift'] = {'warp.amount': .025, 'warp.frequency': 1.8}
    elif look == 'transmission':
        name = 'Text / lost transmission'
        common['text'].update(font=2, reveal=1, word_seconds=.7, size=.25, hue=.48,
            saturation=.85, brightness=.9, back_brightness=.005, motion=2,
            zoom_start=1.04, zoom_end=.92, period=1.4)
        common['bloom'].update(radius=14., strength=1.4, threshold=.2)
        common['raster'].update(softness=4.8, lines=.12, grain=.10, chroma=.03)
        common['tape'].update(tracking=.032, jitter=.0015, chroma_delay=.014, bleed=.022, head_switch=.8)
        common['broadcast'].update(field=.055, static=.97, band=.025, duration=.17, period=1.4, phase=.43, curve=.02)
        common['separation'] = {'amount': .005, 'angle': .1, 'green': .15}
        common['smear'] = {'amount': .12, 'direction': -.8, 'ghosts': 2}
    elif look == 'night':
        name = 'Text / night monitor'
        common['text'].update(size=.037, hue=.57, saturation=.08, brightness=1.2,
                              back_hue=.65, back_saturation=.9, back_brightness=.027)
        common['bloom'].update(radius=8., strength=1.2, threshold=.25)
        common['raster'].update(softness=.8, grain=.08, lines=.10, chroma=.007, line_noise=.045)
        common['broadcast'].update(field=.04, hue=.64, hue_spread=-.06, static=0., duration=0.,
                                   curve=.16, vignette=.85, drift=.4)
        common['tape'].update(tracking=.001, jitter=.0002, chroma_delay=.0006, bleed=.002, head_switch=.1)
        common['frame_jitter'].update(x=.6, y=.5, rotation=.03, scale=.025, rate=24)
    else: raise ValueError('Unknown text study')
    # All effect values are stored in the recipe so inspector ranges and section
    # overrides use the same values as the renderer.
    if 'drift' in common:
        values = common.pop('drift'); common['warp'] = {k.split('.')[1]: v for k,v in values.items()}
    settings = {'speed': 1., 'depth': 0., 'treatment_fps': 24}
    for module, changes in common.items():
        settings.update({f'{module}.{spec.key}': spec.default for spec in MODULE_BY_ID[module].params})
        settings.update({f'{module}.{key}': value for key, value in changes.items()})
    source = normalize_sequence(dict(schema_version=1, render_version=2, name=name, duration=duration, fps=24, seed=2826,
        canvas={'width': 720, 'height': 540, 'framing': 'native'},
        states={'title': {'preset': 'Reference blinds', 'enabled': list(common), 'overrides': settings}},
        cues=[{'time': 0., 'state': 'title', 'transition': 'cut'}]))
    if look == 'phosphor':
        source['states']['wash'] = copy.deepcopy(source['states']['title'])
        state = source['states']['wash']; state['enabled'].append('flare')
        state['overrides'].update({f'flare.{s.key}': s.default for s in MODULE_BY_ID['flare'].params})
        state['overrides'].update({'flare.strength': .33, 'flare.spread': 1.5, 'flare.reach': 1.4,
                                  'flare.position_y': .3, 'flare.position_x': .45, 'flare.fringe': .05})
        for t, name, transition, span in ((.8, 'wash', 'morph', .2), (1.15, 'title', 'morph', .35),
                                          (3.9, 'wash', 'morph', .15), (4.2, 'title', 'morph', .25)):
            source['cues'].append({'time': t, 'state': name, 'transition': transition, 'duration': span})
    if look == 'transmission':
        source['states']['red'] = copy.deepcopy(source['states']['title'])
        source['states']['red']['overrides'].update({'text.hue': .05, 'text.saturation': .03,
            'text.back_hue': .965, 'text.back_brightness': .5, 'text.back_saturation': .82,
            'broadcast.field': .01, 'broadcast.band': 0.})
        source['cues'] = [{'time': t, 'state': name, 'transition': 'cut'} for t, name in
                         ((0., 'red'), (.21, 'title'), (2.8, 'red'), (3.01, 'title'))]
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = {'phosphor':'Phosphor / drift / signal loss', 'pressure':'Recede / reverse',
        'transmission':'Words / echoes / interruption', 'night':'Quiet night signal'}[look]
    return normalize_composition(project)
