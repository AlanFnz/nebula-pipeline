"""Offscreen functional tests; runs real Qt events, decoding and render workers."""
import copy
import os
import subprocess
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from engine import render_frame
from media import decode_frames
from studio import Studio, STYLE


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    return app


def wait_for(predicate, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("GUI operation timed out")


@pytest.fixture
def window(app, tmp_path):
    clip = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=3", "-c:v", "libx264", str(clip)], check=True)
    window = Studio()
    window.show()
    window.open_clip(clip)
    wait_for(lambda: window.info is not None and len(window.frames) >= 24)
    yield window
    window.close()
    wait_for(lambda: not window.isVisible())


def settled(w):
    return not w.debounce.isActive() and w.preview_future.done() and w.timeline.value() in w.frames


def test_rapid_changes_scrub_bypass_ab_and_stale_job(window):
    w = window
    old_generation = w.generation
    old_packet = w.viewer.packet
    for i in range(18):
        w.controls["blur"].spins[0].setValue(i * .2)
        w.timeline.setValue(i)
        QApplication.processEvents()
    w.timeline.setValue(12)
    w.stage_checks["print"].setChecked(False)
    wait_for(lambda: settled(w))
    w.capture.click()
    snapshot = copy.deepcopy(w.snapshot)
    w.stage_checks["scan"].setChecked(False)
    w.controls["px"].spins[0].setValue(8)
    wait_for(lambda: settled(w))
    # A and B both use the exact source/time; only settings differ.
    source = next(decode_frames(w.info, w.params["fps"], 12, 1, 480))[1]
    packet = w.frames[12]
    assert packet[1] == render_frame(source, w.params, 12).tobytes()
    assert packet[2] == render_frame(source, snapshot, 12).tobytes()
    # Simulate an already-queued late result and late error from an obsolete job.
    before = w.viewer.packet
    w.on_event(old_generation, "frame", (12, old_packet, 99))
    w.on_event(old_generation, "error", "stale failure")
    assert w.viewer.packet is before
    assert w.status.text() != "Preview error · stale failure"
    w.timeline.setValue(6)
    wait_for(lambda: settled(w))
    assert w.snapshot == snapshot
    assert w.compare.isChecked()


def test_loop_playback_preset_and_full_size(window, tmp_path):
    from parameters import load, save
    w = window
    w.loop_start.setValue(.5)
    w.loop_length.setCurrentIndex(0)
    wait_for(lambda: settled(w))
    w.timeline.setValue(6)
    w.play.click()
    initial = w.timeline.value()
    wait_for(lambda: w.timeline.value() != initial)
    w.play.click()
    w.capture_a()
    w.controls["grain"].spins[0].setValue(.2)
    file = tmp_path / "preset.json"
    save(file, w.params)
    w.apply_params(load(file))
    assert w.snapshot is None
    assert w.controls["grain"].spins[0].value() == .2
    w.full_still()
    wait_for(lambda: settled(w))
    assert w.viewer.packet[0] == (320, 240)
    w.capture_a()
    w.controls["fps"].spins[0].setValue(10)
    assert w.snapshot is None


def test_export_from_gui_and_close_during_preview(window, tmp_path):
    w = window
    dest = tmp_path / "gui-export.mp4"
    w.loop_length.setCurrentIndex(0)
    w.start_export(dest)
    wait_for(lambda: w.export_future.done() and w.export_progress.value() == 100)
    assert dest.exists()
    assert w.export_button.isEnabled()
    w.full_still()
    w.close()
    wait_for(lambda: not w.isVisible())
