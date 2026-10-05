"""Image-driven modulation remains opt-in, seekable and usable with every source."""
import copy

import numpy as np
import pytest
from PIL import Image

from synth import MODULES, MODULE_BY_ID, curated_presets, default_synth_preset, normalize_synth, render_synth_frame
from synth_composition import compile_composition, load_composition, save_composition
from synth_modulation import _row_sample, render_crt_capture, render_scan_modulation, signal_region
from synth_modulation_recipes import MODULATED_CRT_EFFECTS, modulated_crt_composition
from synth_sequence import render_sequence_frame
from synth_video import TREATMENTS, apply_treatment, video_composition
from test_synth_video import clip
from test_synth_video_ui import window

NEW_MODULES = ('scan_modulation','crt_capture')
RENDERERS = {'scan_modulation':render_scan_modulation,'crt_capture':render_crt_capture}


def params(module='scan_modulation',**changes):
    return dict({s.key:s.default for s in MODULE_BY_ID[module].params},**changes)


def apply(module,image,time=.21,speed=1.,seed=19,**changes):
    return RENDERERS[module](image,params(module,**changes),time,speed,seed,(image.shape[1],image.shape[0]))


def source_preset(source,*effects):
    p = default_synth_preset()
    p.update(width=120,height=90,speed=1.,depth=0.)
    for entry in p['modules']:
        entry['enabled'] = entry['id'] in (source,*effects)
    return p


@pytest.mark.parametrize('module',NEW_MODULES)
def test_mix_zero_is_exact_and_black_emits_no_light(module):
    image = np.random.default_rng(4).uniform(-.1,1.3,(69,97,3)).astype(np.float32)
    assert np.array_equal(apply(module,image,mix=0.),image)
    for time in (0.,.27,9.):
        assert not apply(module,np.zeros_like(image),time=time).any()
    if module == 'scan_modulation':
        assert not apply(module,np.zeros_like(image),key_invert=1,sparks=1.,spark_threshold=0.,black=0.).any()


@pytest.mark.parametrize('module',NEW_MODULES)
def test_seeking_is_deterministic_clocks_hold_and_speed_or_rate_zero_freezes(module):
    image = np.random.default_rng(7).random((69,97,3),dtype=np.float32)
    settings = dict(cadence=10.,rate=1.)
    times = (0.,.21,12.,.31,1.4)
    expected = {time:apply(module,image,time=time,**settings) for time in times}
    for time in reversed(times):
        assert np.array_equal(apply(module,image,time=time,**settings),expected[time])
    assert np.array_equal(expected[.21],apply(module,image,time=.29,**settings))
    assert not np.array_equal(expected[.21],expected[.31])
    assert not np.array_equal(expected[.21],apply(module,image,seed=20,**settings))
    assert np.array_equal(apply(module,image,time=0.,speed=0.),apply(module,image,time=12.,speed=0.))
    assert np.array_equal(apply(module,image,time=0.,rate=0.),apply(module,image,time=12.,rate=0.))
    assert not np.array_equal(apply(module,image,time=.211,cadence=0.),apply(module,image,time=.219,cadence=0.))


def test_luma_and_hue_keys_select_image_regions_and_invert_exactly():
    source = np.array([[(1.,0.,0.),(0.,1.,0.),(0.,0.,1.),(.5,.5,.5),(0.,0.,0.)]],dtype=np.float32)
    p = params(region=2,key_hue=0.,key_width=.04,key_floor=0.,key_softness=.01,key_saturation=.1)
    mask,luma = signal_region(source,p,(5,1))
    assert np.array_equal(mask,np.array([[1.,0.,0.,0.,0.]],dtype=np.float32))
    inverted,_ = signal_region(source,dict(p,key_invert=1),(5,1))
    assert np.array_equal(mask+inverted,np.ones_like(mask))
    highlight,_ = signal_region(source,dict(p,region=1,key_floor=.3,key_softness=.1),(5,1))
    assert np.array_equal(highlight,np.array([[0.,1.,0.,1.,0.]],dtype=np.float32))
    assert luma[0,1] > luma[0,0] > luma[0,2]
    # Red wraps across hue zero, so a hue selected near one also selects red.
    wrapped,_ = signal_region(source,dict(p,key_hue=.99),(5,1))
    assert np.array_equal(wrapped,mask)


@pytest.mark.parametrize('angle,axis',[(0.,0),(90.,1)])
def test_directional_fade_softly_limits_key_on_requested_canvas_axis(angle,axis):
    source = np.ones((80,80,3),dtype=np.float32)
    p = params(region=0,fade=1.,fade_start=.3,fade_width=.4,fade_angle=angle)
    mask,_ = signal_region(source,p,(80,80))
    line = mask[:,40] if axis == 0 else mask[40,:]
    assert line[0] == 1 and line[-1] == 0
    assert np.all(np.diff(line) <= 0)
    assert 0 < line[40] < 1
    assert np.array_equal(mask,mask[:,[40]].repeat(80,axis=1) if axis == 0 else mask[[40],:].repeat(80,axis=0))


def test_selection_view_and_unselected_pixels_use_original_image():
    image = np.zeros((48,80,3),dtype=np.float32)
    image[:,:40] = (1.,0.,0.)
    image[:,40:] = (0.,1.,0.)
    settings = dict(region=2,key_hue=0.,key_width=.04,key_floor=0.,key_softness=.01,
                    wave=0.,tear=0.,streak=0.,sparks=0.)
    output = apply('scan_modulation',image,**settings)
    assert np.array_equal(output[:,40:],image[:,40:])
    assert not np.array_equal(output[:,:40],image[:,:40])
    key = apply('scan_modulation',image,show_key=1,**settings)
    assert np.all(key[:,:40] == 1) and not key[:,40:].any()


@pytest.mark.parametrize('channels',[False,True])
def test_subpixel_rows_sample_black_outside_canvas_without_wrap(channels):
    image = np.tile(np.arange(1,6,dtype=np.float32),(3,1))
    if channels: image = np.repeat(image[...,None],3,axis=2)
    output = _row_sample(image,np.array([1.,-1.,.5],dtype=np.float32))
    scalar = output[...,0] if channels else output
    assert np.array_equal(scalar[0],np.array([0.,1.,2.,3.,4.]))
    assert np.array_equal(scalar[1],np.array([2.,3.,4.,5.,0.]))
    assert np.array_equal(scalar[2],np.array([0.,1.5,2.5,3.5,4.5]))
    assert not _row_sample(image,np.full(3,100.)).any()


def test_new_modules_append_to_existing_order_and_stay_off_in_old_documents():
    ids = [module.id for module in MODULES]
    assert ids[ids.index(NEW_MODULES[0]):ids.index(NEW_MODULES[1])+1] == list(NEW_MODULES)
    for preset in [default_synth_preset(),*curated_presets().values()]:
        assert all(not entry['enabled'] for entry in preset['modules'] if entry['id'] in NEW_MODULES)
        legacy = copy.deepcopy(preset)
        legacy['modules'] = [entry for entry in legacy['modules'] if entry['id'] not in NEW_MODULES]
        normalized = normalize_synth(legacy)
        assert [entry['id'] for entry in normalized['modules']] == [entry['id'] for entry in legacy['modules']]
        assert not any(entry['id'] in NEW_MODULES for entry in normalized['modules'])
    p = source_preset('slab')
    old = copy.deepcopy(p)
    old['modules'] = [entry for entry in old['modules'] if entry['id'] not in NEW_MODULES]
    assert render_synth_frame(old,time_seconds=.3).tobytes() == render_synth_frame(p,time_seconds=.3).tobytes()


@pytest.mark.parametrize('source',['text','slab'])
@pytest.mark.parametrize('effect',NEW_MODULES)
def test_generated_sources_support_both_effects(source,effect):
    p = source_preset(source,effect)
    output = render_synth_frame(p,time_seconds=.31)
    assert output.size == (120,90)
    assert output.tobytes() == render_synth_frame(p,time_seconds=.31).tobytes()
    next(entry for entry in p['modules'] if entry['id']==effect)['params']['mix'] = 0.
    assert output.tobytes() != render_synth_frame(p,time_seconds=.31).tobytes()


def test_scan_original_input_precedes_subject_cutout():
    p = source_preset('subject_cutout','scan_modulation')
    scan = next(entry for entry in p['modules'] if entry['id']=='scan_modulation')['params']
    scan.update(input=1,show_key=1,region=2,key_hue=0.,key_width=.05,key_floor=0.,key_softness=.01)
    cutout = next(entry for entry in p['modules'] if entry['id']=='subject_cutout')['params']
    cutout.update(silhouette=1.,paper=0.,background_detail=0.,shadow=0.,feather=0.)
    image = Image.new('RGB',(120,90),(255,0,0))
    mask = Image.new('L',(120,90),255)
    original_key = render_synth_frame(p,time_seconds=.31,source_image=image,source_mask=mask)
    assert np.asarray(original_key).min() == 255
    scan['input'] = 0
    current_key = render_synth_frame(p,time_seconds=.31,source_image=image,source_mask=mask)
    assert not np.asarray(current_key).any()


def test_generated_original_input_precedes_color_treatment():
    p = source_preset('text','chroma_print','scan_modulation')
    print_p = next(entry for entry in p['modules'] if entry['id']=='chroma_print')['params']
    print_p.update(mid_saturation=0.,white_saturation=0.,warm_color=0.)
    scan = next(entry for entry in p['modules'] if entry['id']=='scan_modulation')['params']
    scan.update(input=1,show_key=1,region=2,key_hue=0.,key_width=.5,key_floor=.2,key_softness=.01,key_saturation=.1)
    original = render_synth_frame(p,time_seconds=.31)
    scan['input'] = 0
    current = render_synth_frame(p,time_seconds=.31)
    assert np.asarray(original).max() > 0
    assert not np.asarray(current).any()


class SyntheticFrames:
    def frame(self,footage,time,edge=None):
        image = Image.new('RGB',(128,96),(0,0,0))
        image.paste((230,90,30),(20,12,100,84))
        return image

    def mask(self,footage,time,preset,mode,**kwargs):
        return Image.new('L',(preset['width'],preset['height']),255)


def test_video_recipe_roundtrip_and_treatment_preserve_media_clock(clip,tmp_path):
    before = copy.deepcopy(clip)
    project = modulated_crt_composition(clip)
    assert clip == before
    assert set(MODULATED_CRT_EFFECTS) <= set(project['effects'])
    provider = SyntheticFrames()
    seq = compile_composition(project)
    expected = render_sequence_frame(seq,.31,(120,80),frame_provider=provider)
    path = tmp_path/'modulated.json'
    save_composition(path,project)
    restored = load_composition(path)
    assert restored == project
    assert expected.tobytes() == render_sequence_frame(compile_composition(restored),.31,(120,80),frame_provider=provider).tobytes()
    source = video_composition(clip)
    source['footage'].update(x=17.,y=-8.,rotation=13.,zoom=1.3,motion_fps=6.,treatment_fps=12.)
    frozen = copy.deepcopy(source)
    index = next(i for i,(name,_) in enumerate(TREATMENTS) if name == 'Cyan / modulated CRT')
    treated = apply_treatment(source,index)
    assert source == frozen
    for key in ('footage','sections','canvas'):
        assert treated[key] == source[key]
    assert all(module in treated['effects'] for module in NEW_MODULES)


def test_native_effect_controls_edit_and_undo(window):
    from synth_effects import effect_preset
    project = copy.deepcopy(window.composition)
    for module in NEW_MODULES:
        project['effects'][module] = effect_preset(module)
    window.set_composition(project)
    effects = window.composer.effects_panel
    for module,key,value in [('scan_modulation','wave',42.),('scan_modulation','fade',.7),('crt_capture','moire',.4)]:
        effects.inspect_effect(module)
        control = effects.controls[f'{module}.{key}'].input
        before = control.value()
        control.setValue(value)
        assert window.composition['effects'][module]['params'][f'{module}.{key}'] == value
        window.undo_composition()
        assert effects.controls[f'{module}.{key}'].input.value() == before


@pytest.mark.parametrize('module',NEW_MODULES)
def test_partial_mix_blends_with_source_and_extreme_supported_controls_are_finite(module):
    image = np.random.default_rng(83).random((49,73,3),dtype=np.float32)
    full = apply(module,image,mix=1.)
    partial = apply(module,image,mix=.4)
    assert np.allclose(partial,image*.6+full*.4,rtol=1e-6,atol=1e-6)
    # Exercise simultaneous control limits, including reversed black/white
    # points, steep fades and large off-canvas displacement.
    for limit in ('minimum','maximum'):
        p = {spec.key:getattr(spec,limit) for spec in MODULE_BY_ID[module].params}
        p['mix'] = 1.
        if module == 'scan_modulation': p['show_key'] = 0
        result = RENDERERS[module](image,p,17.31,1.,19,(73,49))
        assert result.shape == image.shape
        assert np.isfinite(result).all()
