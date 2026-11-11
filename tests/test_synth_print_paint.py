import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication
from test_synth_effects_editor_integration import make_window
from synth import MODULE_BY_ID
from synth_print import render_print_surface
from synth_print_paint import paint_tick
from synth_blender_recipes import orbital_rings_composition, orbital_painted_composition
from synth_starters import starter_composition
from synth_composition import save_composition, load_composition


def settings(**values):
    return dict({p.key:p.default for p in MODULE_BY_ID['print_surface'].params},**values)


def test_legacy_print_modes_keep_their_recorded_pixels():
    # Recorded with the 0.93.0 renderer, including a black area for each stock.
    a=np.random.default_rng(42).random((73,91,3),dtype=np.float32);a[:25]=0
    expected=('7a6ec7a041cd794928c012b9facbf5a056a7f2a822273eff7b2813e207a53c13',
              '6a7557d06c1dbc9afdb34e1a22b331d425f5fbfbaa870d9b0ba56f007e3e2d41')
    for mode,digest in enumerate(expected):
        result=render_print_surface(a,settings(background_mode=mode),.4,1.,3)
        assert hashlib.sha256(np.uint8(np.clip(result,0,1)*255).tobytes()).hexdigest()==digest


def test_paint_is_random_access_held_looping_and_does_not_modify_input():
    a=np.random.default_rng(12).random((75,60,3),dtype=np.float32);before=a.copy()
    p=settings(surface=1,cadence=8,paint_period=7.5)
    first=render_print_surface(a,p,.001,1.,8)
    assert np.array_equal(first,render_print_surface(a,p,.05,1.,8))
    assert not np.array_equal(first,render_print_surface(a,p,.15,1.,8))
    render_print_surface(a,p,30.4,1.,8)
    assert np.array_equal(first,render_print_surface(a,p,7.501,1.,8))
    assert np.array_equal(first,render_print_surface(a,p,.001,1.,8))
    assert np.array_equal(render_print_surface(a,p,0.,0.,8),render_print_surface(a,p,100.,0.,8))
    assert np.array_equal(a,before)
    assert np.array_equal(a,render_print_surface(a,dict(p,mix=0),.1,1.,8))
    assert np.isfinite(first).all() and first.min()>=0 and first.max()<=1
    assert paint_tick(-.01,1,8,0)==-1


def test_paint_preserves_palette_and_changes_fill_as_well_as_contours():
    a=np.empty((180,144,3),np.float32);a[:]=(.18,.35,.48)
    a[35:145,30:114]=(.8,.15,.08)
    p=settings(surface=1,cadence=8,paint_drift=4,paint_registration=4,boil=1.)
    first=render_print_surface(a,p,0.,1.,8);second=render_print_surface(a,p,.2,1.,8)
    red=first[60:120,50:90].mean((0,1));blue=first[:25].mean((0,1))
    assert red[0]>red[1]*3 and blue[2]>blue[0]*1.8
    assert np.abs(first[60:120,50:90]-second[60:120,50:90]).mean()>.002
    assert np.abs(first[30:40,30:114]-second[30:40,30:114]).mean()>.01
    # Even narrow sources and controls at their extremes produce finite pixels.
    for shape in ((1,20,3),(20,1,3),(1,1,3)):
        out=render_print_surface(np.ones(shape,np.float32)*.5,dict(p,paint_drift=10,paint_outline_width=4),1e6,1.,8)
        assert out.shape==shape and np.isfinite(out).all()


def test_second_recipe_retains_first_scene_and_roundtrips(tmp_path):
    original=orbital_rings_composition();painted=orbital_painted_composition()
    root=Path(__file__).parents[1]
    assert original==json.loads((root/'presets/orbital-rings-v1.json').read_text())
    assert painted==starter_composition('orbital-rings')
    assert painted['source']==original['source']
    assert painted['sections']==original['sections']
    assert painted['effects']['print_surface']['params']['print_surface.surface']==1
    save_composition(tmp_path/'paint.json',painted)
    assert load_composition(tmp_path/'paint.json')==painted


def test_paint_controls_show_only_applicable_fields_and_support_undo(make_window,monkeypatch):
    import synth_blender_bridge as bridge
    monkeypatch.setattr(bridge,'render_frame',lambda p,a,size,**kw:Image.new('RGB',size))
    window=make_window(composition=orbital_painted_composition())
    before=copy.deepcopy(window.composition)
    panel=window.composer.effects_panel;panel.inspect_effect('print_surface')
    panel.show_all_controls.setChecked(True);QApplication.processEvents()
    assert panel.controls['print_surface.paint_wash'].isVisible()
    assert not panel.controls['print_surface.noise_floor'].isVisible()
    panel.controls['print_surface.paint_drift'].input.setValue(4.)
    assert window.composition['effects']['print_surface']['params']['print_surface.paint_drift']==4.
    window.undo_composition();assert window.composition==before
    panel.controls['print_surface.surface'].input.setCurrentIndex(0)
    QApplication.processEvents()
    assert panel.controls['print_surface.noise_floor'].isVisible()
    assert not panel.controls['print_surface.paint_wash'].isVisible()
    window.undo_composition();assert window.composition==before
