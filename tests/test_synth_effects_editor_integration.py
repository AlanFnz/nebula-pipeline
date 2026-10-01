"""The focused editor participates in the real workspace and document lifecycle."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QThreadPool
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from studio_theme import apply_theme
from synth_composition import load_composition
from synth_sequence import reference_sequence
from synth_starters import starter_composition
from synth_studio import SynthStudio


@pytest.fixture
def make_window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    windows = []
    def make(**kwargs):
        window = SynthStudio(**kwargs)
        windows.append(window)
        window.resize(1280, 800); window.show(); app.processEvents()
        return window
    yield make
    for window in windows: window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()


@pytest.mark.parametrize('size', [(1280, 720), (1440, 900)])
def test_composer_header_stays_visible_inside_real_workspace(make_window, size):
    window = make_window()
    window.resize(*size); window.splitter.setSizes([size[0] - 410, 400])
    panel = window.composer; effect = panel.effects_panel
    effect.inspect_effect('broadcast')
    QApplication.processEvents()
    assert window.height() == size[1]
    assert window.inspector_host.currentWidget() is window.composer_host
    assert window.composer.parentWidget() is window.composer_host
    scope_y = panel.scope_combo.mapTo(window, QPoint()).y()
    title_y = effect.inspector_title.mapTo(window, QPoint()).y()
    effect.parameter_scroll.verticalScrollBar().setValue(effect.parameter_scroll.verticalScrollBar().maximum())
    QApplication.processEvents()
    assert panel.scope_combo.mapTo(window, QPoint()).y() == scope_y
    assert effect.inspector_title.mapTo(window, QPoint()).y() == title_y
    assert effect.parameter_scroll.viewport().height() >= 100
    assert not window.has_unsaved_changes()


def test_contextual_toolbar_follows_visible_panel_and_is_safe_in_overview(make_window):
    window = make_window(); panel = window.composer
    panel.effects_panel.show_overview()
    assert not window.reset_controls_button.isEnabled()
    panel.effects_panel.inspect_effect('ghosts')
    assert window.reset_controls_button.text() == 'Restore this effect'
    panel.look_tabs.setCurrentWidget(panel.master_panel)
    assert window.reset_controls_button.text() == 'Reset master'
    panel.look_tabs.setCurrentWidget(panel.object_panel)
    assert window.reset_controls_button.text() == 'Restore object controls'
    assert not window.has_unsaved_changes()


def test_hidden_text_draft_marks_document_and_saves_original_scope(make_window, monkeypatch, tmp_path):
    document = starter_composition('text-transmission')
    second = copy.deepcopy(document['sections'][0]); second['id'] = 'second-section'
    document['sections'].append(second)
    window = make_window(composition=document)
    panel = window.composer; effect = panel.effects_panel
    effect.inspect_effect('text'); panel.change_scope(1)
    first_id = panel.document['sections'][0]['id']
    control = effect.controls['text.content']
    control.input.editor.setPlainText('A FIRST SECTION DRAFT')
    assert window.document_title.text().startswith('* ')
    panel.select_section(1)
    effect.inspect_effect('tape')
    path = tmp_path / 'saved.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.save_sequence_dialog()
    saved = load_composition(path)
    original_section = next(section for section in saved['sections'] if section['id'] == first_id)
    assert original_section['effects']['text']['params']['text.content'] == 'A FIRST SECTION DRAFT'
    assert saved['sections'][1]['effects'].get('text', {}).get('params', {}).get('text.content') != 'A FIRST SECTION DRAFT'
    assert effect.effect_id == 'tape' and not window.has_unsaved_changes()
    assert not window.document_title.text().startswith('* ')
    window.undo_composition()
    assert window.has_unsaved_changes()
    window.redo_composition()
    assert not window.has_unsaved_changes()


def test_lazy_object_text_editor_participates_in_dirty_status(make_window):
    window = make_window()
    panel = window.composer; panel.change_object('text')
    window.mark_document_clean()
    panel.look_tabs.setCurrentWidget(panel.object_panel)
    panel.object_panel.controls['text.content'].input.editor.setPlainText('OBJECT WORDING DRAFT')
    assert window.document_title.text().startswith('* ')
    panel.change_object('particles')
    assert window.pending_text_edits()
    assert window.prepare_document_save()
    assert window.composition['effects']['text']['params']['text.content'] == 'OBJECT WORDING DRAFT'
    assert window.composition['effects']['text']['mode'] == 'off'


def test_detailed_editor_keeps_its_scroll_host(make_window):
    window = make_window(sequence=reference_sequence())
    assert window.composer is None
    assert window.inspector_host.currentWidget() is window.inspector_scroll
    assert window.inspector_scroll.widget() is not None
    assert not window.has_unsaved_changes()


def test_pinned_timeline_fps_updates_preview_export_and_undo(make_window):
    window = make_window(); panel = window.composer
    panel.change_scope(1)
    before = copy.deepcopy(window.composition)
    panel.fps.setValue(12)
    assert window.composition['fps'] == window.sequence['fps'] == 12
    assert window.has_unsaved_changes()
    panel.arrangement_button.click(); QApplication.processEvents()
    assert panel.fps.isVisible()
    window.undo_composition()
    assert window.composition == before
    assert window.composer.fps.value() == before['fps']
    assert not window.has_unsaved_changes()
