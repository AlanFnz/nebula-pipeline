"""The still, the typed frame and the movie use the same absolute frame index."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit

from nebula.core.media import Cancellation, Cancelled
from nebula.documents.synth_composition import blank_composition, compile_composition
from nebula.documents.synth_media import export_still, export_synth_video, render_output_frame
from nebula.documents.synth_montage import MontageRenderer, add_asset, insert_clip, new_montage
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.render.synth import default_synth_preset
from nebula.ui.synth_frame_export_ui import FrameExportDialog
from nebula.ui.synth_montage_ui import MontageWindow
from nebula.ui.synth_studio import SynthStudio


@pytest.fixture
def editor(tmp_path, monkeypatch):
    monkeypatch.setenv('NEBULA_STATE_DIR', str(tmp_path))
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda *_: None)
    doc = blank_composition()
    doc['fps'] = 30
    doc['canvas'].update(width=113, height=65)
    doc['sections'][0]['duration'] = 15.
    window = SynthStudio(composition=doc)
    window.show()
    window.activateWindow()
    app.processEvents()
    yield window
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_playhead_readout_seeks_without_waiting_for_preview(editor):
    before = copy.deepcopy(editor.composition)
    editor.timeline.setValue(150)
    assert editor.frame_number.value() == 150
    assert editor.time_label.text() == '00:05.00'
    assert editor.frame_number.maximum() == 449

    editor.timeline.setFocus()
    field = editor.frame_number.lineEdit()
    QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=QPoint(field.width() - 5, field.height() // 2))
    QApplication.processEvents()
    assert field.selectedText() == '150'
    QTest.keyClicks(editor.frame_number, '180')
    assert editor.timeline.value() == 150
    QTest.keyClick(editor.frame_number, Qt.Key.Key_Return)
    assert editor.timeline.hasFocus() and editor.timeline.value() == 180
    QTest.keyClick(editor.timeline, Qt.Key.Key_Left)
    assert editor.frame_number.value() == 179
    QTest.keyClick(editor.timeline, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert editor.frame_number.value() == 189
    editor.display_frame(0., ((1, 1), bytes(3)))
    assert editor.time_label.text() == '00:06.30'
    assert editor.frame_number.value() == 189
    assert editor.composition == before

    editor.sequence['duration'] = .2
    editor.update_timeline_max()
    assert editor.frame_number.maximum() == editor.frame_number.value() == 5
    assert editor.time_label.text() == '00:00.17'


def test_dialog_pins_frame_uses_full_canvas_and_honors_file_format(editor, tmp_path):
    def render(size, _cancel):
        return Image.new('RGB', size, 'white')
    dialog = FrameExportDialog(editor, tmp_path / 'piece.png', {'width':1080, 'height':1920},
                               150, 30, 'Composition', render)
    dialog.show()
    QApplication.processEvents()
    assert [dialog.resolution.itemData(i) for i in range(3)] == [(202, 360), (405, 720), (1080, 1920)]
    assert dialog.resolution.currentIndex() == 2 and dialog.selectedNameFilter() == dialog.PNG
    assert dialog.selectedFiles() == [str(tmp_path / 'piece-f000150.png')]
    assert not dialog.quality.isVisible()
    for _ in range(100):
        if not dialog.thumbnail.pixmap().isNull(): break
        QTest.qWait(10)
    assert not dialog.thumbnail.pixmap().isNull()
    types = dialog.findChild(QComboBox, 'fileTypeCombo')
    types.setFocus()
    QTest.keyClick(types, Qt.Key.Key_Down)
    assert dialog.selectedNameFilter() == dialog.JPEG
    assert dialog.quality.isVisible() and dialog.defaultSuffix() == 'jpg'
    file_name = dialog.findChild(QLineEdit, 'fileNameEdit')
    file_name.setFocus()
    file_name.setText('my-still.png')
    QTest.keyClick(file_name, Qt.Key.Key_Return)
    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.selectedFiles() == [str(tmp_path / 'my-still.jpg')]
    dialog.deleteLater()


def test_frame_action_renders_original_playhead_and_working_edits(editor, tmp_path, monkeypatch):
    path = tmp_path / 'frame.png'
    editor.quality.setCurrentIndex(0)
    editor.timeline.setValue(150)
    original = copy.deepcopy(editor.sequence)
    before = copy.deepcopy(editor.composition)
    def choose(parent, suggested, canvas, frame, fps, scope, render):
        assert frame == 150 and fps == 30 and scope == 'Working composition'
        parent.timeline.setValue(171)
        return path, (canvas['width'], canvas['height']), 95
    monkeypatch.setattr(FrameExportDialog, 'choose', choose)
    editor.export_button.frame_action.trigger()
    assert editor.export_job
    editor.jobs.waitForDone(10000)
    QApplication.processEvents()
    assert editor.export_job is None and editor.export_button.isEnabled()
    assert editor.composition == before and editor.timeline.value() == 171
    with Image.open(path) as out:
        assert out.format == 'PNG' and out.size == (113, 65)
        assert out.tobytes() == render_sequence_frame(original, 5., out.size).tobytes()


def test_png_matches_actual_movie_input_before_h264(tmp_path, monkeypatch):
    import nebula.documents.synth_sequence as sequence_module
    seq = compile_composition(blank_composition())
    preset = default_synth_preset()
    frame = 3
    size = (113, 65)
    def render(size, cancel):
        return render_output_frame(preset, seq, frame, size, cancel)
    path = export_still(render, tmp_path / 'still.png', size, 95, Cancellation())
    captured = []
    def capture(*args, **kwargs):
        image = render_sequence_frame(*args, **kwargs)
        captured.append((args[1], image.tobytes()))
        return image
    monkeypatch.setattr(sequence_module, 'render_sequence_frame', capture)
    export_synth_video(preset, tmp_path / 'clip.mp4', start=frame, count=1, size=size, sequence=seq)
    with Image.open(path) as out:
        assert captured == [(frame / seq['fps'], out.tobytes())]


def test_standalone_preset_jpeg_and_cancelled_replacement(tmp_path):
    preset = default_synth_preset()
    def render(size, cancel):
        return render_output_frame(preset, None, 4, size, cancel)
    path = export_still(render, tmp_path / 'small.jpeg', (64, 80), 84, Cancellation())
    with Image.open(path) as out:
        assert out.format == 'JPEG' and out.size == (64, 80)
    original = path.read_bytes()
    def interrupted(size, cancel):
        cancel.cancel()
        return Image.new('RGB', size)
    with pytest.raises(Cancelled):
        export_still(interrupted, path, (64, 80), 90, Cancellation())
    assert path.read_bytes() == original


def test_montage_still_uses_block_at_absolute_playhead(editor, tmp_path, monkeypatch):
    monkeypatch.setattr(MontageWindow, 'request_frame', lambda *_: None)
    monkeypatch.setattr(MontageWindow, 'initialize_media', lambda *_: None)
    montage, key = add_asset(new_montage({'width':160, 'height':120}, 30), 'Study', study=editor.composition)
    montage, _ = insert_clip(montage, key, frames=3)
    montage, _ = insert_clip(montage, key, in_frame=70, frames=10)
    window = editor.open_montage(document=montage)
    window.seek(6)
    assert window.frame_number.value() == 6 and window.frame_number.maximum() == 12
    path = tmp_path / 'montage.png'
    def choose(parent, suggested, canvas, frame, fps, scope, render):
        assert frame == 6 and scope == 'Montage'
        return path, (160, 120), 95
    monkeypatch.setattr(FrameExportDialog, 'choose', choose)
    window.export_button.frame_action.trigger()
    window.pool.waitForDone(10000)
    QApplication.processEvents()
    with MontageRenderer(montage) as renderer, Image.open(path) as out:
        assert out.tobytes() == renderer.frame(6).tobytes()
