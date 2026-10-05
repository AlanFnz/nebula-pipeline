"""Signal folding stays opt-in, seekable, editable and source independent."""
import copy
import numpy as np
import pytest
from PIL import Image
from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_composition import compile_composition, save_composition, load_composition
from synth_effects import effect_preset
from synth_repetition import render_signal_repetition
from synth_repetition_recipes import temporal_fragments_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_video import TREATMENTS, apply_treatment, video_composition
from test_synth_video import clip
from test_synth_video_ui import window


def params(**changes):
    return dict({s.key:s.default for s in MODULE_BY_ID['signal_repetition'].params},**changes)


def image():
    y,x=np.mgrid[:64,:96].astype(np.float32)
    return np.stack((x/96,y/64,(x+y)/160),axis=2)


def render(p=None,t=.21,source=None):
    a=image() if source is None else source
    return render_signal_repetition(a,p or params(),t,1.,23,(a.shape[1],a.shape[0]))


def test_bypass_mix_and_empty_selection_preserve_pixels():
    a=image()
    assert render(params(mix=0.),source=a) is a
    full=render(source=a)
    assert np.allclose(render(params(mix=.4),source=a),a*.6+full*.4,atol=1e-6)
    assert np.array_equal(render(params(region=1,key_floor=.9),source=a*.05),a*.05)


def test_absolute_clocks_are_seekable_holdable_and_freezable():
    expected={t:render(t=t) for t in (0.,.1,3.,2.,.22)}
    for t in reversed(expected): assert np.array_equal(render(t=t),expected[t])
    assert not np.array_equal(expected[.1],expected[.22])
    assert np.array_equal(render(params(cadence=10.),.21),render(params(cadence=10.),.29))
    assert np.array_equal(render(params(rate=0.),0),render(params(rate=0.),12))
    assert not np.array_equal(render(t=.211),render(t=.219))


def test_key_and_outside_treatment_stay_scoped_and_input_is_untouched():
    a=image();before=a.copy()
    p=params(region=1,key_floor=.5,key_softness=.1)
    key=render(dict(p,show_key=1),source=a)[...,0]
    assert (key==0).any() and (key==1).any()
    result=render(p,source=a)
    assert np.array_equal(result[key==0],a[key==0])
    outside=render(dict(p,outside_mix=1.,outside_saturation=0.,outside_level=.4),source=a)
    assert np.allclose(outside[key==0],.4)
    assert np.array_equal(a,before)


@pytest.mark.parametrize('source',['slab','text'])
def test_generated_sources_and_disabled_legacy_rendering(source):
    preset=default_synth_preset();preset.update(width=96,height=64,depth=0.)
    for entry in preset['modules']: entry['enabled']=entry['id']==source
    legacy=copy.deepcopy(preset)
    legacy['modules']=[m for m in legacy['modules'] if m['id']!='signal_repetition']
    before=render_synth_frame(legacy,time_seconds=.21)
    assert before.tobytes()==render_synth_frame(preset,time_seconds=.21).tobytes()
    next(m for m in preset['modules'] if m['id']=='signal_repetition')['enabled']=True
    assert before.tobytes()!=render_synth_frame(preset,time_seconds=.21).tobytes()


@pytest.mark.parametrize('shape',[(1,1),(1,8),(8,1),(45,73)])
@pytest.mark.parametrize('limit',['minimum','maximum'])
def test_control_extremes_are_finite_on_any_canvas(shape,limit):
    p={s.key:getattr(s,limit) for s in MODULE_BY_ID['signal_repetition'].params}
    p.update(mix=1.,show_key=0,region=0)
    a=np.random.default_rng(31).random((*shape,3),dtype=np.float32)
    result=render(p,17.3,a)
    assert result.shape==a.shape and np.isfinite(result).all()


class Frames:
    def __init__(self): self.modes=[]
    def frame(self,*args,**kwargs): return Image.fromarray(np.uint8(image()*255))
    def mask(self,*args,**kwargs):
        self.modes.append(args[3]);m=Image.new('L',(96,64));m.paste(255,(32,0,96,64));return m


def test_foreground_is_optional_and_independent_of_cutout_mode(clip):
    project=video_composition(clip)
    project['canvas']=dict(width=96,height=64,framing='native')
    provider=Frames()
    clean=render_sequence_frame(compile_composition(project),.2,(96,64),provider)
    assert provider.modes==[]
    project['effects']['signal_repetition']=effect_preset('signal_repetition')
    project['effects']['signal_repetition']['params'].update({'signal_repetition.region':3})
    out=render_sequence_frame(compile_composition(project),.2,(96,64),provider)
    assert provider.modes==[0]
    assert np.array_equal(np.asarray(out)[:,:32],np.asarray(clean)[:,:32])
    project['effects']['subject_cutout']=effect_preset('subject_cutout')
    project['effects']['subject_cutout']['params']['subject_cutout.mode']=1
    provider.modes=[]
    render_sequence_frame(compile_composition(project),.2,(96,64),provider)
    assert provider.modes==[1,0]
    project['effects']['signal_repetition']['params']['signal_repetition.mix']=0.
    provider.modes=[]
    render_sequence_frame(compile_composition(project),.2,(96,64),provider)
    assert provider.modes==[1]


def test_recipe_round_trip_automations_and_source_treatment(clip,tmp_path):
    original=copy.deepcopy(clip)
    p=temporal_fragments_composition(clip)
    assert clip==original
    assert p['footage']['end_mode']=='hold'
    assert len(p['sections'])==1 and len(p['sections'][0]['automations'])==2
    seq=compile_composition(p)
    def spacing(t):
        return next(m for m in resolve_sequence_frame(seq,t)[-1]['modules'] if m['id']=='signal_repetition')['params']['spacing']
    assert spacing(0)>spacing(.3) and spacing(.67)>spacing(.3)
    path=tmp_path/'study.json';save_composition(path,p)
    restored=load_composition(path)
    assert restored==p
    provider=Frames()
    assert render_sequence_frame(seq,.2,(96,96),provider).tobytes()==render_sequence_frame(compile_composition(restored),.2,(96,96),provider).tobytes()
    clean=video_composition(clip)
    index=next(i for i,(name,_) in enumerate(TREATMENTS) if name=='Temporal fragments')
    treated=apply_treatment(clean,index)
    assert treated['footage']==clean['footage']
    assert treated['sections']==clean['sections']
    assert 'signal_repetition' in treated['effects']


def test_native_controls_edit_and_undo(window):
    p=copy.deepcopy(window.composition);p['effects']['signal_repetition']=effect_preset('signal_repetition')
    window.set_composition(p)
    panel=window.composer.effects_panel;panel.inspect_effect('signal_repetition')
    control=panel.controls['signal_repetition.spacing'].input
    before=control.value();control.setValue(53.)
    assert window.composition['effects']['signal_repetition']['params']['signal_repetition.spacing']==53.
    window.undo_composition()
    assert panel.controls['signal_repetition.spacing'].input.value()==before


def test_inspector_only_shows_relevant_selection_and_background_controls(window):
    p=copy.deepcopy(window.composition)
    p['effects']['signal_repetition']=effect_preset('signal_repetition')
    window.set_composition(p)
    panel=window.composer.effects_panel;panel.inspect_effect('signal_repetition')
    assert panel.controls['signal_repetition.key_hue'].isHidden()
    assert panel.controls['signal_repetition.outside_level'].isHidden()
    panel.controls['signal_repetition.region'].input.setCurrentIndex(2)
    assert not panel.controls['signal_repetition.key_hue'].isHidden()
    panel.controls['signal_repetition.region'].input.setCurrentIndex(3)
    assert panel.controls['signal_repetition.key_hue'].isHidden()
    assert not panel.controls['signal_repetition.key_invert'].isHidden()
    panel.controls['signal_repetition.outside_mix'].input.setValue(1.)
    assert not panel.controls['signal_repetition.outside_level'].isHidden()


@pytest.mark.parametrize('time,expected',[
    (0.,'bb356c7e1c4c1afffd964f2cfb22f48693bc4160269725977446d21b4887aeab'),
    (.21,'becc8b52a321fac9838281e037630b6c289a6bbea792cb95fcc1c1df75ca0e13'),
    (3.2,'69c8940a6e4375e128d5455b284fe86b22cf6cf4a1c3302ebc13a8d74ced1158'),
])
def test_neutral_motion_matches_v070_pixels(time,expected):
    import hashlib
    pixels=np.uint8(np.clip(render(t=time)*255,0,255))
    assert hashlib.sha256(pixels.tobytes()).hexdigest()==expected


def test_living_motion_seeks_holds_and_freezes_as_one_signal():
    p=params(band_flow=.85,sync_loss=.9,line_flutter=.85)
    expected={t:render(p,t) for t in (0.,.12,.24,.61,1.21,3.)}
    for t in reversed(expected): assert np.array_equal(render(p,t),expected[t])
    assert np.array_equal(render(dict(p,rate=0),0),render(dict(p,rate=0),99))
    assert np.array_equal(render(dict(p,cadence=10),.21),render(dict(p,cadence=10),.29))
    # The evolving signal must remain active on a completely still input.
    living=np.mean([np.abs(expected[b]-expected[a]).mean() for a,b in ((0.,.12),(.12,.24))])
    quiet=np.mean([np.abs(render(t=b)-render(t=a)).mean() for a,b in ((0.,.12),(.12,.24))])
    assert living > quiet*1.4


def test_unlock_events_are_irregular_bounded_and_continuous_at_windows():
    from synth_repetition import _sync_envelope
    times=np.arange(0,5,.005)
    values=np.array([_sync_envelope(t,1.4,23) for t in times])
    assert np.isfinite(values).all() and values.min()==0 and .7<values.max()<=1
    assert len(set(np.round(values[values>0],4)))>100
    for t in range(1,6):
        assert abs(_sync_envelope(t/1.4-1e-7,1.4,23)-_sync_envelope(t/1.4+1e-7,1.4,23))<1e-4
    assert all(_sync_envelope(t,0,23)==0 for t in times[::25])
    assert not np.array_equal(values,[_sync_envelope(t,1.4,24) for t in times])


def test_living_motion_does_not_pull_black_edges_into_the_canvas():
    a=np.full((72,48,3),.8,dtype=np.float32)
    p=params(band_flow=1.,sync_loss=1.,line_flutter=1.,outline_warp=40.,edge_echo=1.)
    for t in (0.,.3,.6,1.2):
        out=render(p,t,a)
        assert np.isfinite(out).all()
        assert (out.mean(axis=2)>.04).all()


def test_living_recipe_and_treatment_are_separate_from_original(clip,tmp_path):
    from synth_repetition_recipes import living_fragments_composition
    original=temporal_fragments_composition(clip)
    p=living_fragments_composition(clip)
    assert temporal_fragments_composition(clip)==original
    assert original['effects']['signal_repetition']['params']['signal_repetition.band_flow']==0
    assert p['effects']['signal_repetition']['params']['signal_repetition.band_flow']>0
    assert not p['sections'][0].get('automations')
    assert p['footage']==original['footage']
    assert resolve_sequence_frame(compile_composition(p),.2)[-1]['speed']==1.
    path=tmp_path/'living.json';save_composition(path,p)
    assert load_composition(path)==p
    index=next(i for i,(name,_) in enumerate(TREATMENTS) if name=='Living fragments')
    clean=video_composition(clip)
    treated=apply_treatment(clean,index)
    assert treated['sections']==clean['sections'] and treated['footage']==clean['footage']
    assert treated['effects']['signal_repetition']['params']['signal_repetition.sync_loss']>0


def test_living_controls_can_be_automated_and_undone(window):
    from synth_automation import target_parameter
    from synth_inspector import control_group
    p=copy.deepcopy(window.composition);p['effects']['signal_repetition']=effect_preset('signal_repetition')
    window.set_composition(p)
    panel=window.composer.effects_panel;panel.inspect_effect('signal_repetition')
    for key in ('band_flow','sync_loss','line_flutter'):
        path='signal_repetition.'+key
        assert target_parameter(path).maximum==1
        assert control_group(path)=='Motion & timing'
        panel.controls[path].input.setValue(.75)
        assert window.composition['effects']['signal_repetition']['params'][path]==.75
        window.undo_composition()
        assert panel.controls[path].input.value()==0
