"""Deterministic, source-free visual synthesizer for Nebula Studio.

The renderer is intentionally stateless: a frame is a pure function of a
versioned preset, continuous time and output size.  That makes scrubbing,
variation generation and export agree without a temporal feedback buffer.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass
from numbers import Real
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

SYNTH_SCHEMA_VERSION = 1
SYNTH_PRESETS_DIR = Path.home() / ".nebula_pipeline" / "synth_presets"


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    default: float | int | str
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float = 0.01
    kind: str = "float"
    hint: str = ""


@dataclass(frozen=True)
class Module:
    id: str
    label: str
    description: str
    params: tuple[Param, ...]


def P(key, label, default, minimum=0, maximum=1, step=.01, hint="", kind=None):
    if kind is None:
        integer_bounds = float(minimum).is_integer() and float(maximum).is_integer()
        kind = "int" if isinstance(default, int) and not isinstance(default, bool) and step == 1 and integer_bounds else "float"
    if kind == "int":
        step = 1
    return Param(key, label, default, minimum, maximum, step, kind=kind, hint=hint)


MODULES = (
    Module("slab", "Luminous slabs", "Vertical luminous sources with white cores and colored edges.", (
        P("count", "Slab count", 1, 1, 5, 1, "Number of vertical sources."),
        P("width", "Core width", .18, .02, .8, .01, "Width of the bright central aperture."),
        P("spacing", "Spacing", .22, .02, 1, .01, "Distance between slab centers."),
        P("edge_softness", "Edge softness", .08, .005, .35, .005, "Soft luminous edge falloff."),
        P("magenta", "Magenta edge", .85, 0, 1, .01, "Purple/magenta channel strength."),
        P("cyan", "Cyan fringe", .42, 0, 1, .01, "Green/cyan channel fringe strength."),
        P("jitter", "Shape irregularity", .12, 0, .5, .01, "Slow shape wobble; does not randomize every frame."),
    )),
    Module("blinds", "Irregular Venetian blinds", "Horizontal rays that swell into an asymmetric central aperture.", (
        P("rows", "Ray count", 9, 2, 32, 1, "Number of horizontal rays", kind="int"),
        P("thickness", "Ray thickness", .012, .002, .12, .001, "Thickness of the thin outer rays."),
        P("aperture", "Aperture width", .34, .03, .95, .01, "Width of the thick central region."),
        P("swelling", "Central swelling", .9, 0, 1, .01, "How much rays thicken inside the aperture."),
        P("taper", "Pinch / taper", .8, 0, 1, .01, "Asymmetric point-like taper toward the sides."),
        P("asymmetry", "Asymmetry", .22, -1, 1, .01, "Offsets one side of the aperture envelope."),
        P("orientation", "Orientation", 0.0, -1, 1, .01, "Blend from horizontal rays to vertical rays."),
        P("phase", "Phase", 0.0, -1, 1, .01, "Phase offset for the ray pattern."),
        P("offset", "Pattern offset", 0.0, -1, 1, .01, "Slides the ray stack across the frame."),
        P("aperture_position", "Aperture position", 0.0, -1, 1, .01, "Moves the thick central aperture."),
        P("edge_softness", "Edge softness", .06, .005, .4, .005, "Softness of colored ray edges."),
        P("curvature", "Row curvature", .16, -1, 1, .01, "Bends each ray around its aperture."),
        P("row_drift", "Row drift", .08, 0, .5, .01, "Independent smooth drift for each ray."),
        P("irregularity", "Irregularity", .16, 0, 1, .01, "Uneven thickness and ray breaks."),
        P("magenta", "Magenta edge", .9, 0, 1, .01, "Colored edge around white rays."),
    )),
    Module("warp", "Independent warp", "Displaces rows and columns without temporal feedback.", (
        P("amount", "Warp amount", .035, 0, .25, .001, "Normalized displacement."),
        P("frequency", "Warp frequency", 3.2, .1, 16, .1, "Number of broad waves across the frame."),
        P("direction", "Direction", .35, -1, 1, .01, "Blend between horizontal and vertical displacement."),
        P("speed", "Warp speed", .7, 0, 4, .05, "Animation rate for this module."),
    )),
    Module("separation", "Color separation", "R/G/B registration offsets for a fractured signal edge.", (
        P("amount", "Separation", .018, 0, .15, .001, "Normalized channel displacement."),
        P("angle", "Angle", .15, -1, 1, .01, "Direction of the color split."),
        P("green", "Green restraint", .35, 0, 1, .01, "Keep green closer to the luminance core."),
    )),
    Module("smear", "Horizontal smear", "Stateless luminous trails extending from bright forms.", (
        P("amount", "Trail length", .12, 0, .7, .01, "Normalized horizontal trail length."),
        P("direction", "Direction", .2, -1, 1, .01, "Left/right balance of the trails."),
        P("ghosts", "Ghost count", 4, 1, 10, 1, "Number of shifted translucent copies", kind="int"),
    )),
    Module("bloom", "Bloom", "Soft overexposure around luminous regions.", (
        P("threshold", "Threshold", .42, 0, 1, .01, "Luminance threshold for glow."),
        P("radius", "Radius", 9.0, .5, 40, .5, "Blur radius in output pixels at reference size."),
        P("strength", "Strength", .55, 0, 2, .01, "Glow contribution."),
    )),
    Module("raster", "Raster + grain", "Scan lines, fine grain and restrained color noise.", (
        P("lines", "Scanline depth", .18, 0, .8, .01, "Darkness of alternating rows."),
        P("grain", "Fine grain", .08, 0, .5, .01, "Fine luminance grain."),
        P("chroma", "Chroma noise", .035, 0, .25, .005, "Small colored noise component."),
    )),
)
MODULE_BY_ID = {module.id: module for module in MODULES}


def _defaults(module: Module):
    return {param.key: param.default for param in module.params}


def default_synth_preset():
    return {
        "schema_version": SYNTH_SCHEMA_VERSION,
        "name": "Irregular blinds",
        "width": 720,
        "height": 576,
        "treatment_fps": 25,
        "export_fps": 25,
        "loop_seconds": 4.0,
        "seed": 2409,
        "speed": .55,
        "depth": .75,
        "variation_mode": "smooth",
        "animation": {
            "targets": {
                "blinds.aperture": {"depth": .18, "rate": .22},
                "blinds.aperture_position": {"depth": .16, "rate": .17},
                "blinds.curvature": {"depth": .22, "rate": .14},
                "slab.width": {"depth": .12, "rate": .12},
                "slab.spacing": {"depth": .08, "rate": .11},
            }
        },
        "modules": [
            {"id": module.id, "enabled": module.id in {"slab", "blinds", "warp", "separation", "smear", "bloom", "raster"}, "params": _defaults(module)}
            for module in MODULES
        ],
    }


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def normalize_synth(raw=None):
    """Validate/upgrade a synth preset while preserving unknown future modules."""
    base = default_synth_preset()
    if raw is None:
        return base
    if not isinstance(raw, dict):
        raise ValueError("Synth preset must be a JSON object")
    if int(raw.get("schema_version", 1)) != SYNTH_SCHEMA_VERSION:
        raise ValueError(f"Unsupported synth schema version: {raw.get('schema_version')}")
    result = copy.deepcopy(base)
    for key in ("name", "variation_mode"):
        if key in raw:
            result[key] = str(raw[key])
    for key, minimum, maximum in (("width", 64, 4096), ("height", 64, 4096), ("treatment_fps", 1, 120), ("export_fps", 1, 120), ("seed", 0, 2**31 - 1), ("speed", 0, 8), ("depth", 0, 1), ("loop_seconds", .1, 3600)):
        if key in raw:
            value = raw[key]
            if not _finite(value) or not minimum <= float(value) <= maximum:
                raise ValueError(f"{key} is outside the supported range")
            result[key] = int(value) if key in {"width", "height", "treatment_fps", "export_fps", "seed"} else float(value)
    if result["variation_mode"] not in {"smooth", "stepped"}:
        raise ValueError("variation_mode must be smooth or stepped")
    animation = raw.get("animation", result["animation"])
    if not isinstance(animation, dict) or not isinstance(animation.get("targets", {}), dict):
        raise ValueError("animation.targets must be an object")
    result["animation"] = {"targets": {}}
    for key, target in animation.get("targets", {}).items():
        if not isinstance(key, str) or not isinstance(target, dict):
            raise ValueError("Each animation target needs a key and object")
        depth = target.get("depth", 0)
        rate = target.get("rate", 1)
        if not _finite(depth) or not _finite(rate) or float(depth) < 0 or float(rate) < 0:
            raise ValueError(f"Invalid animation target: {key}")
        result["animation"]["targets"][key] = {"depth": float(depth), "rate": float(rate)}
    modules = raw.get("modules", result["modules"])
    if not isinstance(modules, list):
        raise ValueError("modules must be a list")
    result["modules"] = []
    for entry in modules:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Each module needs an id")
        module = MODULE_BY_ID.get(entry["id"])
        if module is None:
            # Unknown modules are retained for forward-compatible save/reload,
            # but skipped by the current renderer.
            result["modules"].append(copy.deepcopy(entry))
            continue
        params = _defaults(module)
        incoming = entry.get("params", {})
        if not isinstance(incoming, dict):
            raise ValueError(f"{module.id}.params must be an object")
        for spec in module.params:
            if spec.key not in incoming:
                continue
            value = incoming[spec.key]
            if not _finite(value):
                raise ValueError(f"{module.id}.{spec.key} must be finite")
            if spec.kind == "float" and not spec.minimum <= float(value) <= spec.maximum:
                raise ValueError(f"{module.id}.{spec.key} is outside the supported range")
            if spec.kind == "int" and not float(value).is_integer():
                raise ValueError(f"{module.id}.{spec.key} must be an integer")
            if spec.kind == "int" and not int(spec.minimum) <= int(value) <= int(spec.maximum):
                raise ValueError(f"{module.id}.{spec.key} is outside the supported range")
            params[spec.key] = int(value) if spec.kind == "int" else float(value)
        result["modules"].append({"id": module.id, "enabled": bool(entry.get("enabled", True)), "params": params})
    return result


def load_synth(path):
    return normalize_synth(json.loads(Path(path).read_text()))


def save_synth(path, preset):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize_synth(preset), indent=2) + "\n")


def _seed(seed, name, *parts):
    key = ":".join(map(str, ("nebula-synth-v1", seed, name, *parts))).encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "little")


def _smooth(seed, name, position, mode="smooth"):
    if mode == "stepped":
        position = math.floor(position)
    left = math.floor(position)
    fraction = position - left
    rng_a = random.Random(_seed(seed, name, left))
    a = rng_a.uniform(-1, 1)
    if mode == "stepped":
        return a
    b = random.Random(_seed(seed, name, left + 1)).uniform(-1, 1)
    eased = fraction * fraction * (3 - 2 * fraction)
    return a + (b - a) * eased


def _hsv(hue, saturation=1, value=1):
    h = (hue % 1) * 6
    i = int(h)
    f = h - i
    p, q, t = value * (1 - saturation), value * (1 - saturation * f), value * (1 - saturation * (1 - f))
    return np.array(((value, t, p), (q, value, p), (p, value, t), (p, q, value), (t, p, value), (value, p, q))[i], dtype=np.float32)


def _zero_roll(arr, shift, axis=1):
    out = np.zeros_like(arr)
    if shift == 0:
        return arr.copy()
    if axis == 1:
        if shift > 0:
            out[:, shift:] = arr[:, :-shift]
        else:
            out[:, :shift] = arr[:, -shift:]
    else:
        if shift > 0:
            out[shift:] = arr[:-shift]
        else:
            out[:shift] = arr[-shift:]
    return out


def _add(arr, mask, color):
    arr += mask[..., None] * color[None, None, :]


def _clock(preset, t):
    """Global animation clock: speed and depth both have visible meaning."""
    return float(t) * float(preset["speed"])


def _modulated(preset, module_id, key, value, t, minimum=None, maximum=None):
    target = preset.get("animation", {}).get("targets", {}).get(f"{module_id}.{key}")
    if not target or not preset.get("depth", 0):
        return value
    span = (float(maximum) - float(minimum)) if minimum is not None and maximum is not None else max(abs(float(value)), 1.0)
    noise = _smooth(preset["seed"], f"mod:{module_id}.{key}", _clock(preset, t) * target["rate"], preset["variation_mode"])
    result = float(value) + noise * target["depth"] * span * float(preset["depth"])
    if minimum is not None:
        result = max(float(minimum), result)
    if maximum is not None:
        result = min(float(maximum), result)
    return result


def _render_slab(arr, p, t, preset, module_index):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    xn = (x / max(1, w - 1)) * 2 - 1
    q = p
    clock = _clock(preset, t)
    wobble = _smooth(preset["seed"], "slab-shape", clock * .6, preset["variation_mode"]) * q["jitter"] * .18 * preset["depth"]
    count = int(q["count"])
    width = _modulated(preset, "slab", "width", q["width"], t, .02, .8)
    spacing = _modulated(preset, "slab", "spacing", q["spacing"], t, .02, 1)
    for index in range(count):
        center = (index - (count - 1) / 2) * spacing + wobble
        dist = np.abs(xn - center)
        core = np.exp(-((dist / max(.001, width / 2)) ** 8))
        edge = np.exp(-(((dist - width / 2) / max(.002, q["edge_softness"])) ** 2))
        color = _hsv(.88 + .06 * index, .08, 1.0)
        _add(arr, core, color)
        _add(arr, edge * q["magenta"], np.array((1.0, .04, .65), dtype=np.float32))
        fringe = np.exp(-(((dist - width * .72) / max(.003, q["edge_softness"] * 1.7)) ** 2))
        _add(arr, fringe * q["cyan"], np.array((.02, .55, .45), dtype=np.float32))


def _render_blinds(arr, p, t, preset, module_index):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    xn = (x / max(1, w - 1)) * 2 - 1
    yn = y / max(1, h - 1)
    clock = _clock(preset, t)
    base_hue = .86 + .03 * _smooth(preset["seed"], "blind-hue", clock, preset["variation_mode"])
    orientation = float(p.get("orientation", 0))
    theta = orientation * math.pi / 2
    yn2 = yn * 2 - 1
    u = xn * math.cos(theta) + yn2 * math.sin(theta)
    v = -xn * math.sin(theta) + yn2 * math.cos(theta)
    vn = (v + 1) / 2
    for row in range(int(p["rows"])):
        row_unit = (row + .5) / p["rows"]
        drift = _smooth(preset["seed"], "blind-row", row + clock * .65, preset["variation_mode"]) * p["row_drift"] * preset["depth"] / max(1, p["rows"])
        cy = row_unit + drift + p.get("offset", 0) * .25
        curvature = _modulated(preset, "blinds", "curvature", p["curvature"], t, -1, 1)
        bend = curvature * (u ** 2) * .18 * math.sin(clock + row * .71 + p.get("phase", 0) * math.pi) * preset["depth"]
        distance = np.abs(vn - cy - bend)
        aperture = _modulated(preset, "blinds", "aperture", p["aperture"], t, .03, .95)
        aperture_pos = _modulated(preset, "blinds", "aperture_position", p.get("aperture_position", 0), t, -1, 1)
        half_aperture = max(.01, aperture / 2)
        asym = p["asymmetry"] * .28 + aperture_pos * .45
        absu = np.abs(u - asym)
        # A shallow plateau creates the broad white patches; the outer ramp
        # preserves the pinched/tapered ends seen in the reference.
        shoulder = max(.01, half_aperture * .32)
        envelope = np.clip((half_aperture - absu) / shoulder, 0, 1)
        envelope = np.power(envelope, .72)
        taper = 1 - p["taper"] * (1 - envelope)
        local_thickness = p["thickness"] * (1 + p["swelling"] * envelope * (3.0 + .55 * _smooth(preset["seed"], "blind-bulk", row, preset["variation_mode"])))
        local_thickness *= np.clip(taper, .08, 1.2)
        irregular = 1 + p["irregularity"] * .18 * _smooth(preset["seed"], "blind-width", row + clock, preset["variation_mode"])
        edge_power = 2 + (1 - np.clip(p.get("edge_softness", .06) / .4, 0, 1)) * 6
        mask = np.exp(-((distance / np.maximum(.001, local_thickness * irregular)) ** edge_power))
        # Thin rays remain visible to the edges while the aperture holds a
        # near-rectangular bright section.
        mask *= .78 + .22 * envelope
        white = np.array((1.0, .94, .9), dtype=np.float32)
        _add(arr, mask, white)
        edge = np.exp(-((distance / np.maximum(.001, local_thickness * 1.8)) ** 2)) - mask * .7
        edge *= np.clip(.35 + envelope, 0, 1) * (1 + p.get("edge_softness", .06) * 2)
        edge = np.clip(edge, 0, 1) * p["magenta"]
        color = _hsv(base_hue + .015 * row, .82, .8)
        _add(arr, edge, color)


def _warp(arr, p, t, preset):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    phase = _clock(preset, t) * p["speed"]
    direction = p["direction"]
    dx = p["amount"] * w * (np.sin(y / max(1, h - 1) * math.tau * p["frequency"] + phase) * (1 - abs(direction)) + direction * np.sin(x / max(1, w - 1) * math.tau * p["frequency"] + phase * .73))
    dy = p["amount"] * h * (.35 * np.sin(x / max(1, w - 1) * math.tau * p["frequency"] + phase * .51))
    xs = np.clip(np.rint(x - dx).astype(int), 0, w - 1)
    ys = np.clip(np.rint(y - dy).astype(int), 0, h - 1)
    return arr[ys, xs]


def _separate(arr, p, t, preset):
    h, w = arr.shape[:2]
    shift = int(p["amount"] * w)
    angle = p["angle"]
    horizontal = int(shift * math.cos(angle * math.pi / 2))
    vertical = int(shift * math.sin(angle * math.pi / 2))
    out = arr.copy()
    out[..., 0] = _zero_roll(arr[..., 0], horizontal, 1)
    out[..., 2] = _zero_roll(arr[..., 2], -horizontal, 1)
    if vertical:
        out[..., 0] = _zero_roll(out[..., 0], vertical, 0)
        out[..., 2] = _zero_roll(out[..., 2], -vertical, 0)
    # Green restraint is a real registration control: at 1 it stays put; at 0
    # it follows the chromatic displacement halfway.
    green_shift = int(horizontal * (1 - p["green"]) * .5)
    out[..., 1] = _zero_roll(arr[..., 1], green_shift, 1)
    return out


def _smear(arr, p):
    if p["amount"] <= 0:
        return arr.copy()
    h, w = arr.shape[:2]
    out = arr.copy()
    ghosts = int(p["ghosts"])
    direction = 1 if p["direction"] >= 0 else -1
    for index in range(1, ghosts + 1):
        shift = direction * int(p["amount"] * w * index / ghosts)
        if shift:
            out += _zero_roll(arr, shift, 1) * (.22 / index)
    return out


def _bloom(arr, p):
    image = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")
    lum = np.asarray(image.convert("L"), dtype=np.float32) / 255
    mask = np.clip((lum - p["threshold"]) / max(.001, 1 - p["threshold"]), 0, 1)
    bright = np.asarray(image, dtype=np.float32) * mask[..., None]
    blurred = np.asarray(Image.fromarray(np.clip(bright, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(p["radius"])), dtype=np.float32) / 255
    return arr + blurred * p["strength"]


def _raster(arr, p, seed, treatment_frame):
    h, w = arr.shape[:2]
    result = arr.copy()
    result[::2] *= 1 - p["lines"]
    rng = np.random.default_rng(_seed(seed, "raster", treatment_frame))
    luminance = np.mean(result, axis=2, keepdims=True)
    result += rng.normal(0, p["grain"], result.shape).astype(np.float32) * np.sqrt(np.clip(luminance, 0, 1))
    chroma = rng.normal(0, p["chroma"], (h, w, 1)).astype(np.float32)
    result[..., 0] += chroma[..., 0]
    result[..., 2] -= chroma[..., 0]
    return result


RENDERERS = {
    "slab": lambda arr, params, t, preset, index: _render_slab(arr, params, t, preset, index),
    "blinds": lambda arr, params, t, preset, index: _render_blinds(arr, params, t, preset, index),
    "warp": lambda arr, params, t, preset, index: _warp(arr, params, t, preset),
    "separation": lambda arr, params, t, preset, index: _separate(arr, params, t, preset),
    "smear": lambda arr, params, t, preset, index: _smear(arr, params),
    "bloom": lambda arr, params, t, preset, index: _bloom(arr, params),
    "raster": lambda arr, params, t, preset, index: _raster(arr, params, preset["seed"], round(t * preset["treatment_fps"])),
}


def render_synth_frame(preset, frame=0, time_seconds=None, size=None):
    """Render one frame at continuous time; `frame` is only a default clock."""
    p = normalize_synth(preset)
    width, height = size or (p["width"], p["height"])
    t = frame / p["treatment_fps"] if time_seconds is None else float(time_seconds)
    # The treatment rate is a real hold rate for the complete image, not only
    # for grain. This keeps preview, scrub and export identical at any FPS.
    t = math.floor(t * p["treatment_fps"] + 1e-9) / p["treatment_fps"]
    arr = np.zeros((height, width, 3), dtype=np.float32)
    # A gentle green-black ground keeps overexposed forms anchored like the reference.
    arr[..., 1] = .004
    arr[..., 2] = .006
    treatment_frame = round(t * p["treatment_fps"])
    for index, entry in enumerate(p["modules"]):
        if not entry.get("enabled", True):
            continue
        module_id = entry.get("id")
        renderer = RENDERERS.get(module_id)
        if renderer is None:
            continue
        params = entry.get("params", {})
        rendered = renderer(arr, params, t, p, index)
        if rendered is not None:
            arr = rendered
    return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")


def curated_presets():
    base = default_synth_preset()
    slab = copy.deepcopy(base)
    slab["name"] = "Luminous slab"
    for item in slab["modules"]:
        item["enabled"] = item["id"] in {"slab", "separation", "smear", "bloom", "raster"}
    slab["speed"], slab["seed"] = .28, 1101
    blinds = copy.deepcopy(base)
    blinds["name"] = "Reference blinds"
    for item in blinds["modules"]:
        item["enabled"] = item["id"] in {"blinds", "warp", "separation", "smear", "bloom", "raster"}
    blinds["seed"] = 2409
    for item in blinds["modules"]:
        if item["id"] == "warp":
            item["params"].update({"amount": .018, "frequency": 2.4})
        elif item["id"] == "separation":
            item["params"].update({"amount": .009, "green": .7})
        elif item["id"] == "smear":
            item["params"].update({"amount": .06, "ghosts": 3})
    unstable = copy.deepcopy(blinds)
    unstable["name"] = "Unstable aperture"
    unstable["speed"], unstable["depth"], unstable["seed"] = 1.3, 1, 7117
    for item in unstable["modules"]:
        if item["id"] == "blinds":
            item["params"].update({"irregularity": .55, "row_drift": .22, "curvature": .48, "taper": .94, "swelling": 1})
        elif item["id"] == "warp":
            item["params"].update({"amount": .1, "frequency": 5.5, "speed": 1.8})
        elif item["id"] == "separation":
            item["params"]["amount"] = .05
    return {item["name"]: normalize_synth(item) for item in (slab, blinds, unstable)}
