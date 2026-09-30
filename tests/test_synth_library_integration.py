"""Library inspection and metadata never replace an edited document implicitly."""
import copy
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox
import synth_studio
import synth_studies
from synth_studies_ui import StudiesDialog
from test_synth_unsaved import make_window, edit


class StillService(QObject):
    ready = Signal(int, str, object, object, str)
    generation = 0
    closed = False

    def reset(self):
        self.generation += 1
        return self.generation

    def request(self, jobs):
        pass

    def close(self):
        self.closed = True


def browser_for(window, monkeypatch, tmp_path):
    monkeypatch.setattr(synth_studies, 'studies_directory', lambda: tmp_path)
    monkeypatch.setattr(synth_studio, 'StudiesDialog',
                        lambda parent: StudiesDialog(parent, directory=tmp_path,
                                                     thumbnail_service=StillService()))
    window.manage_studies()
    return window.studies_dialog


def select(browser, identifier):
    from PySide6.QtCore import Qt
    for row in range(browser.table.rowCount()):
        if browser.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == identifier:
            browser.table.selectRow(row)
            return
    raise AssertionError(f'Missing Study {identifier}')


def test_inspection_and_favorite_do_not_dirty_or_replace_document(make_window, monkeypatch, tmp_path):
    window = make_window()
    original = copy.deepcopy(window.composition)
    identity = window.document_identity
    browser = browser_for(window, monkeypatch, tmp_path)
    select(browser, 'text-transmission')
    browser.change_favorite('text-transmission', True)
    assert window.composition == original and window.document_identity is identity
    assert not window.has_unsaved_changes()
    assert next(x for x in synth_studies.study_records(tmp_path)
                if x.identifier == 'text-transmission').favorite
    browser.close()


def test_browser_load_honors_cancel_then_discard(make_window, monkeypatch, tmp_path):
    window = make_window(); edit(window)
    original = copy.deepcopy(window.composition)
    identity = window.document_identity
    browser = browser_for(window, monkeypatch, tmp_path)
    select(browser, 'text-transmission')
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **kw: QMessageBox.StandardButton.Cancel)
    browser.request_load()
    assert window.composition == original and window.document_identity is identity
    assert window.has_unsaved_changes() and browser.isVisible()
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **kw: QMessageBox.StandardButton.Discard)
    browser.request_load()
    assert window.document_identity is not identity and not window.has_unsaved_changes()
    assert window.composition['name'] != original['name']
    assert window.document_path is None and browser.isVisible()
    browser.close()


def test_browser_warming_yields_to_editor_export_and_window_close(make_window, monkeypatch, tmp_path):
    window = make_window()
    window.auto_prepare.setChecked(False)
    window.preview_debounce.stop(); window.render_queued = False
    browser = browser_for(window, monkeypatch, tmp_path)
    window.update_study_browser_priority()
    assert not browser._rendering_paused
    window.render_running = True
    window.update_study_browser_priority()
    assert browser._rendering_paused
    generation = browser.thumbnails.generation
    window.update_study_browser_priority()
    assert browser.thumbnails.generation == generation
    window.render_running = False
    window.export_job = object()
    try:
        window.update_study_browser_priority()
        assert browser._rendering_paused
    finally:
        window.export_job = None
    window.update_study_browser_priority()
    assert not browser._rendering_paused
    assert window.close()
    assert browser.thumbnails.closed and not window.study_browser_priority_timer.isActive()
