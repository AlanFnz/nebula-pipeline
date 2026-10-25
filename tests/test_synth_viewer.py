import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt, QThreadPool
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from synth_studio import SynthStudio
from synth_viewer import SynthViewer


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_fit_percent_zoom_panning_and_reset_use_canvas_dimensions(app):
    viewer = SynthViewer(); viewer.resize(500, 400); viewer.set_canvas_size((1000, 800)); viewer.show(); app.processEvents()
    try:
        assert viewer.display_scale() == .5
        assert viewer.target_rect().width() == 500
        viewer.set_zoom(1.)
        assert viewer.target_rect().width() == 1000
        assert viewer.target_rect().height() == 800
        QTest.mousePress(viewer, Qt.MouseButton.LeftButton, pos=QPoint(250, 200))
        QTest.mouseMove(viewer, QPoint(290, 230))
        QTest.mouseRelease(viewer, Qt.MouseButton.LeftButton, pos=QPoint(290, 230))
        assert viewer.pan == QPointF(40, 30)
        viewer.pan = QPointF(5000, -5000); viewer.clamp_pan()
        assert viewer.pan == QPointF(250, -200)
        viewer.set_zoom(0.)
        assert viewer.pan.isNull() and viewer.target_rect().width() == 500
    finally: viewer.close()


@pytest.mark.parametrize('modifier', [Qt.KeyboardModifier.NoModifier,
                                     Qt.KeyboardModifier.ControlModifier,
                                     Qt.KeyboardModifier.MetaModifier])
def test_wheel_zoom_retains_point_under_cursor_and_shift_scroll_pans(app, modifier):
    viewer = SynthViewer(); viewer.resize(400, 320); viewer.show(); viewer.set_zoom(2.); app.processEvents()
    try:
        anchor = QPoint(260, 170)
        before = viewer.target_rect(); position = (QPointF(anchor) - before.topLeft()) / viewer.display_scale()
        QTest.wheelEvent(viewer.windowHandle(), anchor, QPoint(0, 120), stateKey=modifier)
        after = viewer.target_rect()
        assert viewer.zoom > 2.
        assert ((QPointF(anchor) - after.topLeft()) / viewer.display_scale() - position).manhattanLength() < .001
        zoom = viewer.zoom; pan = QPointF(viewer.pan)
        QTest.wheelEvent(viewer.windowHandle(), anchor, QPoint(0, -120), stateKey=Qt.KeyboardModifier.ShiftModifier)
        assert viewer.zoom == zoom and viewer.pan != pan
        QTest.wheelEvent(viewer.windowHandle(), anchor, QPoint(0, -120), stateKey=modifier)
        assert viewer.zoom == pytest.approx(2.)
    finally: viewer.close()


def send_trackpad_scroll(viewer, pixels, *, angle=QPoint(), phase=Qt.ScrollPhase.ScrollUpdate):
    anchor = QPointF(260, 170)
    event = QWheelEvent(anchor, viewer.mapToGlobal(anchor), pixels, angle,
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, phase, False)
    QApplication.sendEvent(viewer, event)


def test_trackpad_zoom_is_continuous_and_gesture_boundaries_preserve_fit(app):
    viewer = SynthViewer(); viewer.resize(400, 320); viewer.show(); app.processEvents()
    try:
        spy = QSignalSpy(viewer.zoomChanged)
        for phase in (Qt.ScrollPhase.ScrollBegin, Qt.ScrollPhase.ScrollEnd):
            send_trackpad_scroll(viewer, QPoint(), phase=phase)
        # A trackpad's horizontal component is not a vertical zoom fallback.
        send_trackpad_scroll(viewer, QPoint(10, 0), angle=QPoint(0, 120))
        assert viewer.zoom == 0. and spy.count() == 0
        fit_scale = viewer.display_scale()
        send_trackpad_scroll(viewer, QPoint(0, 1), angle=QPoint(0, 120))
        assert fit_scale < viewer.zoom < fit_scale * 1.01

        viewer.set_zoom(2.)
        anchor = QPointF(260, 170)
        position = (anchor - viewer.target_rect().topLeft()) / viewer.display_scale()
        for _ in range(12):
            send_trackpad_scroll(viewer, QPoint(0, 1))
        assert viewer.zoom == pytest.approx(2. * 2 ** .1)
        assert ((anchor - viewer.target_rect().topLeft()) / viewer.display_scale() - position).manhattanLength() < .001
        for _ in range(12):
            send_trackpad_scroll(viewer, QPoint(0, -1))
        assert viewer.zoom == pytest.approx(2.)
        send_trackpad_scroll(viewer, QPoint(0, 1000000))
        assert viewer.zoom == 8.
        send_trackpad_scroll(viewer, QPoint(0, -1000000))
        assert viewer.zoom == .05
        QTest.mouseDClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(200, 160))
        assert viewer.zoom == 0. and viewer.pan.isNull()
    finally: viewer.close()


def test_workspace_zoom_and_column_width_do_not_change_the_document(app):
    window = SynthStudio(); window.show(); app.processEvents()
    try:
        project = copy.deepcopy(window.composition); sequence = copy.deepcopy(window.sequence)
        generation = window.settings_generation
        window.view_zoom.setValue(150)
        assert window.viewer.zoom == 1.5
        send_trackpad_scroll(window.viewer, QPoint(0, 12))
        assert window.viewer.zoom > 1.5
        assert window.view_zoom.value() == pytest.approx(window.viewer.zoom * 100, abs=.05)
        assert not window.fit_view_button.isChecked()
        before = window.splitter.sizes()
        window.splitter.moveSplitter(before[0] - 100, 1); app.processEvents()
        assert window.splitter.sizes()[1] > before[1] + 70
        assert window.splitter.handleWidth() >= 8
        assert window.composition == project and window.sequence == sequence
        assert window.settings_generation == generation
    finally:
        window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()


def test_first_launch_fullscreen_then_restores_window_mode_splitter_and_zoom(app, tmp_path):
    settings = QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat)
    window = SynthStudio(settings=settings); window.show_workspace(); app.processEvents()
    try:
        assert window.isFullScreen()
        assert not window.fullscreen_button.isCheckable()
        QTest.mouseClick(window.fullscreen_button, Qt.MouseButton.LeftButton); app.processEvents()
        assert not window.isFullScreen()
        assert window.fullscreen_button.accessibleName() == 'Full screen'
        window.resize(1280, 780); app.processEvents()
        window.splitter.moveSplitter(610, 1); window.viewer.set_zoom(.75)
    finally:
        window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()
    assert settings.value('window/mode') == 'normal'
    assert settings.value('window/geometry') and settings.value('window/splitter')
    restored = SynthStudio(settings=settings); restored.show_workspace(); app.processEvents()
    try:
        assert not restored.isFullScreen()
        assert restored.viewer.zoom == .75 and restored.view_zoom.value() == 75
        assert restored.splitter.sizes()[1] >= 380
        # A detailed copy does not own or overwrite the main workspace settings.
        restored.open_detailed_copy(); child = restored.detail_windows[-1]
        assert child.workspace_settings is None
        child.close()
    finally:
        restored.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()
