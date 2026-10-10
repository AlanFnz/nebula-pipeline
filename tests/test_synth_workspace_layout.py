"""Workspace resizing must keep transport reachable and documents unchanged."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QSettings, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from studio_theme import apply_theme
from synth_studio import SynthStudio


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def close_window(window, app):
    window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()


def visible_in(widget, viewport):
    return viewport.rect().contains(widget.mapTo(viewport, widget.rect().center()))


@pytest.mark.parametrize('size, minimum_height', [((1280, 800), 300), ((1440, 900), 390)])
def test_default_layout_gives_the_monitor_room_without_forcing_a_taller_window(app, size, minimum_height):
    window = SynthStudio()
    window.resize(*size)
    window.show()
    app.processEvents()
    try:
        assert window.height() == size[1]
        assert window.document_title.text() and window.document_title.width() >= 100
        assert window.viewer.height() >= minimum_height
        assert window.preview_splitter.orientation() == Qt.Orientation.Vertical
        for control in (window.play, window.timeline, window.preview_status):
            assert visible_in(control, window.preview_splitter.widget(0))
    finally:
        close_window(window, app)


def test_vertical_drag_changes_viewport_without_editing_or_invalidating_preview(app):
    window = SynthStudio()
    window.resize(1440, 900)
    window.show()
    app.processEvents()
    try:
        window.preview_splitter.setSizes([420, 280])
        app.processEvents()
        document = copy.deepcopy(window.composition)
        sequence = copy.deepcopy(window.sequence)
        preset = copy.deepcopy(window.preset)
        generation = window.settings_generation
        height = window.viewer.height()
        handle = window.preview_splitter.handle(1)
        start = handle.rect().center()
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(handle, start + QPoint(0, 70))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=start + QPoint(0, 70))
        app.processEvents()
        assert window.viewer.height() >= height + 50
        assert window.composition == document
        assert window.sequence == sequence
        assert window.preset == preset
        assert window.settings_generation == generation
    finally:
        close_window(window, app)


def test_small_window_keeps_timeline_and_scrolled_controls_reachable(app):
    window = SynthStudio()
    window.resize(1280, 720)
    window.show()
    app.processEvents()
    try:
        window.preview_splitter.moveSplitter(window.height(), 1)
        app.processEvents()
        assert window.height() == 720
        assert window.viewer.height() >= 240
        window.splitter.moveSplitter(0, 1)
        app.processEvents()
        scroll = window.preview_controls_scroll
        assert scroll.height() >= 112
        assert window.section_scroll.height() == 78
        assert visible_in(window.section_timeline, scroll.viewport())
        assert scroll.verticalScrollBar().maximum() > 0
        for control in (window.preview_scope, window.prepare_preview):
            scroll.ensureWidgetVisible(control)
            app.processEvents()
            assert visible_in(control, scroll.viewport())
            left = control.mapTo(scroll.viewport(), QPoint(0, 0)).x()
            assert left >= 0 and left + control.width() <= scroll.viewport().width()
        assert visible_in(window.export_button, window.header_host)
        assert visible_in(window.quality, window.transport)
        assert visible_in(window.play, window.preview_splitter.widget(0))
        assert visible_in(window.preview_status, window.preview_splitter.widget(0))
    finally:
        close_window(window, app)


def test_vertical_split_restores_separately_from_document_and_column_width(app, tmp_path):
    settings = QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat)
    settings.setValue('window/mode', 'normal')
    window = SynthStudio(settings=settings)
    window.resize(1440, 900)
    window.show_workspace()
    app.processEvents()
    window.preview_splitter.moveSplitter(470, 1)
    window.splitter.moveSplitter(780, 1)
    app.processEvents()
    expected = window.preview_splitter.sizes()
    close_window(window, app)
    assert settings.value('window/preview_splitter')
    restored = SynthStudio(settings=settings)
    restored.show_workspace()
    app.processEvents()
    # Offscreen Qt clamps saved geometry to its small virtual screen. Compare
    # the remembered splits at the same window size, as on the real display.
    restored.resize(1440, 900)
    app.processEvents()
    try:
        assert all(abs(actual - wanted) <= 3 for actual, wanted in zip(restored.preview_splitter.sizes(), expected))
        assert abs(restored.splitter.sizes()[0] - 780) <= 3
        assert not restored.has_unsaved_changes()
    finally:
        close_window(restored, app)
