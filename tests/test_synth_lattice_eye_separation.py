import copy

import numpy as np
import pytest

from synth import default_synth_preset
from synth_composition import compile_composition, load_composition, save_composition
from synth_lattice import render_chromatic_lattice
from synth_lattice_eye import blink_opening, render_eye
from synth_lattice_recipes import watching_eye_composition
from synth_lattice_relief import rgb
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from test_synth_lattice_eye_reveal import params
from test_synth_effects_editor_integration import make_window


def eye(p, t=0., size=360):
    return render_eye(np.full((size,size,3),.7,np.float32),p,t,
                      dict(seed=141126,speed=1.),(size/2,size/2),size/8,size/720)


def test_gap_defaults_off_and_does_not_change_reserved_or_disabled_eyes():
    arr=np.zeros((256,144,3),np.float32)
    preset=dict(default_synth_preset(),width=144,height=256,seed=141126,speed=1.)
    for placement in (0,1):
        p=params(eye_placement=placement,eye_reveal=1.,eye_blink_fps=6)
        legacy={k:v for k,v in p.items() if k!='eye_separation'}
        for t in (0.,2.,2.08,2.17,5.38):
            a=render_chromatic_lattice(arr,p,t,preset)
            assert np.array_equal(a,render_chromatic_lattice(arr,legacy,t,preset))
            if not placement:
                assert np.array_equal(a,render_chromatic_lattice(arr,dict(p,eye_separation=40.),t,preset))
        disabled=dict(p,eye_enabled=0)
        assert np.array_equal(render_chromatic_lattice(arr,disabled,2.,preset),
                              render_chromatic_lattice(arr,dict(disabled,eye_separation=40.),2.,preset))
    assert 'chromatic_lattice.eye_separation' not in watching_eye_composition()['source']['states']['orbit']['overrides']


def test_gap_uses_background_and_shrinks_with_the_lid_without_changing_eye_or_distant_cells():
    p=params(eye_placement=1,eye_size=5.7,eye_blink_count=0,eye_separation=12.)
    open_eye=eye(p); closed=eye(dict(p,eye_opening=0.))
    base=eye(dict(p,eye_separation=0.))
    # Whole drawing and center remain the original eye; surrounding lattice is local.
    assert np.array_equal(open_eye[170:190,170:190],base[170:190,170:190])
    assert np.array_equal(open_eye[:100],base[:100])
    assert np.array_equal(open_eye[250:],base[250:])
    # Above the outer ink crease the gap is paper, rather than a lighter outline.
    assert np.allclose(open_eye[112,180],rgb(p,'paper'))
    assert np.allclose(base[112,180],.7)
    # Closing releases the same position; no static ellipse remains behind.
    assert np.allclose(closed[112,180],.7)
    # Increasing the control widens the margin, not the eye itself.
    wider=eye(dict(p,eye_separation=28.))
    assert np.count_nonzero(np.max(abs(wider-base),axis=-1)>.01) > np.count_nonzero(np.max(abs(open_eye-base),axis=-1)>.01)
    assert np.array_equal(wider[170:190,170:190],open_eye[170:190,170:190])


def test_gap_scales_with_artwork_resolution():
    p=params(eye_placement=1,eye_size=5.7,eye_blink_count=0,eye_separation=12.)
    # Sample identical artwork positions away from antialiased edges.
    a=eye(p, size=360);b=eye(p,size=720)[::2,::2]
    assert np.allclose(a[112,180],b[112,180])
    assert np.allclose(a[108,180],b[108,180])
    assert np.allclose(a[112,180],rgb(p,'paper'))
    assert np.allclose(a[108,180],.7)


def test_reveal_covers_the_new_margin_during_a_held_blink_then_settles():
    p=params(eye_placement=1,eye_size=5.7,eye_separation=12.,eye_reveal=1.,
             eye_reveal_duration=.12,eye_blink_fps=6)
    start=next(t for t in np.arange(0,8,1/6) if blink_opening(t,p,141126)<.1)
    a=eye(p,start+.001);b=eye(dict(p,eye_reveal=0.),start+.001)
    # This row was only covered by the new contour margin, not the old open eye.
    assert np.max(abs(a[112]-b[112]))>.1
    assert np.array_equal(eye(p,start+.13),eye(dict(p,eye_reveal=0.),start+.13))
    assert np.array_equal(a[:100],b[:100])


@pytest.mark.parametrize('size',[(144,256),(256,144),(180,180)])
def test_gap_stays_local_finite_and_seek_independent_at_extremes(size):
    w,h=size;arr=np.zeros((h,w,3),np.float32)
    preset=dict(default_synth_preset(),width=w,height=h,seed=141126,speed=1.)
    p=params(eye_placement=1,eye_size=7.,eye_line=2.,eye_separation=200.,
             eye_reveal=1.,eye_blink_fps=6,eye_ripple=.8,eye_ripple_response=3,eye_ripple_glow=200.)
    a=render_chromatic_lattice(arr,p,2.1,preset)
    render_chromatic_lattice(arr,p,6.,preset)
    assert np.array_equal(a,render_chromatic_lattice(arr,p,2.1,preset))
    assert np.allclose(a,render_chromatic_lattice(arr,p,10.1,preset),atol=1e-5)
    assert np.isfinite(a).all() and a.min()>=0 and a.max()<=1


def test_gap_control_visibility_undo_and_saved_render(make_window,tmp_path):
    w=make_window(composition=watching_eye_composition());c=w.composer;panel=c.object_panel
    c.look_tabs.setCurrentWidget(panel)
    path='chromatic_lattice.eye_separation'
    assert path not in panel.object_eligible
    panel.controls['chromatic_lattice.eye_placement'].input.setCurrentIndex(1)
    assert path in panel.object_eligible
    before=copy.deepcopy(c.document)
    assert panel.controls[path].input.maximum()==200.
    panel.controls[path].input.setValue(80.)
    changed=copy.deepcopy(c.document)
    assert changed['effects']['chromatic_lattice']['params'][path]==80.
    save_composition(tmp_path/'gap.json',changed)
    loaded=load_composition(tmp_path/'gap.json');assert loaded==changed
    a,b=compile_composition(changed),compile_composition(loaded)
    preset=resolve_sequence_frame(b,0)[-1]
    assert next(m['params'] for m in preset['modules'] if m['id']=='chromatic_lattice')['eye_separation']==80.
    assert render_sequence_frame(a,2.1,(144,256)).tobytes()==render_sequence_frame(b,2.1,(144,256)).tobytes()
    w.undo_composition();assert c.document==before
    w.redo_composition();assert c.document==changed
    panel.controls['chromatic_lattice.eye_enabled'].input.setCurrentIndex(0)
    assert path not in panel.object_eligible
