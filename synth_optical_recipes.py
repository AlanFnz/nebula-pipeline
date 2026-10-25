"""Editable phrase study on dark optical stock."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def dark_print_composition():
    enabled = ('text', 'optical_print')
    settings = {'speed': 1., 'depth': 0., 'treatment_fps': 12}
    for module in enabled:
        settings.update({f'{module}.{p.key}': p.default for p in MODULE_BY_ID[module].params})
    settings.update({
        'text.content': 'REVOLUTION IS NOW', 'text.font': 1, 'text.weight': 900,
        'text.reveal': 4, 'text.reading_duration': 7.5, 'text.reading_final': 1.75,
        'text.reading_transition': .33, 'text.reading_breakup': 1.,
        'text.size': .48, 'text.fit_width': .88, 'text.tracking': .01,
        'text.saturation': 0., 'text.back_brightness': 0.,
        'optical_print.reading_clarity': 1.,
        'optical_print.damage': .6, 'optical_print.motion': 1.,
        'optical_print.grain': .09, 'optical_print.pale_ink': .85,
        'optical_print.cuts': 6., 'optical_print.reading_hold': .65,
        'optical_print.fragment_mix': 1., 'optical_print.fragment_typeface': 1,
        'optical_print.halation': .85, 'optical_print.spot': 1.,
    })
    sequence = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Text / dark optical print', duration=7.5, fps=12, seed=251026,
        canvas={'width': 956, 'height': 720, 'framing': 'native'},
        states={'print': {'preset': 'Reference blinds', 'enabled': list(enabled), 'overrides': settings}},
        cues=[{'time': 0., 'state': 'print', 'transition': 'cut'}]))
    project = composition_from_sequence(sequence)
    project['phrases']['custom']['name'] = 'Words / dark exposures / final phrase'
    return normalize_composition(project)
