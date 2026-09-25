import copy

import numpy as np
import pytest

from synth import _breakup
from synth_composition import (
    blank_composition, compile_composition, load_composition, normalize_composition,
    reference_composition, save_composition,
)
from synth_effects import EFFECTS, describe_effects, effect_preset, state_values
from synth_sequence import render_sequence_frame


def pixels(project, time=.4):
    return render_sequence_frame(compile_composition(project), time, (160, 128)).tobytes()


@pytest.mark.parametrize("effect", EFFECTS, ids=lambda effect: effect.id)
def test_effects_can_be_applied_to_a_new_section_and_bypassed(effect):
    project = blank_composition()
    # Processors need a source. Generators also work from an empty field.
    if effect.id not in {"forms", "rays", "particles"}:
        project["effects"]["forms"] = effect_preset("forms")
    baseline = pixels(project)
    project["sections"][0]["effects"][effect.id] = effect_preset(effect.id)
    changed = pixels(project)
    assert changed != baseline, effect.id
    assert pixels(project) == changed
    project["sections"][0]["effects"][effect.id]["mode"] = "off"
    assert pixels(project) != changed


def test_overrides_are_absolute_local_reversible_and_persistent(tmp_path):
    project = reference_composition(refined=True)
    before = compile_composition(project)
    project["sections"][1]["effects"]["rays"] = effect_preset("rays", 1)
    project["sections"][1]["effects"]["rays"]["params"]["blinds.rows"] = 17
    after = compile_composition(project)
    for name, state in after["states"].items():
        if name.startswith("section-2:"):
            values, enabled = state_values(state)
            assert values["blinds.rows"] == 17
            assert "blinds" in enabled
    for t in (0., 10., 12.8):
        assert render_sequence_frame(after, t, (96, 72)).tobytes() == render_sequence_frame(before, t, (96, 72)).tobytes()
    assert render_sequence_frame(after, 6.2, (96, 72)).tobytes() != render_sequence_frame(before, 6.2, (96, 72)).tobytes()
    path = tmp_path / "effects.json"
    save_composition(path, project)
    assert load_composition(path) == project
    assert pixels(load_composition(path), 6.2) == pixels(project, 6.2)
    project["sections"][1]["effects"].clear()
    assert compile_composition(project) == before


def test_global_effect_local_bypass_and_restore_keep_inherited_parameters():
    project = reference_composition(True)
    project["effects"]["ghosts"] = effect_preset("ghosts")
    project["effects"]["ghosts"]["params"]["smear.ghosts"] = 8
    project["sections"][1]["effects"]["ghosts"] = {"mode": "off", "params": {}}
    state = compile_composition(project)["states"]["section-2:slab"]
    values, enabled = state_values(state)
    assert "smear" not in enabled and values["slab.ghost_opacity"] == 0
    project["sections"][1]["effects"]["ghosts"]["mode"] = "on"
    values, enabled = state_values(compile_composition(project)["states"]["section-2:slab"])
    assert "smear" in enabled and values["slab.ghost_opacity"] == .34 and values["smear.ghosts"] == 8
    project["effects"]["ghosts"]["mode"] = "off"
    # A local On overrides a global Off without retaining the global mute values.
    values, enabled = state_values(compile_composition(project)["states"]["section-2:slab"])
    assert "smear" in enabled and values["slab.ghost_opacity"] == .34


def test_inspector_reports_real_recipe_ranges_and_active_effects():
    sequence = compile_composition(reference_composition(True))
    rays = describe_effects([s for name, s in sequence["states"].items() if name.startswith("section-1:")])
    blocks = describe_effects([s for name, s in sequence["states"].items() if name.startswith("section-2:")])
    assert rays["rays"]["active"] and rays["rays"]["intermittent"]
    low, high = rays["rays"]["ranges"]["blinds.rows"]
    assert low < high and high > 1
    assert not blocks["rays"]["active"]
    assert blocks["forms"]["active"]
    assert rays["forms"]["ranges"] != blocks["forms"]["ranges"]


def test_breakup_is_random_access_and_holds_at_its_own_rate():
    image = np.linspace(0, 1, 64 * 80 * 3, dtype=np.float32).reshape((64, 80, 3))
    settings = {"amount": .25, "bands": 12, "dropout": .3, "rate": 5, "mix": 1}
    preset = {"seed": 72}
    first = _breakup(image, settings, .01, preset)
    assert np.array_equal(first, _breakup(image, settings, .19, preset))
    assert not np.array_equal(first, _breakup(image, settings, .21, preset))
    _breakup(image, settings, 100, preset)
    assert np.array_equal(first, _breakup(image, settings, .01, preset))
    assert np.array_equal(image, _breakup(image, dict(settings, mix=0), .01, preset))
    assert np.array_equal(_breakup(image, dict(settings, rate=0), 0, preset), _breakup(image, dict(settings, rate=0), 25, preset))


@pytest.mark.parametrize("entry", [
    {"mode": "surprise", "params": {}},
    {"params": {"slab.width": .4}},
    {"params": {"breakup.bands": 2.5}},
    {"params": {"breakup.amount": float("nan")}},
    {"params": {"breakup.mix": 2}},
])
def test_invalid_effect_settings_are_rejected(entry):
    project = blank_composition()
    project["effects"]["breakup"] = entry
    with pytest.raises(ValueError): normalize_composition(project)


def test_older_documents_upgrade_without_changing_frames():
    project = reference_composition(True)
    original = copy.deepcopy(project)
    del project["effects"]
    for section in project["sections"]: del section["effects"]
    assert normalize_composition(project) == original
    assert pixels(project) == pixels(original)


def test_new_clip_has_no_hidden_study_events():
    project = blank_composition()
    sequence = compile_composition(project)
    assert len(sequence["cues"]) == 1
    assert not sequence["field"]["cloud_strength"]
    assert all(not state["enabled"] for state in sequence["states"].values())
    assert pixels(project, 0) == pixels(project, 12)
