"""Native project names use the existing payloads and replacement safeguards."""
import copy
import json
from pathlib import Path
import plistlib

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from synth_composition import blank_composition, load_composition, save_composition
from synth_project_files import ProjectFileOpener, choose_save_path
from synth_montage import load_montage
from test_synth_unsaved import make_window, edit
from test_synth_navigation import workspace
from test_synth_recent_projects import app, wait_for


@pytest.mark.parametrize('mode', ['composition', 'sequence', 'preset'])
def test_new_extension_roundtrips_exact_payload_and_legacy_save_stays_json(make_window, monkeypatch, tmp_path, mode):
    window = make_window(mode)
    edit(window)
    expected = copy.deepcopy(window.document_state())
    # New projects default to .nebula; explicit legacy names remain valid.
    dialogs = []
    def choose(*args):
        dialogs.append(args)
        return str(tmp_path/'first.nebula'), ''
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose)
    assert window.save_sequence_dialog()
    assert dialogs[0][2].endswith('.nebula')
    assert window.document_state() == expected
    saved = (tmp_path/'first.nebula').read_bytes()
    assert isinstance(json.loads(saved), dict)
    edit(window)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *_: QMessageBox.StandardButton.Discard)
    assert window.open_document_path(tmp_path/'first.nebula')
    assert window.document_state() == expected
    legacy = tmp_path/'legacy.json'; legacy.write_bytes(saved)
    assert window.open_document_path(legacy)
    edit(window)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: pytest.fail('Save must retain the legacy path'))
    assert window.save_sequence_dialog()
    assert window.document_path == legacy
    assert (tmp_path/'first.nebula').read_bytes() == saved
    # Save As proposes the native extension beside the old file and leaves it intact.
    legacy_bytes = legacy.read_bytes()
    def save_as(*args):
        assert args[2] == str(tmp_path/'legacy.nebula')
        return args[2], ''
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', save_as)
    assert window.save_as_dialog()
    assert legacy.read_bytes() == legacy_bytes
    assert window.open_document_path(tmp_path/'legacy.nebula')
    assert not window.has_unsaved_changes()


@pytest.mark.parametrize('name,selected,expected', [
    ('Untitled', '', 'Untitled.nebula'),
    ('Draft.v2', '', 'Draft.v2.nebula'),
    ('Legacy', 'Legacy JSON (*.json)', 'Legacy.json'),
    ('Legacy.JSON', '', 'Legacy.JSON'),
    ('Piece.nebula', '', 'Piece.nebula'),
    ('', '', ''),
])
def test_save_dialog_keeps_explicit_formats_and_adds_missing_suffix(monkeypatch, name, selected, expected):
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (name, selected))
    assert choose_save_path(None, 'Save project', 'Untitled.nebula') == expected


def test_finder_queues_startup_deduplicates_and_respects_cancel(make_window, monkeypatch, tmp_path):
    app = QApplication.instance()
    opener = ProjectFileOpener(app)
    window = make_window()
    project = blank_composition(); project['name'] = 'Finder opened'
    path = tmp_path/'A project with spaces.nebula'; save_composition(path, project)
    calls = []; original = window.open_document_path
    monkeypatch.setattr(window, 'open_document_path', lambda p: calls.append(p) or original(p))
    try:
        app.sendEvent(app, QFileOpenEvent(QUrl.fromLocalFile(str(path))))
        app.sendEvent(app, QFileOpenEvent(str(path)))
        app.processEvents()
        assert not calls  # No workspace bound yet: preserve the launch event.
        opener.bind(window, [path])  # Also supplied as a startup argument.
        wait_for(app, lambda: window.document_path == path)
        assert len(calls) == 1
        edit(window); before = copy.deepcopy(window.document_state())
        app.sendEvent(app, QFileOpenEvent(str(path))); app.processEvents()
        assert len(calls) == 1 and window.document_state() == before
        other = tmp_path/'second.nebula'; save_composition(other, blank_composition())
        monkeypatch.setattr(QMessageBox, 'warning', lambda *_: QMessageBox.StandardButton.Cancel)
        app.sendEvent(app, QFileOpenEvent(str(other))); app.processEvents()
        assert len(calls) == 2 and window.document_path == path
        assert window.document_state() == before and window.has_unsaved_changes()
        # Invalid native files take the existing error path and cannot replace the document.
        errors = []; monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[-1]))
        bad = tmp_path/'bad.nebula'; bad.write_text('not JSON')
        app.sendEvent(app, QFileOpenEvent(str(bad))); app.processEvents()
        assert errors and window.document_state() == before
        assert not app.sendEvent(app, QFileOpenEvent(QUrl('https://example.com/project.nebula')))
    finally:
        opener.timer.stop(); app.removeEventFilter(opener); opener.deleteLater()


def test_finder_waits_for_modal_dialog_and_routes_through_montage_guard(workspace, monkeypatch, tmp_path):
    root, montage, app = workspace
    opener = ProjectFileOpener(app); opener.bind(root)
    target = tmp_path/'next.nebula'; save_composition(target, blank_composition())
    original = copy.deepcopy(montage.document)
    dialog = QDialog(root); dialog.setModal(True); dialog.show(); app.processEvents()
    try:
        app.sendEvent(app, QFileOpenEvent(str(target))); app.processEvents()
        assert opener.pending == [target] and root.workspace_navigation.montage is montage
        monkeypatch.setattr(montage, 'may_replace', lambda: False)
        dialog.close(); app.processEvents()
        opener.deliver()
        assert root.workspace_navigation.montage is montage and montage.document == original
        monkeypatch.setattr(montage, 'may_replace', lambda: True)
        app.sendEvent(app, QFileOpenEvent(str(target)))
        wait_for(app, lambda: root.document_path == target)
        assert root.workspace_navigation.montage is None
    finally:
        dialog.close(); opener.timer.stop(); app.removeEventFilter(opener); opener.deleteLater()


def test_montage_save_as_native_keeps_complete_document_and_legacy_original(workspace, monkeypatch, tmp_path):
    root, montage, app = workspace
    expected = copy.deepcopy(montage.document)
    legacy = montage.path
    assert montage.save()
    old = legacy.read_bytes()
    dialogs = []
    def choose(*args):
        dialogs.append(args)
        return str(tmp_path/'assembled.nebula'), ''
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose)
    assert root.save_as_dialog()
    assert dialogs[0][2].endswith('.nebula')
    assert load_montage(tmp_path/'assembled.nebula') == expected
    assert legacy.read_bytes() == old
    assert root.open_document_path(tmp_path/'assembled.nebula')
    assert root.workspace_navigation.montage.document == expected


def test_macos_type_registration_owns_only_nebula_and_has_document_icon():
    root = Path(__file__).resolve().parents[1]
    metadata = plistlib.loads((root/'packaging/Info.plist').read_bytes())
    kind, = metadata['UTExportedTypeDeclarations']
    document, = metadata['CFBundleDocumentTypes']
    assert kind['UTTypeTagSpecification']['public.filename-extension'] == ['nebula']
    assert 'public.json' in kind['UTTypeConformsTo']
    assert document['LSItemContentTypes'] == [kind['UTTypeIdentifier']]
    assert document['LSHandlerRank'] == 'Owner' and document['CFBundleTypeRole'] == 'Editor'
    assert document['CFBundleTypeIconFile'] == kind['UTTypeIconFile'] == 'nebula-document.icns'
