"""Contact film is deterministic, portable and composes before screen finishes."""
import copy
import numpy as np
import pytest
from PIL import Image
from synth import MODULE_BY_ID, _seed, default_synth_preset, render_synth_frame
from synth_contact_print import render_contact_print
from synth_contact_recipes import contact_print_composition
from synth_composition import compile_composition, load_composition, save_composition
from synth_broadcast import render_broadcast
from synth_effects import effect_preset
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_starters import starter_composition


def test_study_roundtrip_authored_frames_and_seek_order(tmp_path):
    p=starter_composition('text-contact-film')
    assert p == contact_print_composition()
    save_composition(tmp_path/'study.json',p)
    s=compile_composition(load_composition(tmp_path/'study.json'))
    assert s['fps']==12 and s['duration']==8.
    assert s['canvas']['width']==956 and s['canvas']['height']==720
    assert len(s['cues'])==96
    originals={n:render_sequence_frame(s,n/12,(128,96)).tobytes() for n in (0,7,14,16,25,38,39,54,67,78,88,94)}
    for n in (94,88,78,67,54,39,38,14,7,25,0,16):
        assert render_sequence_frame(s,n/12,(128,96)).tobytes()==originals[n]
    assert set(originals[16])=={0}
    assert len(set(originals.values()))==12


def test_extended_cut_retains_reference_opening_and_does_not_loop():
    original=starter_composition('text-contact-film-original')
    assert original==contact_print_composition(extended=False)
    short=compile_composition(original)
    long=compile_composition(contact_print_composition())
    assert short['duration']==3.25
    for frame in range(39):
        assert render_sequence_frame(short,frame/12,(96,72)).tobytes()==render_sequence_frame(long,frame/12,(96,72)).tobytes()
    assert set(render_sequence_frame(long,95/12,(96,72)).tobytes())=={0}
    assert len(long['cues'])==96
    assert all(cue['transition']=='cut' for cue in long['cues'])


@pytest.mark.parametrize('source_kind',['text','video'])
@pytest.mark.parametrize('custom_order',[False,True])
def test_broadcast_treats_whole_contact_film(source_kind,custom_order):
    p=default_synth_preset()
    for m in p['modules']:
        m['enabled']=m['id'] in ('text','contact_print','broadcast')
        if m['id']=='broadcast':
            m['params'].update(field=0.,static=0.,curve=.25,vignette=0.,reverse=0.)
    if custom_order: p['effect_order']=['contact_print','broadcast']
    source=None
    if source_kind=='video':
        next(m for m in p['modules'] if m['id']=='text')['enabled']=False
        source=Image.new('RGB',(128,96),(180,70,50))
    dry=copy.deepcopy(p)
    next(m for m in dry['modules'] if m['id']=='broadcast')['enabled']=False
    t=.6
    pixels=np.asarray(render_synth_frame(dry,time_seconds=t,size=(128,96),source_image=source),np.float32)/255
    settings=next(m['params'] for m in p['modules'] if m['id']=='broadcast')
    expected=render_broadcast(pixels,settings,t,p['speed'],_seed(p['seed'],'broadcast'))
    actual=np.asarray(render_synth_frame(p,time_seconds=t,size=(128,96),source_image=source),float)
    assert np.max(abs(actual-np.clip(expected*255,0,255)))<2
    assert actual[:8,:8].max()==0


def test_badge_text_changes_render_without_reference_asset():
    p=contact_print_composition()
    s=compile_composition(p)
    a=render_sequence_frame(s,14/12,(192,144))
    for state in s['states'].values():
        state['overrides'].update({'text.content':'SIGNAL','text.badge_subtitle':'NEW IMPRESSION'})
    b=render_sequence_frame(s,14/12,(192,144))
    assert a.tobytes()!=b.tobytes()
    preset=resolve_sequence_frame(s,14/12)[-1]
    text=next(m for m in preset['modules'] if m['id']=='text')
    assert text['params']['badge_subtitle']=='NEW IMPRESSION'


@pytest.mark.parametrize('setting,value',[('opening',0),('opening',1.5),('gate_angle',180),('scale',.1),('scale',4),('grain_size',4),('shutter',1.5)])
def test_extreme_controls_finite_without_mutating_input(setting,value):
    settings={s.key:s.default for s in MODULE_BY_ID['contact_print'].params}
    settings[setting]=value
    source=np.random.default_rng(4).random((72,48,3),dtype=np.float32)
    saved=source.copy()
    result=render_contact_print(source,settings,1.25,1.,42,(48,72))
    assert np.array_equal(source,saved)
    assert result.shape==source.shape and np.isfinite(result).all()
    assert result.min()>=0 and result.max()<=1
    if setting=='opening' and value==0: assert not result.any()


def test_exposure_automation_offsets_the_authored_exposure():
    p=contact_print_composition()
    baseline=compile_composition(p)
    p['sections'][0]['automations']=[dict(id='light',path='contact_print.exposure',
        amount=.4,enabled=True,easing='smooth',start_fraction=0.,
        attack_fraction=0.,hold_fraction=.9,recovery_fraction=.1)]
    changed=compile_composition(p)
    def exposure(seq,t):
        return next(m['params']['exposure'] for m in resolve_sequence_frame(seq,t)[-1]['modules'] if m['id']=='contact_print')
    for t in (.4,1.,2.):
        assert exposure(changed,t)==pytest.approx(min(3.,exposure(baseline,t)+.4))
