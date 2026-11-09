"""Full-pattern editing, independent playhead, and lossless historic sound."""
import copy
import pytest
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QWidget
from synth_sound_sequencer_ui import StepSequencer
from synth_visual_sound_ui import VisualSoundDialog
from synth_visual_sound import instrument_sound
from test_synth_visual_sound_ui import app
from test_synth_visual_sound_instrument import signals
from test_synth_arpeggio import render
from studio_theme import apply_theme


def config():
    c = instrument_sound()
    c.update(arp_mode='sequence', sequence_length=16, sequence_trigger='loop', bpm=119.7654321)
    c['sequence'][15].update(semitones=7, velocity=.65321978, gate=.723456)
    c['sequence'][6]['enabled'] = False
    return c


@pytest.mark.parametrize('width,height', [(1280, 780), (1280, 800), (1440, 900)])
@pytest.mark.parametrize('midi', [False, True], ids=['internal', 'midi'])
def test_all_steps_and_precise_editor_fit_without_horizontal_scroll(app, width, height, midi):
    apply_theme(app)
    owner = QWidget();owner.midi_monitor_enabled = midi
    dialog = VisualSoundDialog(owner);dialog.set_config(config());dialog.tabs.setCurrentIndex(2)
    dialog.resize(width, height);dialog.show();app.processEvents()
    seq = dialog.sequencer;scroll = dialog.tabs.widget(2);viewport = scroll.viewport()
    assert dialog.midi_hint.isVisible() == midi
    assert dialog.size().width() == width and dialog.size().height() == height
    assert seq.grid.width() <= viewport.width()
    assert scroll.horizontalScrollBar().maximum() == 0
    for widget in [dialog.arp_pitch.number, dialog.arp_pitch.mode, *seq.cells,
                   seq.step_on, seq.step_gate, seq.step_velocity, seq.step_note]:
        assert widget.isVisible()
        origin = widget.mapTo(viewport, QPoint(0, 0))
        assert viewport.rect().contains(origin)
        assert viewport.rect().contains(widget.mapTo(viewport, widget.rect().bottomRight()))
    seq.focus_button.click();app.processEvents()
    assert not dialog.preview_pane.isVisible()
    assert scroll.horizontalScrollBar().maximum() == 0
    dialog.tabs.setCurrentIndex(0);app.processEvents()
    assert dialog.preview_pane.isVisible()
    dialog.tabs.setCurrentIndex(2);seq.focus_button.click();app.processEvents()
    assert dialog.preview_pane.isVisible()
    dialog.articulation_toggle.click();app.processEvents()
    assert dialog.attack.isVisible() and dialog.release.isVisible()
    assert scroll.horizontalScrollBar().maximum() == 0
    dialog.close();owner.deleteLater();app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_switching_pattern_mode_keeps_root_editable_and_undoable(app):
    dialog = VisualSoundDialog();dialog.set_config(config());dialog.tabs.setCurrentIndex(2)
    dialog.show();app.processEvents()
    baseline = dialog.read_config()
    dialog.arp_mode.setCurrentIndex(dialog.arp_mode.findData('visual'));app.processEvents()
    assert dialog.arp_pitch.dial.isVisible() and dialog.arp_pitch.number.isVisible()
    assert dialog.arp_notes.isVisible() and not dialog.sequencer.isVisible()
    assert len(dialog.sound_undo) == 1
    assert dialog.undo_draft();app.processEvents()
    assert dialog.arp_pitch.number.isVisible() and not dialog.arp_pitch.dial.isVisible()
    assert dialog.sequencer.isVisible() and not dialog.arp_notes.isVisible()
    assert dialog.read_config() == baseline
    dialog.close();dialog.deleteLater();app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_selecting_focusing_and_playback_preserve_exact_values_and_pcm(app):
    c = config();dialog = VisualSoundDialog();dialog.set_config(c)
    seq = dialog.sequencer;baseline = dialog.read_config()
    assert baseline == c
    edited = QSignalSpy(seq.changed)
    seq.select_step(15);seq.set_root(217.9);seq.focus_button.setChecked(True)
    seq.set_schedule([dict(time=i*.125, step=i) for i in range(16)], dict(c, bpm=120))
    for time in (.14, .26, .39, 1.95): seq.set_time(time)
    assert seq.selected == 15 and seq.active == 15 and seq.cells[15].isChecked()
    seq.set_time(.01)
    assert seq.selected == 15 and seq.cells[15].isChecked() and seq.cells[0].playing
    assert not seq.cells[0].isChecked()
    assert edited.count() == 0 and not dialog.has_sound_draft()
    assert dialog.read_config() == baseline
    before = render(c, signals(.6));after = render(dialog.read_config(), signals(.6))
    assert before.tobytes() == after.tobytes()
    dialog.close()


def test_edit_only_one_step_and_shortening_keeps_all_sixteen(app):
    seq = StepSequencer();seq.load(config());seq.show();app.processEvents()
    original = seq.config();seq.select_step(15)
    seq.step_gate.setValue(53)
    expected = copy.deepcopy(original);expected['sequence'][15]['gate'] = .53
    assert seq.config() == expected
    seq.length.setValue(8)
    assert len(seq.config()['sequence']) == 16
    assert all(cell.isVisible() for cell in seq.cells)
    assert all(not cell.in_pattern for cell in seq.cells[8:])
    assert 'Outside pattern' in seq.selection_label.text()
    seq.length.setValue(16)
    assert seq.config() == expected and all(cell.in_pattern for cell in seq.cells)
    # No quantization of velocity, other gates or tempo as a side effect.
    assert seq.config()['sequence'][15]['velocity'] == .65321978
    assert seq.config()['bpm'] == original['bpm']
    seq.close()


def test_keyboard_selection_edit_and_escape_do_not_touch_unrelated_steps(app):
    dialog = VisualSoundDialog();dialog.set_config(config());dialog.tabs.setCurrentIndex(2)
    dialog.show();dialog.activateWindow();app.processEvents()
    seq = dialog.sequencer;original = seq.config()
    seq.cells[0].click();seq.cells[0].click()
    assert seq.cells[0].isChecked() and seq.config() == original
    # Native macOS accessibility toggles checkable buttons without clicked.
    seq.cells[15].setChecked(True)
    assert seq.selected == 15 and seq.step_note.value() == original['sequence'][15]['semitones']
    assert sum(cell.isChecked() for cell in seq.cells) == 1
    seq.cells[15].setChecked(False)
    assert seq.cells[15].isChecked() and seq.config() == original
    seq.focus_step(0);QTest.keyClick(seq.cells[0], Qt.Key.Key_End)
    assert seq.selected == 15
    QTest.keyClick(seq.cells[15], Qt.Key.Key_Return)
    assert seq.step_note.hasFocus()
    seq.step_note.selectAll();QTest.keyClicks(seq.step_note, '-5')
    # Playback must not overwrite a field that is being typed.
    seq.set_schedule([dict(time=0., step=0)], config());seq.set_time(.01)
    assert '-5' in seq.step_note.text()
    QTest.keyClick(seq.step_note, Qt.Key.Key_Escape);app.processEvents()
    assert dialog.isVisible() and seq.config() == original and seq.selected == 15
    QTest.keyClick(seq.cells[15], Qt.Key.Key_Space)
    assert not seq.config()['sequence'][15]['enabled']
    assert dialog.undo_draft() and seq.config() == original
    QTest.keyClick(seq.cells[15], Qt.Key.Key_Left)
    assert seq.selected == 14 and seq.cells[14].hasFocus()
    dialog.close()


def test_drag_is_one_undo_and_does_not_move_playback_or_selection(app):
    dialog = VisualSoundDialog();dialog.set_config(config());dialog.tabs.setCurrentIndex(2)
    dialog.show();app.processEvents();seq = dialog.sequencer;before = dialog.read_config()
    cell = seq.cells[15]
    QTest.mousePress(cell, Qt.MouseButton.LeftButton, pos=QPoint(15, 95))
    for y in (90, 85, 80): QTest.mouseMove(cell, QPoint(15, y))
    QTest.mouseRelease(cell, Qt.MouseButton.LeftButton, pos=QPoint(15, 80))
    assert len(dialog.sound_undo) == 1 and seq.selected == 15
    assert dialog.read_config()['sequence'][15]['semitones'] != before['sequence'][15]['semitones']
    assert dialog.undo_draft() and dialog.read_config() == before
    assert seq.selected == 15
    assert dialog.redo_draft()
    assert dialog.read_config()['sequence'][:15] == before['sequence'][:15]
    dialog.close()
