"""Irregular rolling noise stays independent, bounded and seekable."""
import copy
import numpy as np
from synth import MODULE_BY_ID
from synth_broadcast import _band_events, band_passes, irregular_band, render_broadcast
from synth_composition import compile_composition, load_composition, save_composition
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition


def params(**changes):
    return dict({s.key:s.default for s in MODULE_BY_ID['broadcast'].params},
                **dict(dict(band_motion=1,band=.08,static=.6,field=0.,duration=0.,curve=0.,vignette=0.),**changes))


def test_passes_have_irregular_gaps_and_independent_varied_traits():
    events=[cell+e[0] for cell in range(200) for e in _band_events(17,cell)]
    gaps=np.diff(events)
    assert .7 < gaps.mean() < 1.3
    assert gaps.min()<.2 and gaps.max()>3 and gaps.std()>.6
    p=params(band_interval=2.,band_travel=.7,band_variation=1.)
    samples=[list(band_passes(p,t,17)) for t in np.arange(0,40,.02)]
    assert any(not s for s in samples) and any(len(s)>1 for s in samples)
    passes=[event for sample in samples for event in sample]
    assert np.ptp([b[1] for b in passes])>.05
    assert np.ptp([b[2] for b in passes])>.3
    for t in (1.,4.,7.3,14.):
        assert list(band_passes(p,t,17))==list(band_passes(p,t,17))
    assert samples != [list(band_passes(p,t,18)) for t in np.arange(0,40,.02)]


def test_pass_enters_and_leaves_outside_screen_and_zero_variation_is_uniform(monkeypatch):
    monkeypatch.setattr('synth_broadcast._band_events',lambda seed,cell: ((.5,.8,.9,.2,.1,.6),) if cell==0 else ())
    rows=np.linspace(-1,1,501,dtype=np.float32)[:,None]
    p=params(phase=0.,band_interval=2.,band_travel=1.,band_variation=0.)
    assert not irregular_band(rows,p,1.,17).any()
    assert not irregular_band(rows,p,2.,17).any()
    before=irregular_band(rows,p,1.001,17)
    assert before.max()<.03
    assert list(band_passes(p,1.5,17))==[(0.,.08,1.)]
    assert irregular_band(rows,p,1.5,17).max()==1.
    assert not irregular_band(rows,dict(p,band=0.),1.5,17).any()
    p['band_variation']=1.
    # At full variation this chosen event moves upward, with a wider envelope.
    duration=1+.75*(2*.8-1)
    assert list(band_passes(p,1+duration*.25,17))[0][0]>0
    assert list(band_passes(p,1+duration*.75,17))[0][0]<0


def test_band_event_schedule_is_independent_of_texture_fps_and_resolution():
    p=params()
    rows=np.array([-.8,-.3,.1,.9],dtype=np.float32)[:,None]
    samples={t:irregular_band(rows,p,t,42) for t in (0.,.3,1.,3.,7.8,13.)}
    for t in reversed(samples):
        assert np.array_equal(samples[t],irregular_band(rows,dict(p,rate=3.,static_style=1),t,42))
        assert np.array_equal(samples[t],irregular_band(np.repeat(rows,3,axis=0),p,t,42)[::3])
    image=np.random.default_rng(1).random((30,40,3),dtype=np.float32)
    assert np.array_equal(render_broadcast(image,p,4.,.5,42),render_broadcast(image,p,2.,1.,42))
    assert np.array_equal(render_broadcast(image,p,4.,0.,42),render_broadcast(image,p,0.,1.,42))
    assert render_broadcast(image,dict(p,mix=0),2.,1.,42) is image


def test_long_time_work_is_bounded_and_output_finite(monkeypatch):
    calls=[]
    def events(seed,cell):
        calls.append(cell);return ((.5,.9,.9,.5,.8,.1),)
    monkeypatch.setattr('synth_broadcast._band_events',events)
    p=params(band_interval=.25,band_travel=12.,band_variation=1.,band=1.)
    rows=np.linspace(-1,1,50,dtype=np.float32)[:,None]
    for clock in (0.,1e6):
        calls.clear();mask=irregular_band(rows,p,clock,17)
        assert len(calls)<=86
        assert np.isfinite(mask).all() and 0<=mask.min()<=mask.max()<=1
    _band_events.cache_clear()
    for i in range(800): _band_events(1,i)
    assert _band_events.cache_info().currsize<=512


def test_new_band_settings_roundtrip_with_clip_override(tmp_path):
    p=starter_composition('image-memory');p['sections'].append(copy.deepcopy(p['sections'][0]));p['sections'][1]['id']='second'
    p['effects']['broadcast']={'mode':'on','params':{'broadcast.band_motion':1,'broadcast.band_interval':2.3,'broadcast.band_travel':.8,'broadcast.band_variation':.9,'broadcast.band':.09,'broadcast.static':.4}}
    p['sections'][0]['effects']['broadcast']={'params':{'broadcast.band_interval':4.}}
    save_composition(tmp_path/'bands.json',p)
    seq=compile_composition(p);loaded=compile_composition(load_composition(tmp_path/'bands.json'))
    for t in (0.,.5,8.,15.5,23.):
        assert render_sequence_frame(seq,t,(72,96)).tobytes()==render_sequence_frame(loaded,t,(72,96)).tobytes()
