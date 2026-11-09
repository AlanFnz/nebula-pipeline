"""Only Open requests a launch; linking is an undoable document edit."""
import copy

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from synth_composition import load_composition, blank_composition
from synth_live_set import LIVE_SET
from synth_live_set_ui import QDesktopServices
from test_synth_sound_session import editor


@pytest.fixture(autouse=True)
def no_real_launch(monkeypatch):
    calls = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: calls.append(url.toLocalFile()) or True)
    return calls


def choose(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))


def test_link_button_then_open_save_and_reopen(editor, monkeypatch, tmp_path, no_real_launch):
    window, dialog, app = editor
    live = tmp_path / 'Music #1 & Σ.als';live.write_bytes(b'Live Set')
    choose(monkeypatch, live)
    dialog.live_set_button.click()
    assert window.composition[LIVE_SET] == str(live)
    assert window.has_unsaved_changes() and not dialog.has_sound_draft()
    assert not no_real_launch
    assert live.name in dialog.live_set_button.accessibleName()
    assert window.workspace_live_set_button.path == str(live)
    assert '&&' in dialog.live_set_button.text()
    dialog.live_set_button.click()
    assert no_real_launch == [str(live)]
    assert not window.midi_monitor_enabled
    assert window.save_sequence_dialog()
    loaded = load_composition(window.document_path)
    assert loaded[LIVE_SET] == str(live)
    window.set_composition(loaded, guard=False);window.open_visual_sound()
    assert dialog.live_set_button.path == str(live)
    assert no_real_launch == [str(live)]
    window.set_composition(blank_composition(), guard=False)
    assert dialog.live_set_button.path is None
    assert window.workspace_live_set_button.path is None
    assert no_real_launch == [str(live)]


def test_link_preserves_sound_draft_prepared_frames_and_transport(editor, monkeypatch, tmp_path):
    window, dialog, _ = editor
    live = tmp_path / 'Music.als';live.touch();choose(monkeypatch, live)
    dialog.opening.setValue(87)
    draft = dialog.read_config();history = copy.deepcopy(dialog.sound_undo)
    applied = copy.deepcopy(window.composition['generated_sound']);sequence = copy.deepcopy(window.sequence)
    assert window.ensure_preview_context()
    packet = ((1, 1), b'123');window.preview_frames.put(0, packet)
    window.play.setChecked(True);anchor = window.play_started
    dialog.live_set_button.click()
    assert dialog.read_config() == draft and dialog.sound_undo == history
    assert window.composition['generated_sound'] == applied and window.sequence == sequence
    assert window.preview_frames.get(0) == packet
    assert window.play.isChecked() and window.play_started == anchor
    window.play.setChecked(False)


def test_change_unlink_undo_and_cancel_do_not_touch_sets(editor, monkeypatch, tmp_path, no_real_launch):
    window, dialog, _ = editor
    first = tmp_path / 'First.als';second = tmp_path / 'Second.als'
    first.touch();second.touch();choose(monkeypatch, first);dialog.live_set_button.click()
    choose(monkeypatch, second);dialog.live_set_button.link_action.trigger()
    assert window.composition[LIVE_SET] == str(second)
    dialog.live_set_button.unlink_action.trigger()
    assert LIVE_SET not in window.composition and dialog.live_set_button.path is None
    window.undo_composition()
    assert window.composition[LIVE_SET] == str(second) and dialog.live_set_button.path == str(second)
    window.undo_composition()
    assert window.composition[LIVE_SET] == str(first)
    before = copy.deepcopy(window.composition)
    choose(monkeypatch, '');dialog.live_set_button.link_action.trigger()
    assert window.composition == before and first.exists() and second.exists()
    assert not no_real_launch
    assert window.protected_document_destination(first)
    alias = tmp_path / 'alias.json';alias.symlink_to(first)
    assert window.protected_document_destination(alias)


def test_missing_set_can_be_cancelled_then_relocated_and_opened(editor, monkeypatch, tmp_path, no_real_launch):
    window, dialog, _ = editor
    old = tmp_path / 'Old.als';old.touch();window.set_linked_live_set(str(old))
    new = old.rename(tmp_path / 'Moved.als')
    choose(monkeypatch, '');dialog.live_set_button.click()
    assert window.composition[LIVE_SET] == str(old) and not no_real_launch
    choose(monkeypatch, new);dialog.live_set_button.click()
    assert window.composition[LIVE_SET] == str(new) and no_real_launch == [str(new)]


def test_launch_failure_keeps_link_and_reports_error(editor, monkeypatch, tmp_path):
    window, dialog, _ = editor
    live = tmp_path / 'Music.als';live.touch();window.set_linked_live_set(str(live))
    errors = [];monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[2]))
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda _: False)
    before = copy.deepcopy(window.composition);dialog.live_set_button.click()
    assert window.composition == before and len(errors) == 1
    assert 'Ableton Live' in errors[0]


@pytest.mark.parametrize('kind', ['missing', 'directory', 'wrong_extension'])
def test_invalid_selection_keeps_current_link(editor, monkeypatch, tmp_path, kind, no_real_launch):
    window, dialog, _ = editor
    path = tmp_path / ('Wrong.txt' if kind == 'wrong_extension' else 'Music.als')
    if kind == 'directory': path.mkdir()
    if kind == 'wrong_extension': path.touch()
    errors = [];monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[2]))
    before = copy.deepcopy(window.composition);choose(monkeypatch, path);dialog.live_set_button.click()
    assert window.composition == before and errors and not no_real_launch
