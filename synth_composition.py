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
from synth_effects import apply_effects, merge_effects, normalize_effects

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
        "macros": neutral_macros(), "geometry": default_geometry(), "effects": {}, "variation": 0, "locks": [],
        "sections": [
            {"id": f"section-{index + 1}", "phrase": key, "duration": round(end - start, 2),
             "macros": neutral_macros(), "geometry": default_geometry(section=True), "effects": {}, "variation": 0, "locks": []}
            for index, (key, _name, start, end) in enumerate(PHRASES)
        ],
    }


def composition_from_sequence(sequence):
    """An imported detailed sequence remains intact as one reusable phrase."""
    source = normalize_sequence(sequence)
    result = reference_composition()
    result.update(name=source["name"], source=source, fps=source["fps"], seed=source["seed"])
    result["phrases"] = {"custom": {"name": source["name"], "start": 0., "end": source["duration"]}}
    result["sections"] = [{"id": "section-1", "phrase": "custom", "duration": source["duration"], "macros": neutral_macros(), "geometry": default_geometry(section=True), "effects": {}, "variation": 0, "locks": []}]
    return result


def blank_composition():
    """A single clean section to build from reusable effects."""
    source = normalize_sequence({
        "schema_version": 1, "name": "Free composition", "duration": 15., "fps": 25, "seed": 2409,
        "states": {"blank": {"preset": "Reference blinds", "enabled": [], "overrides": {"slab.ghost_opacity": 0., "slab.cloud_strength": 0., "slab.cloud_detail": 0.}}},
        "cues": [{"time": 0., "state": "blank", "transition": "cut"}],
    })
    return composition_from_sequence(source)


def particle_composition(refined=False):
    """One editable section; the particle module owns its assembly cycle."""
    if refined:
        return _particle_signal_composition()
    project = blank_composition()
    project["name"] = "Particle head"
    project["source"]["name"] = "Particle head"
    project["phrases"]["custom"]["name"] = "Assemble / disperse"
    state = project["source"]["states"]["blank"]
    state["enabled"] = ["particles", "bloom", "raster"]
    state["overrides"].update({
        "speed": 1., "depth": 0., "treatment_fps": 25,
        "particles.period": 15., "particles.phase": .03,
        "particles.count": 42000, "particles.dot_size": 1.3,
        "particles.dispersion": 1.1, "particles.collapse": .8,
        "particles.turbulence": .3, "particles.yaw": -48.,
        "particles.pitch": -4., "particles.rotation_speed": 4.,
        "particles.intensity": 2.3, "particles.saturation": .45,
        "particles.color_spread": .6, "particles.color_drift": .012,
        "particles.shimmer": .45, "particles.xray": .025,
        "bloom.threshold": .3, "bloom.radius": 6., "bloom.strength": .35,
        "raster.softness": .3, "raster.lines": .12, "raster.grain": .05,
        "raster.chroma": .006, "raster.line_noise": .045,
    })
    return normalize_composition(project)


def _particle_signal_composition():
    """Three phrases layer signal treatments over one continuous particle clock."""
    project = particle_composition()
    base = copy.deepcopy(project["source"]["states"]["blank"])
    base["enabled"] = ["particles", "flare", "warp", "separation", "smear", "interference", "bloom", "raster", "breakup"]
    base["overrides"].update({
        "particles.attractor": 3, "particles.motion": 1,
        "particles.period": 4.6, "particles.phase": .02,
        "particles.acceleration": .9, "particles.chaos": .78, "particles.overshoot": .65,
        "particles.count": 48000, "particles.dot_size": 1.05,
        "particles.dispersion": 1.08, "particles.collapse": .98,
        "particles.turbulence": .22, "particles.flow": 1.4,
        "particles.yaw": -32., "particles.pitch": -3., "particles.rotation_speed": 3.5,
        "particles.saturation": .8, "particles.hue": .74, "particles.color_spread": 1.1,
        "particles.intensity": 2.7, "particles.color_drift": .035, "particles.jitter": .002,
        "particles.released_brightness": .22,
        "warp.amount": .009, "warp.frequency": 4.5, "warp.speed": 1.3,
        "separation.amount": .003, "separation.angle": .15,
        "smear.amount": .014, "smear.ghosts": 3,
        "interference.chroma": .55, "interference.depth": .4, "interference.comb": .3,
        "interference.bands": 8., "interference.speed": 1.4,
        "flare.strength": 0., "flare.position_y": .9, "flare.position_x": .5,
        "flare.spread": .04, "flare.reach": .85,
        "bloom.threshold": .2, "bloom.radius": 5., "bloom.strength": .42,
        "raster.softness": .45, "raster.lines": .16, "raster.line_noise": .07,
        "breakup.amount": .025, "breakup.bands": 20, "breakup.dropout": .04,
        "breakup.rate": 8., "breakup.mix": 0.,
    })
    variants = {
        "charge": {},
        "crest": {"flare.strength": .55, "flare.spread": .065, "interference.chroma": .3},
        "storm": {"warp.amount": .021, "interference.chroma": .85, "interference.depth": .65,
                  "interference.comb": .65, "particles.turbulence": .32, "particles.jitter": .003},
        "tear": {"warp.amount": .018, "breakup.mix": .85, "interference.chroma": .95,
                 "interference.depth": .72, "interference.speed": 2.2, "separation.amount": .006},
        "return": {"particles.turbulence": .16, "interference.depth": .32, "interference.chroma": .7,
                   "particles.intensity": 2.35, "raster.line_noise": .05},
    }
    states = {}
    for name, overrides in variants.items():
        states[name] = copy.deepcopy(base)
        states[name]["overrides"].update(overrides)
    cues = [(0., "charge", 0.), (2.45, "crest", .12), (2.65, "charge", .18),
            (4.8, "storm", .2), (6.35, "tear", .08), (6.65, "storm", .16),
            (8.65, "crest", .08), (8.85, "storm", .18),
            (10.2, "return", .25), (12.75, "crest", .10), (12.95, "return", .18)]
    project["name"] = "Particle signal"
    project["source"].update(name="Particle signal", states=states,
        cues=[{"time": t, "state": name, "transition": "morph" if duration else "cut", "duration": duration} for t, name, duration in cues])
    phrases = (("charge", "Charge & gather", 0., 4.8), ("storm", "Signal storm", 4.8, 10.2), ("return", "Release & return", 10.2, 15.))
    project["phrases"] = {key: {"name": name, "start": start, "end": end} for key, name, start, end in phrases}
    section = project["sections"][0]
    project["sections"] = [dict(copy.deepcopy(section), id=f"section-{index + 1}", phrase=key, duration=round(end - start, 2)) for index, (key, _, start, end) in enumerate(phrases)]
    return normalize_composition(project)


def particle_orbit_composition():
    """A faster, outward release variant; the earlier signal recipe stays intact."""
    project = _particle_signal_composition()
    project["name"] = project["source"]["name"] = "Particle orbit"
    for state in project["source"]["states"].values():
        state["overrides"].update({
            "particles.release": 1, "particles.period": 3.8,
            "particles.orbit_speed": 24., "particles.orbit_start": .7,
            "particles.dispersion": .9, "particles.scale": .8,
            "particles.released_brightness": .65, "particles.rotation_speed": 1.5,
            "flare.position_y": .5, "flare.spread": .12,
        })
    project["phrases"]["charge"]["name"] = "Gather & expand"
    project["phrases"]["storm"]["name"] = "Orbiting signal"
    project["phrases"]["return"]["name"] = "Disperse & return"
    return normalize_composition(project)


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
    result["effects"] = normalize_effects(raw.get("effects", {}))
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
        section["effects"] = normalize_effects(section.get("effects", {}))
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


def phrase_events(project, section):
    phrase = project["phrases"][section["phrase"]]
    first, last = phrase["start"], phrase["end"]
    cues = project["source"]["cues"]
    active = next((cue for cue in reversed(cues) if cue["time"] <= first), cues[0])
    events = [copy.deepcopy(cue) for cue in cues if first <= cue["time"] < last]
    if not events or events[0]["time"] > first:
        events.insert(0, dict(active, time=first, transition="cut", duration=0.))
    return events


def compile_composition(raw):
    """Compile the arrangement to the same public sequence format as before."""
    project = normalize_composition(raw)
    result = copy.deepcopy(project["source"])
    result.update(name=project["name"], fps=project["fps"], seed=project["seed"], states={}, cues=[])
    fps = project["fps"]
    ranges = section_ranges(project)
    result["duration"] = ranges[-1][1]
    # The optional field track keeps its original absolute-time contract.
    for section, (start, end) in zip(project["sections"], ranges):
        phrase = project["phrases"][section["phrase"]]
        first, last = phrase["start"], phrase["end"]
        events = phrase_events(project, section)
        effects = merge_effects(project["effects"], section["effects"])
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
                    state = _adjust_state(project["source"]["states"][cue["state"]], macros, offset, effective_geometry(project, section))
                    result["states"][state_name] = apply_effects(state, effects)
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
