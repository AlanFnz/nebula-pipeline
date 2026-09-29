"""Irregular exposure clocks stay ordered, seekable and compatible with old Studies."""
import copy
import hashlib

import numpy as np
import pytest

import synth_chroma
from synth import MODULE_BY_ID
from synth_chroma import fragment_mask, render_slice_echo, slice_clock, slice_envelope, slice_events
from synth_portrait_recipes import CRT_BARS_EFFECTS, UNSTABLE_CRT_EFFECTS, crt_bars_composition, unstable_crt_composition
from synth_video import TREATMENTS, apply_treatment, video_composition
from test_synth_video import clip
from test_synth_video_ui import window

CONTROLS = ('timing_scatter', 'motion_chaos', 'flash_scatter', 'flash_source')


def params(**changes):
    return dict({s.key:s.default for s in MODULE_BY_ID['slice_echo'].params}, **changes)


def render(image, p, time, speed=1., seed=31):
    return render_slice_echo(image,p,time,speed,seed,(image.shape[1],image.shape[0]))


@pytest.mark.parametrize('scatter', [.1,.9,1.])
def test_irregular_boundaries_are_ordered_and_durations_bounded(scatter):
    p = params(cadence=0.,period=.2,phase=.37,timing_scatter=scatter)
    starts = {}
    for time in np.linspace(-2,8,2001):
        tick,progress,elapsed,duration = slice_clock(p,time,1.,19)
        assert 0 <= progress < 1
        assert 0 <= elapsed < duration
        assert .2*(1-.9*scatter) <= duration <= .2*(1+.9*scatter)
        start = time-elapsed
        if tick in starts:
            assert start == pytest.approx(starts[tick])
        starts[tick] = start
        # Resolve each inferred boundary from both sides, including boundaries
        # that precede zero. No missing or duplicated event is permitted.
        assert slice_clock(p,start+1e-8,1.,19)[0] == tick
        assert slice_clock(p,start-1e-8,1.,19)[0] == tick-1
    ordered = sorted(starts.items())
    assert all(b[0] == a[0]+1 and b[1] > a[1] for a,b in zip(ordered,ordered[1:]))
    durations = np.diff([start for _,start in ordered])
    assert np.ptp(durations) > .02*scatter
    assert np.mean(durations) == pytest.approx(p['period'],abs=.005)


def test_arbitrary_seek_is_deterministic_and_all_clocks_hold_or_freeze():
    p = params(activity=1.,cadence=10.,period=.3,timing_scatter=.9,motion_chaos=.8,
               envelope=.2,flash_opacity=.8,flash_scatter=1.,width=.4,edge_breakup=.3)
    image = np.random.default_rng(19).random((57,81,3),dtype=np.float32)
    times = [-.51,.21,.29,2.4,90.,.31]
    expected = {t:render(image,p,t) for t in times}
    for t in reversed(times):
        assert np.array_equal(render(image,p,t),expected[t])
    assert np.array_equal(expected[.21],expected[.29])
    assert not np.array_equal(expected[.21],expected[.31])
    assert np.array_equal(render(image,p,0.,0.),render(image,p,90.,0.))
    assert slice_clock(p,.21,1.,31) == slice_clock(p,.29,1.,31)
    assert slice_events(p,.21,1.,31) == slice_events(p,.29,1.,31)
    assert slice_envelope(p,.21,1.,31) == slice_envelope(p,.29,1.,31)


def test_envelope_and_fragment_layout_share_irregular_event_boundaries():
    p = params(period=1.,cadence=0.,phase=0.,timing_scatter=1.,envelope=.2,
               activity=1.,travel=0.,width=.5,edge_breakup=.5)
    seed = 37
    _,_,elapsed,duration = slice_clock(p,2.5,1.,seed)
    start = 2.5-elapsed
    rows = ((np.arange(53,dtype=np.float32)+.5)/53)[:,None]
    mask = lambda t:fragment_mask(p,rows,71,53,.5,.4,t,1.,seed,0)
    first = start+.01*duration
    second = start+.99*duration
    assert slice_events(p,first,1.,seed) == slice_events(p,second,1.,seed)
    assert np.array_equal(mask(first),mask(second))
    assert not np.array_equal(mask(second),mask(start+duration+1e-8))
    for fraction in (.01,.1,.2,.5,.9,.99):
        edge = min(1.,fraction/.2,(1-fraction)/.2)
        assert slice_envelope(p,start+fraction*duration,1.,seed) == pytest.approx(edge*edge*(3-2*edge))


def test_turbulence_is_nonlinear_independent_per_bar_and_preserves_layout_rng():
    base = params(activity=1.,cadence=0.,period=1.,travel=0.,count=3)
    turbulent = dict(base,motion_chaos=1.)
    times = [.1,.2,.3]
    layouts = [slice_events(turbulent,t,1.,31) for t in times]
    legacy = slice_events(base,.1,1.,31)
    for layout in layouts:
        assert [event[1] for event in layout] == [event[1] for event in legacy]
        assert [event[4:] for event in layout] == [event[4:] for event in legacy]
    second_difference = np.array(layouts[0])[:,:4].astype(float)-2*np.array(layouts[1])[:,:4].astype(float)+np.array(layouts[2])[:,:4].astype(float)
    assert np.max(np.abs(second_difference[:,0])) > .001
    assert np.ptp(second_difference[:,0]) > .001
    assert layouts[0] == slice_events(turbulent,.1,1.,31)


@pytest.mark.parametrize('seconds', [.01,2.])
def test_irregular_flash_duration_is_capped_by_its_actual_interval(monkeypatch,seconds):
    p = params(cadence=0.,period=.11,timing_scatter=1.,motion_chaos=1.,
               flash_period=.3,flash_scatter=1.,flash_seconds=seconds,flash_opacity=.8)
    seed = 31
    flash_seed = int(np.random.SeedSequence((seed,1763)).generate_state(1)[0])
    flash_clock = dict(p,period=p['flash_period'],timing_scatter=p['flash_scatter'])
    calls = []
    def recording_pass(image, settings, time, speed, seed, size, source_arr=None):
        calls.append((settings,time,seed))
        return image
    monkeypatch.setattr(synth_chroma,'_render_slice_pass',recording_pass)
    image = np.zeros((2,2,3),dtype=np.float32)
    for time in np.linspace(.1,2.,20):
        tick,_,elapsed,interval = slice_clock(flash_clock,time,1.,flash_seed)
        duration = min(seconds,interval)
        start = time-elapsed
        calls.clear()
        render(image,p,start+duration*.5,seed=seed)
        assert len(calls) == 2
        flash,flash_time,actual_seed = calls[1]
        assert actual_seed == flash_seed
        assert flash['opacity'] == pytest.approx(p['flash_opacity']*.5)
        assert flash['motion_chaos'] == flash['travel'] == flash['envelope'] == 0
        assert slice_clock(flash,flash_time,1.,actual_seed)[0] == tick
        if duration < interval:
            calls.clear()
            render(image,p,start+duration+1e-8,seed=seed)
            assert len(calls) == 1
        else:
            calls.clear()
            render(image,p,start+interval+1e-8,seed=seed)
            assert len(calls) == 2
            assert calls[1][0]['opacity'] == pytest.approx(p['flash_opacity'],abs=1e-5)


@pytest.mark.parametrize('time,expected', [
    (.02,'0dc2d9107340a296063b7b5c4128fb6a6d43b097bdc12e72b5550bf8a9a905ab'),
    (.11,'2a1875e8a05b15c4811ae46521a020e3daef5390feffa4f13551aac4029b0342'),
    (.29,'5f006e450497408f35ffc5b8fd8ed4922d66cd1df6d9a7030333a477851c8083'),
    (1.37,'763d79be81cc022037f280521de6bef1f59930b710dbfd8778e3d3fb7448613e'),
])
def test_missing_or_zero_timing_controls_preserve_legacy_flash_pixels(time,expected):
    # Captured from 3535309 before optional timing and turbulence controls.
    p = params(activity=1.,count=4,cadence=0.,envelope=.2,flash_opacity=.7,
               flash_period=.3,flash_seconds=.14,width=.55,edge_breakup=.3)
    image = np.random.default_rng(912).random((67,93,3),dtype=np.float32)
    assert all(p[key] == 0 for key in CONTROLS)
    for settings in (p,{key:value for key,value in p.items() if key not in CONTROLS}):
        result = render(image,settings,time,.85,412)
        assert hashlib.sha256(result.tobytes()).hexdigest() == expected


def test_new_recipe_is_independent_and_source_treatment_preserves_framing(clip):
    frozen = copy.deepcopy(CRT_BARS_EFFECTS)
    old = crt_bars_composition(clip)
    new = unstable_crt_composition(clip)
    assert TREATMENTS[8][0] == 'Cyan / CRT bars'
    assert TREATMENTS[9][0] == 'Cyan / unstable CRT'
    assert old['sections'] == new['sections']
    assert 'tape' in new['effects']
    assert new['effects']['slice_echo']['params']['slice_echo.timing_scatter'] > 0
    assert new['effects']['slice_echo']['params']['slice_echo.flash_source'] == 1
    new['effects']['slice_echo']['params']['slice_echo.flash_opacity'] = 0
    assert CRT_BARS_EFFECTS == frozen
    assert unstable_crt_composition(clip)['effects']['slice_echo']['params']['slice_echo.flash_opacity'] > 0
    assert CRT_BARS_EFFECTS['slice_echo'] is not UNSTABLE_CRT_EFFECTS['slice_echo']
    project = video_composition(clip)
    project['footage'].update(x=19.,y=-31.,rotation=17.,zoom=1.2)
    treated = apply_treatment(project,9)
    for key in ('footage','sections','canvas'):
        assert treated[key] == project[key]
    assert apply_treatment(project,8)['effects']['slice_echo']['params']['slice_echo.timing_scatter'] == 0


def test_timing_and_turbulence_controls_edit_and_undo_in_native_inspector(window):
    panel = window.composer
    panel.apply_video_treatment(9)
    effects = panel.effects_panel
    effects.inspect_effect('slice_echo')
    for key,value in [('timing_scatter',.4),('motion_chaos',.8),('flash_scatter',.2)]:
        control = effects.controls[f'slice_echo.{key}'].input
        before = control.value()
        control.setValue(value)
        assert window.composition['effects']['slice_echo']['params'][f'slice_echo.{key}'] == value
        window.undo_composition()
        assert effects.controls[f'slice_echo.{key}'].input.value() == before


def test_original_source_flashes_recover_image_color_and_keep_bars_outside_patches(monkeypatch):
    seed = 31
    def fixed_events(settings, time, speed, event_seed):
        if event_seed == seed:
            return ((.5,3.,0.,0.,1.,True),)
        return ((.5,.4,0.,0.,1.,False),)
    monkeypatch.setattr(synth_chroma,'slice_events',fixed_events)
    p = params(activity=1.,count=1,cadence=0.,screen=0.,opacity=1.,envelope=0.,
               width=1.,height=3.,hue=0.,saturation=1.,color_mix=1.,exposure=0.,
               negative=0.,flash_opacity=1.,flash_seconds=.1,flash_period=.3,
               flash_count=1,flash_width=.4,flash_height=.4,flash_breakup=0.,flash_negative=0.)
    image = np.full((80,80,3),.5,dtype=np.float32)
    bars = render(image,dict(p,flash_opacity=0.),0.,seed=seed)
    combined = render(image,dict(p,flash_source=0),0.,seed=seed)
    original = render(image,dict(p,flash_source=1),0.,seed=seed)
    flash_seed = int(np.random.SeedSequence((seed,1763)).generate_state(1)[0])
    rows = ((np.arange(80,dtype=np.float32)+.5)/80)[:,None]
    flash = dict(p,width=p['flash_width'],edge_breakup=0.,period=p['flash_period'])
    mask = fragment_mask(flash,rows,80,80,.5,.4,0.,1.,flash_seed,0)
    outside = mask == 0
    inside = mask == 1
    assert outside.any() and inside.any()
    assert np.array_equal(original[outside],bars[outside])
    assert np.array_equal(combined[outside],bars[outside])
    assert np.all(original[inside,1] > .49)
    assert np.all(combined[inside,1] == 0)
    assert np.all(np.ptp(original[inside],axis=1) == 0)
    assert not np.array_equal(original,combined)
