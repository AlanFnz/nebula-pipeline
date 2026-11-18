"""Color swatches author complete, undoable scene colors without changing studies."""
import copy
import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QApplication
from nebula.sources.synth_blender_colors import color_spec, scene_colors
from nebula.ui.synth_color_ui import ColorPicker, display_color
from nebula.documents.synth_blender_recipes import optical_relic_composition, orbital_smooth_painted_composition, yin_yang_continuous_composition
from nebula.documents.synth_composition import compile_composition, normalize_composition
from nebula.documents.synth_sequence import resolve_sequence_frame
from test_synth_effects_editor_integration import make_window


def params(doc, time=0):
    preset = resolve_sequence_frame(compile_composition(doc), time)[-1]
    return next(m['params'] for m in preset['modules'] if m['id'] == 'blender_scene')


@pytest.mark.parametrize('recipe,keys', [
    (optical_relic_composition, {'blender_background', 'blender_metal'}),
    (orbital_smooth_painted_composition, {'blender_sky', 'blender_ground', 'blender_paint', 'blender_accent'}),
    (yin_yang_continuous_composition, {'blender_background', 'blender_metal'})])
def test_cards_match_finish_and_navigation_is_read_only(make_window, recipe, keys):
    w = make_window(composition=recipe()); c = w.composer; p = c.object_panel
    c.look_tabs.setCurrentWidget(p); QApplication.processEvents()
    original = copy.deepcopy(c.document)
    assert p.color_panel.active_keys == keys
    for key in keys:
        context = c.color_context(key)
        assert context['hsv'] == tuple(params(original)[channel] for channel in color_spec(key).channels)
        assert p.color_panel.cards[key].isVisible()
    p.object_filter.setText('hue'); p.object_filter.clear()
    assert c.document == original and not w.has_unsaved_changes()


def test_color_picker_hex_brightness_scopes_cancel_undo_and_restore(make_window, monkeypatch):
    doc = yin_yang_continuous_composition()
    second = copy.deepcopy(doc['sections'][0]); second['id'] = 'other'; doc['sections'].append(second)
    w = make_window(composition=doc); c = w.composer; panel = c.object_panel.color_panel
    before = copy.deepcopy(c.document)
    monkeypatch.setattr(ColorPicker, 'exec', lambda d: QDialog.DialogCode.Accepted)
    panel.open_picker('blender_background')
    assert c.document == before  # Accept unchanged composition color must do nothing.
    def cancel(d):
        d.picker.setCurrentColor(QColor('#190031')); return QDialog.DialogCode.Rejected
    monkeypatch.setattr(ColorPicker, 'exec', cancel); panel.open_picker('blender_background')
    assert c.document == before
    def choose(d):
        assert d.scope.currentData() is None
        d.picker.setCurrentColor(QColor('#190031')); return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ColorPicker, 'exec', choose); panel.open_picker('blender_background')
    after = copy.deepcopy(c.document)
    p = params(after)
    assert display_color(tuple(p[k] for k in color_spec('blender_background').channels)).name() == '#190031'
    assert p['background_light'] < .2
    assert after['sections'] == before['sections']
    w.undo_composition(); assert w.composition == before
    w.redo_composition(); assert w.composition == after
    assert normalize_composition(after) == after
    c.restore_color('blender_background'); assert c.document == before
    c.select_section(1)
    def black(d):
        assert d.scope.currentData() == 'other'
        d.picker.setCurrentColor(QColor('#000000')); return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ColorPicker, 'exec', black); panel.open_picker('blender_metal')
    assert params(c.document)['metal_light'] == .82
    assert params(c.document, 16.)['metal_light'] == 0.
    assert c.document['effects'] == before['effects']


def test_part_color_is_independent_and_respects_material_inheritance(make_window, monkeypatch):
    w = make_window(composition=yin_yang_continuous_composition()); c = w.composer; p = c.object_panel
    c.look_tabs.setCurrentWidget(p)
    p.part_selector.setCurrentIndex(p.part_selector.findData('ring2'))
    assert not p.color_panel.active_keys
    p.controls['blender_scene.part_ring2_inherit'].input.setChecked(False)
    assert p.color_panel.active_keys == {'blender_part_ring2'}
    before = copy.deepcopy(c.document)
    def choose(d):
        d.picker.setCurrentColor(QColor('#8b194a')); return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ColorPicker, 'exec', choose)
    p.color_panel.open_picker('blender_part_ring2')
    from nebula.sources.synth_blender_parts import part_poses
    pose = part_poses(params(c.document), 0)['ring2']['material']
    assert display_color((pose['hue'], pose['saturation'], pose['light'])).name() == '#8b194a'
    assert params(c.document)['metal_hue'] == params(before)['metal_hue']
    w.undo_composition(); assert c.document == before
    c.restore_color('blender_part_ring2'); assert params(c.document)['part_ring2_inherit'] == 0


def test_neutral_brightness_keeps_legacy_requests(monkeypatch):
    import numpy as np
    from PIL import Image
    import nebula.sources.synth_blender_bridge as bridge
    from nebula.sources.synth_blender import render_blender_scene
    from nebula.sources.synth_blender_parts import part_poses
    calls = []
    monkeypatch.setattr(bridge, 'render_frame', lambda p, a, size, **kw: calls.append((p, kw)) or Image.new('RGB', size))
    p = params(optical_relic_composition())
    render_blender_scene(np.zeros((4,4,3)), p, 0, dict(speed=1, width=4, height=4, canvas={'width':4,'height':4,'framing':'native'}))
    assert 'metal_light' not in calls[-1][0] and 'background_light' not in calls[-1][0]
    p['part_upper_inherit'] = 0
    assert 'light' not in part_poses(p,0)['upper']['material']
    p['metal_light'] = .2; p['background_light'] = .8
    render_blender_scene(np.zeros((4,4,3)), p, 0, dict(speed=1, width=4, height=4, canvas={'width':4,'height':4,'framing':'native'}))
    assert calls[-1][0]['metal_light'] == .2 and calls[-1][0]['background_light'] == .8
