import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt, QThreadPool
from PySide6.QtTest import QTest
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


def test_wheel_zoom_retains_point_under_cursor_and_plain_scroll_only_pans(app):
    viewer = SynthViewer(); viewer.resize(400, 320); viewer.show(); viewer.set_zoom(2.); app.processEvents()
    try:
        anchor = QPoint(260, 170)
        before = viewer.target_rect(); position = (QPointF(anchor) - before.topLeft()) / viewer.display_scale()
        QTest.wheelEvent(viewer.windowHandle(), anchor, QPoint(0, 120), stateKey=Qt.KeyboardModifier.ControlModifier)
        after = viewer.target_rect()
        assert viewer.zoom > 2.
        assert ((QPointF(anchor) - after.topLeft()) / viewer.display_scale() - position).manhattanLength() < .001
        zoom = viewer.zoom; pan = QPointF(viewer.pan)
        QTest.wheelEvent(viewer.windowHandle(), anchor, QPoint(0, -120))
        assert viewer.zoom == zoom and viewer.pan != pan
    finally: viewer.close()


def test_workspace_zoom_and_column_width_do_not_change_the_document(app):
    window = SynthStudio(); window.show(); app.processEvents()
    try:
        project = copy.deepcopy(window.composition); sequence = copy.deepcopy(window.sequence)
        generation = window.settings_generation
        window.view_zoom.setValue(150)
        assert window.viewer.zoom == 1.5
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
