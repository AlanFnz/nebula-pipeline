import copy
import subprocess

from synth import curated_presets, default_synth_preset, load_synth, normalize_synth, render_synth_frame, save_synth
from synth_media import export_synth_video


def only_module(preset, module_id):
    p = copy.deepcopy(preset)
    p["modules"] = [entry for entry in p["modules"] if entry["id"] == module_id]
    return p


def test_synth_is_deterministic_and_random_access_uses_time():
    preset = default_synth_preset()
    a = render_synth_frame(preset, frame=3, time_seconds=.4, size=(120, 96))
    b = render_synth_frame(preset, frame=999, time_seconds=.4, size=(120, 96))
    assert a.tobytes() == b.tobytes()


def test_treatment_rate_holds_the_complete_image_and_speed_zero_is_static():
    preset = only_module(default_synth_preset(), "blinds")
    preset["treatment_fps"] = 5
    assert render_synth_frame(preset, time_seconds=.01, size=(120, 96)).tobytes() == render_synth_frame(preset, time_seconds=.05, size=(120, 96)).tobytes()
    preset["speed"] = 0
    assert render_synth_frame(preset, time_seconds=0, size=(120, 96)).tobytes() == render_synth_frame(preset, time_seconds=2, size=(120, 96)).tobytes()


def test_schema_preserves_unknown_modules_and_round_trips(tmp_path):
    preset = default_synth_preset()
    preset["modules"].append({"id": "future", "enabled": True, "params": {"x": 1}})
    path = tmp_path / "preset.json"
    save_synth(path, preset)
    loaded = load_synth(path)
    assert loaded["modules"][-1]["id"] == "future"
    assert normalize_synth(loaded)["modules"][-1]["params"]["x"] == 1


def test_curated_presets_render():
    for preset in curated_presets().values():
        assert render_synth_frame(preset, time_seconds=.2, size=(96, 72)).size == (96, 72)


def test_synth_export_is_atomic_and_has_expected_duration(tmp_path):
    preset = only_module(default_synth_preset(), "blinds")
    preset.update({"width": 96, "height": 72, "loop_seconds": .2, "export_fps": 10})
    target = tmp_path / "synth.mp4"
    export_synth_video(preset, target)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=nb_frames,width,height", "-of", "default=noprint_wrappers=1", str(target)], capture_output=True, text=True, check=True).stdout
    assert "width=96" in probe and "height=72" in probe and "nb_frames=2" in probe
