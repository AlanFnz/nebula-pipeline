"""Editable typography and optical treatment reconstructed from ref-20."""
import copy

from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


PAGES = (
    "HUH\nNOBODY'S\nTALL LIKE THIS\nTALKS LIKE THIS\nI'M BALD AS SHIT\nHUH\nWHOLE LOTTA PEOPLE\nIN HERE\nYOU CAN'T MISS\nI'M SIX FOOT SIX",
    "NOBODY'S UP LIKE THIS\nFUCKS LIKE THIS\nI WAS BROKE AS SHIT\nHUH\nWHOLE LOTTA PEOPLE\nIN HERE\nYOU CAN'T MISS YEAH\nPLEASE DON'T STARE",
)


def phosphor_scroll_composition():
    common = {
        'text': dict(content=PAGES[0], font=0, reveal=5, scroll_rate=0., scroll_position=0.,
                     size=.094, leading=.97, tracking=-.025, stretch_x=.72,
                     fit=1, fit_width=.94, saturation=0., brightness=.68, back_brightness=0.,
                     press_height=.035, press_width=.025, press_angle=1., press_baseline=.015),
        'curved_screen': dict(angle=20., curve=.48, center_x=.22, spacing=90., wear=.85, line_width=1.35,
                              grid=.38, grid_fade=.98, patina=.4, background=.115, grain=.065,
                              rate=1., drift=.65, vibration=1.35, flutter=2.4, breathing=.045, boil=.65),
        'signal_etch': dict(grain=.10, grain_size=.8, streak=2., erosion=.08, core=.85,
                            roughness=1.5, scatter=.22, spread_x=7., spread_y=8., pulse=0.,
                            organic=4.2, organic_scale=8., organic_rate=3.4,
                            glints=.8, glint_size=105., glint_rate=1.2),
        'crt_capture': dict(phosphor=.04, moire=.025, field=.1, bend=.4, softness=.75,
                            focus_drift=.2, exposure=0., flicker=.07, grain=.18,
                            halation=.85, radius=15., threshold=.4, cadence=24.),
        'bloom': dict(threshold=.64, radius=18., strength=.45),
    }
    settings = dict(speed=1., depth=0., treatment_fps=24, object_x=-28.)
    for module, values in common.items():
        settings.update({f'{module}.{s.key}': s.default for s in MODULE_BY_ID[module].params})
        settings.update({f'{module}.{key}': value for key, value in values.items()})
    states = {}; cues = []
    def cue(name, frame, page, position, transition=0):
        overrides = copy.deepcopy(settings)
        overrides.update({'text.content': PAGES[page], 'text.scroll_position': position})
        states[name] = dict(preset='Reference blinds', enabled=list(common), overrides=overrides)
        cues.append(dict(time=frame/24, state=name, transition='morph' if transition else 'cut', duration=transition/24))
    cue('Surface', 0, 0, 0.)
    for page, starts in enumerate(((8, 21, 39, 62, 78, 102, 121, 139, 168, 184),
                                   (218, 248, 271, 291, 307, 329, 344, 365))):
        if page: cue('Second stanza', 213, page, 0.)
        for line, start in enumerate(starts):
            cue(f'{page+1}.{line+1} {PAGES[page].splitlines()[line]}', start, page, float(line+1), 7)
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Text / phosphor scroll', duration=395/24, fps=24, seed=201117,
        canvas=dict(width=960, height=720, framing='native'), states=states, cues=cues))
    project = composition_from_sequence(source)
    split = 213/24
    project['phrases'] = {
        'first': dict(name='First stanza / rising lines', start=0., end=split),
        'second': dict(name='Second stanza / rising lines', start=split, end=395/24),
    }
    template = project['sections'][0]
    project['sections'] = [dict(copy.deepcopy(template), id=f'stanza-{i+1}', phrase=key,
                                duration=phrase['end']-phrase['start'])
                           for i, (key, phrase) in enumerate(project['phrases'].items())]
    project['effect_order'] = ['signal_etch', 'curved_screen', 'crt_capture', 'bloom']
    return normalize_composition(project)
