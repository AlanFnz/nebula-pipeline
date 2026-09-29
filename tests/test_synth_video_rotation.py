"""Source rotation keeps uniform framing, masks and existing renders aligned."""
import hashlib
import math

import numpy as np
from PIL import Image, ImageDraw
import pytest

from synth_composition import compile_composition, load_composition, save_composition
from synth_video import (PROXY_EDGE, VideoFrameProvider, frame_on_canvas,
                         normalize_footage, relink_footage, video_composition)
from test_synth_video import clip
from test_synth_video_ui import window, wait_until


@pytest.mark.parametrize('fit,size,expected', [
    ('contain',(128,96),'72f85d798012b41a711d2e93b15072b4ff3827fc4bc29c838648dd0204488b3e'),
    ('contain',(65,49),'b7d072823bd9ab5be136a4d94735f27804b9ab9c7b89a02c8d1a21c90b7ceeac'),
    ('cover',(128,96),'a01338c479525c1ab3209308cd9ab0e88d77da2933dc7ea49faa7c658daf38b9'),
    ('cover',(65,49),'a00937f36aa50a635c426be1ff40b72d77db74e942e233d23e6df06caf77d9b6'),
    ('original',(128,96),'fde689293d21c7312c882eae9bb9715cdf1d85d85ad29d27b47035f5ed661df1'),
    ('original',(65,49),'e5410ed0ab92fc43368556b3955e46309b7effd2aa3ce22201f5c178e6a05e6d'),
])
def test_zero_and_missing_rotation_preserve_pre_change_pixels(fit,size,expected):
    # Golden outputs captured before the rotation branch was introduced.
    image = Image.fromarray(np.random.default_rng(67).integers(0,256,(size[1],size[0],3),dtype=np.uint8))
    footage = dict(width=128,height=96,fit=fit,zoom=1.23,x=13.,y=-8.)
    for settings in (footage,dict(footage,rotation=0.)):
        out = frame_on_canvas(image,settings,dict(width=123,height=211),(83,142))
        assert hashlib.sha256(out.tobytes()).hexdigest() == expected


def markers():
    image = Image.new('RGB',(128,96))
    draw = ImageDraw.Draw(image)
    draw.ellipse((54,38,73,57),fill='white')
    draw.rectangle((85,45,90,50),fill=(255,0,0))
    draw.rectangle((61,21,66,26),fill=(0,255,0))
    draw.rectangle((37,45,42,50),fill=(0,0,255))
    return image


@pytest.mark.parametrize('fit', ['contain','cover','original'])
@pytest.mark.parametrize('angle', [-90.,37.,90.])
def test_rotation_is_clockwise_uniform_and_moves_around_positioned_source_center(fit,angle):
    footage = dict(width=128,height=96,fit=fit,zoom=.7,x=11.,y=-13.,rotation=angle)
    canvas = dict(width=220,height=300)
    size = (220,300)
    arr = np.asarray(frame_on_canvas(markers(),footage,canvas,size))
    factor = min(220/128,300/96) if fit == 'contain' else max(220/128,300/96) if fit == 'cover' else 1.
    scale = factor*.7
    center = np.array((109.5+11,149.5-13))
    cosine,sine = math.cos(math.radians(angle)),math.sin(math.radians(angle))
    rotation = np.array(((cosine,-sine),(sine,cosine)))
    for channel,point in [(0,(24.,0.)),(1,(0.,-24.)),(2,(-24.,0.))]:
        mask = (arr[...,channel] > 200) & (np.delete(arr,channel,axis=2).max(axis=2) < 30)
        ys,xs = np.where(mask)
        assert len(xs) > 0
        expected = center+rotation @ np.array(point)*scale
        assert np.allclose((xs.mean(),ys.mean()),expected,atol=.65)
    ys,xs = np.where(arr.min(axis=2) > 200)
    assert abs(np.ptp(xs)-np.ptp(ys)) <= 1
    assert np.allclose((xs.mean(),ys.mean()),center,atol=.6)


def test_rotation_keeps_rounded_proxy_and_canvas_aspects_uniform():
    image = markers()
    proxy = image.resize((65,49),Image.Resampling.LANCZOS)
    footage = dict(width=128,height=96,fit='contain',zoom=1.2,x=15.,y=-9.,rotation=29.)
    for canvas in (dict(width=120,height=240),dict(width=240,height=120)):
        size = (canvas['width'],canvas['height'])
        centers = []
        for source in (image,proxy):
            arr = np.asarray(frame_on_canvas(source,footage,canvas,size))
            ys,xs = np.where(arr.min(axis=2) > 200)
            assert abs(np.ptp(xs)-np.ptp(ys)) <= 2
            centers.append((xs.mean(),ys.mean()))
        assert np.allclose(centers[0],centers[1],atol=.5)


def test_rotation_validation_relink_and_document_round_trip(clip,tmp_path):
    legacy = dict(clip)
    legacy.pop('rotation',None)
    assert normalize_footage(legacy)['rotation'] == 0
    assert relink_footage(legacy,clip)['rotation'] == 0
    for invalid in (-181.,181.,float('nan'),float('inf'),True,'15'):
        with pytest.raises(ValueError,match='rotation'):
            normalize_footage(dict(clip,rotation=invalid))
    p = video_composition(dict(clip,rotation=-14.5))
    p['footage'].update(x=18.,y=-9.,zoom=1.3,fit='cover')
    p['footage'] = relink_footage(p['footage'],clip)
    assert p['footage']['rotation'] == -14.5
    saved = tmp_path/'rotated.json'
    save_composition(saved,p)
    assert compile_composition(load_composition(saved)) == compile_composition(p)
    assert load_composition(saved)['footage']['rotation'] == -14.5


def test_rotation_reuses_decoder_but_invalidates_framed_mask_cache(clip,tmp_path,monkeypatch):
    calls = []
    def fake_mask(footage,*args):
        calls.append(footage.get('rotation',0.))
        return Image.new('L',(30,20),128)
    with VideoFrameProvider(preview=True,directory=tmp_path) as provider:
        source = provider.frame(clip,.25,96)
        count = provider.decode_count
        turned = dict(clip,rotation=15.)
        assert provider.frame(turned,.25,96).tobytes() == source.tobytes()
        assert provider.decode_count == count
        monkeypatch.setattr(provider,'_mask',fake_mask)
        for footage in (clip,clip,turned,turned,clip):
            provider.mask(footage,.25,dict(width=120,height=180),0)
        assert calls == [0.,15.]
    assert len(list(tmp_path.glob('*.mkv'))) == 1


def test_mask_detection_and_retention_receive_the_same_rotated_framing(clip,tmp_path,monkeypatch):
    import synth_cutout
    seen = []
    class Source:
        def frame(self,*args,**kwargs): return markers()
        def close(self): pass
    def fake_mask(image,*args,**kwargs):
        seen.append(image.copy())
        return image.convert('L')
    monkeypatch.setattr(synth_cutout,'subject_mask',fake_mask)
    # Retention must compare neighboring masks in the same transformed space.
    def retain(frame,mask,neighbors,strength):
        assert len(neighbors) == 2
        for adjacent,adjacent_mask in neighbors:
            assert adjacent.tobytes() == frame.tobytes()
            assert adjacent_mask.tobytes() == mask.tobytes()
        return mask
    monkeypatch.setattr(synth_cutout,'retain_mask',retain)
    footage = dict(clip,rotation=17.,fit='cover',zoom=1.1,x=5.,y=-8.)
    canvas = dict(width=120,height=180)
    ratio = PROXY_EDGE/180
    size = (round(120*ratio),PROXY_EDGE)
    expected = frame_on_canvas(markers(),footage,canvas,size)
    with VideoFrameProvider(directory=tmp_path) as provider:
        provider.mask_provider = Source()
        actual = provider.mask(footage,.5,canvas,0,retention=.5)
    assert len(seen) == 3
    assert all(image.tobytes() == expected.tobytes() for image in seen)
    assert actual.tobytes() == expected.convert('L').tobytes()


def test_native_source_rotation_control_is_global_and_undoable(window,tmp_path):
    panel = window.composer
    panel.duplicate_section()
    panel.select_section(1)
    panel.look_tabs.setCurrentWidget(panel.video_panel)
    control = panel.video_panel.controls['rotation']
    assert control.accessibleName() == 'Video Rotation'
    assert control.minimum() == -180 and control.maximum() == 180
    assert 'clockwise' in control.toolTip()
    control.setValue(14.5)
    assert window.composition['footage']['rotation'] == 14.5
    assert window.sequence['footage']['rotation'] == 14.5
    panel.select_section(0)
    assert control.value() == 14.5
    window.undo_composition()
    assert control.value() == 0
    window.redo_composition()
    assert control.value() == 14.5
    wait_until(lambda: not window.render_running and not window.render_queued)
    path = tmp_path/'rotation-ui.json'
    save_composition(path,window.composition)
    window.set_composition(load_composition(path))
    assert control.value() == 14.5
