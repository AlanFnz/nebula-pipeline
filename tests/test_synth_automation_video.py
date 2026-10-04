"""Gestures share the preview/export evaluator without moving source clocks."""
import copy
import json
import subprocess
import numpy as np
from synth import default_synth_preset
from synth_automation import absolute_event
from synth_composition import compile_composition, stretch_section
from synth_effects import effect_preset
from synth_media import export_synth_video
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_video import video_composition, inspect_video, VideoFrameProvider
from test_synth_video import clip
from test_synth_automation import gesture, project


def test_video_and_effects_resize_scales_gesture_only_once(clip):
    p=video_composition(clip); p['sections'][0]['automations']=[dict(gesture(),path='tape.pull',amount=.6)]
    p['effects']['tape']=effect_preset('tape',3)
    for mode in ('effects','video'):
        resized=stretch_section(p,p['sections'][0]['id'],2.,mode)
        seq=compile_composition(resized); event=seq['automations'][0]
        assert event['start']==.8
        assert event['attack']==.04 and event['recovery']==.12
        resolved=resolve_sequence_frame(seq,.84)[-1]
        assert next(m for m in resolved['modules'] if m['id']=='tape')['params']['pull'] > .59
        clean=copy.deepcopy(seq); clean.pop('automations')
        with VideoFrameProvider() as provider:
            for t in (.1,.7,1.,1.5):
                assert np.array_equal(render_sequence_frame(seq,t,(96,72),provider),render_sequence_frame(clean,t,(96,72),provider))
            assert not np.array_equal(render_sequence_frame(seq,.84,(96,72),provider),render_sequence_frame(clean,.84,(96,72),provider))
        assert resolve_sequence_frame(seq,.84)[2:4]==resolve_sequence_frame(clean,.84)[2:4]


def test_mp4_export_contains_gesture_at_original_duration_and_fps(tmp_path):
    p=project(); p['fps']=15
    p['effects']['tape']=effect_preset('tape',3)
    p['sections'][0]['automations']=[dict(gesture(),path='tape.pull',amount=.7)]
    seq=compile_composition(p)
    output=export_synth_video(default_synth_preset(),tmp_path/'pull.mp4',sequence=seq,size=(120,80))
    info=inspect_video(output)
    assert abs(info['duration']-10)<1/15 and info['fps']==15
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],check=True,capture_output=True).stdout
    frames=np.frombuffer(decoded,np.uint8).reshape(-1,80,120,3)
    assert len(frames)==150
    base=copy.deepcopy(seq); base.pop('automations')
    expected=np.asarray(render_sequence_frame(seq,4.2,(120,80))).astype(float)
    baseline=np.asarray(render_sequence_frame(base,4.2,(120,80))).astype(float)
    exported=frames[63].astype(float)
    assert np.abs(exported-expected).mean() < np.abs(exported-baseline).mean()/2
