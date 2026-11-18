import copy

import numpy as np
import pytest

from nebula.render.synth import default_synth_preset
from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.sources.synth_lattice import render_chromatic_lattice
from nebula.sources.synth_lattice_eye import EYE_KEYS, blink_opening
from nebula.documents.synth_lattice_recipes import watching_eye_composition, printed_orbit_composition, lattice_composition
from nebula.documents.synth_sequence import render_sequence_frame, resolve_sequence_frame
from nebula.documents.synth_starters import starter_composition


def params():
    preset = resolve_sequence_frame(compile_composition(watching_eye_composition()), 0)[-1]
    return next(m['params'] for m in preset['modules'] if m['id'] == 'chromatic_lattice')


def test_eye_is_opt_in_and_previous_recipes_and_pixels_stay_unchanged():
    assert starter_composition('printed-orbit') == printed_orbit_composition()
    assert starter_composition('chromatic-lattice') == lattice_composition()
    original = resolve_sequence_frame(compile_composition(printed_orbit_composition()), 0)[-1]
    p = next(m['params'] for m in original['modules'] if m['id'] == 'chromatic_lattice')
    legacy = {k: v for k, v in p.items() if k not in EYE_KEYS}
    arr = np.zeros((240,135,3), np.float32)
    for t in (0., 1.9, 2.1, 5.5):
        assert np.array_equal(render_chromatic_lattice(arr, p, t, original),
                              render_chromatic_lattice(arr, legacy, t, original))


def test_irregular_blink_is_periodic_controllable_and_has_fast_closure():
    p = params(); times = np.arange(0, 8, 1/240)
    values = np.array([blink_opening(t, p, 141126) for t in times])
    assert values.min() == 0 and values.max() == 1
    assert values == pytest.approx([blink_opening(t+8, p, 141126) for t in times], abs=1e-12)
    starts = times[np.flatnonzero(np.diff(values < .99, prepend=False) & (values < .99))]
    assert len(starts) == 3  # Two events, one with an extra blink.
    assert max(np.diff(starts)) > min(np.diff(starts))*3
    first = values[(times >= starts[0]) & (times < starts[0]+.5)]
    assert np.sum((first[:-1]-first[1:]) > .001) < np.sum((first[1:]-first[:-1]) > .001)
    assert blink_opening(2, dict(p, eye_blink_count=0, eye_opening=.4), 141126) == .4
    assert blink_opening(2, dict(p, eye_opening=0), 141126) == 0


def test_blink_cadence_holds_poses_and_keeps_fractional_cycles_periodic():
    p = params()
    legacy = {k:v for k,v in p.items() if k != 'eye_blink_fps'}
    for t in np.arange(0,8,1/120):
        assert blink_opening(t,p,141126) == blink_opening(t,legacy,141126)
    for fps in (6,8,12):
        stepped = dict(p,eye_blink_fps=fps,eye_blink_period=3.7,eye_blink_phase=.23)
        continuous = dict(stepped,eye_blink_fps=0,eye_blink_phase=0)
        changed = False
        for t in np.arange(0,3.7,1/120):
            value = blink_opening(t,stepped,141126)
            assert value == pytest.approx(blink_opening(t+3.7,stepped,141126),abs=1e-12)
            sample = np.floor(((t+.23*3.7)%3.7)*fps+1e-9)/fps
            assert value == blink_opening(sample,continuous,141126)
            changed |= value != blink_opening(t,dict(stepped,eye_blink_fps=0),141126)
        assert changed


def test_cadence_changes_only_the_eye_not_cells_or_texture():
    p=params();arr=np.zeros((256,144,3),np.float32)
    preset=dict(default_synth_preset(),width=144,height=256,seed=141126,speed=1.)
    differences=[]
    for t in (1.95,2.04,2.12,5.21,5.38):
        a=render_chromatic_lattice(arr,p,t,preset)
        b=render_chromatic_lattice(arr,dict(p,eye_blink_fps=6),t,preset)
        assert np.array_equal(a[:80],b[:80])
        assert np.array_equal(a[175:],b[175:])
        differences.append(np.max(abs(a-b)))
    assert max(differences)>.05


def test_overlay_preserves_cells_outside_eye_even_when_closed_and_clearance_is_ignored():
    from nebula.sources.synth_lattice import lattice_frame
    p = dict(params(), eye_placement=1, grain=0., softness=0., glow=0.)
    arr = np.zeros((256,144,3),np.float32)
    preset = dict(default_synth_preset(),width=144,height=256,seed=141126,speed=1.)
    center, spacing, _ = lattice_frame(p,(144,256),preset)
    yy,xx = np.mgrid[:256,:144]
    # The old reserve removes whole cells beyond the contour. Those surrounding
    # pixels must now match the uninterrupted lattice, for every eyelid pose.
    width = p['eye_size']*spacing
    outside = (abs(xx-center[0]) > width*.55) | (abs(yy-center[1]) > width*.32)
    for opening in (0.,.4,1.):
        values = dict(p, eye_blink_count=0, eye_opening=opening)
        overlay = render_chromatic_lattice(arr,values,2.1,preset)
        cells = render_chromatic_lattice(arr,dict(values,eye_enabled=0),2.1,preset)
        reserved = render_chromatic_lattice(arr,dict(values,eye_placement=0),2.1,preset)
        assert np.array_equal(overlay[outside],cells[outside])
        assert np.max(abs(reserved[outside]-cells[outside])) > .05
        assert np.max(abs(overlay-cells)) > .05
        assert np.array_equal(overlay,render_chromatic_lattice(arr,dict(values,eye_clearance=1.5),2.1,preset))


def test_missing_eye_placement_keeps_legacy_rendering():
    p=params(); arr=np.zeros((256,144,3),np.float32)
    legacy={k:v for k,v in p.items() if k != 'eye_placement'}
    preset=dict(default_synth_preset(),width=144,height=256,seed=141126,speed=1.)
    for t in (0.,2.04,2.12,5.38):
        assert np.array_equal(render_chromatic_lattice(arr,p,t,preset),
                              render_chromatic_lattice(arr,legacy,t,preset))


def test_eye_placement_ui_hides_unused_spacing_and_round_trips_with_undo(make_window,tmp_path):
    w=make_window(composition=watching_eye_composition()); c=w.composer; panel=c.object_panel
    c.look_tabs.setCurrentWidget(panel)
    original=copy.deepcopy(c.document)
    control=panel.controls['chromatic_lattice.eye_placement']
    assert control.input.currentText() == 'Leave space'
    assert 'chromatic_lattice.eye_clearance' in panel.object_eligible
    control.input.setCurrentIndex(1)
    changed=copy.deepcopy(c.document)
    assert 'chromatic_lattice.eye_clearance' not in panel.object_eligible
    assert 'chromatic_lattice.eye_size' in panel.object_eligible
    save_composition(tmp_path/'overlay.json',changed)
    assert load_composition(tmp_path/'overlay.json') == changed
    w.undo_composition(); assert c.document == original
    assert 'chromatic_lattice.eye_clearance' in panel.object_eligible
    w.redo_composition(); assert c.document == changed


def test_blink_cadence_ui_save_and_undo(make_window,tmp_path):
    from nebula.ui.synth_effect_parameter_ui import format_value
    w=make_window(composition=watching_eye_composition());c=w.composer
    control=c.object_panel.controls['chromatic_lattice.eye_blink_fps']
    original=copy.deepcopy(c.document)
    assert control.input.text()=='Timeline FPS'
    assert format_value(control.path,0)=='Timeline FPS'
    assert format_value(control.path,8)=='8 fps'
    control.input.setValue(8)
    changed=copy.deepcopy(c.document)
    assert changed['effects']['chromatic_lattice']['params'][control.path]==8
    save_composition(tmp_path/'cadence.json',changed)
    loaded=load_composition(tmp_path/'cadence.json')
    assert loaded==changed
    preset=resolve_sequence_frame(compile_composition(loaded),0)[-1]
    assert next(m['params'] for m in preset['modules'] if m['id']=='chromatic_lattice')['eye_blink_fps']==8
    w.undo_composition();assert c.document==original
    assert control.input.text()=='Timeline FPS'
    w.redo_composition();assert c.document==changed


def test_eye_study_round_trip_random_seeking_and_complete_loop(tmp_path):
    project = watching_eye_composition()
    assert starter_composition('watching-eye') == project
    save_composition(tmp_path/'eye.json', project)
    assert load_composition(tmp_path/'eye.json') == project
    s = compile_composition(project); size = (144,256)
    first = render_sequence_frame(s,0,size).tobytes()
    s['duration'] = 16
    assert render_sequence_frame(s,8,size).tobytes() == first
    before = render_sequence_frame(s,2.1,size).tobytes()
    render_sequence_frame(s,6.4,size)
    assert render_sequence_frame(s,2.1,size).tobytes() == before
    assert before != first


@pytest.mark.parametrize('size',[(144,256),(240,135),(192,192)])
def test_eye_extremes_keep_frames_finite_at_all_aspects(size):
    w,h = size; arr=np.zeros((h,w,3),np.float32)
    preset=dict(default_synth_preset(),width=w,height=h,speed=1.)
    p=params()
    for controls in (dict(eye_size=1,eye_opening=0),
                     dict(eye_size=7,eye_iris=1.35,eye_pupil=.85,eye_line=2),
                     dict(eye_blink_count=12,eye_blink_period=1,eye_blink_duration=1.5)):
        result=render_chromatic_lattice(arr,dict(p,**controls),2.06,preset)
        assert result.shape == arr.shape and np.isfinite(result).all()
        assert result.min() >= 0 and result.max() <= 1
    assert not arr.any()


def test_eye_controls_palette_and_undo_are_available(make_window):
    from PySide6.QtWidgets import QApplication
    w=make_window(composition=watching_eye_composition());c=w.composer;p=c.object_panel
    c.look_tabs.setCurrentWidget(p);QApplication.processEvents()
    original=copy.deepcopy(c.document)
    assert p.color_panel.active_keys == {'lattice_face_a','lattice_face_b','lattice_paper','lattice_eye','lattice_eye_ink'}
    assert 'chromatic_lattice.eye_blink_duration' in p.object_eligible
    assert 'chromatic_lattice.eye_pupil' in p.object_eligible
    assert 'Center eye' in p.object_groups and 'Eye blinking' in p.object_groups
    c.change_color('lattice_eye',(.21,.25,.92),None)
    changed=copy.deepcopy(c.document)
    assert changed['effects']['chromatic_lattice']['params']['chromatic_lattice.eye_light'] == .92
    w.undo_composition();assert c.document==original
    w.redo_composition();assert c.document==changed
    w.undo_composition()
    p.controls['chromatic_lattice.eye_enabled'].input.setCurrentIndex(0)
    assert 'chromatic_lattice.eye_pupil' not in p.object_eligible
    assert p.color_panel.active_keys == {'lattice_face_a','lattice_face_b','lattice_paper'}
    w.undo_composition();assert c.document==original


from test_synth_effects_editor_integration import make_window
