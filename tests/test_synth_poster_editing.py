"""Artwork depth, canvas gestures and the poster export entry point."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest
from PySide6.QtCore import QDeadlineTimer, QPoint, QSettings, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.documents.synth_poster import PosterFrame
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.documents.synth_starting_points import new_piece
from nebula.ui.synth_studio import SynthStudio


def printed_words():
    doc = new_piece('poster', {'width': 200, 'height': 250}, text='O')
    key = 'type_overprint'
    doc['effects'][key] = {'mode': 'on', 'params': {key+'.content': 'Ink', key+'.height': .15,
                           key+'.y': .53, key+'.light': 1., key+'.saturation': 0.}}
    doc['effect_order'].insert(0, key)
    return doc


def test_artwork_stack_retains_print_and_visibility_across_export(tmp_path):
    doc = printed_words()
    original = copy.deepcopy(doc)
    def pixels(document):
        return np.asarray(render_sequence_frame(compile_composition(document), 0.))
    frame = PosterFrame(compile_composition(doc), 0., doc['poster'])
    word = 'type_overprint'
    ink = np.asarray(frame.mask(word, frame.canvas)) > 230
    plate = np.asarray(frame.mask('plate', frame.canvas, material=True)) > 249
    clean = pixels(doc)
    doc['poster']['hidden'] = [word, 'text']
    plate_only = pixels(doc)
    doc['poster']['hidden'] = ['text']
    doc['poster']['order'] = ['plate', word, 'text']
    changed = pixels(doc)
    region = ink & plate
    assert region.sum() > 30
    assert np.abs(changed[region].astype(float) - plate_only[region]).mean() < 4.
    assert np.abs(clean[region].astype(float) - changed[region]).mean() > 25.
    saved = tmp_path / 'print.nebula'
    save_composition(saved, doc)
    np.testing.assert_array_equal(changed, pixels(load_composition(saved)))
    assert doc['effect_order'] == original['effect_order']
    doc['poster'] = original['poster']
    np.testing.assert_array_equal(clean, pixels(doc))


def test_independent_copies_and_new_plate():
    doc = printed_words()
    key = 'type_overprint'
    section = doc['sections'][0]
    section['effects'][key] = {'mode': 'recipe', 'params': {key+'.height': .21}}
    frame = PosterFrame(compile_composition(doc), 0, doc['poster'])
    clone = frame.add_layer(doc, 'text', duplicate=key, above=key)
    assert section['effects'][clone]['params'][clone+'.height'] == .21
    section['effects'][clone]['params'][clone+'.height'] = .32
    after = PosterFrame(compile_composition(doc), 0, doc['poster'])
    assert after.modules[key]['height'] == .21 and after.modules[clone]['height'] == .32
    shape = after.add_layer(doc, 'plate', above=clone)
    after = PosterFrame(compile_composition(doc), 0, doc['poster'])
    assert after.by_key[shape].kind == 'plate' and after.order.index(shape) < after.order.index(clone)
    source = after.add_layer(doc, 'text', duplicate='text', above='text')
    after = PosterFrame(compile_composition(doc), 0, doc['poster'])
    assert after.mask(source, after.canvas).tobytes() == after.mask('text', after.canvas).tobytes()
    assert after.modules[source]['layout'] == 1


def test_poster_canvas_wording_alignment_transform_and_output(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    doc = printed_words()
    win = SynthStudio(composition=doc, settings=QSettings(str(tmp_path/'ui.ini'), QSettings.Format.IniFormat))
    view, panel = win.viewer, win.composer.layers_panel
    def ready():
        deadline = QDeadlineTimer(10000)
        while not win.poster_editable() and not deadline.hasExpired():
            QTest.qWait(10)
        assert win.poster_editable()
    try:
        win.show()
        app.processEvents()
        ready()
        frame = panel.frame
        rect = view.target_rect()
        key = 'type_overprint'
        rows, cols = np.where(np.asarray(frame.mask(key, frame.canvas)) > 245)
        x, y = cols[len(rows)//2], rows[len(rows)//2]
        pos = QPoint(round(rect.x()+(x+.5)*rect.width()/frame.canvas[0]),
                     round(rect.y()+(y+.5)*rect.height()/frame.canvas[1]))
        QTest.mouseDClick(view, Qt.MouseButton.LeftButton, pos=pos)
        assert panel.selected == key and view.word_editor
        view.word_editor.setPlainText('Proof')
        QTest.keyClick(view.word_editor, Qt.Key.Key_Return)
        assert panel.frame.modules[key]['content'] == 'Proof'
        win.undo_action.trigger()
        assert panel.frame.modules[key]['content'] == 'Ink'
        ready()
        QTest.mouseDClick(view, Qt.MouseButton.LeftButton, pos=pos)
        view.word_editor.setPlainText('Discarded')
        QTest.keyClick(view.word_editor, Qt.Key.Key_Escape)
        assert panel.frame.modules[key]['content'] == 'Ink'
        panel.select(key)
        view.setFocus()
        center = panel.frame.center(key)
        QTest.keyClick(view, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        assert panel.frame.center(key)[0] == pytest.approx(center[0]+10)
        assert win.timeline.value() == 0
        panel.align_center('plate')
        assert panel.frame.center(key) == pytest.approx(panel.frame.center('plate'))
        panel.select('plate')
        ready()
        corners, _, rotate = view._plate_handles(panel.frame, 'plate')
        start = corners[2].toPoint()
        size = panel.frame.dye['mask_size']
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=start)
        assert view.drag.mode == 'scale'
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=start+QPoint(9, 8))
        assert panel.frame.dye['mask_size'] > size
        win.undo_action.trigger()
        ready()
        start = rotate.toPoint()
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=start)
        assert view.drag.mode == 'rotate'
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=start+QPoint(12, 0))
        assert abs(panel.frame.dye['mask_angle']) > 1.
        panel.animate.click()
        assert win.poster_animation.isChecked()
        dialog = win.composer.automation_dialogs[-1]
        assert dialog.target.currentData() == 'dye_transfer.mask_angle' and panel.selected == 'plate'
        dialog.reject()
        assert win.export_button.text() == 'Export poster…'
        assert [action.text() for action in win.export_button.menu().actions()] == ['Export MP4']
        called = []
        monkeypatch.setattr('nebula.ui.synth_frame_export_ui.FrameExportDialog.choose', lambda *a: called.append(a))
        win.export_button.click()
        assert len(called) == 1 and called[0][3] == win.timeline.value()
        panel.duplicate_layer()
        duplicate = panel.selected
        assert panel.frame.by_key[duplicate].kind == 'plate'
        initial_order = list(panel.frame.order)
        panel.tree.setFocus()
        source = panel.tree.visualItemRect(panel.items[duplicate]).center()
        above = panel.tree.visualItemRect(panel.items[initial_order[initial_order.index(duplicate)-1]])
        destination = QPoint(source.x(), above.top()+2)
        QTest.mousePress(panel.tree.viewport(), Qt.MouseButton.LeftButton, pos=source)
        QTest.mouseMove(panel.tree.viewport(), source+QPoint(18,0))
        QTest.mouseMove(panel.tree.viewport(), destination)
        QTest.mouseRelease(panel.tree.viewport(), Qt.MouseButton.LeftButton, pos=destination)
        assert panel.frame.order.index(duplicate) == initial_order.index(duplicate)-1
        win.undo_action.trigger()
        assert panel.frame.order == initial_order
        QTest.keyClick(panel.tree, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
        assert panel.frame.order.index(duplicate) == initial_order.index(duplicate)-1
        win.undo_action.trigger()
        assert panel.frame.order == initial_order
        panel.items[duplicate].setCheckState(0, Qt.CheckState.Unchecked)
        assert duplicate in win.sequence['poster_stack']['hidden']
        assert duplicate in panel.items
        win.undo_action.trigger()
        assert duplicate not in panel.frame.hidden
    finally:
        win.mark_document_clean()
        win.close()
        QThreadPool.globalInstance().waitForDone()
        app.processEvents()
