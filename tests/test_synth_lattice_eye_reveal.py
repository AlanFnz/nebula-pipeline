import copy

import numpy as np
import pytest

from synth import default_synth_preset
from synth_composition import compile_composition, load_composition, save_composition
from synth_lattice import lattice_frame, render_chromatic_lattice
from synth_lattice_eye import blink_opening, render_eye
from synth_lattice_recipes import watching_eye_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame


def params(**changes):
    preset = resolve_sequence_frame(compile_composition(watching_eye_composition()), 0)[-1]
    p = next(m['params'] for m in preset['modules'] if m['id'] == 'chromatic_lattice')
    return dict(p, **changes)


def test_disabled_reveal_preserves_previous_pixels_in_every_placement():
    arr = np.zeros((256,144,3),np.float32)
    preset = dict(default_synth_preset(),width=144,height=256,seed=141126,speed=1.)
    for placement in (0,1):
        p = params(eye_placement=placement)
        legacy = {k:v for k,v in p.items() if not k.startswith('eye_reveal')}
        for t in (0.,2.,2.04,2.12,2.3,5.38):
            assert np.array_equal(render_chromatic_lattice(arr,p,t,preset),
                                  render_chromatic_lattice(arr,legacy,t,preset))
            if placement == 0:
                assert np.array_equal(render_chromatic_lattice(arr,p,t,preset),
                                      render_chromatic_lattice(arr,dict(p,eye_reveal=1.),t,preset))


def test_reveal_fills_in_during_held_blink_without_modifying_surroundings():
    # A uniform pigment isolates the reveal from the moving cell geometry.
    p = params(eye_placement=1,eye_reveal=1.,eye_reveal_duration=.12,
               eye_blink_fps=6,eye_size=5.7)
    preset = dict(seed=141126,speed=1.)
    source = np.full((360,360,3),.7,np.float32)
    center, spacing, unit = lattice_frame(p,(360,360),dict(preset,width=360,height=360))
    times = np.arange(0,8,1/6)
    start = next(t for t in times if blink_opening(t,p,141126) < .1)
    differences = []
    for delta in (.001,.04,.08,.13):
        a = render_eye(source.copy(),p,start+delta,preset,center,spacing,unit)
        b = render_eye(source.copy(),dict(p,eye_reveal=0.),start+delta,preset,center,spacing,unit)
        assert np.array_equal(a[:100], b[:100])
        assert np.array_equal(a[245:], b[245:])
        differences.append(float(np.sum(abs(a-b))))
        if delta == .04:
            # Fine grains give both visible and not-yet-visible pigment,
            # rather than uniformly fading the entire uncovered region.
            row = abs(a[157,:,0]-b[157,:,0])
            assert np.count_nonzero(np.diff(row>.03)) > 10
    assert differences[0] > differences[1] > differences[2] > differences[3]
    assert differences[-1] == 0
    for t in (0.,3.,7.):
        assert np.array_equal(render_eye(source.copy(),p,t,preset,center,spacing,unit),
                              render_eye(source.copy(),dict(p,eye_reveal=0.),t,preset,center,spacing,unit))


@pytest.mark.parametrize('fps',[0,6,12])
def test_reveal_is_periodic_seek_independent_and_respects_speed(fps):
    p = params(eye_placement=1,eye_reveal=1.,eye_blink_fps=fps,
               eye_blink_period=3.7,eye_blink_phase=.94)
    source=np.full((180,180,3),.7,np.float32)
    def frame(t,speed=1.):
        return render_eye(source.copy(),p,t,dict(seed=141126,speed=speed),(90,90),30.,.5)
    for t in (0.,.05,.15,.4,1.,2.06,3.69):
        a=frame(t)
        frame(t+.3)
        assert np.array_equal(a,frame(t))
        assert np.max(abs(a-frame(t+3.7))) < 1e-6
        assert np.array_equal(a,frame(t/2,2.))
        assert np.isfinite(a).all()


def test_reveal_saved_composition_renders_identically_after_reload(tmp_path):
    project = watching_eye_composition()
    overrides = project['effects'].setdefault('chromatic_lattice',{'mode':'recipe','params':{}})['params']
    overrides.update({'chromatic_lattice.eye_placement':1,'chromatic_lattice.eye_reveal':.85,
                      'chromatic_lattice.eye_reveal_duration':.14,'chromatic_lattice.eye_reveal_grain':2.})
    save_composition(tmp_path/'reveal.json',project)
    loaded = load_composition(tmp_path/'reveal.json')
    assert project == loaded
    a = compile_composition(project); b = compile_composition(loaded)
    for t in (0.,2.08,2.12):
        assert render_sequence_frame(a,t,(144,256)).tobytes() == render_sequence_frame(b,t,(144,256)).tobytes()


def test_reveal_controls_follow_overlay_and_are_undoable(make_window):
    w=make_window(composition=watching_eye_composition()); c=w.composer; panel=c.object_panel
    c.look_tabs.setCurrentWidget(panel)
    path='chromatic_lattice.eye_reveal'
    assert path not in panel.object_eligible
    panel.controls['chromatic_lattice.eye_placement'].input.setCurrentIndex(1)
    assert path in panel.object_eligible
    assert 'Eye reveal' in panel.object_groups
    original=copy.deepcopy(c.document)
    panel.controls[path].input.setValue(.9)
    changed=copy.deepcopy(c.document)
    assert changed['effects']['chromatic_lattice']['params'][path] == .9
    w.undo_composition(); assert c.document == original
    w.redo_composition(); assert c.document == changed
    panel.controls['chromatic_lattice.eye_enabled'].input.setCurrentIndex(0)
    assert path not in panel.object_eligible


from test_synth_effects_editor_integration import make_window
