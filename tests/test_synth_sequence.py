import copy
import subprocess

from synth import curated_presets
from synth_media import export_synth_video
from synth_sequence import load_sequence, normalize_sequence, reference_sequence, render_sequence_frame, save_sequence


def test_reference_sequence_has_ordered_cues_and_deterministic_scrub():
    sequence = reference_sequence()
    assert sequence["duration"] == 15.0
    assert all(a["time"] <= b["time"] for a, b in zip(sequence["cues"], sequence["cues"][1:]))
    a = render_sequence_frame(sequence, 1.36, (120, 96))
    b = render_sequence_frame(sequence, 1.36, (120, 96))
    assert a.tobytes() == b.tobytes()


def test_sequence_round_trip_and_editable_cue(tmp_path):
    sequence = reference_sequence()
    sequence["cues"][1]["duration"] = .04
    path = tmp_path / "study.json"
    save_sequence(path, sequence)
    loaded = load_sequence(path)
    assert loaded["cues"][1]["duration"] == .04
    assert "fullflash" in loaded["states"]


def test_sequence_export_is_one_continuous_fps_grid(tmp_path):
    sequence = reference_sequence()
    sequence["duration"] = .2
    sequence["cues"] = [cue for cue in sequence["cues"] if cue["time"] <= .2]
    sequence = normalize_sequence(sequence)
    preset = curated_presets()["Reference blinds"]
    preset.update({"width": 96, "height": 72})
    output = tmp_path / "study.mp4"
    export_synth_video(preset, output, sequence=sequence, size=(96, 72))
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=nb_frames,width,height", "-of", "default=noprint_wrappers=1", str(output)], capture_output=True, text=True, check=True).stdout
    assert "nb_frames=5" in info and "width=96" in info and "height=72" in info
