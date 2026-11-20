"""Monitor feedback follows work, without changing the artwork or rendering it."""
import copy

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog

from nebula.ui.synth_studio import ExportJob
from test_synth_composer_ui import window, wait_until
from test_synth_preview_range import setup
from test_synth_preview_scope import prepared


def test_foreground_loading_stops_on_completion_error_and_hide(window, monkeypatch):
    before = setup(window, monkeypatch)
    jobs = []
    monkeypatch.setattr(window.jobs, 'start', jobs.append)
    window.preview_frames.clear()
    window.request_frame()
    status = window.preview_status
    assert status.mode == 'loading' and status.animation.isActive()
    assert status.text() == 'Updating preview…'
    serial = window.request_serial
    QTest.qWait(220)
    assert len(jobs) == 1 and window.request_serial == serial
    window.hide()
    assert not status.animation.isActive()
    window.show()
    assert status.animation.isActive()
    jobs[0].run()
    assert status.mode == 'idle' and not status.animation.isActive()
    assert not window.preview_image_stale
    assert 'Preview paused' in status.text()
    window.preview_frames.clear(); window.request_frame()
    jobs[-1].signals.failed.emit('Test failure')
    assert status.mode == 'idle' and not status.animation.isActive()
    assert 'unavailable' in status.text()
    assert window.composition == before


def test_preparation_and_cancel_report_work_even_when_paused(window, monkeypatch):
    before = setup(window, monkeypatch)
    assert window.frame_status.text() == 'Up to date'
    jobs = []
    monkeypatch.setattr(window.jobs, 'start', jobs.append)
    window.prepare_playback()
    assert not window.play.isChecked()
    assert window.preview_status.mode == 'loading'
    assert 'Preparing playback range' in window.preview_status.text()
    assert window.frame_status.text() == 'Up to date'
    window.prepare_playback()  # Cancel while the batch is pending.
    assert window.preview_status.mode == 'idle'
    assert not window.preview_status.animation.isActive()
    assert 'cancelled' in window.preview_status.text()
    jobs[0].run()  # A cancelled worker cannot restart the spinner.
    assert window.preview_status.mode == 'idle'
    assert window.composition == before


def test_export_wait_does_not_spin_and_resumes_loop_preview_after_edit(window, monkeypatch, tmp_path):
    setup(window, monkeypatch)
    window.prepare_playback(); prepared(window)
    window.loop_preview_range.setChecked(True)
    jobs = []
    start = window.jobs.start
    monkeypatch.setattr(window.jobs, 'start', jobs.append)
    window.auto_prepare.setChecked(True)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(tmp_path/'clip.mp4'), ''))
    window.export_dialog()
    export = window.export_job
    assert isinstance(export, ExportJob)
    exported_sequence = copy.deepcopy(export.sequence)
    status = window.preview_status
    assert status.mode == 'waiting' and not status.animation.isActive()
    window.composer.macro_controls['width'].spin.setValue(1.2)
    QTest.qWait(150)
    assert window.preview_image_stale
    assert status.mode == 'waiting' and not status.animation.isActive()
    assert status.text() == 'Preview waiting for export · changes pending'
    assert window.frame_status.text() == 'Waiting'
    assert 'changes pending' in status.accessibleDescription()
    assert export.sequence == exported_sequence and export.sequence != window.sequence
    monkeypatch.setattr(window.jobs, 'start', start)
    window._finish_export(export)
    assert status.mode == 'loading'
    wait_until(lambda: not window.preview_image_stale and status.mode == 'idle')
    assert not status.animation.isActive()
    assert window.loop_preview_range.isChecked()
    assert window.frame_status.text() == 'Up to date'


def test_edit_and_seek_only_mark_current_after_the_matching_frame_is_shown(window, monkeypatch):
    setup(window, monkeypatch)
    jobs = []
    monkeypatch.setattr(window.jobs, 'start', jobs.append)
    light = window.frame_status
    assert light.isVisible() and light.text() == 'Up to date'
    old_packet = window.viewer.packet
    window.invalidate(force_clear=True)
    assert light.text() == 'Updating' and window.viewer.packet is old_packet
    wait_until(lambda: len(jobs) == 1)
    window.invalidate(force_clear=True)
    jobs[0].run()
    assert light.text() == 'Updating' and window.viewer.packet is old_packet
    wait_until(lambda: len(jobs) == 2)
    window.timeline.setValue(6)
    jobs[1].run()
    assert light.text() != 'Up to date' and window.viewer.packet is old_packet
    wait_until(lambda: len(jobs) == 3)
    jobs[2].run()
    assert light.text() == 'Up to date'
    assert window.cover_frame == (window.settings_generation, 6 / window.preview_fps())
    window.timeline.setValue(8)
    assert light.text() == 'Updating'
    jobs[-1].signals.failed.emit('Missing frame')
    assert light.text() == 'Unavailable'
    window.request_frame()
    assert light.text() == 'Updating'
    jobs[-1].run()
    assert light.text() == 'Up to date'
    # Returning to the previously shown frame needs no new render.
    count = len(jobs)
    window.timeline.setValue(6)
    assert light.text() == 'Up to date' and len(jobs) == count


def test_export_does_not_hide_a_foreground_update_that_can_run(window, monkeypatch):
    setup(window, monkeypatch)
    jobs = []
    monkeypatch.setattr(window.jobs, 'start', jobs.append)
    window.export_job = ExportJob(window.preset, '/tmp/unused.mp4', (64, 48), window.sequence)
    window.invalidate(force_clear=True)
    wait_until(lambda: bool(jobs))
    assert window.preview_status.mode == 'loading'
    jobs[-1].run()
    assert not window.preview_image_stale
    assert window.preview_status.mode == 'waiting'
    assert 'changes pending' not in window.preview_status.text()
    window._finish_export(window.export_job)
    assert window.preview_status.mode == 'idle'


def test_loop_waits_for_its_own_frame_while_other_batches_finish(window, monkeypatch):
    setup(window, monkeypatch)
    jobs = []
    monkeypatch.setattr(window.jobs, 'start', jobs.append)
    window.loop_preview_range.setChecked(True)
    window.invalidate(force_clear=True)
    wait_until(lambda: not window.preview_debounce.isActive())
    assert window.frame_status.text() == 'Waiting'
    window.prepare_full_playback()
    frame = window.timeline.value()
    assert frame not in jobs[0].frames
    assert window.preview_status.mode == 'loading' and window.frame_status.text() == 'Waiting'
    while frame not in jobs[-1].frames:
        job = jobs[-1]
        job.run()
        wait_until(lambda: jobs[-1] is not job)
    assert window.frame_status.text() == 'Updating'
    jobs[-1].signals.failed.emit('Could not prepare this batch')
    assert window.frame_status.text() == 'Unavailable'
    window.prepare_full_playback()
    assert frame in jobs[-1].frames and window.frame_status.text() == 'Updating'
    jobs[-1].run()
    assert window.frame_status.text() == 'Up to date'
    window.cancel_preparation()
