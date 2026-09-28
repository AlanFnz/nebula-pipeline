"""Readable repeats retain wording, reveal timing and existing saved layouts."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from synth import MODULE_BY_ID, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_sequence import _state_preset, render_sequence_frame
from synth_starters import starter_composition
from synth_text import text_layout, wrapped_text
from test_synth_text import extent


def params(**changes):
    return dict({s.key:s.default for s in MODULE_BY_ID['text'].params}, **changes)


def test_wrapping_preserves_words_and_explicit_blank_lines():
    assert wrapped_text('REVOLUTION IS NOW',5)[0]=='REVOL\nUTION\nIS\nNOW'
    assert wrapped_text('\nNOW\n\nIS NOW\n',5)[0]=='\nNOW\n\nIS\nNOW\n'
    text,mapping=wrapped_text('REVOLUTION',5)
    assert text=='REVOL\nUTION'
    assert mapping==(0,1,2,3,4,None,5,6,7,8,9)


def test_type_on_keeps_original_character_clock_and_stable_wrapped_bounds():
    p=params(content='REVOLUTION',wrap_columns=5,reveal=2,word_seconds=.1)
    frames=[text_layout(p,t,1,(720,504)) for t in (0,.51,.61,1.01)]
    assert len({m.size for m,_,_ in frames})==1
    assert len({(sx,sy) for _,sx,sy in frames})==1
    first_line,second_line=frames[1][0],frames[2][0]
    assert first_line.getbbox()[3] < first_line.height*.6
    assert second_line.getbbox()[3] > second_line.height*.8
    assert not frames[0][0].getbbox()


def test_wrapped_maximum_input_stays_within_eight_lines_and_bounded_masks():
    p=params(content='W'*512,wrap_columns=1,copies=6,copy_floor=.9,reveal=2)
    assert wrapped_text(p['content'],1)[0].count('\n')==7
    mask,_,_=text_layout(p,300,1,(720,504))
    assert max(mask.size)<=4096


def test_repeat_size_floor_reduces_duplicates_before_shrinking_type():
    p=params(content='REVOLUTION',font=1,size=.3,wrap_columns=5,leading=.96,copies=3,fit_width=.84)
    dense=text_layout(p,0,1,(720,504))
    readable=text_layout(dict(p,copy_floor=.92),0,1,(720,504))
    assert readable[0].width < dense[0].width
    assert readable[2] > dense[2]*1.5
    # With a single copy, the width bound still wins over the desired size.
    m,sx,_=text_layout(dict(p,copy_floor=1.,fit_width=.1),0,1,(720,504))
    assert m.width*sx <= 72.001


def test_all_lost_transmission_words_are_large_centered_and_canvas_preserving():
    seq=compile_composition(starter_composition('text-transmission'))
    p=_state_preset(seq,seq['cues'][0]['state']);p.update(width=360,height=252)
    for m in p['modules']: m['enabled']=m['id']=='text'
    text=next(m['params'] for m in p['modules'] if m['id']=='text')
    text.update(back_brightness=0.,saturation=0.,brightness=1.)
    for t in (0,.65,1.3):
        before=extent(render_synth_frame(p,time_seconds=t))
        rows=np.asarray(render_synth_frame(p,time_seconds=t)).max(axis=(1,2)) > 100
        edges=np.diff(np.pad(rows.astype(int),(1,1)))
        line_heights=np.where(edges==-1)[0]-np.where(edges==1)[0]
        assert len(line_heights)==1
        assert line_heights.min() >= 252*.30
        assert (before[0]+before[2])/2==pytest.approx(180,abs=3)
        assert (before[1]+before[3])/2==pytest.approx(126,abs=3)
    p.update(resize_canvas(p,{'width':540,'height':720}))
    after=extent(render_synth_frame(p,time_seconds=1.3))
    assert after==tuple(v+d for v,d in zip(before,(90,234,90,234)))


@pytest.mark.parametrize('look', ['phosphor','transmission','night'])
def test_prior_refinements_keep_their_saved_pixels(look):
    root=Path(__file__).resolve().parents[1]
    document=json.loads((root/'presets/text-studies-v2.json').read_text())['text-'+look]
    hashes=json.loads((root/'tests/fixtures/text-studies-v2-hashes.json').read_text())['text-'+look]
    seq=compile_composition(document)
    for t,expected in hashes.items():
        assert hashlib.sha256(render_sequence_frame(seq,float(t),(200,150)).tobytes()).hexdigest()==expected


def test_wrapping_controls_round_trip_with_custom_wording(tmp_path):
    p=starter_composition('text-transmission')
    p['effects']['text']={'mode':'recipe','params':{'text.content':'TRANSFORMATION IS HERE','text.wrap_columns':6,'text.copy_floor':.8}}
    path=tmp_path/'wrapped.json';save_composition(path,p)
    assert load_composition(path)==p
    seq=compile_composition(p)
    before=render_sequence_frame(seq,.45,(200,140))
    render_sequence_frame(seq,4.5,(200,140))
    assert render_sequence_frame(seq,.45,(200,140)).tobytes()==before.tobytes()
