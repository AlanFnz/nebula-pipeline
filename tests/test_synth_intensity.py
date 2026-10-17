"""Effect opacity is independent of authored settings, timing and scope."""
import copy

import numpy as np
import pytest
from PIL import Image

from synth import default_synth_preset, render_synth_frame
from synth_composition import blank_composition, compile_composition, save_composition, load_composition
from synth_effects import EFFECT_BY_ID, effect_preset, describe_effects
from synth_intensity import PATHS, SignalBranches, blend_pass, intensity_path
from synth_sequence import render_sequence_frame, resolve_sequence_frame


def project(effect, intensity=100):
    p = blank_composition()
    p['effects']['forms'] = effect_preset('forms')
    p['effects'][effect] = effect_preset(effect)
    p['effects'][effect]['params'][intensity_path(effect)] = intensity
    return p


def pixels(p, time=.42):
    return np.asarray(render_sequence_frame(compile_composition(p), time, (96, 72)))


@pytest.mark.parametrize('effect', [e for e in PATHS if e != 'subject_cutout'])
def test_zero_removes_contribution_and_full_matches_missing_default(effect):
    p = project(effect)
    full = pixels(p)
    del p['effects'][effect]['params'][intensity_path(effect)]
    assert np.array_equal(full, pixels(p))
    p['effects'][effect]['params'][intensity_path(effect)] = 0
    zero = pixels(p)
    p['effects'][effect]['mode'] = 'off'
    assert np.array_equal(zero, pixels(p)), effect


@pytest.mark.parametrize('effect', [e for e in PATHS if e != 'subject_cutout'])
def test_partial_intensity_is_deterministic_and_keeps_effect_settings(effect):
    p = project(effect, 37.5)
    before = copy.deepcopy(p)
    actual = pixels(p)
    assert np.array_equal(actual, pixels(p))
    assert p == before
    assert intensity_path(effect) in EFFECT_BY_ID[effect].paths
    info = describe_effects(compile_composition(p)['states'].values())[effect]
    assert info['ranges'][intensity_path(effect)] == (37.5, 37.5)


def test_stage_mix_precedes_the_next_effect_and_handles_in_place_renderers(monkeypatch):
    from synth import RENDERERS
    p = default_synth_preset()
    for m in p['modules']: m['enabled'] = m['id'] in ('flare', 'bloom')
    def in_place(image, *args): image[:] = .8
    monkeypatch.setitem(RENDERERS, 'flare', in_place)
    monkeypatch.setitem(RENDERERS, 'bloom', lambda image, *args: image**2)
    next(m for m in p['modules'] if m['id']=='flare')['params']['effect_intensity'] = 50
    result = np.asarray(render_synth_frame(p, size=(32,24)))
    expected = (np.array((.055,.067,.055),dtype=np.float32)*.5 + .4)**2
    assert np.array_equal(result[0,0], (expected*255).astype(np.uint8))
    dry = np.ones((2,2,3),dtype=np.float32)
    assert blend_pass(dry, 0, lambda _: pytest.fail('zero must skip work')) is dry


def test_compound_ghosts_blend_both_passes_once(monkeypatch):
    from synth import RENDERERS
    p = default_synth_preset()
    for m in p['modules']: m['enabled'] = m['id'] in ('slab','warp','smear')
    monkeypatch.setitem(RENDERERS,'slab', lambda im,p,*_: im + .2 + p['ghost_opacity']*.2)
    monkeypatch.setitem(RENDERERS,'warp', lambda im,*_: im**2)
    monkeypatch.setitem(RENDERERS,'smear', lambda im,*_: im+.1)
    ghost = next(m for m in p['modules'] if m['id']=='smear')['params']
    ghost['effect_intensity'] = 100
    wet = np.asarray(render_synth_frame(p,size=(32,24))).astype(float)
    ghost['effect_intensity'] = 0
    dry = np.asarray(render_synth_frame(p,size=(32,24))).astype(float)
    ghost['effect_intensity'] = 50
    half = np.asarray(render_synth_frame(p,size=(32,24))).astype(float)
    assert np.max(np.abs(half-(wet+dry)/2)) <= 1
    assert not np.array_equal(wet, dry)


def test_overlapping_compound_effects_keep_independent_dry_paths():
    s = SignalBranches(np.array([.2],dtype=np.float32))
    s.begin('ghosts',.4); s.apply(lambda x,o:x if 'ghosts' in o else x+.1)
    s.begin('broadcast',.3); s.apply(lambda x,o:x if 'broadcast' in o else 1-x)
    s.apply(lambda x,o:x*x)
    s.end('ghosts'); s.end('broadcast')
    expected = .7*(.6*.2**2+.4*.3**2)+.3*(.6*.8**2+.4*.7**2)
    assert s.result()[0] == pytest.approx(expected)


@pytest.mark.parametrize('early',[0,1])
def test_broadcast_zero_removes_early_exposure_and_late_screen(early):
    p = project('broadcast',0)
    p['effects']['broadcast']['params'].update({'broadcast.reverse_stage':early,'broadcast.reverse':.9,'broadcast.edge_fringe':.5})
    zero=pixels(p)
    p['effects']['broadcast']['mode']='off'
    assert np.array_equal(zero,pixels(p))


def test_low_res_mixes_complete_renders_including_master_and_overlays():
    p=project('low_res'); p['effects']['low_res']['params']['low_res.resolution']=180
    seq=compile_composition(p)
    seq['cues'][0].update(transition='flash', duration=1., intensity=.4)
    seq['field'].update(cloud_strength=.12,cloud_start=0.)
    def render(strength):
        branch=copy.deepcopy(seq)
        for state in branch['states'].values(): state['overrides']['low_res.effect_intensity']=strength
        return render_sequence_frame(branch,.2,(300,200))
    dry,wet=render(0),render(100)
    assert dry.tobytes()!=wet.tobytes()
    assert render(35).tobytes()==Image.blend(dry,wet,.35).tobytes()


def test_cutout_zero_does_not_require_a_mask_and_half_restores_original_pixels():
    p=default_synth_preset()
    for m in p['modules']: m['enabled']=m['id']=='subject_cutout'
    params=next(m for m in p['modules'] if m['id']=='subject_cutout')['params']
    source=Image.new('RGB',(48,32),(120,160,200))
    params['effect_intensity']=0
    assert render_synth_frame(p,size=source.size,source_image=source).tobytes()==source.tobytes()
    mask=Image.new('L',source.size,0)
    params['effect_intensity']=100
    wet=render_synth_frame(p,size=source.size,source_image=source,source_mask=mask)
    params['effect_intensity']=50
    half=render_synth_frame(p,size=source.size,source_image=source,source_mask=mask)
    assert half.tobytes()==Image.blend(source,wet,.5).tobytes()


def test_scope_instances_automation_and_saved_roundtrip(tmp_path):
    p=project('tape',80)
    p['effects']['tape@2']=effect_preset('tape@2')
    p['effects']['tape@2']['params']['tape@2.effect_intensity']=25
    second=copy.deepcopy(p['sections'][0]); second['id']='second'
    p['sections'].append(second)
    p['sections'][0]['effects']['tape']={'mode':'recipe','params':{'tape.effect_intensity':40}}
    p['sections'][0]['automations']=[dict(id='fade',path='tape.effect_intensity',amount=-100,enabled=True,
        easing='smooth',start_fraction=0,attack_fraction=.1,hold_fraction=.2,recovery_fraction=.1)]
    seq=compile_composition(p)
    def values(t): return {m['id']:m['params'].get('effect_intensity') for m in resolve_sequence_frame(seq,t)[-1]['modules']}
    duration=p['sections'][0]['duration']
    assert values(0)['tape']==40
    assert values(duration*.15)['tape']==0
    assert values(duration*.6)['tape']==40
    assert values(duration*1.5)['tape']==80
    assert values(duration*.15)['tape@2']==25
    save_composition(tmp_path/'mix.json',p)
    assert load_composition(tmp_path/'mix.json')==p
    p['effects']['tape']['bypassed']=True
    seq=compile_composition(p)
    assert not next(m for m in resolve_sequence_frame(seq,duration*.15)[-1]['modules'] if m['id']=='tape')['enabled']


@pytest.mark.parametrize('value',[-1,101,float('nan')])
def test_invalid_intensity_is_rejected(value):
    with pytest.raises(ValueError): compile_composition(project('bloom',value))


def test_ghost_companion_intensity_automates_when_smear_module_is_disabled():
    from synth_automation import apply_automations
    p=default_synth_preset()
    for m in p['modules']: m['enabled']=m['id']=='slab'
    event=dict(id='fade',path='smear.effect_intensity',amount=-70,enabled=True,
               easing='linear',start=0,attack=.1,hold=.5,recovery=.1)
    result=apply_automations(p,[event],.3)
    smear=next(m for m in result['modules'] if m['id']=='smear')
    assert not smear['enabled'] and smear['params']['effect_intensity']==30
    assert render_synth_frame(result,size=(96,72)).tobytes()!=render_synth_frame(p,size=(96,72)).tobytes()


def test_zero_diagnostic_points_to_intensity():
    from synth_effect_diagnostics import explain_effect
    p=project('broadcast',0)
    facts=explain_effect(p,compile_composition(p),'broadcast',0)
    assert any(f.code=='zero' and f.target=='broadcast.effect_intensity' for f in facts)
