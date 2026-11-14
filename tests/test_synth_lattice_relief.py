import copy
import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset
from synth_composition import compile_composition, load_composition, save_composition
from synth_lattice import render_chromatic_lattice
from synth_lattice_recipes import lattice_composition, printed_orbit_composition
from synth_lattice_relief import sweep_size, color_phase
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_starters import starter_composition


def params():
    preset = resolve_sequence_frame(compile_composition(printed_orbit_composition()), 0)[-1]
    return next(m['params'] for m in preset['modules'] if m['id']=='chromatic_lattice')


def test_portable_held_cadence_loop_and_previous_study(tmp_path):
    project = printed_orbit_composition()
    assert starter_composition('printed-orbit') == project
    assert starter_composition('chromatic-lattice') == lattice_composition()
    sequence = compile_composition(project)
    assert sequence['duration'] == 8 and sequence['fps'] == 24
    assert (sequence['canvas']['width'],sequence['canvas']['height']) == (720,1280)
    frame = lambda t: render_sequence_frame(sequence,t,(144,256)).tobytes()
    first = frame(0)
    assert frame(1/24) == first  # The reference holds each pose for two frames.
    assert frame(2/24) != first
    assert frame(1.5) != frame(2.5)
    assert frame(1.5) == frame(1.5)  # Random seeking cannot alter accumulated history.
    extended=copy.deepcopy(sequence);extended['duration']=16.
    assert render_sequence_frame(extended,8.,(144,256)).tobytes()==first
    # Resolve directly: the sequence player clamps timestamps to its duration.
    p=params();arr=np.zeros((256,144,3),np.float32)
    preset=dict(default_synth_preset(),width=144,height=256,speed=1.)
    assert np.max(abs(render_chromatic_lattice(arr,p,0,preset)-render_chromatic_lattice(arr,p,8,preset))) < 1e-5
    save_composition(tmp_path/'orbit.json',project)
    assert render_sequence_frame(compile_composition(load_composition(tmp_path/'orbit.json')),1.5,(144,256)).tobytes()==frame(1.5)


def test_angular_sweeps_have_independent_directions_periods_and_phases():
    p=params();x=np.array((1.,0.,-1.,0.));y=np.array((0.,1.,0.,-1.))
    # Largest cells advance right → bottom → left → top at quarter periods.
    for i in range(4): assert np.argmax(sweep_size(x,y,float(i),p)) == i
    assert sweep_size(x,y,1.,dict(p,sweep_direction=1)) == pytest.approx(sweep_size(x,y,3.,p))
    assert color_phase(x,y,1.,dict(p,color_direction=0)) == pytest.approx(color_phase(x,y,3.,p))
    assert color_phase(x,y,1.,dict(p,period=2.)) == pytest.approx(color_phase(x,y,1.,p))
    assert sweep_size(x,y,1.,dict(p,color_period=8.)) == pytest.approx(sweep_size(x,y,1.,p))
    assert np.all(sweep_size(x,y,2.,dict(p,pulse=0.))==1.)


@pytest.mark.parametrize('shape,sides',[(0,6),(1,6),(2,6),(3,3),(3,5),(3,12)])
def test_shapes_and_extreme_controls_stay_bounded(shape,sides):
    arr=np.full((135,240,3),.2,np.float32)
    preset=dict(default_synth_preset(),width=240,height=135)
    p=dict(params(),shape=shape,sides=sides,spacing=24.,size=1.,minimum=0.,rotation=39.,corner=0.)
    for t in (0.,1.3,3.9):
        result=render_chromatic_lattice(arr,p,t,preset)
        assert result.shape==arr.shape and np.isfinite(result).all()
        assert result.min()>=0 and result.max()<=1
    assert np.all(arr==np.float32(.2))
    assert render_chromatic_lattice(arr,dict(p,mix=0.),1.,preset) is arr


def test_new_surface_defaults_do_not_change_optical_rendering():
    from synth_lattice_relief import RELIEF_KEYS
    arr=np.full((96,128,3),.1,np.float32);preset=dict(default_synth_preset(),width=128,height=96)
    p={param.key:param.default for param in MODULE_BY_ID['chromatic_lattice'].params}
    for wave in (0,1,2):
        values=dict(p,wave_shape=wave,palette=wave)
        legacy={k:v for k,v in values.items() if k not in RELIEF_KEYS}
        assert np.array_equal(render_chromatic_lattice(arr,values,1.3,preset),render_chromatic_lattice(arr,legacy,1.3,preset))


def test_printed_palette_and_directions_are_editable_and_undoable(make_window):
    from PySide6.QtWidgets import QApplication
    from synth_blender_colors import color_spec
    w=make_window(composition=printed_orbit_composition());c=w.composer;p=c.object_panel
    c.look_tabs.setCurrentWidget(p);QApplication.processEvents()
    original=copy.deepcopy(c.document)
    assert p.color_panel.active_keys=={'lattice_face_a','lattice_face_b','lattice_paper'}
    assert 'chromatic_lattice.sweep_direction' in p.object_eligible
    assert 'chromatic_lattice.wavelength' not in p.object_eligible
    assert 'chromatic_lattice.palette' not in p.object_eligible
    key='lattice_face_a';ctx=c.color_context(key)
    assert ctx['scope_id'] is None and len(ctx['palette'])==3
    c.change_color(key,(.1,.8,.7),None)
    changed=c.document
    assert all(changed['effects']['chromatic_lattice']['params'][path]==value
               for path,value in zip(color_spec(key).paths,(.1,.8,.7)))
    w.undo_composition();assert c.document==original
    w.redo_composition();assert c.document==changed
    w.undo_composition()
    p.controls['chromatic_lattice.surface'].input.setCurrentIndex(0)
    assert not p.color_panel.active_keys
    assert 'chromatic_lattice.paper_hue' not in p.object_eligible
    w.undo_composition();assert c.document==original


from test_synth_effects_editor_integration import make_window
