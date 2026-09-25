"""Editable, deterministic cue sequences for source-free synth transitions."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from synth import _seed, SYNTH_SCHEMA_VERSION, curated_presets, normalize_synth, render_synth_frame

SEQUENCE_SCHEMA_VERSION = 1
NEUTRAL_FIELD = {
    "valley_start": 0.0,
    "valley_end": 0.0,
    "valley_gain": 1.0,
    "cloud_start": 0.0,
    "cloud_strength": 0.0,
    "cloud_late_start": 0.0,
    "cloud_late_rate": 0.0,
}


def _state(base_name, overrides=None, enabled=None):
    return {"preset": base_name, "overrides": overrides or {}, **({"enabled": enabled} if enabled is not None else {})}


def reference_sequence():
    """A 15 second authored study of the reference's rapid shape changes."""
    return {
        "schema_version": SEQUENCE_SCHEMA_VERSION,
        "name": "Reference study · first 15 seconds",
        "duration": 15.0,
        "fps": 25,
        "seed": 15025,
        "field": {
            "valley_start": 11.4,
            "valley_end": 13.2,
            "valley_gain": .45,
            "cloud_start": 8.2,
            "cloud_strength": .045,
            "cloud_late_start": 14.2,
            "cloud_late_rate": .20,
        },
        "states": {
            "blinds": _state("Reference blinds", {"blinds.aperture": .52, "blinds.aperture_position": .40, "blinds.aperture_height": .64, "blinds.thickness": .014, "blinds.swelling": .78, "blinds.taper": .45, "blinds.curvature": .02, "warp.amount": .002, "separation.amount": .004, "smear.amount": .045, "bloom.strength": .18, "raster.grain": .045}),
            "burst": _state("Reference blinds", {"blinds.aperture": .52, "blinds.aperture_position": .40, "blinds.thickness": .022, "blinds.swelling": 1.0, "blinds.taper": .48, "warp.amount": .035, "separation.amount": .012, "smear.amount": .18, "bloom.strength": .40}),
            "slab": _state("Luminous slab", {"slab.height": .60, "slab.position_x": .16, "slab.position_y": .04, "slab.width": .30, "slab.edge_softness": .010, "slab.edge_hardness": .94, "slab.notch": .16, "slab.intensity": .96, "slab.ghost_width": .58, "slab.ghost_offset": .30, "slab.ghost_opacity": .40, "smear.amount": .12, "separation.amount": .006}),
            "double": _state("Luminous slab", {"slab.count": 1, "slab.height": .56, "slab.position_x": .08, "slab.spacing": .32, "slab.width": .24, "slab.edge_softness": .010, "slab.position_y": .06, "slab.notch": .38, "slab.intensity": .86, "slab.ghost_width": .82, "slab.ghost_offset": .34, "slab.ghost_opacity": .46, "smear.amount": .16, "separation.amount": .009}),
            "magenta": _state("Luminous slab", {"slab.count": 1, "slab.height": .58, "slab.position_x": .16, "slab.position_y": .04, "slab.width": .26, "slab.edge_softness": .012, "slab.notch": .28, "slab.intensity": .76, "slab.fill_magenta": .78, "slab.magenta": 1.0, "slab.ghost_width": .72, "slab.ghost_offset": .34, "slab.ghost_opacity": .48, "bloom.strength": .32, "smear.amount": .13, "separation.amount": .006}),
            "outline": _state("Luminous slab", {"slab.height": .56, "slab.position_x": .17, "slab.position_y": .02, "slab.width": .17, "slab.edge_softness": .008, "slab.hollow": .98, "slab.edge_hardness": .98, "slab.notch": .40, "slab.intensity": .52, "slab.ghost_width": .70, "slab.ghost_offset": .34, "slab.ghost_opacity": .42, "bloom.strength": .20, "smear.amount": .07, "separation.amount": .004}),
            "noisy": _state("Luminous slab", {"slab.height": .58, "slab.position_x": .18, "slab.position_y": .03, "slab.width": .28, "slab.edge_softness": .012, "slab.notch": .48, "slab.intensity": .80, "slab.ghost_width": .78, "slab.ghost_offset": .36, "slab.ghost_opacity": .52, "bloom.strength": .28, "raster.grain": .18, "raster.chroma": .06, "smear.amount": .16, "separation.amount": .003}),
            "dimfilled": _state("Luminous slab", {"slab.height": .56, "slab.position_x": .18, "slab.position_y": .02, "slab.width": .26, "slab.edge_softness": .012, "slab.hollow": .02, "slab.notch": .32, "slab.intensity": .70, "slab.ghost_width": .72, "slab.ghost_offset": .34, "slab.ghost_opacity": .36, "bloom.strength": .18, "raster.grain": .11, "raster.chroma": .03, "smear.amount": .10, "separation.amount": .002}),
            "one": _state("Reference blinds", {"blinds.rows": 1, "blinds.thickness": .075, "blinds.aperture": .24, "blinds.aperture_height": .52, "blinds.swelling": 1.0, "blinds.taper": .28, "separation.amount": .004, "smear.amount": .06}),
            "two": _state("Reference blinds", {"blinds.rows": 2, "blinds.thickness": .026, "blinds.aperture": .22, "blinds.swelling": .90, "blinds.taper": .42, "separation.amount": .004, "smear.amount": .05}),
            "four": _state("Reference blinds", {"blinds.rows": 4, "blinds.thickness": .020, "blinds.aperture": .24, "blinds.swelling": .88, "blinds.taper": .52, "separation.amount": .005, "smear.amount": .05}),
            "eight": _state("Reference blinds", {"blinds.rows": 8, "blinds.thickness": .014, "blinds.aperture": .27, "blinds.swelling": .84, "blinds.taper": .66, "separation.amount": .005, "smear.amount": .05}),
            "dense": _state("Reference blinds", {"blinds.rows": 18, "blinds.thickness": .007, "blinds.aperture": .30, "blinds.swelling": .72, "blinds.taper": .78, "warp.amount": .012, "separation.amount": .004, "smear.amount": .03}),
            "fullflash": _state("Luminous slab", {"slab.count": 1, "slab.height": 1.0, "slab.position_x": .02, "slab.position_y": 0, "slab.width": .78, "slab.edge_hardness": .35, "slab.intensity": 1.5, "slab.ghost_width": .9, "slab.ghost_offset": .22, "slab.ghost_opacity": .48, "bloom.strength": 1.2, "smear.amount": .22, "separation.amount": .004}),
            "late_slab": _state("Luminous slab", {"slab.height": .58, "slab.position_x": .18, "slab.position_y": .04, "slab.width": .30, "slab.intensity": .62, "slab.ghost_width": .82, "slab.ghost_offset": .34, "slab.ghost_opacity": .46, "slab.notch": .25, "bloom.strength": .42, "smear.amount": .20, "separation.amount": .004}),
        },
        "cues": [
            {"time": 0.00, "state": "blinds", "transition": "cut", "duration": 0.00},
            {"time": 0.36, "state": "fullflash", "transition": "flash", "duration": .08, "intensity": .90},
            {"time": 0.40, "state": "outline", "transition": "cut", "duration": 0.00},
            {"time": 0.44, "state": "one", "transition": "cut", "duration": 0.00},
            {"time": 0.48, "state": "fullflash", "transition": "flash", "duration": .08, "intensity": 1.0},
            {"time": 0.56, "state": "four", "transition": "sweep", "duration": .08, "intensity": .32, "direction": 1},
            {"time": 0.64, "state": "one", "transition": "cut", "duration": 0.00},
            {"time": 0.68, "state": "two", "transition": "cut", "duration": 0.00},
            {"time": 0.72, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 0.76, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 0.80, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 0.88, "state": "slab", "transition": "sweep", "duration": .08, "intensity": .25, "direction": 1},
            {"time": 1.12, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 1.16, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 1.20, "state": "two", "transition": "cut", "duration": 0.00},
            {"time": 1.24, "state": "burst", "transition": "flash", "duration": .08, "intensity": .76},
            {"time": 1.32, "state": "slab", "transition": "sweep", "duration": .08, "intensity": .26, "direction": -1},
            {"time": 1.36, "state": "fullflash", "transition": "flash", "duration": .08, "intensity": 1.0},
            {"time": 1.44, "state": "burst", "transition": "sweep", "duration": .08, "intensity": .58, "direction": 1},
            {"time": 1.48, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 1.52, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 1.56, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 1.60, "state": "slab", "transition": "sweep", "duration": .08, "intensity": .20, "direction": -1},
            {"time": 1.72, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 1.76, "state": "burst", "transition": "sweep", "duration": .08, "intensity": .66, "direction": 1},
            {"time": 1.84, "state": "burst", "transition": "flash", "duration": .08, "intensity": .92},
            {"time": 1.88, "state": "two", "transition": "cut", "duration": 0.00},
            {"time": 1.92, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 2.00, "state": "outline", "transition": "cut", "duration": 0.00},
            {"time": 2.08, "state": "burst", "transition": "flash", "duration": .08, "intensity": .65},
            {"time": 2.16, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 2.20, "state": "double", "transition": "morph", "duration": .12},
            {"time": 2.76, "state": "blinds", "transition": "cut", "duration": 0.00},
            {"time": 3.16, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 3.24, "state": "blinds", "transition": "cut", "duration": 0.00},
            {"time": 3.28, "state": "double", "transition": "sweep", "duration": .08, "intensity": .20, "direction": 1},
            {"time": 3.32, "state": "double", "transition": "cut", "duration": 0.00},
            {"time": 3.84, "state": "slab", "transition": "morph", "duration": .10},
            {"time": 4.12, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 4.52, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 4.64, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 4.68, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 4.72, "state": "two", "transition": "cut", "duration": 0.00},
            {"time": 4.76, "state": "one", "transition": "cut", "duration": 0.00},
            {"time": 4.80, "state": "two", "transition": "cut", "duration": 0.00},
            {"time": 4.84, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 4.92, "state": "burst", "transition": "sweep", "duration": .08, "intensity": .52, "direction": -1},
            {"time": 5.00, "state": "burst", "transition": "flash", "duration": .08, "intensity": .72},
            {"time": 5.20, "state": "slab", "transition": "cut", "duration": 0.00},
            {"time": 6.10, "state": "double", "transition": "morph", "duration": .24},
            {"time": 7.15, "state": "slab", "transition": "cut", "duration": 0.00},
            {"time": 7.62, "state": "magenta", "transition": "morph", "duration": .18},
            {"time": 8.04, "state": "noisy", "transition": "morph", "duration": .20},
            {"time": 9.15, "state": "double", "transition": "sweep", "duration": .16, "intensity": .28, "direction": -1},
            {"time": 9.48, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 9.52, "state": "double", "transition": "cut", "duration": 0.00},
            {"time": 9.80, "state": "slab", "transition": "cut", "duration": 0.00},
            {"time": 10.08, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 10.12, "state": "eight", "transition": "cut", "duration": 0.00},
            {"time": 10.16, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 10.20, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 10.24, "state": "two", "transition": "cut", "duration": 0.00},
            {"time": 10.28, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 10.32, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 10.40, "state": "four", "transition": "cut", "duration": 0.00},
            {"time": 10.48, "state": "one", "transition": "cut", "duration": 0.00},
            {"time": 10.52, "state": "two", "transition": "sweep", "duration": .08, "intensity": .42, "direction": 1},
            {"time": 10.68, "state": "burst", "transition": "sweep", "duration": .08, "intensity": .78, "direction": 1},
            {"time": 10.72, "state": "outline", "transition": "cut", "duration": 0.00},
            {"time": 10.76, "state": "fullflash", "transition": "flash", "duration": .08, "intensity": 1.0},
            {"time": 10.84, "state": "double", "transition": "sweep", "duration": .08, "intensity": .25, "direction": -1},
            {"time": 10.92, "state": "outline", "transition": "cut", "duration": 0.00},
            {"time": 10.96, "state": "outline", "transition": "cut", "duration": 0.00},
            {"time": 11.18, "state": "outline", "transition": "morph", "duration": .18},
            {"time": 11.20, "state": "dense", "transition": "cut", "duration": 0.00},
            {"time": 11.28, "state": "double", "transition": "cut", "duration": 0.00},
            {"time": 11.40, "state": "dimfilled", "transition": "cut", "duration": 0.00},
            {"time": 12.05, "state": "dimfilled", "transition": "cut", "duration": 0.00},
            {"time": 13.05, "state": "double", "transition": "morph", "duration": .18},
            {"time": 13.20, "state": "dimfilled", "transition": "cut", "duration": 0.00},
            {"time": 13.62, "state": "outline", "transition": "cut", "duration": 0.00},
            {"time": 14.05, "state": "late_slab", "transition": "sweep", "duration": .14, "intensity": .20, "direction": 1},
            {"time": 14.54, "state": "late_slab", "transition": "flash", "duration": .13, "intensity": .12},
        ],
    }


def normalize_sequence(raw=None):
    if raw is None:
        return reference_sequence()
    if not isinstance(raw, dict):
        raise ValueError("Synth sequence must be a JSON object")
    if int(raw.get("schema_version", 0)) != SEQUENCE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported sequence schema version: {raw.get('schema_version')}")
    result = copy.deepcopy(reference_sequence())
    result["name"] = str(raw.get("name", result["name"]))
    for key, lo, hi in (("duration", .1, 3600), ("fps", 1, 120), ("seed", 0, 2**31 - 1)):
        value = raw.get(key, result[key])
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not lo <= float(value) <= hi:
            raise ValueError(f"{key} is outside the supported range")
        result[key] = int(value) if key in {"fps", "seed"} else float(value)
    field = copy.deepcopy(raw.get("field", NEUTRAL_FIELD))
    if not isinstance(field, dict):
        raise ValueError("field must be an object")
    result["field"] = copy.deepcopy(NEUTRAL_FIELD)
    for key, default in NEUTRAL_FIELD.items():
        value = field.get(key, default)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"field.{key} must be finite")
        result["field"][key] = float(value)
    states = raw.get("states", result["states"])
    if not isinstance(states, dict):
        raise ValueError("states must be an object")
    result["states"] = {}
    for name, state in states.items():
        if not isinstance(name, str) or not isinstance(state, dict) or state.get("preset") not in curated_presets():
            raise ValueError(f"Unknown sequence state: {name}")
        overrides = state.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError(f"{name}.overrides must be an object")
        result["states"][name] = {"preset": state["preset"], "overrides": copy.deepcopy(overrides)}
        if "enabled" in state:
            result["states"][name]["enabled"] = list(state["enabled"])
    cues = raw.get("cues", result["cues"])
    if not isinstance(cues, list) or not cues:
        raise ValueError("cues must be a non-empty list")
    normalized = []
    last = -1
    for cue in cues:
        if not isinstance(cue, dict) or cue.get("state") not in result["states"]:
            raise ValueError("Each cue needs a known state")
        time = cue.get("time")
        duration = cue.get("duration", 0)
        if not isinstance(time, (int, float)) or not math.isfinite(float(time)) or float(time) < 0 or float(time) > result["duration"]:
            raise ValueError("Cue time is outside the sequence")
        if not isinstance(duration, (int, float)) or not math.isfinite(float(duration)) or float(duration) < 0:
            raise ValueError("Cue duration must be non-negative")
        if float(time) < last:
            raise ValueError("Cues must be sorted by time")
        last = float(time)
        item = {"time": float(time), "state": cue["state"], "transition": str(cue.get("transition", "cut")), "duration": min(float(duration), result["duration"] - float(time))}
        for key in ("intensity", "direction"):
            if key in cue:
                item[key] = float(cue[key])
        if item["transition"] not in {"cut", "morph", "sweep", "flash"}:
            raise ValueError("transition must be cut, morph, sweep or flash")
        normalized.append(item)
    result["cues"] = normalized
    return result


def save_sequence(path, sequence):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize_sequence(sequence), indent=2) + "\n")


def load_sequence(path):
    return normalize_sequence(json.loads(Path(path).read_text()))


def _apply_override(preset, path, value):
    parts = path.split(".")
    if len(parts) == 1 and parts[0] in preset:
        preset[parts[0]] = value
        return
    if len(parts) != 2:
        return
    module_id, key = parts
    for entry in preset["modules"]:
        if entry.get("id") == module_id:
            entry.setdefault("params", {})[key] = value
            return


def _state_preset(sequence, state_name):
    state = sequence["states"][state_name]
    preset = copy.deepcopy(curated_presets()[state["preset"]])
    for path, value in state.get("overrides", {}).items():
        _apply_override(preset, path, value)
    if "enabled" in state:
        enabled = set(state["enabled"])
        for entry in preset["modules"]:
            entry["enabled"] = entry.get("id") in enabled
    # Authored study cues own their timing. Disable the standalone preset's
    # slow LFO targets so a cue cannot be silently reshaped underneath it.
    preset["animation"]["targets"] = {}
    preset["seed"] = int((preset["seed"] + sequence["seed"]) % (2**31 - 1))
    return normalize_synth(preset)


def _ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def _interpolate_presets(first, second, amount):
    """Interpolate numeric geometry/signal controls before rendering.

    This keeps a transition spatially coherent: rows, apertures, slab widths
    and exposure change as one generated form instead of dissolving two images.
    """
    result = copy.deepcopy(first)
    for key in ("speed", "depth"):
        if key in second and isinstance(second[key], (int, float)):
            result[key] = float(first.get(key, second[key])) * (1 - amount) + float(second[key]) * amount
    by_id = {entry.get("id"): entry for entry in second.get("modules", [])}
    for entry in result.get("modules", []):
        other = by_id.get(entry.get("id"))
        if not other:
            continue
        entry["enabled"] = entry.get("enabled", True) if amount < .5 else other.get("enabled", True)
        for key, value in other.get("params", {}).items():
            original = entry.get("params", {}).get(key, value)
            if isinstance(original, (int, float)) and isinstance(value, (int, float)):
                interpolated = float(original) * (1 - amount) + float(value) * amount
                entry.setdefault("params", {})[key] = round(interpolated) if key in {"count", "rows", "ghosts"} else interpolated
            elif amount >= .5:
                entry.setdefault("params", {})[key] = value
    return normalize_synth(result)


def _transition_images(sequence, cue_index, time_seconds, size):
    cue = sequence["cues"][cue_index]
    if cue_index == 0 or cue.get("transition") == "cut" or cue.get("duration", 0) <= 0:
        return render_synth_frame(_state_preset(sequence, cue["state"]), time_seconds=time_seconds, size=size), None, 0.0, cue
    previous = sequence["cues"][cue_index - 1]
    duration = float(cue.get("duration", 0))
    elapsed = time_seconds - float(cue["time"])
    current = render_synth_frame(_state_preset(sequence, previous["state"]), time_seconds=time_seconds, size=size)
    target = render_synth_frame(_state_preset(sequence, cue["state"]), time_seconds=time_seconds, size=size)
    if elapsed >= duration:
        return target, None, 0.0, cue
    return current, target, _ease(elapsed / duration), cue


def render_sequence_frame(sequence, time_seconds, size=None):
    seq = normalize_sequence(sequence)
    t = max(0.0, min(float(seq["duration"]), float(time_seconds)))
    cue_index = 0
    for index, cue in enumerate(seq["cues"]):
        if cue["time"] <= t:
            cue_index = index
        else:
            break
    cue = seq["cues"][cue_index]
    transition = cue.get("transition", "cut")
    amount = 0.0
    if cue_index > 0 and transition != "cut" and cue.get("duration", 0) > 0:
        amount = _ease((t - cue["time"]) / cue["duration"])
        if amount >= 1:
            amount = 1.0
    if cue_index > 0 and transition != "cut" and amount < 1:
        previous = seq["cues"][cue_index - 1]
        first = _state_preset(seq, previous["state"])
        second = _state_preset(seq, cue["state"])
        # Sweeps and flashes are authored as event overlays: their target
        # geometry is visible on the first frame of the event. Only morphs
        # spend their onset frame on the previous geometry.
        base = second if transition in {"sweep", "flash"} else _interpolate_presets(first, second, amount)
        current = render_synth_frame(base, time_seconds=t, size=size)
    else:
        current = render_synth_frame(_state_preset(seq, cue["state"]), time_seconds=t, size=size)
    result = np.asarray(current, dtype=np.float32) / 255
    if transition == "sweep" and amount < 1:
        direction = float(cue.get("direction", 1))
        y = np.linspace(-1, 1, result.shape[0])[:, None]
        edge = -1 + amount * 2 if direction >= 0 else 1 - amount * 2
        sweep = np.clip((y - edge) / .16, 0, 1) if direction >= 0 else np.clip((edge - y) / .16, 0, 1)
        result += sweep[..., None] * float(cue.get("intensity", .5)) * np.array((1.0, .985, .98), dtype=np.float32)[None, None, :]
    if transition == "flash" and amount < 1:
        # Flash peaks on its first held frame instead of vanishing at onset.
        intensity = float(cue.get("intensity", .6)) * (1.0 - .35 * amount)
        y, x = np.mgrid[0:result.shape[0], 0:result.shape[1]]
        xn = x / max(1, result.shape[1] - 1) * 2 - 1
        sweep = np.exp(-(((xn - (.15 + .55 * amount)) / .42) ** 2))
        flash_color = np.array((1.0, .985, .98), dtype=np.float32)[None, None, :]
        result = result * (1 - .90 * intensity) + flash_color * (.90 * intensity)
        result += intensity * .12 * sweep[..., None] * flash_color
    field = seq.get("field", NEUTRAL_FIELD)
    if field["valley_start"] <= t <= field["valley_end"] and field["valley_end"] > field["valley_start"]:
        result *= field["valley_gain"]
    if t >= field["cloud_start"] and field["cloud_strength"] > 0:
        cloud_strength = field["cloud_strength"] if t < field["cloud_late_start"] else min(.2, field["cloud_strength"] + (t - field["cloud_late_start"]) * field["cloud_late_rate"])
        rng = np.random.default_rng(_seed(seq["seed"], "sequence-cloud", round(t * seq["fps"])))
        cloud = rng.normal(0, cloud_strength, result.shape[:2]).astype(np.float32)
        y, x = np.mgrid[0:result.shape[0], 0:result.shape[1]]
        cloud_mask = np.exp(-((((x / max(1, result.shape[1] - 1) - .62) / .42) ** 2) + (((y / max(1, result.shape[0] - 1) - .5) / .65) ** 2)))
        result += cloud[..., None] * cloud_mask[..., None] * np.array((.72, .82, .78), dtype=np.float32)[None, None, :]
    return Image.fromarray(np.clip(result * 255, 0, 255).astype(np.uint8), "RGB")
