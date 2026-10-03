"""Export dialogs retain only successful MP4 folders across studies and sessions."""
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from synth_composition import blank_composition
from test_synth_effects_editor_integration import make_window


def test_successful_export_remembers_folder_across_windows_and_detailed_copy(make_window, monkeypatch, tmp_path):
    settings_path = tmp_path / 'settings.ini'
    settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    window = make_window(settings=settings)
    exports = tmp_path / 'my exports'; exports.mkdir()
    output = exports / 'take.mp4'
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(output), ''))
    window.export_dialog()
    job = window.export_job
    assert not settings.contains('export/directory')
    window.export_finished(job, str(output)); window._finish_export(job)
    assert settings.value('export/directory') == str(exports)
    assert Path(window.suggested_output_path('.mp4')).parent == exports
    assert not window.has_unsaved_changes()
    window.load_starter_id('approved')
    assert Path(window.suggested_output_path('.mp4')).parent == exports
    restarted = make_window(settings=QSettings(str(settings_path), QSettings.Format.IniFormat))
    defaults = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: defaults.append(args[2]) or ('', ''))
    restarted.export_dialog()
    assert Path(defaults[-1]).parent == exports
    assert Path(defaults[-1]).name == Path(restarted.suggested_output_path('.mp4')).name
    assert restarted.export_job is None
    restarted.open_detailed_copy()
    detail = restarted.detail_windows[-1]
    try:
        assert Path(detail.suggested_output_path('.mp4')).parent == exports
    finally:
        detail.close()


def test_failed_cancelled_and_stale_exports_keep_previous_folder(make_window, monkeypatch, tmp_path):
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    previous = tmp_path / 'previous'; previous.mkdir()
    settings.setValue('export/directory', str(previous))
    window = make_window(settings=settings)
    next_folder = tmp_path / 'next'; next_folder.mkdir()
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(next_folder / 'next.mp4'), ''))
    for error in ('Export cancelled', 'Could not encode'):
        window.export_dialog(); job = window.export_job
        window.export_failed(job, error); window._finish_export(job)
        assert settings.value('export/directory') == str(previous)
        window.export_finished(job, str(next_folder / 'stale.mp4'))
        assert settings.value('export/directory') == str(previous)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    window.export_dialog()
    assert settings.value('export/directory') == str(previous)


def test_missing_export_directory_falls_back_and_document_save_is_separate(make_window, monkeypatch, tmp_path):
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    settings.setValue('export/directory', str(tmp_path / 'deleted folder'))
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    movies = tmp_path / 'Movies'; movies.mkdir()
    documents = tmp_path / 'Documents'; documents.mkdir()
    window = make_window(settings=settings)
    assert Path(window.suggested_output_path('.mp4')).parent == movies
    assert Path(window.suggested_output_path('.json')).parent == documents


def test_actual_mp4_export_records_its_folder(make_window, monkeypatch, tmp_path):
    from test_synth_video_ui import wait_until
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    document = blank_composition()
    document['sections'][0]['duration'] = .08
    document['canvas'] = {'width': 128, 'height': 96, 'framing': 'native'}
    window = make_window(composition=document, settings=settings)
    folder = tmp_path / 'rendered'; folder.mkdir()
    output = folder / 'actual.mp4'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(output), ''))
    window.export_dialog()
    wait_until(lambda: window.export_job is None)
    assert output.exists(), window.status.text()
    assert settings.value('export/directory') == str(folder)
    assert Path(window.suggested_output_path('.mp4')).parent == folder
