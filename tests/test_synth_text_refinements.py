"""Source-independent recording faults and portable refined text studies."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, render_synth_frame
from synth_broadcast import render_broadcast
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_text import text_layout
from test_synth_text import source, extent


def broadcast(**changes):
    p = {s.key:s.default for s in MODULE_BY_ID['broadcast'].params}
    return dict(p, **changes)


def test_pressure_keeps_its_approved_pixels():
    hashes = json.loads((Path(__file__).parent/'fixtures/text-pressure-v2-hashes.json').read_text())
    sequence = compile_composition(starter_composition('text-pressure'))
    for t, expected in hashes.items():
        assert hashlib.sha256(render_sequence_frame(sequence, float(t), (200,150)).tobytes()).hexdigest() == expected


def test_repeated_text_is_one_positionable_canvas_preserving_group():
    p = source(copies=3, copy_gap=.45, fit_width=.65)
    before = extent(render_synth_frame(p))
    assert before[2]-before[0] <= 400*.65 + 2
    p.update(resize_canvas(p, {'width':600,'height':800}))
    p.update(object_x=20.,object_y=-15.)
    assert extent(render_synth_frame(p)) == tuple(v+d for v,d in zip(before,(120,235,120,235)))


def test_long_repeated_type_on_masks_stay_bounded_and_stable():
    p = {s.key:s.default for s in MODULE_BY_ID['text'].params}
    p.update(content='W'*512, copies=6, copy_gap=3., reveal=2)
    early = text_layout(p, .7, 1., (720,540))
    late = text_layout(p, 18., 1., (720,540))
    assert max(early[0].size) <= 4096
    assert early[0].size == late[0].size and early[1:] == late[1:]


@pytest.mark.parametrize('changes', [dict(wash=.7),dict(static_style=1,outages=.7,sync_tear=.9),
                                    dict(halo=1.5,screen=1.)])
def test_new_wear_supports_video_and_bypasses_exactly(changes):
    p=source();p.update(width=120,height=90)
    for m in p['modules']:
        m['enabled']=m['id']=='broadcast'
        if m['id']=='broadcast': m['params'].update(changes)
    video=Image.new('RGB',(120,90),(5,15,40));video.paste((220,240,200),(40,30,80,60))
    first=render_synth_frame(p,time_seconds=.7,source_image=video)
    assert first.tobytes()!=video.tobytes()
    render_synth_frame(p,time_seconds=3.5,source_image=video)
    assert first.tobytes()==render_synth_frame(p,time_seconds=.7,source_image=video).tobytes()
    next(m for m in p['modules'] if m['id']=='broadcast')['params']['mix']=0.
    assert render_synth_frame(p,time_seconds=.7,source_image=video).tobytes()==video.tobytes()


def test_outage_timing_is_independent_of_resolution_and_optics():
    p=broadcast(field=0.,duration=0.,band=0.,outages=.35,static_style=1,curve=0.,vignette=0.)
    timelines=[]
    for shape, optics in [((60,80,3),{}),((90,150,3),{'screen':1.,'halo':2.})]:
        frames=[render_broadcast(np.zeros(shape,dtype=np.float32),dict(p,**optics),i/24,1,14) for i in range(30)]
        timelines.append([f.max()>.3 for f in frames])
    assert timelines[0]==timelines[1]
    assert 0 < sum(timelines[0]) < 30


@pytest.mark.parametrize('look', ['phosphor','transmission','night'])
def test_refined_studies_round_trip_with_custom_controls_and_preserve_first_versions(look,tmp_path):
    p=starter_composition('text-'+look)
    assert p != starter_composition('text-'+look+'-original')
    p['effects']['text']={'mode':'recipe','params':{'text.content':'SIGNAL NOW','text.copies':3}}
    p['effects']['broadcast']={'mode':'recipe','params':{'broadcast.wash':.35,'broadcast.screen':.4}}
    path=tmp_path/'study.json';save_composition(path,p)
    expected=render_sequence_frame(compile_composition(p),.6,(200,150))
    assert render_sequence_frame(compile_composition(load_composition(path)),.6,(200,150)).tobytes()==expected.tobytes()
