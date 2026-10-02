"""Native A/B preview and Keep/Discard never leak into committed export data."""
import copy
import os
import time
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from studio_theme import apply_theme
from synth_exploration import capture_snapshot, restore_snapshot
from synth_exploration_ui import SnapshotsDialog, VaryEffectDialog
from synth_sequence import render_sequence_frame
from synth_studio import SynthStudio
from test_synth_creative import animated
from test_synth_video import clip
from synth_video import video_composition
from synth_starting_points import new_piece


def wait_for(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline: QTest.qWait(10)
    assert predicate()


def settle(window):
    wait_for(lambda: not window.render_running and not window.render_queued and not window.preview_debounce.isActive())


@pytest.fixture
def window(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([]); apply_theme(app)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(SynthStudio, 'preview_size', lambda self: (96, 72) if self.quality.currentIndex() == 0 else (192, 144))
    w = SynthStudio(composition=animated(), settings=QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat))
    w.auto_prepare.setChecked(False); w.resize(1280, 720); w.show(); settle(w)
    w.composer.effects_panel.inspect_effect('tape')
    yield w
    w.end_comparison(); w.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()


def capture(window):
    project, identifier = capture_snapshot(window.composition, 'Original')
    window.composer.commit(project, 'snapshot-capture'); settle(window)
    return identifier


def test_same_frame_comparison_is_read_only_and_edits_return_to_b(window):
    identifier = capture(window)
    window.composer.effects_panel.change_creative('damage', 1.6); window.timeline.setValue(30); settle(window)
    working = copy.deepcopy(window.composition); history = copy.deepcopy(window.undo_compositions)
    original = restore_snapshot(window.composition, identifier)
    window.compare_snapshot(identifier); settle(window)
    assert window.current_time == 1.2 and window.timeline.value() == 30
    assert window.viewer.packet[1] == render_sequence_frame(window.preview_sequence(), 1.2, window.preview_size()).tobytes()
    assert window.composition == working and window.undo_compositions == history
    a = window.viewer.packet
    window.set_comparison_side('b'); settle(window)
    assert window.current_time == 1.2 and window.viewer.packet != a
    serial = window.request_serial
    window.set_comparison_side('a'); settle(window); assert window.viewer.packet == a
    assert 'cached' in window.preview_status.text() and window.request_serial > serial
    window.composer.effects_panel.change_creative('damage', 1.7); settle(window)
    assert window.comparison['side'] == 'b'
    assert window.viewer.packet[1] == render_sequence_frame(window.sequence, 1.2, window.preview_size()).tobytes()
    window.restore_saved_snapshot(identifier); settle(window)
    assert window.composition == original and window.comparison is None
    window.undo_composition(); assert window.composition['effects']['tape']['creative']['values']['damage'] == 1.7


def test_audition_discard_is_clean_and_keep_is_one_undoable_edit(window):
    window.mark_document_clean(); before = copy.deepcopy(window.composition); history = len(window.undo_compositions)
    dialog = VaryEffectDialog(window, 'tape'); dialog.show()
    assert not dialog.controls['cadence'].isChecked()
    dialog.try_variation(); settle(window)
    assert window.composition == before and len(window.undo_compositions) == history
    assert window.has_unsaved_changes() and window.audition_pending()
    assert not window.save_sequence_dialog(); window.export_dialog(); assert window.export_job is None
    assert window.preview_sequence() != window.sequence
    dialog.reject(); settle(window)
    assert window.composition == before and not window.has_unsaved_changes()
    dialog.deleteLater()
    dialog = VaryEffectDialog(window, 'tape'); dialog.show(); dialog.try_variation(); settle(window)
    expected = copy.deepcopy(dialog.candidate)
    dialog.keep_variation(); settle(window)
    assert window.composition == expected and len(window.undo_compositions) == history + 1
    assert window.comparison is None and window.has_unsaved_changes()
    window.undo_composition(); assert window.composition == before
    window.redo_composition(); assert window.composition == expected
    dialog.deleteLater()


def test_snapshot_controls_capture_remove_restore_and_explain_incompatibility(window):
    dialog = SnapshotsDialog(window); dialog.show()
    assert not dialog.compare.isEnabled()
    dialog.name.setText('Take A'); dialog.capture_current(); identifier = dialog.selected_id()
    assert dialog.compare.isEnabled() and window.has_unsaved_changes()
    window.composer.document['fps'] = 20; window.composer.commit(window.composer.document, 'fps')
    dialog.refresh(); assert not dialog.compare.isEnabled() and dialog.restore.isEnabled()
    assert 'FPS' in dialog.notice.text()
    dialog.restore_selected(); assert window.composition['fps'] == 25
    dialog.compare_selected(); settle(window); assert window.comparison['snapshot_id'] == identifier
    dialog.remove_selected(); assert window.comparison is None and not window.composition.get('snapshots')
    window.undo_composition(); assert window.composition['snapshots'][0]['id'] == identifier
    dialog.reject(); dialog.deleteLater()


def test_stale_a_render_cannot_enter_b_cache_or_view(window, monkeypatch):
    identifier = capture(window); window.composer.effects_panel.change_creative('damage', 1.6); settle(window)
    queued = []; monkeypatch.setattr(window.jobs, 'start', queued.append)
    window.compare_snapshot(identifier); window.preview_debounce.stop(); window.request_frame()
    old = queued[-1]; assert old.sequence == window.comparison['a_sequence']
    window.set_comparison_side('b'); window.preview_debounce.stop(); window.request_frame()
    shown = window.viewer.packet
    window._receive_foreground_frame(old, (old.settings_generation, old.request_serial, 0., (1, 1), b'old', .01))
    window._release_job(old)
    assert window.viewer.packet == shown and not window.preview_frames.items
    wait_for(lambda: len(queued) == 2)
    current = queued[-1]; assert current.sequence == window.sequence
    image = render_sequence_frame(current.sequence, current.time_seconds, current.size)
    window._receive_foreground_frame(current, (current.settings_generation, current.request_serial, current.time_seconds, image.size, image.tobytes(), .01))
    window._release_job(current); assert window.viewer.packet[1] == image.tobytes()


def test_prepared_a_frames_and_export_b_remain_separate(window, monkeypatch, tmp_path):
    project = copy.deepcopy(window.composition); project['sections'][0]['duration'] = .12
    window.composer.commit(project, 'duration'); settle(window)
    identifier = capture(window); window.composer.effects_panel.change_creative('damage', 1.6); settle(window)
    window.compare_snapshot(identifier); settle(window); window.prepare_playback()
    wait_for(lambda: window.prepare_job is None and not window.preparation_explicit)
    for frame in range(3):
        size, raw = window.preview_frames.get(frame)
        assert raw == render_sequence_frame(window.preview_sequence(), frame/25, size).tobytes()
    queued = []; monkeypatch.setattr(window.jobs, 'start', queued.append)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path/'working.mp4'), ''))
    window.export_dialog(); job = window.export_job
    assert job.sequence == window.sequence and job.sequence != window.preview_sequence()
    window._finish_export(job)


def test_comparison_quality_changes_and_document_replacement_clear_a(window):
    identifier = capture(window); window.compare_snapshot(identifier); settle(window)
    window.quality.setCurrentIndex(1); settle(window)
    assert window.viewer.packet[0] == (192, 144)
    assert window.viewer.packet[1] == render_sequence_frame(window.preview_sequence(), 0., (192, 144)).tobytes()
    window.set_composition(animated('frame_jitter'), guard=False); settle(window)
    assert window.comparison is None and window.preview_sequence() == window.sequence


def test_snapshot_capture_retains_ready_pixels_and_ui_save_open_library(window, monkeypatch, tmp_path):
    cached = dict(window.preview_frames.items); identifier = capture(window)
    assert dict(window.preview_frames.items) == cached
    assert 'cached' in window.preview_status.text()
    path = tmp_path / 'snapshots.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.save_sequence_dialog() and not window.has_unsaved_changes()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    window.load_sequence_dialog(); settle(window)
    assert window.composition['snapshots'][0]['id'] == identifier
    assert not window.has_unsaved_changes()


def test_cancel_close_retains_audition_and_discard_restores_b(window, monkeypatch):
    dialog = VaryEffectDialog(window, 'tape'); dialog.try_variation(); settle(window)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.close() and window.audition_pending() and not window.closing
    dialog.reject(); settle(window); assert not window.audition_pending()
    dialog.deleteLater()


def test_video_a_compares_treated_signal_and_restores_source_preview(window, clip):
    window.set_composition(video_composition(clip), guard=False); settle(window)
    window.source_preview.setChecked(True); settle(window)
    identifier = capture(window)
    window.composer.effects_panel.inspect_effect('tape')
    window.composer.effects_panel.apply_look(); settle(window)
    window.compare_snapshot(identifier); settle(window)
    assert not window.preview_bypass() and not window.source_preview.isEnabled()
    assert window.viewer.packet[1] == render_sequence_frame(window.preview_sequence(), 0., window.preview_size(), window.video_frames).tobytes()
    window.end_comparison(); settle(window)
    assert window.source_preview.isChecked() and window.source_preview.isEnabled()


def test_snapshot_media_cannot_be_overwritten_by_save_as(window, clip, tmp_path):
    video, _ = capture_snapshot(video_composition(clip), 'Original source')
    project = new_piece('shape'); project['snapshots'] = video['snapshots']
    window.set_composition(project, guard=False); settle(window)
    alias = tmp_path / 'alias.mov'; alias.symlink_to(clip['path'])
    assert window.protected_document_destination(clip['path'])
    assert window.protected_document_destination(alias)


def test_selected_preview_keeps_absolute_clock_when_switching_during_play(window, monkeypatch):
    window.composer.duplicate_section(); settle(window)
    identifier = capture(window)
    window.composer.effects_panel.change_creative('damage', 1.6); settle(window)
    window.section_timeline.select_at(1); window.preview_scope.setCurrentIndex(1)
    window.compare_snapshot(identifier); settle(window)
    scope = window.active_preview_scope(); start = scope.intervals[0][0]
    original_clock = time.monotonic
    clock = [100.]; monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    window.play.setChecked(True); window.play_timer.stop()
    clock[0] += .4; window.advance()
    assert window.timeline.value() == start + 10
    window.set_comparison_side('b'); assert window.timeline.value() == start + 10
    clock[0] += .2; window.advance()
    assert window.timeline.value() == start + 15
    window.play.setChecked(False)
    monkeypatch.setattr('synth_studio.time.monotonic', original_clock); settle(window)
    assert window.viewer.packet[1] == render_sequence_frame(window.sequence, (start+15)/25, window.preview_size()).tobytes()
