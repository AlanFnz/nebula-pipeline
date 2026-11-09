"""Live Set links survive document workflows without becoming render inputs."""
import copy
import json

import pytest

from synth_composition import blank_composition, compile_composition, load_composition, normalize_composition, save_composition
from synth_live_set import LIVE_SET
from synth_montage import new_montage, add_asset, insert_clip, load_montage, protect_destination, save_montage
from synth_preview import _visual_document
from synth_studies import save_study, study_composition


def test_link_survives_save_study_and_independent_variants_without_copying_set(tmp_path):
    live = tmp_path / 'Live Project' / 'Music #1 & Σ.als'
    live.parent.mkdir();live.write_bytes(b'unchanged Live Set')
    project = blank_composition();original = copy.deepcopy(project)
    project[LIVE_SET] = str(live)
    assert compile_composition(project) == compile_composition(original)
    assert _visual_document(project) == _visual_document(original)
    assert project['schema_version'] == normalize_composition(project)['schema_version']
    saved = tmp_path / 'piece.json';save_composition(saved, project)
    assert load_composition(saved) == project
    root = tmp_path / 'Studies'
    first = save_study(project, 'First', root)
    project[LIVE_SET] = str(tmp_path / 'Another.als')
    second = save_study(project, 'Second', root)
    assert study_composition(first, root)[LIVE_SET] == str(live)
    assert study_composition(second, root)[LIVE_SET] == project[LIVE_SET]
    assert not list(root.rglob('*.als'))
    assert live.read_bytes() == b'unchanged Live Set'


def test_relative_link_resolves_at_load_and_missing_set_does_not_prevent_loading(tmp_path):
    project = blank_composition();project[LIVE_SET] = 'Live Project/Missing.als'
    path = tmp_path / 'piece.json';path.write_text(json.dumps(project))
    loaded = load_composition(path)
    assert loaded[LIVE_SET] == str(tmp_path / 'Live Project/Missing.als')
    saved = tmp_path / 'elsewhere' / 'copy.json';save_composition(saved, loaded)
    assert load_composition(saved) == loaded


@pytest.mark.parametrize('path', ['', 12, {}, 'wrong.txt', 'bad\0.als'])
def test_invalid_link_is_rejected_without_mutating_document(path):
    project = blank_composition();project[LIVE_SET] = path;before = copy.deepcopy(project)
    with pytest.raises(ValueError, match='Live Set'): normalize_composition(project)
    assert project == before


def test_old_documents_keep_no_link():
    project = blank_composition()
    assert LIVE_SET not in normalize_composition(project)
    project[LIVE_SET] = None
    assert LIVE_SET not in normalize_composition(project)


def test_snapshot_links_resolve_without_changing_the_working_link(tmp_path):
    from synth_exploration import capture_snapshot, restore_snapshot
    project = blank_composition();project[LIVE_SET] = 'First.als'
    project, snapshot = capture_snapshot(project, 'First version')
    project[LIVE_SET] = 'Second.als'
    path = tmp_path / 'snapshots.json';save_composition(path, project)
    loaded = load_composition(path)
    assert loaded[LIVE_SET] == str(tmp_path / 'Second.als')
    assert restore_snapshot(loaded, snapshot)[LIVE_SET] == str(tmp_path / 'First.als')


def test_montage_keeps_block_link_and_protects_the_set_and_alias(tmp_path):
    live = tmp_path / 'Music.als';live.write_bytes(b'original')
    project = blank_composition();project[LIVE_SET] = str(live)
    montage, key = add_asset(new_montage(), 'Study', study=project)
    montage, _ = insert_clip(montage, key)
    path = tmp_path / 'montage.json';save_montage(path, montage)
    loaded = load_montage(path)
    assert loaded['assets'][key]['document'][LIVE_SET] == str(live)
    alias = tmp_path / 'alias.json';alias.symlink_to(live)
    for target in (live, alias):
        with pytest.raises(ValueError): protect_destination(loaded, target)
    assert live.read_bytes() == b'original'
