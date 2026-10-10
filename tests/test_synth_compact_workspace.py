"""Compact chrome must preserve document actions, scope and playback meaning."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QPoint, QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox
from studio_theme import apply_theme
from synth_studio import SynthStudio
from synth_starting_points import new_piece


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([]); apply_theme(app)
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    document = new_piece('shape')
    second = copy.deepcopy(document['sections'][0]); second['id'] = 'second'; second['duration'] = 2.
    document['sections'].append(second)
    window = SynthStudio(composition=document); window.auto_prepare.setChecked(False)
    window.resize(1280, 800); window.show(); app.processEvents()
    yield window
    window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()


def inside(widget, host):
    top = widget.mapTo(host, QPoint())
    return host.rect().contains(top) and host.rect().contains(top + widget.rect().bottomRight())


def test_global_fps_and_save_actions_survive_composer_replacement(window, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    destination = tmp_path / 'composition.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(destination), ''))
    window.save_button.menu().actions()[0].trigger()
    assert destination.exists() and not window.has_unsaved_changes()
    for _ in range(3):
        window.set_composition(copy.deepcopy(window.composition), clean=True)
        QApplication.processEvents()
        assert window.workspace_fps_layout.count() == 2
        assert window.timeline_navigation_layout.count() == 2
        assert window.composer.arrangement_button.parentWidget() is window.timeline_navigation
        assert window.composer.automations_button.parentWidget() is window.timeline_navigation
        assert inside(window.composer.fps, window.header_host)
        assert window.save_study_button.isEnabled()
    window.composer.fps.setValue(12)
    assert window.composition['fps'] == window.preview_fps() == 12
    assert window.has_unsaved_changes()
    window.save_button.click()
    assert not window.has_unsaved_changes()


def test_studio_navigation_keeps_timeline_actions_and_quality_with_their_context(window):
    before = copy.deepcopy(window.composition)
    panel = window.composer
    assert inside(window.quality, window.transport)
    assert inside(panel.arrangement_button, window.section_tools)
    assert inside(panel.automations_button, window.section_tools)
    panel.arrangement_button.click(); QApplication.processEvents()
    assert panel.content_stack.currentWidget() is panel.arrangement_scroll
    panel.arrangement_button.click(); QApplication.processEvents()
    assert panel.content_stack.currentWidget() is panel.parameters_group
    panel.look_tabs.setCurrentWidget(panel.master_panel)
    assert window.reset_controls_button.isVisible()
    panel.look_tabs.setCurrentWidget(panel.effects_panel)
    assert not window.reset_controls_button.isVisible()
    assert window.composition == before and not window.has_unsaved_changes()


def test_editing_scope_is_independent_of_arrangement_selection(window):
    panel = window.composer; timeline = window.section_timeline
    panel.select_section(1)
    selected = set(timeline.selected_ids)
    assert timeline.editing_section_id == 'second'
    panel.change_scope(0)
    assert timeline.editing_section_id is None and timeline.selected_ids == selected
    panel.change_scope(1)
    panel.look_tabs.setCurrentWidget(panel.master_panel)
    assert timeline.editing_section_id is None and timeline.selected_ids == selected
    panel.look_tabs.setCurrentWidget(panel.effects_panel)
    assert timeline.editing_section_id == 'second'
    assert not window.has_unsaved_changes()


def test_prepared_count_means_actual_cached_frames_in_playback_scope(window):
    window.preview_frames.clear()
    second_start = round(window.composition['sections'][0]['duration'] * window.preview_fps())
    for frame in (0, 2, second_start):
        window.preview_frames.put(frame, ((1, 1), b'abc'))
    window.cached_ranges.set_ranges(window.preview_frames.ranges())
    assert window.cache_status.text() == f'Preview ready: 3/{window.timeline.maximum()+1}'
    window.composer.select_section(1)
    window.preview_scope.setCurrentIndex(1)
    assert window.cache_status.text() == f'Preview ready: 1/{window.active_preview_scope().count}'
    window.preview_frames.clear(); window.cached_ranges.set_ranges([])
    assert window.cache_status.text().startswith('Preview ready: 0/')


def test_narrow_monitor_wraps_controls_without_editing_the_piece(window):
    before = copy.deepcopy(window.composition)
    window.begin_comparison(before, 'A long snapshot title to check the monitor layout')
    window.splitter.setSizes([490, 760]); QApplication.processEvents()
    monitor = window.viewer.parentWidget()
    for control in (window.view_zoom, window.snapshots_button, window.compare_a,
                    window.compare_b, window.compare_exit, window.fullscreen_button):
        assert inside(control, monitor)
    assert inside(window.export_button, window.header_host)
    assert window.composition == before
    window.end_comparison()


def test_fit_remains_a_mode_and_transport_strip_tracks_the_scrubber(window):
    window.fit_view_button.click(); window.resize(1440, 900); QApplication.processEvents()
    assert window.viewer.zoom == 0 and window.fit_view_button.isChecked()
    window.view_zoom.setValue(75); window.resize(1280, 800); QApplication.processEvents()
    assert window.viewer.zoom == .75 and not window.fit_view_button.isChecked()
    strip, slider = window.cached_ranges, window.timeline
    assert abs(strip.mapTo(window, QPoint()).x() - slider.mapTo(window, QPoint()).x()) <= 1
    assert strip.mapTo(window, QPoint()).y() - slider.mapTo(window, QPoint()).y() == slider.height()
    assert not window.cancel_export.isVisible()
    assert not window.has_unsaved_changes()


def test_export_feedback_is_reachable_and_only_occupies_space_during_export(window, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'test.mp4'), ''))
    window.preview_splitter.moveSplitter(window.height(), 1)
    window.export_dialog(); job = window.export_job; QApplication.processEvents()
    assert window.export_progress.isVisible() and window.cancel_export.isVisible()
    assert inside(window.export_progress, window.preview_controls_scroll.viewport())
    window.export_progressed(job, 3, 10)
    assert window.export_progress.value() == 30
    window.export_failed(job, 'Export cancelled'); window._finish_export(job)
    assert not window.export_progress.isVisible() and not window.cancel_export.isVisible()
    assert 'cancelled' in window.status.text() and window.status.isVisible()


def test_tall_restored_footer_keeps_controls_packed_at_the_top(window):
    window.resize(1728, 1017); window.preview_splitter.setSizes([660, 280])
    QApplication.processEvents()
    pane = window.preview_controls_scroll.widget()
    tools = window.section_tools
    assert tools.y() <= 6
    assert tools.height() <= tools.sizeHint().height() + 2
    assert window.section_scroll.y() <= tools.y() + tools.height() + 6
    assert window.preview_scope.mapTo(pane, QPoint()).y() <= window.section_scroll.y() + window.section_scroll.height() + 6
