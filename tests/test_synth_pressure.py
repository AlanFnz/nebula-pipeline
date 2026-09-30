"""Pressure refinement is opt-in; saved text looks keep their original pixels."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_broadcast import render_polarity
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_text import text_pose
from test_synth_text import source, extent


BASELINES = json.loads((Path(__file__).parent / 'fixtures/text-studies-v1-hashes.json').read_text())


@pytest.mark.parametrize('identifier', BASELINES)
def test_first_edition_text_studies_keep_captured_pixels(identifier):
    sequence = compile_composition(starter_composition(identifier if identifier.endswith('-original') else identifier + '-original'))
    for time, expected in BASELINES[identifier].items():
        image = render_sequence_frame(sequence, float(time), (200, 150))
        assert hashlib.sha256(image.tobytes()).hexdigest() == expected, (identifier, time)


def test_fill_block_is_explicit_and_canvas_resize_preserves_proportions():
    p = source(fit=2, block_width=.6)
    before = extent(render_synth_frame(p))
    assert before[2]-before[0] == pytest.approx(240, abs=2)
    assert before[3]-before[1] == pytest.approx(36, abs=2)
    p.update(resize_canvas(p, {'width':600,'height':800}))
    assert extent(render_synth_frame(p)) == tuple(v+d for v,d in zip(before,(100,250,100,250)))


def test_perspective_pullback_tracks_depth_and_its_independent_clock():
    p = {s.key:s.default for s in MODULE_BY_ID['text'].params}
    p.update(motion=3,zoom_start=2.,zoom_end=.5,period=1.,cadence=0.)
    assert text_pose(p,0.,1)[1] == 2.
    assert text_pose(p,.5,1)[1] == pytest.approx(.8)
    assert text_pose(p,1.,1)[1] == 2.
    assert text_pose(p,.2,.5) == text_pose(p,.1,1.)


def test_overlapping_exposures_keep_edges_and_random_seeking_is_exact():
    p = {s.key:s.default for s in MODULE_BY_ID['broadcast'].params}
    p.update(reverse=1.,reverse_phase=.75,reverse_period=.12,reverse_blend=1.,field_spread=.1)
    arr = np.zeros((100,120,3),dtype=np.float32);arr[15:85,40:80]=(1,.3,.15)
    assert render_polarity(arr,p,0,1) is arr
    mixed = render_polarity(arr,p,.03,1)
    cancelled = render_polarity(arr,dict(p,field_spread=0),.03,1)
    assert not np.array_equal(mixed,cancelled)
    render_polarity(arr,p,1.01,1)
    assert np.array_equal(mixed,render_polarity(arr,p,.03,1))


def test_early_polarity_treats_video_and_retains_finishing_noise():
    from PIL import Image
    p = default_synth_preset();p.update(width=120,height=90)
    for m in p['modules']:
        m['enabled'] = m['id'] in ('raster','broadcast')
        if m['id']=='broadcast':
            m['params'].update(field=0.,static=0.,curve=0.,vignette=0.,reverse=1.,reverse_stage=1)
    video = Image.new('RGB',(120,90),(50,25,10))
    before=render_synth_frame(p,time_seconds=0,source_image=video)
    assert np.asarray(before).std(axis=(0,1)).max() > 5
    for m in p['modules']:
        if m['id']=='broadcast':m['params']['mix']=0.
    bypass=render_synth_frame(p,time_seconds=0,source_image=video)
    for m in p['modules']:
        if m['id']=='broadcast':m['enabled']=False
    assert bypass.tobytes()==render_synth_frame(p,time_seconds=0,source_image=video).tobytes()


def test_refined_pressure_is_editable_and_round_trips(tmp_path):
    project = starter_composition('text-pressure')
    assert project != starter_composition('text-pressure-original')
    project['effects']['text']={'mode':'recipe','params':{'text.content':'VIVE AHORA','text.block_width':.5}}
    project['effects']['broadcast']={'mode':'recipe','params':{'broadcast.field_spread':.18,'broadcast.edge_fringe':.2}}
    path=tmp_path/'pressure.json';save_composition(path,project)
    expected=render_sequence_frame(compile_composition(project),.2,(180,135))
    assert expected.tobytes()==render_sequence_frame(compile_composition(load_composition(path)),.2,(180,135)).tobytes()
