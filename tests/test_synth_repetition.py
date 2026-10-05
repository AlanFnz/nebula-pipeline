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
