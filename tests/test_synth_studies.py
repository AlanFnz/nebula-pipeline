"""Personal studies preserve recipes and media independently of working edits."""
import copy
from datetime import datetime
import json
import shutil

import pytest

from media import Cancellation, Cancelled
from synth_composition import compile_composition
from synth_sequence import render_sequence_frame
from synth_starters import STARTERS, STARTER_DATES, starter_composition
from synth_studies import LIBRARY_FILE, save_study, set_studies_removed, study_catalogue, study_composition, study_records
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
    assert study_catalogue(root)[-1] == (identifier, f'Ink / worn tape · 1.0s · {datetime.now().astimezone().date()}')
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
    assert study_catalogue(tmp_path) == [(key, f'{label} · {STARTER_DATES[key]}') for key, label, _ in STARTERS]
    with pytest.raises(ValueError, match='Unknown'): study_composition('personal:../elsewhere', tmp_path)


def test_dates_survive_library_moves_and_bad_legacy_metadata_has_a_fallback(tmp_path, monkeypatch):
    import synth_studies
    class Clock(datetime):
        @classmethod
        def now(cls): return cls(2021, 11, 4, 12)
    monkeypatch.setattr(synth_studies, 'datetime', Clock)
    root = tmp_path / 'Studies'
    key = save_study(starter_composition('profile-doryphoros'), 'Old study', root)
    original = study_records(root)[-1]
    assert original.date == '2021-11-04' and not original.estimated_date
    moved = tmp_path / 'Moved'; shutil.copytree(root, moved)
    assert study_records(moved)[-1] == original
    folder = moved / key.split(':')[1]
    (folder / 'metadata.json').write_text('{"saved_at": "not a date"}')
    legacy = study_records(moved)[-1]
    assert legacy.date == datetime.now().date().isoformat()
    assert legacy.estimated_date
    assert set(STARTER_DATES) == {key for key, _, _ in STARTERS}


def test_removing_and_restoring_multiple_studies_is_persistent_and_preserves_media(clip, tmp_path):
    project = video_composition(clip)
    key = save_study(project, 'My source', tmp_path)
    loaded = study_composition(key, tmp_path)
    source = loaded['footage']['path']
    expected = render_sequence_frame(compile_composition(loaded), .2, (96, 72)).tobytes()
    set_studies_removed([key, 'refined'], directory=tmp_path)
    assert not {key, 'refined'} & {key for key, _ in study_catalogue(tmp_path)}
    removed = {entry.identifier for entry in study_records(tmp_path, include_removed=True) if entry.removed}
    assert removed == {key, 'refined'}
    assert study_composition(key, tmp_path) == loaded
    assert loaded['footage']['path'] == source
    assert render_sequence_frame(compile_composition(loaded), .2, (96, 72)).tobytes() == expected
    set_studies_removed([key], removed=False, directory=tmp_path)
    assert key in dict(study_catalogue(tmp_path)) and 'refined' not in dict(study_catalogue(tmp_path))
    set_studies_removed(['refined'], removed=False, directory=tmp_path)
    assert len(study_catalogue(tmp_path)) == len(STARTERS) + 1


def test_bad_ids_or_failed_atomic_write_cannot_remove_other_entries(tmp_path, monkeypatch):
    import synth_studies
    set_studies_removed(['approved'], directory=tmp_path)
    before = (tmp_path / LIBRARY_FILE).read_bytes()
    with pytest.raises(ValueError, match='Unknown'):
        set_studies_removed(['personal:../outside', 'refined'], directory=tmp_path)
    assert (tmp_path / LIBRARY_FILE).read_bytes() == before
    def fail_replace(*args): raise OSError('disk full')
    monkeypatch.setattr(synth_studies.Path, 'replace', fail_replace)
    with pytest.raises(OSError, match='disk full'):
        set_studies_removed(['refined'], directory=tmp_path)
    assert (tmp_path / LIBRARY_FILE).read_bytes() == before
    assert list(tmp_path.iterdir()) == [tmp_path / LIBRARY_FILE]


def test_corrupt_index_does_not_block_loading_or_get_overwritten(tmp_path):
    (tmp_path / LIBRARY_FILE).write_text('{broken')
    assert len(study_catalogue(tmp_path)) == len(STARTERS)
    assert study_composition('refined', tmp_path)['name']
    with pytest.raises(ValueError, match='index'):
        set_studies_removed(['refined'], directory=tmp_path)
    assert (tmp_path / LIBRARY_FILE).read_text() == '{broken'


def test_favorites_preserve_removal_dates_documents_and_duplicate_identity(tmp_path):
    from synth_studies import set_studies_favorite
    project = starter_composition('profile-doryphoros')
    first = save_study(project, 'Duplicate', tmp_path)
    second = save_study(project, 'Duplicate', tmp_path)
    original = {entry.identifier: entry for entry in study_records(tmp_path)}
    recipes = {path: path.read_bytes() for path in tmp_path.glob('*/study.json')}
    set_studies_favorite([first, 'refined'], directory=tmp_path)
    set_studies_removed([first], directory=tmp_path)
    records = {entry.identifier: entry for entry in study_records(tmp_path, include_removed=True)}
    assert records[first].favorite and records[first].removed
    assert not records[second].favorite
    assert records[first].date == original[first].date
    set_studies_removed([first], False, tmp_path)
    assert next(entry for entry in study_records(tmp_path) if entry.identifier == first).favorite
    set_studies_favorite(['refined'], False, tmp_path)
    assert {entry.identifier for entry in study_records(tmp_path) if entry.favorite} == {first}
    assert all(path.read_bytes() == data for path, data in recipes.items())
    moved = tmp_path.parent / (tmp_path.name + '-moved'); shutil.copytree(tmp_path, moved)
    assert study_records(moved) == study_records(tmp_path)


def test_legacy_preferences_unknown_fields_and_corruption_are_preserved(tmp_path):
    from synth_studies import set_studies_favorite
    index = tmp_path / LIBRARY_FILE
    index.write_text(json.dumps({'schema_version': 1, 'removed': ['approved'], 'future': {'color': 'green'}}))
    assert not any(entry.favorite for entry in study_records(tmp_path, include_removed=True))
    set_studies_favorite(['refined'], directory=tmp_path)
    raw = json.loads(index.read_text())
    assert raw['removed'] == ['approved'] and raw['favorites'] == ['refined']
    assert raw['future'] == {'color': 'green'}
    for broken in ('{broken', '{"schema_version":1,"removed":[],"favorites":"refined"}'):
        index.write_text(broken)
        assert study_catalogue(tmp_path)
        with pytest.raises(ValueError, match='index'): set_studies_favorite(['refined'], directory=tmp_path)
        with pytest.raises(ValueError, match='index'): set_studies_removed(['refined'], directory=tmp_path)
        assert index.read_text() == broken


@pytest.mark.parametrize('identifier,category', [('refined', 'Signals'), ('profile-doryphoros', 'Profiles'),
    ('particle-head', 'Particles'), ('text-phosphor', 'Text'), ('ink-bloom', 'Mixed media')])
def test_saved_categories_follow_source_capabilities(identifier, category, tmp_path):
    from synth_studies import composition_category
    project = starter_composition(identifier)
    assert composition_category(project) == category
    key = save_study(project, 'Name does not imply its category', tmp_path)
    assert next(entry for entry in study_records(tmp_path) if entry.identifier == key).category == category


def test_categories_respect_source_replacement_and_ignore_treatment_rays(tmp_path):
    from synth_studies import composition_category
    project = starter_composition('profile-doryphoros')
    project['effects']['rays'] = {'mode': 'on', 'params': {}}
    assert composition_category(project) == 'Profiles'
    project['effects']['silhouette'] = {'mode': 'off', 'params': {}}
    project['effects']['text'] = {'mode': 'on', 'params': {}}
    assert composition_category(project) == 'Text'
    project['sections'][0]['effects']['text'] = {'mode': 'off', 'params': {}}
    project['sections'][0]['effects']['particles'] = {'mode': 'on', 'params': {}}
    assert composition_category(project) == 'Mixed media'
    for section in project['sections']:
        section['effects']['text'] = {'mode': 'off', 'params': {}}
        section['effects']['particles'] = {'mode': 'on', 'params': {}}
    assert composition_category(project) == 'Particles'
    assert composition_category({'source': {'states': {}}}) == 'Other'
