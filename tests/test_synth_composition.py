import copy

import pytest

from synth_composition import compile_composition, composition_from_sequence, load_composition, normalize_composition, reference_composition, save_composition, vary_composition
from synth_sequence import reference_sequence, render_sequence_frame


def pixels(sequence, time):
    return render_sequence_frame(sequence, time, (96, 72)).tobytes()


def test_neutral_composition_preserves_every_approved_frame():
    original = reference_sequence()
    project = reference_composition()
    assert len(project["sections"]) == 6
    compiled = compile_composition(project)
    assert compiled["duration"] == 15
    assert len(compiled["cues"]) == len(original["cues"]) == 323
    for frame in range(375):
        assert pixels(compiled, frame / 25) == pixels(original, frame / 25), frame


@pytest.mark.parametrize("macro,value,time", [("rhythm", .5, .64), ("width", 1.5, 6.2), ("motion", 0., 2.4), ("texture", 0., 14.8), ("glow", .5, 6.2), ("flashes", 0., .36), ("color", 0., 6.2)])
def test_each_macro_has_a_visible_effect(macro, value, time):
    project = reference_composition()
    baseline = pixels(compile_composition(project), time)
    project["macros"][macro] = value
    assert pixels(compile_composition(project), time) != baseline


def test_section_edit_is_local_and_new_take_round_trips(tmp_path):
    project = reference_composition()
    baseline = compile_composition(project)
    project["sections"][1]["macros"]["color"] = 0
    project["sections"][1]["locks"] = ["color"]
    varied = vary_composition(project, 1)
    assert varied["sections"][1]["macros"]["color"] == 0
    result = compile_composition(varied)
    assert pixels(result, 0) == pixels(baseline, 0)
    assert pixels(result, 6.2) != pixels(baseline, 6.2)
    assert pixels(result, 12.8) == pixels(baseline, 12.8)
    path = tmp_path / "composition.json"
    save_composition(path, varied)
    assert load_composition(path) == varied
    assert pixels(compile_composition(load_composition(path)), 6.2) == pixels(result, 6.2)
    assert vary_composition(project, 1) == varied
    assert project["sections"][1]["variation"] == 0


def test_repetition_reordering_and_import_use_regular_sequence_data():
    project = reference_composition()
    project["sections"] = [project["sections"][1]]
    project["sections"][0]["duration"] = 15
    result = compile_composition(project)
    assert result["duration"] == 15
    assert result["cues"][0]["time"] == 0
    assert result["cues"][-1]["time"] < 15
    assert all(a["time"] <= b["time"] for a, b in zip(result["cues"], result["cues"][1:]))
    imported = composition_from_sequence(result)
    assert pixels(compile_composition(imported), 6.2) == pixels(result, 6.2)
    assert pixels(compile_composition(imported), 14.8) == pixels(result, 14.8)


def test_detailed_copy_and_source_snapshots_are_independent():
    project = reference_composition()
    saved = copy.deepcopy(project)
    compiled = compile_composition(project)
    name = compiled["cues"][0]["state"]
    compiled["states"][name]["overrides"]["blinds.aperture"] = .8
    assert project == saved
    assert project["source"] == reference_sequence()


def test_incomplete_or_invalid_documents_fail_instead_of_replacing_the_source():
    project = reference_composition()
    del project["source"]
    with pytest.raises(ValueError): normalize_composition(project)
    project = reference_composition()
    project["sections"][0]["duration"] = float("nan")
    with pytest.raises(ValueError): normalize_composition(project)
