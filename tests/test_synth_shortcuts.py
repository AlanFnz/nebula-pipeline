"""Window shortcuts leave parameter widgets and local text undo in charge."""
import copy
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QPlainTextEdit
from test_synth_unsaved import make_window, edit


def key(widget, code, modifiers=Qt.KeyboardModifier.NoModifier):
    widget.setFocus(); QApplication.processEvents()
    QTest.keyClick(widget, code, modifiers); QApplication.processEvents()


def test_transport_steps_pause_clamp_and_never_dirty(make_window):
    window = make_window()
    initial = copy.deepcopy(window.composition)
    key(window.viewer, Qt.Key.Key_Space)
    assert window.play.isChecked()
    key(window.viewer, Qt.Key.Key_Right)
    assert not window.play.isChecked() and window.timeline.value() == 1
    key(window.section_timeline, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert window.timeline.value() == 11
    key(window.timeline, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert window.timeline.value() == 1
    key(window.viewer, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert window.timeline.value() == 0
    window.timeline.setValue(window.timeline.maximum())
    key(window.viewer, Qt.Key.Key_Right)
    assert window.timeline.value() == window.timeline.maximum()
    assert window.composition == initial and not window.has_unsaved_changes() and not window.undo_compositions


def test_text_space_arrows_and_undo_stay_local(make_window):
    window = make_window(); window.load_starter_id('text-transmission')
    edit(window); history = copy.deepcopy(window.undo_compositions)
    editor = window.composer.object_panel.controls['text.content'].input.editor
    editor.setFocus(); editor.moveCursor(editor.textCursor().MoveOperation.End)
    QTest.keyClicks(editor, ' xyz')
    assert editor.toPlainText().endswith(' xyz') and not window.play.isChecked()
    QTest.keySequence(editor, QKeySequence(QKeySequence.StandardKey.Undo))
    QApplication.processEvents()
    assert window.undo_compositions == history
    assert not editor.toPlainText().endswith(' xyz')


def test_spin_slider_and_button_keep_normal_keyboard_behavior(make_window):
    window = make_window()
    spin = window.composer.duration
    spin.setFocus(); QApplication.processEvents()
    key(spin, Qt.Key.Key_Up)
    assert window.has_unsaved_changes() and not window.play.isChecked()
    from PySide6.QtWidgets import QSlider
    slider = window.composer.findChildren(QSlider)[0]
    before = slider.value()
    key(slider, Qt.Key.Key_Right)
    assert slider.value() >= before and not window.play.isChecked()
    key(window.play, Qt.Key.Key_Space)
    assert window.play.isChecked()


def test_standard_save_and_composition_undo_shortcuts(make_window, monkeypatch, tmp_path):
    window = make_window(); edit(window)
    window.viewer.setFocus(); QApplication.processEvents()
    QTest.keySequence(window.viewer, QKeySequence(QKeySequence.StandardKey.Undo)); QApplication.processEvents()
    assert not window.has_unsaved_changes()
    QTest.keySequence(window.viewer, QKeySequence(QKeySequence.StandardKey.Redo)); QApplication.processEvents()
    assert window.has_unsaved_changes()
    path = tmp_path / 'shortcut.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    QTest.keySequence(window.viewer, QKeySequence(QKeySequence.StandardKey.Save)); QApplication.processEvents()
    assert path.exists() and not window.has_unsaved_changes()


def test_detailed_editor_disables_composition_undo(make_window):
    window = make_window('sequence')
    assert not window.undo_action.isEnabled() and not window.redo_action.isEnabled()
    assert window.save_action.isEnabled() and window.open_action.isEnabled()


def test_multiple_windows_route_transport_to_focus_owner(make_window, monkeypatch):
    first = make_window(); second = make_window()
    # Route keys independently of how much wall-clock time a busy test host
    # takes to activate the second window while the first is playing.
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: 100.)
    first.activateWindow(); QApplication.processEvents()
    key(first.viewer, Qt.Key.Key_Space)
    assert first.play.isChecked() and not second.play.isChecked()
    second.activateWindow(); QApplication.processEvents()
    key(second.viewer, Qt.Key.Key_Right)
    assert second.timeline.value() == 1 and first.timeline.value() == 0


def test_modal_editor_does_not_trigger_parent_transport(make_window):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    window = make_window()
    dialog = QDialog(window); dialog.setModal(True)
    editor = QPlainTextEdit(); QVBoxLayout(dialog).addWidget(editor)
    dialog.show(); QApplication.processEvents()
    key(editor, Qt.Key.Key_Space)
    assert editor.toPlainText() == ' ' and not window.play.isChecked()
    dialog.close()
