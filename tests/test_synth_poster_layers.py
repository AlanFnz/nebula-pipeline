"""Poster navigation and canvas gestures edit the same native parameters as export."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, QSettings, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.documents.synth_poster import PosterFrame
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.documents.synth_starting_points import new_piece
from nebula.effects.synth_effects import effect_preset
from nebula.ui.synth_new_piece_ui import NewPieceDialog
from nebula.ui.synth_studio import SynthStudio


def poster():
    doc = new_piece('poster', {'width': 320, 'height': 400}, text='O')
    for key, x in [('type_overprint', .25), ('type_overprint@2', .75)]:
        entry = effect_preset(key)
        entry['params'].update({key + '.x': x, key + '.content': 'caption'})
        doc['effects'][key] = entry
    doc['effect_order'] += ['type_overprint', 'type_overprint@2']
    doc['poster']['footer'] = ['type_overprint', 'type_overprint@2']
    return doc


def test_opt_in_keeps_pixels_and_lands_in_real_shapes(tmp_path):
    doc = poster()
    seq = compile_composition(doc)
    legacy = copy.deepcopy(doc)
    del legacy['poster']
    assert compile_composition(legacy) == seq
    path = tmp_path / 'edition.nebula'
    save_composition(path, doc)
    assert load_composition(path)['poster'] == doc['poster']
    frame = PosterFrame(seq, 0, doc['poster'])
    size = frame.canvas
    mask = frame.mask('text', size)
    assert mask.getbbox()
    l, t, r, b = mask.getbbox()
    center = ((l + r) / (2 * size[0]), (t + b) / (2 * size[1]))
    assert frame.pick(center, size) == 'plate'  # inside the O
    assert frame.pick((.02, .02), size) == 'paper'
    assert frame.pick((-.0001, .5), size) is None
    y, x = np.argwhere(np.asarray(mask) > 200)[0]
    assert frame.pick(((x+.5)/size[0], (y+.5)/size[1]), size) == 'text'
    for time in (0, 1.5):
        assert render_sequence_frame(seq, time, (160, 200)).tobytes() == render_sequence_frame(
            compile_composition(load_composition(path)), time, (160, 200)).tobytes()


def test_move_on_reframed_canvas_and_group_transaction():
    from nebula.core.synth_canvas import resize_canvas
    doc = poster()
    doc['canvas'] = resize_canvas(doc['canvas'], {'width': 480, 'height': 600}, fit=True)
    params = doc['effects']['dye_transfer']['params']
    params['dye_transfer.angle'] = 32.
    params['dye_transfer.scale'] = 1.2
    for key in ('plate', 'text', 'footer'):
        changed = copy.deepcopy(doc)
        frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
        frame.move(changed, key, -18., 11.)
        moved = PosterFrame(compile_composition(changed), 0., changed['poster'])
        for member in frame.footer if key == 'footer' else (key,):
            x, y = frame.center(member)
            assert moved.center(member) == pytest.approx((x-18, y+11))
        assert changed['sections'] == doc['sections']
    assert new_piece('text').get('poster') is None


def test_individual_caption_grain_survives_reload_and_leaves_other_ink_alone(tmp_path):
    doc = poster()
    key = 'type_overprint@2'
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    before = np.asarray(render_sequence_frame(compile_composition(doc), 0.))
    doc['effects'][key]['params'][key + '.ink_pinholes'] = 1.
    doc['effects'][key]['params'][key + '.ink_grain'] = .8
    path = tmp_path / 'print.nebula'
    save_composition(path, doc)
    seq = compile_composition(load_composition(path))
    after = np.asarray(render_sequence_frame(seq, 0.))
    changed = np.any(before != after, axis=2)
    assert changed.sum() > 12
    assert not changed[np.asarray(frame.mask(key, frame.canvas)) == 0].any()
    assert not changed[np.asarray(frame.mask('type_overprint', frame.canvas)) > 0].any()
    np.testing.assert_array_equal(after, np.asarray(render_sequence_frame(seq, 0.)))


def test_texture_controls_track_print_order():
    doc = poster()
    doc['effects']['photocopy'] = effect_preset('photocopy')
    doc['effects']['photocopy']['params']['photocopy.process'] = 1
    doc['effect_order'] = ['type_overprint', 'photocopy', 'dye_transfer', 'type_overprint@2']
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    assert 'photocopy.paper_grain' in frame.texture_paths('paper')[0]
    assert 'dye_transfer.dry_ink' in frame.texture_paths('type_overprint')[1]
    assert 'photocopy.pinholes' in frame.texture_paths('text')[1]
    assert frame.texture_paths('type_overprint@2')[1] == ()
    assert frame.texture_paths('footer') == ((), ())
    doc['effects']['dye_transfer']['bypassed'] = True
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    assert 'text.paper_grain' in frame.texture_paths('paper')[0]
    assert 'dye_transfer.dry_ink' not in frame.texture_paths('text')[1]


@pytest.mark.parametrize('reveal', [0, 5])
def test_source_ink_grain_moves_with_the_type_and_exposes_its_background(reveal):
    from nebula.sources.synth_text import placed_text_mask, render_text
    doc = poster()
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    params = dict(frame.modules['text'], content='PRINT', reveal=reveal, scroll_position=1.,
                  scroll_rate=0., size=.19, rotation=0., motion=0, opacity=1., brightness=1.,
                  saturation=0., back_brightness=.15, back_saturation=0.)
    width, height = frame.canvas
    pixels = np.zeros((height, width, 3), np.float32)
    preset = dict(frame.preset, object_x=0., object_y=0.)
    clean = render_text(pixels, params, 0., preset)
    params.update(ink_grain=.85, ink_pinholes=.7, ink_grain_size=2.4)
    dry = render_text(pixels, params, 0., preset)
    mask = np.asarray(placed_text_mask(params, 0., preset, frame.canvas))
    np.testing.assert_array_equal(dry[mask == 0], clean[mask == 0])
    assert np.max(clean - dry) > .1
    moved = render_text(pixels, params, 0., dict(preset, object_x=8.))
    np.testing.assert_allclose(moved[:, 8:], dry[:, :-8], atol=1e-6)


def test_viewer_move_pan_undo_and_switch_document(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda *_: None)
    settings = QSettings(str(tmp_path/'ui.ini'), QSettings.Format.IniFormat)
    doc = poster()
    dialog = NewPieceDialog(doc['canvas'], 25, [])
    dialog.select('poster')
    dialog.poster_text.setPlainText('Edition')
    assert dialog.request()['kind'] == 'poster' and dialog.request()['text'] == 'Edition'
    window = SynthStudio(composition=doc, settings=settings)
    try:
        window.show()
        app.processEvents()
        view = window.viewer
        panel = window.composer.layers_panel
        assert window.composer.look_tabs.currentWidget() is panel
        assert window.preview_controls_scroll.isHidden()
        window.poster_animation.click()
        assert window.preview_controls_scroll.isVisible()
        assert panel.frame.by_key['footer'].kind == 'group'
        assert 'type_overprint' not in window.composer.effects_panel.rack_ids
        original = copy.deepcopy(window.composition)
        panel.select('paper')
        assert 'dye_transfer.paper_grain' in panel.texture.controls
        panel.texture.toggle.click()
        assert 'dye_transfer.stock_relief' in panel.texture.controls
        panel.select('plate')
        panel.texture.controls['dye_transfer.mask_grain_size'].input.setValue(4.)
        assert window.composition['effects']['dye_transfer']['params']['dye_transfer.mask_grain_size'] == 4.
        window.undo_action.trigger()
        assert window.composition == original
        window.composer.change_scope(1)
        panel.select('type_overprint@2')
        assert not panel.texture.toggle.isVisible()
        row = panel.texture.controls['type_overprint@2.ink_grain']
        row.input.setValue(.42)
        section = window.composition['sections'][0]
        assert section['effects']['type_overprint@2']['params']['type_overprint@2.ink_grain'] == .42
        assert window.composition['effects'] == original['effects']
        row.reset_button.click()
        assert 'type_overprint@2.ink_grain' not in window.composition['sections'][0]['effects'].get('type_overprint@2', {}).get('params', {})
        window.undo_action.trigger()
        window.undo_action.trigger()
        assert window.composition == original
        window.composer.change_scope(0)
        panel.select('type_overprint@2')
        panel.change('content', 'Another caption')
        assert window.composition['effects']['type_overprint@2']['params']['type_overprint@2.content'] == 'Another caption'
        assert panel.selected == 'type_overprint@2' and panel.wording.text() == 'Another caption'
        window.undo_action.trigger()
        assert panel.wording.text() == 'caption'
        window.viewer.set_canvas_size((320, 400))
        window.viewer.set_zoom(1.4)
        window.viewer.pan = QPointF(-8, 12)
        window.display_frame(0., ((320, 400), bytes(320*400*3)))
        rect = view.target_rect()
        origin = QPoint(round(rect.x()+rect.width()*.74), round(rect.y()+rect.height()*.62))
        end = origin + QPoint(14, -28)
        original = copy.deepcopy(window.composition)
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=origin)
        assert panel.selected == 'plate'
        QTest.mouseMove(view, end)
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=end)
        assert len(window.undo_compositions) == 1
        before = original['effects']['dye_transfer']['params']
        after = window.composition['effects']['dye_transfer']['params']
        assert after['dye_transfer.mask_x'] == pytest.approx(before['dye_transfer.mask_x']+10/320)
        assert after['dye_transfer.mask_y'] == pytest.approx(before['dye_transfer.mask_y']-20/400)
        path = tmp_path / 'moved.nebula'
        save_composition(path, window.composition)
        assert compile_composition(load_composition(path)) == window.sequence
        window.undo_action.trigger()
        assert window.composition == original
        window.display_frame(0., ((320, 400), bytes(320*400*3)))
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=origin)
        QTest.mouseMove(view, end)
        QTest.keyClick(view, Qt.Key.Key_Escape)
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=end)
        assert window.composition == original and not window.undo_compositions
        window.hand_tool.click()
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=origin)
        QTest.mouseMove(view, end)
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=end)
        assert window.composition == original
        window.set_composition(new_piece('shape'), guard=False)
        assert window.viewer.layers is None and window.poster_tools.isHidden()
        assert window.preview_controls_scroll.isVisible()
    finally:
        QThreadPool.globalInstance().waitForDone()
        window.mark_document_clean()
        window.close()
        app.processEvents()
