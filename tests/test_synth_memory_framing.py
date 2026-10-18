import copy

import numpy as np
import pytest

from synth_composition import compile_composition, load_composition, save_composition, stretch_section
from synth_memory import memory_frame
from synth_memory_framing import AMPLITUDES, center_path, edit_amplitude, motion_bounds
from synth_sequence import resolve_sequence_frame
from synth_starters import starter_composition


def project(**params):
    p=starter_composition('image-memory')
    p['effects']['image_memory']={'mode':'on','params':{'image_memory.'+k:v for k,v in params.items()}}
    return p


@pytest.mark.parametrize('path',range(3))
@pytest.mark.parametrize('shape',range(3))
def test_center_and_canvas_limits_balance_extremes_without_stretching(path,shape):
    p=project(path=path,shape=shape,amplitude_x=70.,amplitude_y=140.)
    p['geometry'].update(position_x=35.,position_y=-45.)
    old=copy.deepcopy(p)
    p=center_path(p);b=motion_bounds(p)
    for axis in range(2):
        assert b.midpoint(axis)==pytest.approx(b.size[axis]*.5,abs=1e-5)
    assert p['effects']==old['effects']
    assert center_path(p)==p
    for axis,key in enumerate(AMPLITUDES):
        other=motion_bounds(p).bounds(1-axis)
        p=edit_amplitude(p,key,10000.)
        b=motion_bounds(p);low,high=b.bounds(axis)
        assert 0<=low<.1 and b.size[axis]-.1<high<=b.size[axis]
        assert b.midpoint(axis)==pytest.approx(b.size[axis]*.5,abs=1e-5)
        assert b.bounds(1-axis)==pytest.approx(other)
        p=edit_amplitude(p,key,0.)
        b=motion_bounds(p)
        assert b.midpoint(axis)==pytest.approx(b.size[axis]*.5,abs=1e-5)
        assert np.ptp(b.centers[:,axis])<1e-5
    assert old['geometry']['position_x']==35.


def test_offset_path_limits_reach_nearest_edge_and_center_can_be_reapplied():
    p=center_path(project());p['geometry']['position_x']+=80.
    b=motion_bounds(p);center=b.midpoint(0)
    p=edit_amplitude(p,AMPLITUDES[0],10000.);b=motion_bounds(p)
    assert b.midpoint(0)==pytest.approx(center,abs=1e-5)
    assert b.bounds(0)[1]==pytest.approx(720,abs=.1)
    p=center_path(p);p=edit_amplitude(p,AMPLITUDES[0],10000.)
    assert motion_bounds(p).bounds(0)==pytest.approx((0,720),abs=.1)


def test_clip_scope_clocks_repeats_and_reframing_match_rendered_positions(tmp_path):
    p=project();second=copy.deepcopy(p['sections'][0]);second['id']='second'
    p['sections'].append(second);p['sections'][0]['loops']=2
    p=stretch_section(p,'second',8.,'effects')
    p['canvas']={'width':1080,'height':1920,'framing':'preserve','reference':{'width':720,'height':960,'framing':'native'}}
    p['geometry'].update(position_x=80.,position_y=-25.)
    p['sections'][1]['effects']['image_memory']={'mode':'recipe','params':{'image_memory.amplitude_x':35.}}
    before=copy.deepcopy(p)
    p=center_path(p,1);p=edit_amplitude(p,AMPLITUDES[1],10000.,1)
    assert p['sections'][0]==before['sections'][0]
    assert p['geometry']==before['geometry'] and p['effects']==before['effects']
    bounds=motion_bounds(p,1);seq=compile_composition(p)
    for i in (0,40,100):
        _,_,clock,_,_,_,_,base=resolve_sequence_frame(seq,30+i/24,normalized=True)
        params=next(m['params'] for m in base['modules'] if m['id']=='image_memory')
        assert bounds.centers[i]==pytest.approx(memory_frame(params,(1080,1920),clock,base)[0])
    assert bounds.midpoint(1)==pytest.approx(960.,abs=1e-5)
    assert bounds.bounds(1)==pytest.approx((0.,1920.),abs=.1)
    save_composition(tmp_path/'centered.json',p)
    assert load_composition(tmp_path/'centered.json')==p
    # A project amplitude edit leaves the explicit clip parameter in place.
    changed=edit_amplitude(p,AMPLITUDES[0],50.)
    assert changed['sections']==p['sections']


def test_stationary_and_oversized_sources_do_not_claim_a_false_limit():
    p=project(travel=0.)
    assert motion_bounds(p).maximum(0) is None
    p=center_path(p);assert motion_bounds(p).midpoint(0)==pytest.approx(360.)
    p=project(size=.6);assert motion_bounds(p).maximum(0) is None
    p['effects']['image_memory']['mode']='off'
    assert motion_bounds(p) is None
    assert center_path(p)==p


def test_style_changes_reuse_motion_analysis_and_existing_values_are_untouched():
    p=project(amplitude_x=200.,amplitude_y=200.)
    before=copy.deepcopy(p);bounds=motion_bounds(p)
    p['effects']['image_memory']['params']['image_memory.glow']=.8
    assert motion_bounds(p) is bounds
    p['effects']['image_memory']['params'].pop('image_memory.glow')
    assert p==before
