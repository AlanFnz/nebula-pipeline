import copy
import os
from pathlib import Path
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication
from synth_studio import SynthStudio
from synth_composition import load_composition, save_composition
from synth_video import VIDEO_EFFECTS, video_composition
from test_synth_video import clip


def wait_until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate(): return
        time.sleep(.01)
    raise AssertionError('Video studio did not settle')


@pytest.fixture
def window(clip, tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    window = SynthStudio(composition=video_composition(clip)); window.show()
    wait_until(lambda: not window.render_running)
    yield window
    window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()


def test_video_controls_scope_effects_before_after_undo_and_reopen(window, tmp_path):
    panel = window.composer
    panel.look_tabs.setCurrentWidget(panel.video_panel)
    assert panel.object_panel.isHidden()
    assert panel.scope_combo.isHidden()
    assert window.fit_subject.isHidden()
    assert not window.source_preview.isHidden()
    assert set(panel.effects_panel.available_ids) == set(VIDEO_EFFECTS)
    panel.video_panel.controls['in'].setValue(.25)
    assert window.composition['footage']['in'] == .25
    window.undo_composition(); assert window.composition['footage']['in'] == 0.
    window.redo_composition(); assert window.composition['footage']['in'] == .25
    panel.video_panel.controls['out'].setValue(.1)
    assert window.composition['footage']['out'] == 1.
    panel.duplicate_section(); panel.select_section(1)
    panel.look_tabs.setCurrentWidget(panel.video_panel)
    panel.video_panel.controls['treatment_fps'].setValue(6)
    assert all(s['overrides']['treatment_fps'] == 6 for s in window.sequence['states'].values())
    panel.video_panel.controls['motion_fps'].setValue(4)
    assert window.composition['footage']['motion_fps'] == 4
    assert window.sequence['footage']['motion_fps'] == 4
    window.undo_composition()
    assert window.composition['footage']['motion_fps'] == 0
    panel.apply_video_treatment(1)
    assert 'tape' in panel.effects_panel.applied_ids
    panel.effects_panel.inspect_effect('ghosts')
    panel.effects_panel.more.setChecked(True)
    assert all(c.isHidden() for key, c in panel.effects_panel.controls.items() if key.startswith('slab.'))
    window.source_preview.setChecked(True)
    wait_until(lambda: not window.render_running and not window.render_queued)
    before = window.viewer.packet
    window.source_preview.setChecked(False)
    wait_until(lambda: not window.render_running and not window.render_queued)
    assert window.viewer.packet != before
    path = tmp_path / 'saved.json'; save_composition(path, window.composition)
    window.set_composition(load_composition(path))
    assert window.composition['footage']['in'] == .25
    window.load_starter_id('profile-doryphoros')
    assert window.source_preview.isHidden() and not window.source_preview.isChecked()
    assert not window.composer.look_tabs.isTabVisible(window.composer.look_tabs.indexOf(window.composer.video_panel))
    assert window.composer.look_tabs.isTabVisible(window.composer.look_tabs.indexOf(window.composer.object_panel))


def test_async_import_preserves_previous_composition_and_relink_is_undoable(window, clip, tmp_path):
    window.load_starter_id('profile-doryphoros')
    previous = copy.deepcopy(window.composition)
    window.start_video_import(clip['path'])
    wait_until(lambda: window.import_job is None)
    assert window.composition['footage']['path'] == clip['path']
    backups = list((tmp_path / 'Library/Application Support/Nebula Studio/Backups').glob('before-video-*.json'))
    assert len(backups) == 1 and load_composition(backups[0]) == previous
    window.composer.video_panel.controls['in'].setValue(.25)
    original = copy.deepcopy(window.composition)
    window.composer.change_video('path', str(tmp_path / 'missing.mkv'))
    window.start_video_import(clip['path'], relink=True)
    wait_until(lambda: window.import_job is None)
    assert window.composition == original
    window.undo_composition()
    assert window.composition['footage']['path'].endswith('missing.mkv')


def test_save_as_study_is_independent_and_loads_from_the_renamed_library(window, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from synth_studies import study_catalogue
    before = copy.deepcopy(window.composition)
    assert window.starter_combo.accessibleName() == 'Studies'
    assert window.starter_combo.placeholderText() == 'Choose a study…'
    assert window.load_starter_button.text() == 'Load study'
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('My tape study', True))
    window.save_study_button.click()
    wait_until(lambda: window.study_job is None)
    assert window.composition == before
    assert window.starter_combo.currentData() is None
    personal = next(key for key, name in study_catalogue() if name.startswith('My tape study'))
    window.composer.change_video('x', 80.)
    window.starter_combo.setCurrentIndex(window.starter_combo.findData(personal))
    assert window.composition['footage']['x'] == 80.
    window.load_starter_button.click()
    assert window.composition['footage']['x'] == before['footage']['x']
    assert window.composition['name'] == 'My tape study'
    assert Path(window.composition['footage']['path']).exists()
    original_name = window.composition['name']
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('', False))
    window.save_study_button.click()
    assert window.study_job is None and window.composition['name'] == original_name
