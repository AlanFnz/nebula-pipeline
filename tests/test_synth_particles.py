"""Particle motion, legacy compatibility and editable composition contracts."""
import copy

import numpy as np
import pytest

from synth import default_synth_preset, normalize_synth, render_synth_frame
from synth_composition import compile_composition, load_composition, particle_composition, save_composition
from synth_effects import describe_effects
from synth_particles import _population, particle_field, render_particles
from synth_sequence import render_sequence_frame


def particle_only():
    preset = default_synth_preset()
    preset["modules"] = [item for item in preset["modules"] if item["id"] == "particles"]
    preset["modules"][0]["enabled"] = True
    preset["speed"] = 1.
    return preset, preset["modules"][0]["params"]


@pytest.mark.parametrize("shape", range(3))
def test_persistent_points_assemble_and_release_without_history(shape):
    preset, params = particle_only()
    params.update(attractor=shape, count=1200, turbulence=0., yaw=0., pitch=0., rotation_speed=0., breathing=0.)
    assembled, _, _, cohesion = particle_field(params, 0, 44)
    target, _, cloud, _ = _population(shape, params["count"], 44)
    assert np.allclose(assembled, target)
    assert np.all(cohesion == 1)
    params["assembly"] = 0.
    released, _, _, cohesion = particle_field(params, 0, 44)
    assert np.allclose(released, cloud * params["dispersion"])
    assert np.all(cohesion == 0)
    assert not np.allclose(released, assembled)
    params.update(assembly=1., breathing=1., turbulence=.25)
    before = particle_field(params, 2, 44)[0]
    particle_field(params, 120, 44)
    assert np.array_equal(before, particle_field(params, 2, 44)[0])
    assert np.isfinite(before).all()
    assert np.linalg.norm(before - particle_field(params, 2.001, 44)[0], axis=1).max() < .02
    assert not np.array_equal(before, particle_field(params, 2, 45)[0])


def test_particle_count_retains_identity_and_input_arrays_are_immutable():
    for small, large in zip(_population(0, 500, 1), _population(0, 900, 1)):
        assert np.array_equal(small, large[:500])
        assert not small.flags.writeable


def test_particle_clock_holds_and_stationary_configuration_is_static():
    preset, params = particle_only()
    preset["treatment_fps"] = 5
    first = render_synth_frame(preset, time_seconds=.21, size=(160, 128)).tobytes()
    assert first == render_synth_frame(preset, time_seconds=.39, size=(160, 128)).tobytes()
    assert first != render_synth_frame(preset, time_seconds=2, size=(160, 128)).tobytes()
    preset["speed"] = 0.
    params["jitter"] = 0.
    assert render_synth_frame(preset, time_seconds=0).tobytes() == render_synth_frame(preset, time_seconds=19).tobytes()


def test_proxy_size_preserves_particle_light_energy():
    preset, params = particle_only()
    params.update(breathing=0., turbulence=0., jitter=0.)
    means = []
    for w, h in ((160, 128), (720, 576)):
        image = render_particles(np.zeros((h, w, 3), dtype=np.float32), params, 3., preset, 10)
        means.append(image.mean())
    assert means[0] == pytest.approx(means[1], rel=.01)


def test_opt_in_generator_bypasses_exactly_and_old_synths_stay_disabled():
    preset = default_synth_preset()
    old = copy.deepcopy(preset)
    old["modules"] = [item for item in old["modules"] if item["id"] != "particles"]
    baseline = render_synth_frame(old, time_seconds=1, size=(160, 128)).tobytes()
    assert render_synth_frame(preset, time_seconds=1, size=(160, 128)).tobytes() == baseline
    particles = next(item for item in preset["modules"] if item["id"] == "particles")
    particles["enabled"] = True
    assert render_synth_frame(preset, time_seconds=1, size=(160, 128)).tobytes() != baseline
    particles["enabled"] = False
    assert render_synth_frame(preset, time_seconds=1, size=(160, 128)).tobytes() == baseline
    assert all(item["id"] != "particles" for item in normalize_synth(old)["modules"])


def test_particle_composition_roundtrip_overrides_and_local_bypass(tmp_path):
    project = particle_composition()
    sequence = compile_composition(project)
    assert len(sequence["cues"]) == 1
    assert describe_effects(sequence["states"].values())["particles"]["active"]
    path = tmp_path / "particle-head.json"
    save_composition(path, project)
    assert load_composition(path) == project
    expected = render_sequence_frame(sequence, 6, (160, 128)).tobytes()
    assert expected == render_sequence_frame(compile_composition(load_composition(path)), 6, (160, 128)).tobytes()
    project["effects"]["particles"] = {"mode": "on", "params": {"particles.attractor": 2, "particles.assembly": .4}}
    assert expected != render_sequence_frame(compile_composition(project), 6, (160, 128)).tobytes()
    project["sections"][0]["effects"]["particles"] = {"mode": "off", "params": {}}
    assert not describe_effects(compile_composition(project)["states"].values())["particles"]["active"]


@pytest.mark.parametrize("params", [{"count": 0}, {"attractor": 3}, {"period": 0}, {"assembly": float("nan")}])
def test_invalid_particle_controls_are_rejected(params):
    preset, settings = particle_only()
    settings.update(params)
    with pytest.raises(ValueError):
        normalize_synth(preset)
