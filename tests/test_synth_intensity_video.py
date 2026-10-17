import copy
import subprocess

import numpy as np
from PIL import Image

from synth import default_synth_preset
from synth_composition import compile_composition
from synth_effects import effect_preset
from synth_media import export_synth_video
from synth_sequence import render_sequence_frame
from synth_video import VideoFrameProvider, video_composition
from test_synth_video import clip


def test_video_cutout_zero_skips_mask_and_low_res_uses_both_resolutions(clip,monkeypatch):
    p=video_composition(clip)
    p['effects']['subject_cutout']=effect_preset('subject_cutout')
    p['effects']['subject_cutout']['params']['subject_cutout.effect_intensity']=0
    p['effects']['low_res']=effect_preset('low_res')
    p['effects']['low_res']['params']['low_res.resolution']=180
    with VideoFrameProvider() as provider:
        monkeypatch.setattr(provider,'mask', lambda *a,**kw: (_ for _ in ()).throw(AssertionError('zero should skip mask')))
        def render(strength):
            p['effects']['low_res']['params']['low_res.effect_intensity']=strength
            return render_sequence_frame(compile_composition(p),.25,(240,180),provider)
        dry,wet=render(0),render(100)
        assert dry.tobytes()!=wet.tobytes()
        assert render(40).tobytes()==Image.blend(dry,wet,.4).tobytes()
        bypass=render_sequence_frame(compile_composition(p),.25,(240,180),provider,True)
        assert np.abs(np.asarray(dry).astype(int)-np.asarray(bypass)).max()<=1


def test_export_matches_preview_through_an_intensity_gesture(clip,tmp_path):
    p=video_composition(clip); p['fps']=12
    p['effects']['chroma_print']=effect_preset('chroma_print')
    p['effects']['chroma_print']['params']['chroma_print.effect_intensity']=30
    p['sections'][0]['automations']=[dict(id='mix',path='chroma_print.effect_intensity',amount=70,
        enabled=True,easing='smooth',start_fraction=0,attack_fraction=.25,hold_fraction=.25,recovery_fraction=.25)]
    seq=compile_composition(p)
    output=export_synth_video(default_synth_preset(),tmp_path/'intensity.mp4',sequence=seq,size=(128,96))
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],check=True,capture_output=True).stdout
    frames=np.frombuffer(raw,dtype=np.uint8).reshape((-1,96,128,3))
    assert len(frames)==12
    with VideoFrameProvider() as provider:
        for frame in (0,4,8,11):
            preview=np.asarray(render_sequence_frame(seq,frame/12,(128,96),provider))
            assert np.abs(preview.astype(float)-frames[frame]).mean()<6
