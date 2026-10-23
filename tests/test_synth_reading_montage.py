import copy

import numpy as np
import pytest

from synth import MODULE_BY_ID, normalize_synth, render_synth_frame, default_synth_preset
from synth_composition import compile_composition, save_composition, load_composition
from synth_effects import effect_preset
from synth_film_print import render_print_collage
from synth_reading_montage import reading_beat, reading_schedule, film_reading_params, letters
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_text import text_layout, render_text


def defaults(module):
    return {s.key: s.default for s in MODULE_BY_ID[module].params}


def text_params(**changes):
    return dict(defaults('text'), reveal=4, **changes)


@pytest.mark.parametrize('text', ['REVOLUTION IS NOW', 'NEBULA', 'Árbol y C\u0327ielo',
                                 'We can change\nthe entire phrase', 'x '*256, '', '   '])
def test_semantic_schedule_shows_every_word_and_complete_finale(text):
    p = text_params(content=text)
    events, final, _ = reading_schedule(p)
    holds = [(a, b, word) for a, b, word, _, burst in events if not burst]
    assert [word for _, _, word in holds] == text.split()
    for a, b, word in holds:
        beat = reading_beat(p, (a+b)/2)
        assert beat.text == word and not beat.burst
    assert reading_beat(p, final).text == text
    assert reading_beat(p, 1000).text == text
    assert reading_beat(p, final).final
    for t in np.linspace(0, 7, 150):
        beat = reading_beat(p, t)
        if beat.burst and not beat.final:
            units = text.split() + [letter for word in text.split() for letter in letters(word)]
            assert beat.text in units


def test_duration_weights_zero_interruptions_and_loop_boundaries():
    p = text_params()
    holds = [b-a for a,b,_,_,burst in reading_schedule(p)[0] if not burst]
    assert holds[0] > holds[2] > holds[1]
    equal = [b-a for a,b,_,_,burst in reading_schedule(dict(p,reading_weight=0))[0] if not burst]
    assert max(equal)-min(equal) < 1e-9
    no_bursts = dict(p, reading_transition=0.)
    assert not any(reading_beat(no_bursts,t).burst for t in np.linspace(0,7,150))
    calm = dict(p, reading_breakup=0.)
    assert all(reading_beat(calm,t).text in p['content'].split()+[p['content']] for t in np.linspace(0,7,150))
    loop = dict(p, reading_loop=1)
    assert reading_beat(loop,.125) == reading_beat(loop,7.125)
    # Reserving too much finale never consumes the complete word phase.
    assert reading_schedule(dict(p,reading_final=30))[1] == pytest.approx(1.4)


@pytest.mark.parametrize('text', ['IS', 'REVOLUTION', 'REVOLUTION IS NOW', 'ÁRBOL\nY LUZ'])
def test_reading_layout_and_collage_preserve_complete_letter_bounds(text):
    p = text_params(content=text, size=.5, font=5, weight=700)
    mask,sx,sy = text_layout(p,6,1,(480,360))
    assert mask.width*sx <= 480*.94 and mask.height*sy <= 360*.65
    preset = default_synth_preset()
    arr = render_text(np.zeros((360,480,3),np.float32),p,6,preset)
    collage = dict(defaults('print_collage'), reading_layout=1., reading_reframe=1., start=.4,end=.5,
                   poster=1., echo=1., copies=3, width=2.,height=4.)
    output = render_print_collage(arr,collage,6,1,1,(480,360),reading_beat(p,6))
    # Bright ink remains wholly inside the margins despite hostile manual crops.
    ys,xs = np.nonzero(output.max(2)>.2)
    assert xs.min()>10 and xs.max()<470 and ys.min()>10 and ys.max()<350
    assert collage['start']==.4  # render does not mutate authored controls


def test_reading_protection_is_optional_and_keeps_optical_edits():
    p=defaults('film_burn'); beat=reading_beat(text_params(),1.)
    assert film_reading_params(p,beat) is p
    protected=dict(p,reading_clarity=1.)
    assert film_reading_params(protected,None) is protected
    quiet=film_reading_params(protected,beat)
    assert quiet['grain']==p['grain'] and quiet['paper_hue']==p['paper_hue']
    brighter=film_reading_params(dict(protected,exposure=p['exposure']*2),beat)
    assert brighter['exposure']==quiet['exposure']*2


def test_optical_motion_follows_word_and_finale_progress_without_mutation():
    p = text_params()
    holds = [(a,b) for a,b,_,_,burst in reading_schedule(p)[0] if not burst]
    for a,b in holds:
        assert reading_beat(p,a+(b-a)*.25).progress == pytest.approx(.25)
        assert reading_beat(p,a+(b-a)*.75).progress == pytest.approx(.75)
    assert reading_beat(p,6.).progress == pytest.approx(.5)
    assert reading_beat(p,70.).progress == 1.
    optical = dict(defaults('film_burn'), reading_clarity=1., reading_motion=1.)
    original = copy.deepcopy(optical)
    frames = [film_reading_params(optical,reading_beat(p,t)) for t in (.4,1.2,2.2)]
    assert max(f['leak_x'] for f in frames)-min(f['leak_x'] for f in frames) > .5
    assert max(f['reversal'] for f in frames)-min(f['reversal'] for f in frames) > .5
    assert all(f['opening']==1.1 for f in frames)  # no gate cuts in readable holds
    assert optical == original
    assert film_reading_params(optical,None) is optical
    off=dict(optical,reading_clarity=0.)
    assert film_reading_params(off,reading_beat(p,1.)) is off
    # User exposure overrides and palette continue to drive the result.
    baseline=film_reading_params(optical,reading_beat(p,1.))
    doubled=film_reading_params(dict(optical,exposure=optical['exposure']*2),reading_beat(p,1.))
    assert doubled['exposure']==pytest.approx(baseline['exposure']*2)


def test_motion_controls_zero_preserve_old_print_and_support_automation():
    from synth_automation import target_parameter
    from synth_reading_montage import collage_reading_params, reading_reframe
    beat=reading_beat(text_params(),1.)
    optical=dict(defaults('film_burn'),reading_clarity=1.)
    missing=dict(optical);missing.pop('reading_motion')
    a=film_reading_params(optical,beat);b=film_reading_params(missing,beat)
    a.pop('reading_motion')
    assert a==b
    collage=dict(defaults('print_collage'),reading_layout=1.)
    assert reading_reframe(collage,beat)==(1.,0.,0.)
    moving=dict(collage,reading_reframe=1.)
    assert reading_reframe(moving,None)==(1.,0.,0.)
    assert reading_reframe(moving,reading_beat(text_params(),.1))==(1.,0.,0.)
    assert reading_reframe(moving,beat)[0] < 1
    assert collage_reading_params(moving,beat)['copies']==1
    for path in ('film_burn.reading_motion','print_collage.reading_reframe'):
        assert target_parameter(path).default == 0.


def test_new_study_text_edit_seek_persistence_and_effect_intensity(tmp_path):
    p=starter_composition('text-reading-print')
    p['effects']['text']=effect_preset('text')
    p['effects']['text']['params']={'text.content':'OTRA FRASE COMPLETA'}
    original=copy.deepcopy(p)
    seq=compile_composition(p)
    images={t:render_sequence_frame(seq,t,(240,180)).tobytes() for t in (0.,.17,1.,3.,6.5)}
    for t in reversed(images): assert render_sequence_frame(seq,t,(240,180)).tobytes()==images[t]
    save_composition(tmp_path/'reading.json',p)
    saved=compile_composition(load_composition(tmp_path/'reading.json'))
    assert render_sequence_frame(saved,6.5,(240,180)).tobytes()==images[6.5]
    assert p==original
    # Reading-aware protection does not bypass the generic effect mix contract.
    preset=default_synth_preset()
    for m in preset['modules']:
        m['enabled']=m['id'] in ('text','film_burn')
        if m['id']=='text':m['params'].update(reveal=4,content='NEBULA')
        if m['id']=='film_burn':m['params'].update(reading_clarity=1.,effect_intensity=0)
    zero=render_synth_frame(preset,time_seconds=1,size=(240,180))
    next(m for m in preset['modules'] if m['id']=='film_burn')['enabled']=False
    assert render_synth_frame(preset,time_seconds=1,size=(240,180)).tobytes()==zero.tobytes()
