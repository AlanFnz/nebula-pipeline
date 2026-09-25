"""Particle motion, legacy compatibility and editable composition contracts."""
import copy
import hashlib

import numpy as np
import pytest

from synth import default_synth_preset, normalize_synth, render_synth_frame
from synth_composition import compile_composition, load_composition, particle_composition, particle_orbit_composition, save_composition
from synth_effects import describe_effects
from synth_particles import _orbit_cloud, _population, _surface_visibility, particle_field, render_particles
from synth_sequence import render_sequence_frame


def particle_only():
    preset = default_synth_preset()
    preset["modules"] = [item for item in preset["modules"] if item["id"] == "particles"]
    preset["modules"][0]["enabled"] = True
    preset["speed"] = 1.
    return preset, preset["modules"][0]["params"]


@pytest.mark.parametrize("shape", range(5))
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


@pytest.mark.parametrize("params", [{"count": 0}, {"attractor": 5}, {"period": 0}, {"assembly": float("nan")}, {"release": 2}, {"orbit_start": 1}, {"orbit_speed": float("inf")}, {"motion": 3}, {"expand_seconds": 0}, {"gather_seconds": 0}, {"motion_peak": 2}])
def test_invalid_particle_controls_are_rejected(params):
    preset, settings = particle_only()
    settings.update(params)
    with pytest.raises(ValueError):
        normalize_synth(preset)


def test_original_particle_study_keeps_pre_surge_pixels():
    sequence = compile_composition(particle_composition())
    # Recorded from beaa70f before mesh sampling, surges and interference.
    frames = (render_sequence_frame(sequence, t, (192, 144)).tobytes() for t in (0, .8, 2., 6., 10., 14.96))
    assert hashlib.sha256(b"".join(frames)).hexdigest() == "842cdfe61497dc12d417cd6683861ff45def95a2ac4a4721e8ee4f28b0918708"


def test_surge_particles_accelerate_overshoot_and_remain_random_access():
    _, p = particle_only()
    p.update(attractor=3, motion=1, count=1000, period=5., phase=0.,
             yaw=0., pitch=0., rotation_speed=0., turbulence=0., chaos=0., overshoot=0., acceleration=1.)
    speeds = []
    for t in (.6, .9, 1.2, 1.5, 1.8):
        a = particle_field(p, t, 20)[0]
        b = particle_field(p, t + .01, 20)[0]
        speeds.append(np.linalg.norm(b - a, axis=1).mean() / .01)
    assert max(speeds) > min(speeds) * 8 + .1
    p["overshoot"] = 1.
    points = particle_field(p, 2.2, 20)[0]
    target, _, cloud, _ = _population(3, 1000, 20)
    direction = target - cloud
    progress = ((points - cloud) * direction).sum(axis=1) / (direction * direction).sum(axis=1)
    assert np.median(progress) > 1.05  # Travels beyond the surface, then settles.
    p.update(chaos=.8, turbulence=.3)
    before, _, _, cohesion = particle_field(p, 1.75, 20)
    assert np.std(cohesion) > .05  # Groups arrive at different times.
    particle_field(p, 72.3, 20)
    assert np.array_equal(before, particle_field(p, 1.75, 20)[0])
    assert np.linalg.norm(particle_field(p, 1.751, 20)[0] - before, axis=1).max() < .03


def test_human_mesh_has_stable_area_samples_and_unit_normals():
    small = _population(3, 300, 81)
    large = _population(3, 1000, 81)
    assert np.array_equal(small[0], large[0][:300])
    assert np.isfinite(large[0]).all()
    assert np.allclose(np.linalg.norm(large[1], axis=1), 1., atol=1e-5)
    assert not np.array_equal(small[0], _population(0, 300, 81)[0])


def test_signal_study_is_editable_without_touching_original(tmp_path):
    original = particle_composition()
    project = particle_composition(True)
    assert len(project["sections"]) == 3
    seq = compile_composition(project)
    assert len(seq["cues"]) == 11
    summary = describe_effects(seq["states"].values())
    assert summary["particles"]["ranges"]["particles.attractor"] == (3, 3)
    assert summary["particles"]["ranges"]["particles.motion"] == (1, 1)
    assert all(summary[key]["active"] for key in ("interference", "flare", "drift", "separation", "raster"))
    path = tmp_path / "signal-head.json"
    save_composition(path, project)
    assert load_composition(path) == project
    assert particle_composition() == original


def test_signal_band_study_keeps_pre_orbit_pixels_and_old_documents_default_to_band():
    sequence = compile_composition(particle_composition(True))
    frames = (render_sequence_frame(sequence, t, (192, 144)).tobytes() for t in (0, .8, 2., 6., 10., 14.96))
    assert hashlib.sha256(b"".join(frames)).hexdigest() == "8ff2dda6e189d1f0b78a6d78d38d9b831e2a8dc0c1e8c1c191ed6277704a803f"
    preset, params = particle_only()
    for key in ("release", "orbit_speed", "orbit_start"):
        params.pop(key)
    assert normalize_synth(preset)["modules"][0]["params"]["release"] == 0


def test_orbit_expands_on_all_axes_and_rotates_without_falling_or_tapering():
    _, p = particle_only()
    p.update(attractor=3, motion=1, release=1, count=2000, breathing=0., assembly=0.,
             yaw=0., pitch=0., rotation_speed=0., turbulence=0., chaos=0.,
             orbit_speed=30., dispersion=1., collapse=1.)
    initial = particle_field(p, 0., 20)[0]
    target = _population(3, 2000, 20)[0]
    assert np.all(initial.std(axis=0) > target.std(axis=0) * 1.4)
    assert (initial[:, 1] > .7).mean() > .1
    assert (initial[:, 1] < -.7).mean() > .1
    later = particle_field(p, 1., 20)[0]
    angle = np.deg2rad(30.)
    assert np.allclose(later[:, 0], initial[:, 0] * np.cos(angle) + initial[:, 2] * np.sin(angle))
    assert np.allclose(later[:, 1], initial[:, 1])
    assert np.allclose(np.linalg.norm(later[:, (0, 2)], axis=1), np.linalg.norm(initial[:, (0, 2)], axis=1))
    p["orbit_speed"] = -30.
    reverse = particle_field(p, 1., 20)[0]
    assert np.allclose(reverse[:, 0], initial[:, 0] * np.cos(angle) - initial[:, 2] * np.sin(angle))
    p["orbit_speed"] = 0.
    assert np.array_equal(initial, particle_field(p, 55., 20)[0])
    p.update(assembly=1., orbit_speed=60.)
    assert np.array_equal(target, particle_field(p, 55., 20)[0])


def test_orbit_waits_for_expansion_and_stays_continuous_across_long_seeks():
    preset, p = particle_only()
    p.update(attractor=3, motion=1, release=1, count=500, period=5., acceleration=1.,
             chaos=0., turbulence=0., orbit_start=.7, orbit_speed=30.,
             yaw=0., pitch=0., rotation_speed=0.)
    target, _, _, attrs = _population(3, 500, 20)
    assert np.array_equal(_orbit_cloud(p, 2.85, target, attrs), _orbit_cloud(p, 3.7, target, attrs))
    assert not np.allclose(_orbit_cloud(p, 3.7, target, attrs), _orbit_cloud(p, 4.2, target, attrs))
    p.update(chaos=.8, turbulence=.25)
    for t in (0., 4.9995, 6.9, 72.3, 10000., 1000000.):
        before = particle_field(p, t, 20)[0]
        assert np.linalg.norm(particle_field(p, t + .001, 20)[0] - before, axis=1).max() < .03
        particle_field(p, 250., 20)
        assert np.array_equal(before, particle_field(p, t, 20)[0])
    preset["speed"] = 0.
    p["jitter"] = 0.
    assert render_synth_frame(preset, time_seconds=0., size=(120, 96)).tobytes() == render_synth_frame(preset, time_seconds=15., size=(120, 96)).tobytes()


def test_orbit_study_has_two_editable_expansions_and_preserves_earlier_studies(tmp_path):
    band = particle_composition(True)
    project = particle_orbit_composition()
    assert len(project["sections"]) == 2
    assert compile_composition(project)["duration"] == 15.
    summary = describe_effects(compile_composition(project)["states"].values())["particles"]["ranges"]
    assert summary["particles.release"] == (1, 1)
    assert summary["particles.period"] == (7.5, 7.5)
    assert summary["particles.motion"] == (2, 2)
    path = tmp_path / "orbit.json"
    save_composition(path, project)
    assert load_composition(path) == project
    assert particle_composition(True) == band


def test_saved_first_orbit_study_keeps_its_pixels():
    seq = compile_composition(particle_orbit_composition(refined=False))
    frames = (render_sequence_frame(seq, t, (192, 144)).tobytes() for t in (0, .8, 2., 6., 10., 14.96))
    assert hashlib.sha256(b"".join(frames)).hexdigest() == "ebe373ee1559c9d8459d8674602aaef1c4954088686cccfa0208dc5c34f36701"


def test_impulse_has_exactly_two_expansions_and_peaked_velocity():
    _, p = particle_only()
    p.update(attractor=3, motion=2, release=1, count=300, period=7.5, phase=0.,
             chaos=.35, yaw=0., pitch=0., rotation_speed=0., turbulence=0., orbit_speed=0.)
    times = np.arange(375) / 25
    release = np.array([1 - particle_field(p, t, 20)[3].mean() for t in times])
    crossings = times[1:][(release[:-1] < .5) & (release[1:] >= .5)]
    assert len(crossings) == 2
    assert crossings[0] == pytest.approx(2.5, abs=.06)
    assert crossings[1] - crossings[0] == pytest.approx(7.5, abs=.04)
    assert release[0] == release[-1] == 0.
    assert (release[80:135] == 1.).all()  # A real hold in the expanded cloud.
    assert (release[175:230] == 0.).all()  # A held portrait between the bursts.

    p["chaos"] = 0.
    sample_times = np.linspace(2.1, 2.85, 151)
    paths = np.array([particle_field(p, t, 20)[0] for t in sample_times])
    speeds = np.linalg.norm(np.diff(paths, axis=0), axis=2).mean(axis=1) / .005
    assert speeds.max() > 3.5 * speeds.mean()
    assert speeds[0] < speeds.max() * .01 and speeds[-1] < speeds.max() * .01
    p["motion_peak"] = 0.
    linear = np.array([particle_field(p, t, 20)[0] for t in sample_times])
    linear_speeds = np.linalg.norm(np.diff(linear, axis=0), axis=2).mean(axis=1) / .005
    assert linear_speeds.max() < linear_speeds.mean() * 1.01


@pytest.mark.parametrize("period", [.5, 7.5, 120.])
def test_impulse_seeking_and_orbit_are_continuous_including_cycle_wraps(period):
    _, p = particle_only()
    p.update(attractor=3, motion=2, release=1, count=300, period=period,
             chaos=.35, turbulence=.15, breathing=1., orbit_speed=24.)
    for phase in (0., .28, .33, .76, .96, .9999):
        t = 1000 * period + phase * period
        before = particle_field(p, t, 20)[0]
        particle_field(p, 30., 20)
        assert np.array_equal(before, particle_field(p, t, 20)[0])
        assert np.linalg.norm(particle_field(p, t + .0001, 20)[0] - before, axis=1).max() < .04


def test_impulse_study_uses_tape_faults_without_added_bars_or_changed_timing():
    from synth_sequence import _state_preset
    seq = compile_composition(particle_orbit_composition())
    summary = describe_effects(seq["states"].values())
    assert summary["tape"]["active"]
    assert all(not summary[key]["active"] for key in ("rays", "forms", "flare", "breakup", "interference"))
    assert summary["tape"]["ranges"]["tape.tracking"][1] >= .1
    assert summary["particles"]["ranges"]["particles.attractor"] == (4, 4)
    assert summary["particles"]["ranges"]["particles.color_spread"][1] < .1
    # The actual rendered recipe, including section boundaries, keeps one clock.
    for t in (2.48, 9.98):
        cue = next(cue for cue in reversed(seq["cues"]) if cue["time"] <= t)
        preset = _state_preset(seq, cue["state"])
        settings = {m["id"]: m for m in preset["modules"]}
        assert settings["particles"]["params"]["motion"] == 2
        assert settings["tape"]["params"]["tracking"] == .005
        assert not settings["blinds"]["enabled"]
    previous = describe_effects(compile_composition(particle_orbit_composition(tape=False))["states"].values())["particles"]["ranges"]
    for key in ("motion", "release", "period", "phase", "expand_seconds", "gather_seconds", "motion_peak", "orbit_speed", "orbit_start"):
        assert summary["particles"]["ranges"][f"particles.{key}"] == previous[f"particles.{key}"]


def test_previous_two_impulse_study_keeps_its_pixels():
    seq = compile_composition(particle_orbit_composition(tape=False))
    frames = (render_sequence_frame(seq, t, (192, 144)).tobytes() for t in (0, .8, 2., 6., 10., 14.96))
    assert hashlib.sha256(b"".join(frames)).hexdigest() == "1eda8e522c270637d12682142e1e4f85104e7ccadf9b6ddd28ffe3c6cc905722"


def test_depth_hides_deeper_face_points_but_releases_the_whole_cloud():
    points = np.array(((0, 0, .8), (0, 0, -.4), (1, 0, -.4)))
    x, y = np.array((.5, .5, .8)), np.array((.5, .5, .5))
    visible = _surface_visibility(points, x, y, np.ones(3), 1.25, 1.)
    assert visible[0] == visible[2] == 1.
    assert visible[1] < .001
    assert np.array_equal(_surface_visibility(points, x, y, np.zeros(3), 1.25, 1.), np.ones(3))
    assert np.array_equal(_surface_visibility(points, x, y, np.ones(3), 1.25, 0.), np.ones(3))


def test_portrait_mesh_keeps_stable_points_and_valid_normals():
    small, large = _population(4, 300, 81), _population(4, 1000, 81)
    assert np.array_equal(small[0], large[0][:300])
    assert np.allclose(np.linalg.norm(large[1], axis=1), 1., atol=1e-5)
    assert np.isfinite(large[0]).all()
    assert not np.array_equal(small[0], _population(3, 300, 81)[0])
