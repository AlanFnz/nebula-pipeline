"""Editable, deterministic cue sequences for source-free synth transitions."""
from __future__ import annotations

import copy
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from synth import _seed, curated_presets, normalize_synth, render_synth_frame

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


@lru_cache(maxsize=2)
def _reference_data(refined=False):
    filename = "composite-signal-refined-15s.json" if refined else "composite-study-15s.json"
    return json.loads((Path(__file__).parent / "presets" / filename).read_text())


def reference_sequence(refined=False):
    """Return an independent, editable copy of the bundled 15-second study."""
    return copy.deepcopy(_reference_data(refined))


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
                value = cue[key]
                lo, hi = (0, 3) if key == "intensity" else (-1, 1)
                if not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
                    raise ValueError(f"Cue {key} is outside the supported range")
                item[key] = float(value)
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
    amount = 1.0
    if transition != "cut" and cue.get("duration", 0) > 0:
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
