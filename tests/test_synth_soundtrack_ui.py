import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication
from synth_soundtrack_ui import SoundtrackDialog, SoundtrackLane


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def track():
    return dict(id='track-1', name='Tone', path='/tone.wav', duration=10.,
                sample_rate=48000, channels=2, **{'in': 2., 'out': 8.},
                offset=1., end_mode='silence', gain=.8, export_audio='soundtrack')


def test_refresh_monitor_and_apply_signals(app, track):
    dialog = SoundtrackDialog()
    edited = QSignalSpy(dialog.trackEdited)
    volume = QSignalSpy(dialog.monitorVolumeChanged)
    mute = QSignalSpy(dialog.monitorMutedChanged)
    dialog.set_track(track, 12.)
    dialog.set_monitor(.5, True)
    assert edited.count() == volume.count() == mute.count() == 0
    assert not dialog.apply_button.isEnabled()
    assert '6.00 s' in dialog.used_label.text()
    assert '12.00 s' in dialog.summary.text()
    dialog.offset_control.setValue(3.)
    dialog.gain.setValue(.4)
    assert edited.count() == 0
    dialog.apply()
    assert edited.count() == 1
    result = edited.at(0)[0]
    assert result['offset'] == 3. and result['gain'] == .4
    assert result['id'] == track['id'] and result['path'] == track['path']
    dialog.apply()
    assert edited.count() == 1
    dialog.monitor_volume.setValue(75)
    dialog.monitor_mute.setChecked(False)
    assert volume.at(0)[0] == .75 and mute.at(0)[0] is False
    assert edited.count() == 1
    dialog.close()


def test_invalid_trim_busy_and_missing_actions(app, track):
    dialog = SoundtrackDialog()
    spy = QSignalSpy(dialog.trackEdited)
    dialog.set_track(track)
    dialog.set_status('Media missing. Relink to restore playback.')
    assert dialog.relink_button.isEnabled()
    dialog.in_control.setValue(8.)
    assert not dialog.apply_button.isEnabled()
    dialog.apply()
    assert spy.count() == 0
    dialog.in_control.setValue(4.)
    assert dialog.apply_button.isEnabled()
    dialog.set_busy(True)
    assert not dialog.apply_button.isEnabled() and not dialog.relink_button.isEnabled()
    dialog.set_busy(False)
    assert dialog.apply_button.isEnabled()
    dialog.set_track(None)
    assert not dialog.editor.isEnabled() and not dialog.remove_button.isEnabled()
    assert dialog.import_button.isEnabled() and not dialog.apply_button.isEnabled()
    dialog.close()


def test_lane_project_seek_keyboard_and_waveform_refresh(app, track):
    lane = SoundtrackLane()
    lane.resize(400, 48)
    assert lane.isHidden()
    seek = QSignalSpy(lane.seekRequested)
    edit = QSignalSpy(lane.editRequested)
    lane.set_track(track, 20.)
    lane.set_peaks([.1, .8, .4])
    lane.set_time(5.)
    lane.show()
    app.processEvents()
    QTest.mouseClick(lane, Qt.MouseButton.LeftButton, pos=QPoint(200, 32))
    assert seek.at(0)[0] == pytest.approx(10.)
    QTest.keyClick(lane, Qt.Key.Key_Right)
    assert seek.at(1)[0] == 6.
    QTest.mouseDClick(lane, Qt.MouseButton.LeftButton, pos=QPoint(100, 32))
    assert edit.count() == 1
    lane.set_track({**track, 'offset': 4., 'end_mode': 'loop'}, 20.)
    assert lane.peaks == [.1, .8, .4]
    lane.grab()  # Both silence and loop paint without reading media.
    lane.set_track({**track, 'path': '/replacement.wav'}, 20.)
    assert lane.peaks == []
    lane.set_track(None, 20.)
    assert lane.isHidden()
    lane.close()


def test_refresh_preserves_subcentisecond_trim(app, track):
    dialog = SoundtrackDialog()
    exact = {**track, 'in': 2.000123456, 'out': 8.000234567}
    dialog.set_track(exact)
    assert dialog.in_control.value() == pytest.approx(exact['in'], abs=1e-11)
    assert not dialog.apply_button.isEnabled()
    dialog.close()


def test_media_actions_and_narrow_dialog(app, track):
    dialog = SoundtrackDialog()
    imported = QSignalSpy(dialog.importRequested)
    relinked = QSignalSpy(dialog.relinkRequested)
    removed = QSignalSpy(dialog.removeRequested)
    dialog.set_track(track)
    dialog.resize(340, 580)
    dialog.show()
    app.processEvents()
    QTest.mouseClick(dialog.import_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(dialog.relink_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(dialog.remove_button, Qt.MouseButton.LeftButton)
    assert imported.count() == relinked.count() == removed.count() == 1
    assert dialog.gain.maximum() == 1.
    assert dialog.gain.textFromValue(.8) == dialog.gain.locale().toString(80., 'f', 2)
    assert dialog.minimumSizeHint().width() <= 340
    dialog.close()


def test_same_authored_track_preserves_draft_but_refreshes_duration(app, track):
    dialog = SoundtrackDialog()
    edited = QSignalSpy(dialog.trackEdited)
    dialog.set_track(track, 12.)
    dialog.in_control.setValue(3.)
    dialog.offset_control.setValue(4.)
    dialog.end_mode.setCurrentIndex(dialog.end_mode.findData('loop'))
    dialog.set_track(dict(track), 20.)
    assert dialog.in_control.value() == 3.
    assert dialog.offset_control.value() == 4.
    assert dialog.end_mode.currentData() == 'loop'
    assert dialog.apply_button.isEnabled()
    assert '20.00 s' in dialog.summary.text()
    assert edited.count() == 0
    # A newly authored track (including Undo) replaces pending edits.
    dialog.set_track({**track, 'offset': 2.}, 20.)
    assert dialog.in_control.value() == track['in']
    assert dialog.offset_control.value() == 2.
    assert dialog.end_mode.currentData() == 'silence'
    assert not dialog.apply_button.isEnabled()
    assert edited.count() == 0
    dialog.close()


def test_external_names_and_status_are_plain_text(app, track):
    dialog = SoundtrackDialog()
    dialog.set_track({**track, 'name': '<b>Tone & rhythm</b>'}, 12.)
    dialog.set_status('<img src="missing.png"> Relink needed')
    assert dialog.summary.textFormat() == Qt.TextFormat.PlainText
    assert dialog.status_label.textFormat() == Qt.TextFormat.PlainText
    assert '<b>Tone & rhythm</b>' in dialog.summary.text()
    assert 'Preview always monitors the soundtrack' in dialog.hint_label.text()
    dialog.resize(340, 600)
    dialog.show()
    app.processEvents()
    assert dialog.minimumSizeHint().width() <= 340
    dialog.close()


def test_drag_is_frame_snapped_and_commits_only_on_release(app, track):
    lane = SoundtrackLane(); lane.resize(400, 48)
    lane.set_track(track, 20., 24); lane.set_editable(True); lane.show(); app.processEvents()
    moved, seek = QSignalSpy(lane.offsetRequested), QSignalSpy(lane.seekRequested)
    QTest.mousePress(lane, Qt.MouseButton.LeftButton, pos=QPoint(40, 32))
    QTest.mouseMove(lane, QPoint(81, 32))
    assert moved.count() == seek.count() == 0
    assert lane.track == track
    assert lane._drag_offset == pytest.approx(73 / 24)
    lane.set_track(track, 20., 24)  # Transport/waveform refresh does not lose the gesture.
    lane.set_time(2.); lane.set_peaks([.5, .8]); lane.grab()
    assert lane._drag_offset == pytest.approx(73 / 24)
    QTest.mouseRelease(lane, Qt.MouseButton.LeftButton, pos=QPoint(81, 32))
    assert moved.count() == 1 and moved.at(0)[0] == pytest.approx(73 / 24)
    assert seek.count() == 0 and lane.track == track and lane._drag_offset is None
    lane.close()


@pytest.mark.parametrize('cancel', ['escape', 'replace', 'disable', 'duration'])
def test_drag_cancel_never_seeks_or_changes_track(app, track, cancel):
    lane = SoundtrackLane(); lane.resize(400, 48)
    lane.set_track(track, 20., 24); lane.set_editable(True); lane.show(); app.processEvents()
    moved, seek = QSignalSpy(lane.offsetRequested), QSignalSpy(lane.seekRequested)
    QTest.mousePress(lane, Qt.MouseButton.LeftButton, pos=QPoint(40, 32))
    QTest.mouseMove(lane, QPoint(100, 32))
    assert lane._drag_offset is not None
    if cancel == 'escape': QTest.keyClick(lane, Qt.Key.Key_Escape)
    elif cancel == 'replace': lane.set_track(dict(track, path='/other.wav'), 20., 24)
    elif cancel == 'disable': lane.set_editable(False)
    else: lane.set_track(track, 10., 24)
    QTest.mouseRelease(lane, Qt.MouseButton.LeftButton, pos=QPoint(100, 32))
    assert moved.count() == seek.count() == 0
    assert lane._drag_offset is None
    lane.close()


def test_drag_bounds_nudge_and_click_have_distinct_intents(app, track):
    lane = SoundtrackLane(); lane.resize(400, 48)
    lane.set_track(track, 20., 24); lane.set_editable(True); lane.show(); app.processEvents()
    moved, seek = QSignalSpy(lane.offsetRequested), QSignalSpy(lane.seekRequested)
    for end, expected in [(QPoint(-100, 32), -6.), (QPoint(500, 32), 479 / 24)]:
        QTest.mousePress(lane, Qt.MouseButton.LeftButton, pos=QPoint(40, 32))
        QTest.mouseMove(lane, end)
        QTest.mouseRelease(lane, Qt.MouseButton.LeftButton, pos=end)
        assert moved.at(moved.count() - 1)[0] == expected
    assert moved.count() == 2 and seek.count() == 0
    QTest.keyClick(lane, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert moved.at(2)[0] == 25 / 24
    QTest.mouseClick(lane, Qt.MouseButton.LeftButton, pos=QPoint(40, 32))
    assert seek.at(0)[0] == 2.
    # Slight hand movement below the platform drag threshold is still a click.
    QTest.mousePress(lane, Qt.MouseButton.LeftButton, pos=QPoint(40, 32))
    QTest.mouseMove(lane, QPoint(41, 32))
    QTest.mouseRelease(lane, Qt.MouseButton.LeftButton, pos=QPoint(41, 32))
    assert moved.count() == 3 and seek.count() == 2
    lane.close()


def test_readonly_lane_does_not_move_or_normalize_existing_placements(app, track):
    lane = SoundtrackLane(); lane.resize(400, 48)
    lane.set_track(dict(track, offset=25.), 20., 24)
    assert lane.track['offset'] == 25.
    lane.set_track(track, 20., 24); lane.show(); app.processEvents()
    moved = QSignalSpy(lane.offsetRequested)
    QTest.mousePress(lane, Qt.MouseButton.LeftButton, pos=QPoint(40, 32))
    QTest.mouseMove(lane, QPoint(100, 32))
    QTest.mouseRelease(lane, Qt.MouseButton.LeftButton, pos=QPoint(100, 32))
    QTest.keyClick(lane, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert moved.count() == 0 and lane.track == track
    lane.close()


def test_negative_placement_dialog_and_off_canvas_drag_handle(app, track):
    track = dict(track, offset=-10.)
    dialog = SoundtrackDialog(); dialog.set_track(track, 20.)
    assert dialog.offset_control.value() == -10.
    assert not dialog.has_pending_changes()
    dialog.gain.setValue(.5); dialog.apply()
    assert dialog.track['offset'] == -10.
    assert dialog.track['in'] == track['in'] and dialog.track['out'] == track['out']
    dialog.close()
    lane = SoundtrackLane(); lane.resize(400, 48)
    lane.set_track(track, 20., 24); lane.set_editable(True); lane.show(); app.processEvents()
    moved = QSignalSpy(lane.offsetRequested)
    # The audio ends before zero; its visible label can bring it back.
    QTest.mousePress(lane, Qt.MouseButton.LeftButton, pos=QPoint(40, 8))
    QTest.mouseMove(lane, QPoint(240, 8))
    QTest.mouseRelease(lane, Qt.MouseButton.LeftButton, pos=QPoint(240, 8))
    assert moved.count() == 1 and moved.at(0)[0] == 0.
    lane.set_track(dict(track, offset=0.), 20., 24)
    QTest.keyClick(lane, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert moved.at(1)[0] == -1 / 24
    lane.close()


def test_negative_waveform_draws_the_audible_part(app, track):
    lane = SoundtrackLane(); lane.resize(400, 48)
    lane.set_track(dict(track, offset=-1.), 20., 24)
    lane.set_peaks([.1, .3, .9, .5, .6, .4, .2, .8, .7, .2]); lane.show(); app.processEvents()
    negative = lane.grab().toImage().copy(15, 18, 380, 27)
    lane.set_track(dict(track, offset=0., **{'in': 3.}), 20., 24)
    equivalent = lane.grab().toImage().copy(15, 18, 380, 27)
    assert negative == equivalent
    lane.set_track(dict(track, offset=-1e9, end_mode='loop'), 20., 24)
    assert not lane.grab().isNull()  # Drawing stays bounded to the viewport.
    lane.close()
