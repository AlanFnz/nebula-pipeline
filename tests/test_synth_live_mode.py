"""Live is opt-in, persistent, and never exports a substitute internal sound."""
import copy

import pytest

from synth_composition import compile_composition, load_composition, save_composition, normalize_composition
from synth_exploration import capture_snapshot, restore_snapshot
from synth_lattice_sound import color_wave_sound
from synth_live_mode import LIVE_OUTPUT, is_live
from synth_output_ui import export_audio_label
from synth_pleated_recipes import pleated_composition
from synth_preview import _visual_document
from synth_studies import save_study, study_composition
from synth_visual_sound import audio_output, default_sound, acid_sound, instrument_sound, normalize_sound


@pytest.mark.parametrize('factory', [instrument_sound, color_wave_sound])
def test_live_mode_roundtrips_project_study_snapshot_and_keeps_visuals(factory, tmp_path):
    project = pleated_composition()
    project['generated_sound'] = normalize_sound(factory())
    project = normalize_composition(project)
    original = copy.deepcopy(project)
    project['generated_sound']['output'] = LIVE_OUTPUT
    path = tmp_path / 'Live.json'
    save_composition(path, project)
    loaded = load_composition(path)
    assert loaded == project
    assert is_live(compile_composition(loaded)['generated_sound'])
    assert _visual_document(compile_composition(loaded)) == _visual_document(compile_composition(original))
    root = tmp_path / 'Studies'
    key = save_study(loaded, 'Live', root)
    assert study_composition(key, root)['generated_sound'] == project['generated_sound']
    captured, key = capture_snapshot(loaded, 'Live')
    captured['generated_sound']['output'] = 'generated'
    assert is_live(restore_snapshot(captured, key)['generated_sound'])
    restored = copy.deepcopy(loaded);restored['generated_sound']['output'] = 'generated'
    assert restored == original


@pytest.mark.parametrize('factory', [default_sound, acid_sound, instrument_sound, color_wave_sound])
def test_old_outputs_and_missing_output_keep_their_behavior(factory):
    original = factory()
    for route in ('generated', 'existing', 'silent'):
        config = dict(original, output=route)
        result = normalize_sound(config)
        assert result['output'] == route and not is_live(result)
        assert audio_output(dict(generated_sound=result)) == ('footage' if route == 'existing' else route)
    del original['output']
    assert normalize_sound(original)['output'] == 'generated'


@pytest.mark.parametrize('factory', [default_sound, acid_sound])
def test_original_instruments_do_not_silently_convert_to_another_instrument(factory):
    with pytest.raises(ValueError): normalize_sound(dict(factory(), output=LIVE_OUTPUT))


def test_live_export_requires_an_explicitly_imported_soundtrack():
    seq = dict(generated_sound=dict(instrument_sound(), output=LIVE_OUTPUT))
    assert audio_output(seq) == 'silent'
    assert 'Live audio is external' in export_audio_label(seq)
    seq['soundtrack'] = dict(export_audio='footage', path='/tmp/Guide.wav')
    assert audio_output(seq) == 'silent'
    seq['soundtrack']['export_audio'] = 'soundtrack'
    assert audio_output(seq) == 'soundtrack'
    assert export_audio_label(seq) == 'Soundtrack · Guide.wav'
