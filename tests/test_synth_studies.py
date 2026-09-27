"""Personal studies preserve recipes and media independently of working edits."""
import copy
import json
import shutil

import pytest

from media import Cancellation, Cancelled
from synth_composition import compile_composition
from synth_sequence import render_sequence_frame
from synth_starters import STARTERS, starter_composition
from synth_studies import save_study, study_catalogue, study_composition
from synth_video import apply_treatment, video_composition
from test_synth_video import clip


def test_saved_video_study_survives_original_and_library_moves(clip, tmp_path):
    original = tmp_path / 'original.mkv'; shutil.copy2(clip['path'], original)
    project = apply_treatment(video_composition(dict(clip, path=str(original))), 1)
    before = copy.deepcopy(project)
    expected = render_sequence_frame(compile_composition(project), .4, (96, 72)).tobytes()
    root = tmp_path / 'Studies'
    identifier = save_study(project, 'Ink / worn tape', root)
    assert project == before
    assert len(study_catalogue(root)) == len(STARTERS) + 1
    assert study_catalogue(root)[-1] == (identifier, 'Ink / worn tape · 1.0s')
    saved = root / identifier.split(':')[1] / 'study.json'
    raw = json.loads(saved.read_text())
    assert raw['footage']['path'] == 'media/source.mkv'
    assert str(original) not in saved.read_text()
    original.unlink()
    moved = tmp_path / 'Relocated'; root.rename(moved)
    loaded = study_composition(identifier, moved)
    assert render_sequence_frame(compile_composition(loaded), .4, (96, 72)).tobytes() == expected
    loaded['effects'].clear()
    assert study_composition(identifier, moved)['effects'] == before['effects']


def test_generated_studies_and_duplicate_names_are_independent(tmp_path):
    project = starter_composition('profile-doryphoros')
    first = save_study(project, 'My profile', tmp_path)
    second = save_study(project, 'My profile', tmp_path)
    assert first != second
    loaded = study_composition(first, tmp_path)
    loaded['name'] = project['name']
    assert loaded == project
    assert study_composition('profile-doryphoros', tmp_path) == project
    assert len(study_catalogue(tmp_path)) == len(STARTERS) + 2


def test_failed_or_cancelled_save_never_publishes_partial_study(clip, tmp_path):
    class CancelDuringCopy(Cancellation):
        calls = 0
        def check(self):
            self.calls += 1
            if self.calls == 2: raise Cancelled()
    project = video_composition(clip)
    with pytest.raises(Cancelled): save_study(project, 'Interrupted', tmp_path, CancelDuringCopy())
    assert list(tmp_path.iterdir()) == []
    project['footage']['path'] = str(tmp_path / 'missing.mp4')
    with pytest.raises(ValueError, match='missing'): save_study(project, 'Missing', tmp_path)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError, match='name'): save_study(project, ' ', tmp_path)


def test_library_ignores_incomplete_files_and_rejects_path_traversal(tmp_path):
    folder = tmp_path / ('a' * 32); folder.mkdir()
    (folder / 'study.json').write_text('{invalid json')
    assert study_catalogue(tmp_path) == [(key, label) for key, label, _ in STARTERS]
    with pytest.raises(ValueError, match='Unknown'): study_composition('personal:../elsewhere', tmp_path)
