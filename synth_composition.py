"""Musical-scale composition above the deterministic sequence renderer.

Documents keep a snapshot of their source material. Sections arrange reusable
phrases and macro controls compile to ordinary sequence states and cues.
"""
from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path

from synth import MODULE_BY_ID, SHAPES, _seed, curated_presets
from synth_sequence import normalize_sequence, reference_sequence

FORMAT = "nebula-composition"
MACROS = {
    "rhythm": ("Rhythm", .25, 2., "Slower holds / faster changes within each section."),
    "width": ("Width", .5, 1.8, "Scale the luminous forms and ray apertures together."),
    "motion": ("Instability", 0., 2., "Registration, edge flutter, deformation and missing fragments."),
    "texture": ("Texture", 0., 2., "Horizontal grain, granular ghosts and the surrounding signal cloud."),
    "glow": ("Brightness", .25, 1.6, "Core intensity and bloom, preserving the color relationships."),
    "flashes": ("Flares", 0., 1.8, "Strength of exposure bursts and sweeps."),
    "color": ("Magenta", 0., 1.8, "Violet-magenta edges and the blue falloff in dim forms."),
}
PATHS = {
    "width": ("slab.width", "blinds.aperture"),
    "motion": ("slab.frame_jitter", "slab.edge_ripple", "slab.jitter", "slab.notch", "blinds.curvature", "blinds.row_drift", "blinds.irregularity", "warp.amount", "flare.bend", "flare.asymmetry"),
    "texture": ("raster.grain", "raster.chroma", "raster.line_noise", "slab.ghost_grain", "slab.cloud_strength", "slab.cloud_detail"),
    "glow": ("slab.intensity", "blinds.intensity", "bloom.strength"),
    "flashes": ("flare.strength",),
    "color": ("slab.fill_magenta", "slab.vertical_tint", "slab.magenta", "blinds.magenta", "flare.fringe"),
}
PHRASES = (
    ("rays", "Ray bursts", 0., 5.24),
    ("blocks", "Blocks & ghosts", 5.24, 8.24),
    ("noise", "Signal drift", 8.24, 10.08),
    ("break", "Breakdown", 10.08, 11.4),
    ("quiet", "Violet pause", 11.4, 13.68),
    ("return", "Noisy return", 13.68, 15.),
)


def neutral_macros():
    return dict.fromkeys(MACROS, 1.)


def default_geometry(section=False):
    return {"shape": "inherit" if section else "original", "height": 1., "diameter": .6, "sides": 6, "rotation": 0.}


def effective_geometry(project, section):
    global_geometry = project["geometry"]
    local_geometry = section["geometry"]
    result = copy.deepcopy(global_geometry if local_geometry["shape"] == "inherit" else local_geometry)
    result["height"] = global_geometry["height"] * local_geometry["height"]
    return result


def reference_composition(refined=False):
    source = reference_sequence(refined=refined)
    return {
        "format": FORMAT, "schema_version": 1,
        "name": "Refined signal" if refined else "Composite signal", "fps": source["fps"], "seed": source["seed"],
        "source": source,
        "phrases": {key: {"name": name, "start": start, "end": end} for key, name, start, end in PHRASES},
        "macros": neutral_macros(), "geometry": default_geometry(), "variation": 0, "locks": [],
        "sections": [
            {"id": f"section-{index + 1}", "phrase": key, "duration": round(end - start, 2),
             "macros": neutral_macros(), "geometry": default_geometry(section=True), "variation": 0, "locks": []}
            for index, (key, _name, start, end) in enumerate(PHRASES)
        ],
    }


def composition_from_sequence(sequence):
    """An imported detailed sequence remains intact as one reusable phrase."""
    source = normalize_sequence(sequence)
    result = reference_composition()
    result.update(name=source["name"], source=source, fps=source["fps"], seed=source["seed"])
    result["phrases"] = {"custom": {"name": source["name"], "start": 0., "end": source["duration"]}}
    result["sections"] = [{"id": "section-1", "phrase": "custom", "duration": source["duration"], "macros": neutral_macros(), "geometry": default_geometry(section=True), "variation": 0, "locks": []}]
    return result


def _number(value, label, low, high, integer=False):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    if integer and not float(value).is_integer():
        raise ValueError(f"{label} must be an integer")
    return int(value) if integer else float(value)


def _controls(raw):
    if not isinstance(raw, dict):
        raise ValueError("Macro controls must be an object")
    result = {}
    for key, (_label, low, high, _hint) in MACROS.items():
        result[key] = _number(raw.get(key, 1.), key, low, high)
    return result


def _geometry(raw, section=False):
    if not isinstance(raw, dict):
        raise ValueError("Geometry must be an object")
    result = default_geometry(section)
    result.update({key: raw[key] for key in result if key in raw})
    shapes = {"original", *(label.lower() for label in SHAPES)}
    if section:
        shapes.add("inherit")
    if not isinstance(result["shape"], str) or result["shape"] not in shapes:
        raise ValueError("Unknown geometry shape")
    for key, low, high in (("height", .25, 2.), ("diameter", .05, 1.5), ("sides", 3, 32), ("rotation", -180, 180)):
        result[key] = _number(result[key], key, low, high, key == "sides")
    return result


def normalize_composition(raw):
    if not isinstance(raw, dict) or raw.get("format") != FORMAT or raw.get("schema_version") != 1:
        raise ValueError("Unsupported composition document")
    result = copy.deepcopy(raw)
    if not isinstance(raw.get("source"), dict):
        raise ValueError("A composition must contain its source recipe")
    result["source"] = normalize_sequence(raw.get("source"))
    result["name"] = str(raw.get("name", "Untitled composition"))
    result["fps"] = _number(raw.get("fps", 25), "FPS", 1, 120, True)
    result["seed"] = _number(raw.get("seed", 0), "Seed", 0, 2**31 - 1, True)
    result["macros"] = _controls(raw.get("macros", {}))
    result["geometry"] = _geometry(raw.get("geometry", {}))
    result["variation"] = _number(raw.get("variation", 0), "Variation", 0, 2**31 - 1, True)
    result["locks"] = [key for key in raw.get("locks", []) if key in MACROS]
    phrases = result.get("phrases")
    if not isinstance(phrases, dict) or not phrases:
        raise ValueError("The composition needs reusable phrases")
    for phrase in phrases.values():
        if not isinstance(phrase, dict):
            raise ValueError("Invalid phrase")
        phrase["start"] = _number(phrase.get("start"), "Phrase start", 0, result["source"]["duration"])
        phrase["end"] = _number(phrase.get("end"), "Phrase end", 0, result["source"]["duration"])
        if phrase["end"] <= phrase["start"]:
            raise ValueError("A phrase must have a positive duration")
        phrase["name"] = str(phrase.get("name", "Phrase"))
    sections = result.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= 64:
        raise ValueError("Use between 1 and 64 sections")
    ids = set()
    for section in sections:
        if not isinstance(section, dict) or section.get("phrase") not in phrases:
            raise ValueError("Unknown section phrase")
        identifier = section.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("Section identifiers must be unique")
        ids.add(identifier)
        duration = _number(section.get("duration"), "Section duration", 1 / result["fps"], 300)
        section["duration"] = max(1, round(duration * result["fps"])) / result["fps"]
        section["macros"] = _controls(section.get("macros", {}))
        section["geometry"] = _geometry(section.get("geometry", {}), section=True)
        section["variation"] = _number(section.get("variation", 0), "Variation", 0, 2**31 - 1, True)
        section["locks"] = [key for key in section.get("locks", []) if key in MACROS]
    if sum(section["duration"] for section in sections) > 3600:
        raise ValueError("Composition is longer than one hour")
    return result


def section_ranges(composition):
    fps = composition["fps"]
    cursor = 0
    result = []
    for section in composition["sections"]:
        frames = max(1, round(section["duration"] * fps))
        result.append((cursor / fps, (cursor + frames) / fps))
        cursor += frames
    return result


def _adjust_state(state, macros, seed_offset, geometry):
    result = copy.deepcopy(state)
    presets = curated_presets()[state["preset"]]
    defaults = {f"{entry['id']}.{key}": value for entry in presets["modules"] for key, value in entry["params"].items()}
    overrides = result.setdefault("overrides", {})
    for module_id, height_key in (("slab", "height"), ("blinds", "aperture_height")):
        if geometry["shape"] != "original":
            overrides[f"{module_id}.shape"] = [label.lower() for label in SHAPES].index(geometry["shape"])
            for key in ("diameter", "sides", "rotation"):
                overrides[f"{module_id}.{key}"] = geometry[key]
        if geometry["height"] != 1:
            path = f"{module_id}.{height_key}"
            spec = next(spec for spec in MODULE_BY_ID[module_id].params if spec.key == height_key)
            overrides[path] = max(spec.minimum, min(spec.maximum, overrides.get(path, defaults[path]) * geometry["height"]))
    for macro, paths in PATHS.items():
        if macros[macro] == 1:
            continue  # Neutral macros preserve the approved settings verbatim.
        for path in paths:
            module_id, key = path.split(".")
            spec = next(spec for spec in MODULE_BY_ID[module_id].params if spec.key == key)
            value = overrides.get(path, defaults[path]) * macros[macro]
            overrides[path] = max(spec.minimum, min(spec.maximum, value))
    if seed_offset:
        overrides["seed"] = (int(overrides.get("seed", presets["seed"])) + seed_offset) % (2**31 - 1)
    return result


def compile_composition(raw):
    """Compile the arrangement to the same public sequence format as before."""
    project = normalize_composition(raw)
    result = copy.deepcopy(project["source"])
    result.update(name=project["name"], fps=project["fps"], seed=project["seed"], states={}, cues=[])
    fps = project["fps"]
    ranges = section_ranges(project)
    result["duration"] = ranges[-1][1]
    source_cues = project["source"]["cues"]
    # The optional field track keeps its original absolute-time contract.
    for section, (start, end) in zip(project["sections"], ranges):
        phrase = project["phrases"][section["phrase"]]
        first, last = phrase["start"], phrase["end"]
        active = next((cue for cue in reversed(source_cues) if cue["time"] <= first), source_cues[0])
        events = [copy.deepcopy(cue) for cue in source_cues if first <= cue["time"] < last]
        if not events or events[0]["time"] > first:
            events.insert(0, dict(active, time=first, transition="cut", duration=0.))
        macros = {key: project["macros"][key] * section["macros"][key] for key in MACROS}
        rate = macros["rhythm"]
        cycle = (last - first) / rate
        variant = (project["variation"], section["variation"])
        offset = _seed(project["seed"], section["id"], *variant) % (2**31 - 1) if any(variant) else 0
        cues_by_frame = {}
        for repetition in range(math.ceil((end - start) / cycle)):
            for cue in events:
                frame = round((start + repetition * cycle + (cue["time"] - first) / rate) * fps)
                if frame >= round(end * fps):
                    break
                state_name = f"{section['id']}:{cue['state']}"
                if state_name not in result["states"]:
                    result["states"][state_name] = _adjust_state(project["source"]["states"][cue["state"]], macros, offset, effective_geometry(project, section))
                item = dict(cue, time=frame / fps, state=state_name)
                item["duration"] = min(float(cue.get("duration", 0)) / rate, end - frame / fps)
                if cue.get("transition") in {"flash", "sweep"}:
                    item["intensity"] = min(3., cue.get("intensity", .6) * macros["flashes"])
                cues_by_frame[frame] = item
        result["cues"].extend(cues_by_frame[frame] for frame in sorted(cues_by_frame))
    return normalize_sequence(result)


def vary_composition(raw, section_index=None):
    result = normalize_composition(raw)
    target = result if section_index is None else result["sections"][section_index]
    target["variation"] += 1
    rng = random.Random(_seed(result["seed"], "composition-take", target.get("id", "whole"), target["variation"]))
    for key, (_name, low, high, _hint) in MACROS.items():
        if key in target["locks"]:
            continue
        target["macros"][key] = round(max(low, min(high, target["macros"][key] + rng.uniform(-.15, .15))), 2)
    return result


def save_composition(path, composition):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize_composition(composition), indent=2) + "\n")


def load_composition(path):
    return normalize_composition(json.loads(Path(path).read_text()))
