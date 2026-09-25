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

from synth_particles import render_particles
from synth_tape import render_tape_damage

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
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Module:
    id: str
    label: str
    description: str
    params: tuple[Param, ...]


def P(key, label, default, minimum=0, maximum=1, step=.01, hint="", kind=None, choices=()):
    if kind is None:
        integer_bounds = float(minimum).is_integer() and float(maximum).is_integer()
        kind = "int" if isinstance(default, int) and not isinstance(default, bool) and step == 1 and integer_bounds else "float"
    if kind == "int":
        step = 1
    return Param(key, label, default, minimum, maximum, step, kind=kind, hint=hint, choices=choices)


SHAPES = ("Rectangle", "Ellipse", "Circle", "Polygon")


def geometry_params():
    return (
        P("shape", "Shape", 0, 0, 3, 1, "Geometry of the luminous source or ray aperture.", choices=SHAPES),
        P("diameter", "Diameter", .6, .05, 1.5, .01, "Circle / polygon diameter as a fraction of image height."),
        P("sides", "Polygon sides", 6, 3, 32, 1, "Number of sides of the regular polygon."),
        P("rotation", "Rotation", 0.0, -180, 180, 1, "Rotation in degrees around the source centre."),
    )


MODULES = (
    Module("slab", "Luminous slabs", "Vertical luminous sources with white cores and colored edges.", (
        *geometry_params(),
        P("count", "Slab count", 1, 1, 5, 1, "Number of vertical sources."),
        P("width", "Core width", .18, .02, .8, .01, "Width of the bright central aperture."),
        P("spacing", "Spacing", .22, .02, 1, .01, "Distance between slab centers."),
        P("height", "Height", .62, .08, 1, .01, "Finite vertical extent of the slab."),
        P("position_x", "Horizontal position", .2, -1, 1, .01, "Moves the slab across the frame."),
        P("position_y", "Vertical position", 0, -1, 1, .01, "Moves the slab up or down."),
        P("edge_hardness", "Edge hardness", .82, 0, 1, .01, "Hard rectangular edge versus soft glow."),
        P("hollow", "Hollow centre", 0, 0, 1, .01, "Cuts a dark channel through the luminous core."),
        P("notch", "Missing chunks", .08, 0, 1, .01, "Adds deterministic interruptions to the block."),
        P("intensity", "Core intensity", 1.0, .1, 1.5, .01, "Brightness of the white slab body."),
        P("fill_magenta", "Magenta fill", 0.0, 0, 1, .01, "Moves the slab body from neutral white toward violet-magenta."),
        P("fill_gradient", "Split fill", 0.0, 0, 1, .01, "Concentrates the magenta fill on the left, leaving a white right core."),
        P("vertical_tint", "Blue falloff", 0.0, 0, 1, .01, "Fades a warm upper core into blue-violet at the bottom."),
        P("ghost_width", "Ghost width", .32, .05, 1, .01, "Width of the dimmer right-hand ghost."),
        P("ghost_offset", "Ghost offset", .24, .02, .8, .01, "Distance of the secondary ghost to the right."),
        P("ghost_opacity", "Ghost opacity", .34, 0, 1, .01, "Strength of the secondary ghost."),
        P("edge_softness", "Edge softness", .08, .005, .35, .005, "Soft luminous edge falloff."),
        P("magenta", "Magenta edge", .85, 0, 1, .01, "Purple/magenta channel strength."),
        P("cyan", "Cyan fringe", .42, 0, 1, .01, "Green/cyan channel fringe strength."),
        P("jitter", "Shape irregularity", .12, 0, .5, .01, "Slow shape wobble; does not randomize every frame."),
        P("frame_jitter", "Frame registration", 0.0, 0, .04, .001, "Small independent horizontal registration changes at the treatment rate."),
        P("edge_ripple", "Edge flutter", 0.0, 0, .04, .001, "Uneven horizontal registration across groups of scan lines."),
        P("ghost_grain", "Ghost grain", 0.0, 0, 1, .01, "Breaks the secondary block into fine signal noise."),
        P("cloud_strength", "Signal cloud", 0.0, 0, 1, .01, "Local noisy halo surrounding the block."),
        P("cloud_tint", "Cloud violet", .8, 0, 1, .01, "Blends gray-green signal noise toward violet."),
        P("cloud_position", "Cloud vertical offset", 0.0, -1, 1, .01, "Moves the noisy halo above or below the block."),
        P("cloud_detail", "Cloud granulation", 0.0, 0, 1, .01, "Clumped signal noise that survives softness, including in the ghost."),
    )),
    Module("blinds", "Irregular Venetian blinds", "Horizontal rays that swell into an asymmetric central aperture.", (
        *geometry_params(),
        P("rows", "Ray count", 9, 1, 32, 1, "Number of horizontal rays", kind="int"),
        P("thickness", "Ray thickness", .012, .002, .12, .001, "Thickness of the thin outer rays."),
        P("aperture", "Aperture width", .34, .03, .95, .01, "Width of the thick central region."),
        P("aperture_height", "Aperture height", .64, .10, 1, .01, "Vertical window for thickening the rays."),
        P("aperture_vertical", "Aperture vertical", 0.0, -1, 1, .01, "Moves the thickening window up or down."),
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
        P("intensity", "Ray intensity", 1.0, .1, 1.5, .01, "Brightness of the white rays and their colored edges."),
        P("tail_spread", "Soft ray tails", 0.0, 0, 1, .01, "Broadens the tapered shoulders outside the central aperture."),
        P("edge_bias", "Colored tail balance", 0.0, -1, 1, .01, "Moves the colored ray fringe toward the left or right tail."),
    )),
    Module("particles", "Particle attractor", "Dots assemble around an invisible 3D surface, then disperse.", (
        P("attractor", "Attractor", 0, 0, 4, 1, "Portrait head adds smooth facial geometry and eye surfaces. Use Surface occlusion to keep the face readable. Only particles are rendered.", choices=("Stylized head", "Sphere", "Ring", "Human head", "Portrait head")),
        P("motion", "Motion", 0, 0, 2, 1, "Gentle drifts; Surges adds uneven arrivals and rebound. Impulse separates quick, peaked moves from longer holds.", choices=("Gentle", "Surges", "Impulse")),
        P("release", "Release", 0, 0, 1, 1, "Cloud / band retains the original dispersion. Expand / orbit releases in every direction, then revolves around the vertical axis.", choices=("Cloud / band", "Expand / orbit")),
        P("assembly", "Assembly", 1.0, 0, 1, .01, "0 = dispersed field; 1 = assembled surface. Breathing animates below this ceiling."),
        P("breathing", "Assembly cycle", 1.0, 0, 1, .01, "Depth of automatic assembly / release. Set to 0 to hold Assembly fixed."),
        P("period", "Cycle seconds", 12.0, .5, 120, .5, "One assembly / release cycle at global speed 1."),
        P("expand_seconds", "Expansion seconds", .75, .1, 5, .05, "Impulse: duration of the outward move, independent of Cycle seconds. Capped at a quarter cycle."),
        P("gather_seconds", "Gather seconds", 1.0, .1, 5, .05, "Impulse: duration of the return to the surface. Capped at a fifth of the cycle."),
        P("motion_peak", "Motion peak", .8, 0, 1, .01, "Impulse: 0 is linear; higher values concentrate velocity into a narrow peak, easing into and out of the move."),
        P("orbit_speed", "Orbit degrees / sec", 20.0, -90, 90, .5, "Expand / orbit: speed of the released cloud. Negative values reverse direction; separate from Head turn."),
        P("orbit_start", "Orbit after expansion", .7, 0, .95, .01, "Expand / orbit: fraction of release before rotation eases in. .7 waits until roughly 70% expanded."),
        P("acceleration", "Acceleration", .8, 0, 1, .01, "Surges: particles hesitate, accelerate sharply, then settle."),
        P("chaos", "Arrival disorder", .7, 0, 1, .01, "Bend and stagger particle paths. Surges also varies cycle timing; Impulse keeps the cycle exact with a small stagger."),
        P("overshoot", "Overshoot", .45, 0, 1, .01, "Surges: pass through the target and rebound before settling."),
        P("count", "Particle count", 22000, 200, 60000, 100, "More points create a denser signal field.", kind="int"),
        P("dot_size", "Dot size", 1.2, .5, 6, .1, "Soft dot radius at 576-pixel image height."),
        P("dispersion", "Dispersion", 1.0, 0, 2, .01, "Spread of released particles around the attractor."),
        P("turbulence", "Turbulence", .18, 0, 1, .01, "Continuous wandering, stronger away from the surface."),
        P("collapse", "Collapse to band", .0, 0, 1, .01, "Cloud / band release only: dots compress toward a low horizontal band."),
        P("flow", "Flow speed", .7, 0, 4, .05, "Rate of the continuous turbulent field."),
        P("phase", "Cycle phase", 0.0, 0, 1, .01, "Move the assembly cycle forward. Impulse starts assembled at 0; Gentle / Surges near .5."),
        P("yaw", "Head turn", -20.0, -180, 180, 1, "Starting rotation around the vertical axis."),
        P("pitch", "Tilt", 0.0, -90, 90, 1, "Tilt the entire 3D field."),
        P("rotation_speed", "Turn degrees / sec", 4.0, -90, 90, .5, "Continuous rotation at global speed 1; 0 holds the view."),
        P("scale", "Scale", 1.0, .2, 2, .01, "Size of the attractor in the image."),
        P("position_x", "Horizontal position", 0.0, -1, 1, .01),
        P("position_y", "Vertical position", 0.0, -1, 1, .01),
        P("perspective", "Perspective", .65, 0, 1, .01, "0 = orthographic; 1 = stronger depth foreshortening."),
        P("xray", "See-through", .08, 0, 1, .01, "Visibility of the back surface through the front dots."),
        P("occlusion", "Surface occlusion", 0.0, 0, 1, .01, "Hide deeper dots behind the assembled face, preventing the mouth interior and back of the head from shining through. Fades away during expansion."),
        P("relief", "Surface relief", .85, 0, 1, .01, "Directional point brightness reveals the nose, eyes and mouth; no solid surface is drawn."),
        P("intensity", "Intensity", 1.35, 0, 3, .01),
        P("released_brightness", "Released brightness", 1.0, 0, 1, .01, "Dim loose particles while retaining bright dots on the assembled surface."),
        P("hue", "Hue", .76, 0, 1, .01, "Color of the central band; 0 = red, .33 = green, .67 = blue."),
        P("saturation", "Saturation", .65, 0, 1, .01),
        P("color_spread", "Spectral spread", .85, 0, 2, .01, "Different colors along the vertical volume."),
        P("color_drift", "Color drift", .025, 0, .5, .005, "Slow color circulation per second."),
        P("shimmer", "Shimmer", .45, 0, 1, .01, "Per-dot brightness fluctuation, independent of its trajectory."),
        P("jitter", "Scan registration", .0015, 0, .02, .0005, "Small held shifts across scan lines."),
    )),
    Module("flare", "Signal flare", "An asymmetric horizontal exposure sweep around the source.", (
        P("strength", "Exposure", 0.0, 0, 3, .01, "Adds a clipped white signal flare."),
        P("position_y", "Vertical position", .5, 0, 1, .01, "Centre of the horizontal sweep."),
        P("position_x", "Horizontal centre", .62, 0, 1, .01, "Strongest part of the exposure."),
        P("spread", "Vertical spread", .25, .02, 2, .01, "From a narrow horizontal burst to full-frame exposure."),
        P("reach", "Horizontal reach", .4, .05, 2, .01, "Width of the flare around its centre."),
        P("fringe", "Violet fringe", .2, 0, 1, .01, "Violet noise around the exposure boundary."),
        P("asymmetry", "Uneven exposure", 0.0, -1, 1, .01, "Different falloff above and below the exposure crest."),
        P("bend", "Exposure bend", 0.0, -1, 1, .01, "Bends the crest away from the brightest part of the source."),
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
    Module("interference", "Signal interference", "Moving chromatic bands and a bent vertical scan comb across the sources.", (
        P("chroma", "Chromatic bands", .65, 0, 1, .01, "Mix broad moving violet, green and blue interference into the signal."),
        P("bands", "Band count", 7.0, 1, 24, .25),
        P("depth", "Band contrast", .45, 0, 1, .01, "Uneven exposure between horizontal bands."),
        P("bend", "Band bending", .3, 0, 1, .01),
        P("comb", "Vertical comb", .35, 0, 1, .01, "Broken vertical strings within the signal."),
        P("speed", "Signal speed", 1.0, 0, 6, .05),
        P("columns", "Comb columns", 130, 20, 320, 1),
        P("mix", "Mix", 1.0, 0, 1, .01),
    )),
    Module("bloom", "Bloom", "Soft overexposure around luminous regions.", (
        P("threshold", "Threshold", .42, 0, 1, .01, "Luminance threshold for glow."),
        P("radius", "Radius", 9.0, .5, 40, .5, "Blur radius in output pixels at reference size."),
        P("strength", "Strength", .55, 0, 2, .01, "Glow contribution."),
    )),
    Module("raster", "Raster + grain", "Scan lines, fine grain and restrained color noise.", (
        P("softness", "Signal softness", 0.0, 0, 5, .1, "Softens the signal before grain; radius at 720-pixel width."),
        P("lines", "Scanline depth", .18, 0, .8, .01, "Darkness of alternating rows."),
        P("grain", "Fine grain", .08, 0, .5, .01, "Fine luminance grain."),
        P("chroma", "Chroma noise", .035, 0, .25, .005, "Small colored noise component."),
        P("line_noise", "Horizontal grain", 0.0, 0, .5, .01, "Correlated signal grain along short horizontal streaks."),
    )),
    Module("breakup", "Signal breakup", "Held horizontal tears and dropouts across the combined image.", (
        P("amount", "Horizontal tear", .08, 0, .5, .01, "Maximum horizontal displacement as a fraction of image width."),
        P("bands", "Bands", 18, 1, 96, 1, "Number of independently displaced horizontal bands."),
        P("dropout", "Dropouts", .12, 0, 1, .01, "Probability of a band losing its signal."),
        P("rate", "Changes per second", 8.0, 0, 60, .5, "Hold rate of the tears; zero freezes the pattern."),
        P("mix", "Mix", .75, 0, 1, .01, "Blend the broken signal with the original."),
    )),
    Module("tape", "Tape damage", "Tracking slips, chroma smear and lost scanlines within the existing image.", (
        P("tracking", "Tracking slip", .04, 0, .3, .002, "Horizontal displacement of short irregular scan regions."),
        P("jitter", "Line jitter", .001, 0, .02, .0005, "Small independent scanline timing errors."),
        P("dropouts", "Dropouts", .3, 0, 1, .01, "Short missing stretches of the recorded image."),
        P("chroma_delay", "Chroma delay", .006, 0, .08, .001, "Delay color relative to luminance, measured as a fraction of image width."),
        P("bleed", "Color bleed", .008, 0, .12, .001, "Smear the source's own color horizontally."),
        P("head_switch", "Head-switch error", .25, 0, 1, .01, "Distort and darken the bottom edge as the tape head changes."),
        P("rate", "Fault changes / sec", 16.0, 0, 60, .5, "Held fault rate at global speed 1; zero freezes the pattern."),
        P("mix", "Mix", .8, 0, 1, .01, "Blend tape faults with the original signal."),
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


def _signal_noise(seed, name, frame, size, grid):
    """A reference-sized noise field keeps its physical scale in the preview."""
    rng = np.random.default_rng(_seed(seed, name, frame))
    noise = rng.normal(size=(grid[1], grid[0])).astype(np.float32)
    return np.asarray(Image.fromarray(noise).resize(size, Image.Resampling.BILINEAR))


def _shape_distance(dx, dy, rx, ry, shape, sides=6, rotation=0, aspect=1):
    """Signed contour distance; rotate in image pixels before normalizing axes."""
    angle = math.radians(rotation)
    x = dx * aspect
    u = (x * math.cos(angle) + dy * math.sin(angle)) / (rx * aspect)
    v = (-x * math.sin(angle) + dy * math.cos(angle)) / ry
    if shape == 0:
        distance = np.maximum(np.abs(u), np.abs(v)) - 1
    elif shape in (1, 2):
        distance = np.hypot(u, v) - 1
    else:
        sector = math.tau / sides
        angle = (np.arctan2(v, u) + math.pi / 2) % sector - sector / 2
        distance = np.hypot(u, v) * np.cos(angle) - math.cos(math.pi / sides)
    return distance * min(rx, ry), u, v


def _render_slab(arr, p, t, preset, module_index):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    xn = (x / max(1, w - 1)) * 2 - 1
    yn = (y / max(1, h - 1)) * 2 - 1
    q = p
    clock = _clock(preset, t)
    frame_clock = round(t * preset["treatment_fps"])
    rng = np.random.default_rng(_seed(preset["seed"], "slab-signal", frame_clock))
    registration = p.get("frame_jitter", 0)
    xn = xn + registration * (rng.normal(0, .25) + .12 * rng.normal(size=(h, 1)))
    if p.get("edge_ripple", 0) > 0:
        ripple = _signal_noise(preset["seed"], "slab-edge", round(t * preset["treatment_fps"]), (1, h), (1, 144))
        xn = xn + ripple * p["edge_ripple"]
    wobble = _smooth(preset["seed"], "slab-shape", clock * .6, preset["variation_mode"]) * q["jitter"] * .18 * preset["depth"]
    count = int(q["count"])
    width = _modulated(preset, "slab", "width", q["width"], t, .02, .8)
    spacing = _modulated(preset, "slab", "spacing", q["spacing"], t, .02, 1)
    vertical_center = float(p.get("position_y", 0)) + .08 * _smooth(preset["seed"], "slab-y", clock * .4, preset["variation_mode"]) * preset["depth"]
    half_height = max(.02, float(p.get("height", .62)))
    shape = int(p.get("shape", 0))
    shaped = shape != 0 or p.get("rotation", 0) != 0
    aspect = w / h
    if shape in (2, 3):
        half_height = p["diameter"]
        width = 2 * half_height / aspect
    vertical_distance = np.abs(yn - vertical_center)
    vertical_mask = np.clip((half_height - vertical_distance) / max(.004, (1 - p["edge_hardness"]) * .10), 0, 1)
    for index in range(count):
        center = float(p.get("position_x", .2)) + (index - (count - 1) / 2) * spacing + wobble
        dist = np.abs(xn - center)
        frame_clock = round(t * preset["treatment_fps"])
        fast_signal = _smooth(preset["seed"], "slab-fill", frame_clock + index * .17, "stepped")
        fill_flicker = .62 + .36 * (fast_signal + 1) / 2
        core = np.clip((width / 2 - dist) / max(.002, q["edge_softness"]), 0, 1) * vertical_mask
        if shaped:
            distance, u, v = _shape_distance(xn - center, yn - vertical_center, width / 2, half_height, shape, p["sides"], p["rotation"], aspect)
            core = np.clip(-distance / max(.002, q["edge_softness"]), 0, 1)
        notch_center = vertical_center + _smooth(preset["seed"], "slab-notch", index + frame_clock, "stepped") * half_height
        # Rectangular bites remove the right side of the body while leaving a
        # narrow vertical stem, which produces the L/T fragments in the study.
        cut_region = ((xn - center) > -width * .30) & (np.abs(yn - notch_center) < half_height * .65)
        if shaped:
            cut_region = (u > -.6) & (np.abs(v - (notch_center - vertical_center) / half_height) < .65)
        notch_probability = float(p.get("notch", 0))
        cut_active = 1.0 if fast_signal < (2 * notch_probability - 1) else 0.0
        core *= 1 - cut_active * cut_region
        hollow = float(p.get("hollow", 0))
        if shaped:
            core *= 1 - hollow * np.clip((-distance - q["edge_softness"] * 1.5) / max(.002, min(width / 2, half_height) * .12), 0, 1)
        else:
            core *= 1 - hollow * np.exp(-((dist / max(.001, width * .25)) ** 8))
        edge = np.exp(-(((xn - center + width / 2) / max(.002, q["edge_softness"])) ** 2)) * vertical_mask
        if shaped:
            edge = np.exp(-(distance / max(.002, q["edge_softness"])) ** 2) * np.clip(.5 - u * .5, 0, 1)
        fill_magenta = float(p.get("fill_magenta", 0.0))
        color = (1.0 - fill_magenta) * np.array((.95, .965, .94), dtype=np.float32) + fill_magenta * np.array((.76, .26, .91), dtype=np.float32)
        if p.get("fill_gradient", 0) > 0:
            split_fill = np.clip((center + width * .18 - xn) / max(.001, width * .20), 0, 1)
            tint = fill_magenta * ((1 - p["fill_gradient"]) + p["fill_gradient"] * split_fill)
            color = (1 - tint[..., None]) * np.array((.95, .965, .94)) + tint[..., None] * np.array((.90, .32, 1.0))
        if p.get("vertical_tint", 0) > 0:
            gradient = np.clip((yn - vertical_center + half_height) / (2 * half_height), 0, 1)
            warm = np.array((.78, .57, .59)); cool = np.array((.34, .22, .75))
            gradient_color = warm + gradient[..., None] * (cool - warm)
            color = color * (1 - p["vertical_tint"]) + gradient_color * p["vertical_tint"]
        if np.ndim(color) > 1:
            arr += (core * fill_flicker * p["intensity"])[..., None] * color
        else:
            _add(arr, core * fill_flicker * p["intensity"], color)
        edge_color = np.array((.78, .02, .65), dtype=np.float32)
        if p.get("vertical_tint", 0) > 0:
            edge_color = edge_color * (1 - p["vertical_tint"]) + np.array((.95, .38, .12)) * p["vertical_tint"]
        _add(arr, edge * q["magenta"] * p["intensity"], edge_color)
        fringe = np.exp(-(((dist - width * .72) / max(.003, q["edge_softness"] * 1.7)) ** 2)) * vertical_mask
        if shaped:
            fringe = np.exp(-((distance - q["edge_softness"]) / max(.003, q["edge_softness"] * 1.7)) ** 2) * np.clip(.5 + u * .5, 0, 1)
        _add(arr, fringe * q["cyan"], np.array((.02, .55, .45), dtype=np.float32))
        ghost_offset = float(p.get("ghost_offset", .24))
        ghost_width = max(.02, width * float(p.get("ghost_width", .32)))
        ghost_dist = np.abs(xn - center - ghost_offset)
        ghost = np.clip((ghost_width - ghost_dist) / max(.006, q["edge_softness"]), 0, 1) * vertical_mask
        if shaped:
            ghost_distance, _, _ = _shape_distance(xn - center - ghost_offset, yn - vertical_center, ghost_width, half_height, shape, p["sides"], p["rotation"], aspect)
            ghost = np.clip(-ghost_distance / max(.006, q["edge_softness"]), 0, 1)
        ghost *= float(p.get("ghost_opacity", .34)) * (.78 + .22 * _smooth(preset["seed"], "slab-ghost", round(t * preset["treatment_fps"]) + index, preset["variation_mode"]))
        ghost *= 1 - cut_active * .90 * (yn > notch_center)
        ghost *= (1 - p.get("ghost_grain", 0)) + p.get("ghost_grain", 0) * np.clip(rng.normal(.65, .52, (h, w)), 0, 1)
        detail = p.get("cloud_detail", 0)
        if detail > 0:
            signal = _signal_noise(preset["seed"], f"slab-cloud-{index}", frame_clock, (w, h), (360, 288))
            patches = _signal_noise(preset["seed"], f"slab-density-{index}", frame_clock, (w, h), (18, 16))
            granules = np.clip(signal * 1.3 - .12, 0, 1.8)
            density = np.clip(.7 + patches * .35, .4, 1.1)
            ghost *= (1 - detail) + detail * np.clip(.8 + signal * 1.2, 0, 1.5)
        _add(arr, ghost * float(p.get("intensity", 1.0)), np.array((.68, .66, .70), dtype=np.float32))
        if p.get("cloud_strength", 0) > 0:
            # Noise lives around the source, with a broad halo and uneven
            # signal density; it does not lift the whole background uniformly.
            cloud_mask = np.exp(-((xn - center) / (width * 1.4)) ** 2 - ((yn - vertical_center - p.get("cloud_position", 0)) / (half_height * 1.2)) ** 4)
            if shaped:
                cloud_distance, cloud_u, _ = _shape_distance(xn - center, yn - vertical_center - p.get("cloud_position", 0), width / 2, half_height, shape, p["sides"], p["rotation"], aspect)
                cloud_mask = np.exp(-(cloud_distance / max(.01, min(width / 2, half_height) * .5)) ** 2) * np.clip(.65 - cloud_u * .35, .15, 1)
            cloud = np.clip(rng.normal(.14, .30, (h, w)), 0, 1) * cloud_mask
            if detail > 0:
                # Concentrate the granular spill at the left edge and above
                # the block, leaving the right-hand ghost legible.
                halo_y = yn - vertical_center - p.get("cloud_position", 0)
                halo = np.exp(-((xn - center + width * .45) / (width * .55)) ** 2 - (halo_y / (half_height * 1.25)) ** 4)
                cap = np.exp(-((xn - center + width * .1) / (width * .8)) ** 2 - ((halo_y + half_height) / .22) ** 2)
                halo_mask = cloud_mask if shaped else np.maximum(halo, cap)
                cloud = cloud * (1 - detail) + granules * density * halo_mask * detail
            tint = p.get("cloud_tint", .8)
            cloud_color = (1 - tint) * np.array((.72, .82, .69)) + tint * np.array((.60, .08, .95))
            _add(arr, cloud * p["cloud_strength"], cloud_color)


def _render_blinds(arr, p, t, preset, module_index):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    xn = (x / max(1, w - 1)) * 2 - 1
    yn = y / max(1, h - 1)
    clock = _clock(preset, t)
    base_hue = .76 + .025 * _smooth(preset["seed"], "blind-hue", clock, preset["variation_mode"])
    orientation = float(p.get("orientation", 0))
    theta = orientation * math.pi / 2
    yn2 = yn * 2 - 1
    u = xn * math.cos(theta) + yn2 * math.sin(theta)
    v = -xn * math.sin(theta) + yn2 * math.cos(theta)
    vn = (v + 1) / 2
    shaped_envelope = None
    for row in range(int(p["rows"])):
        row_unit = (row + .5) / p["rows"]
        drift = _smooth(preset["seed"], "blind-row", row + clock * .65, preset["variation_mode"]) * p["row_drift"] * preset["depth"] / max(1, p["rows"])
        cy = row_unit + drift + p.get("offset", 0) * .25
        curvature = _modulated(preset, "blinds", "curvature", p["curvature"], t, -1, 1)
        bend = curvature * (u ** 2) * .18 * math.sin(clock + row * .71 + p.get("phase", 0) * math.pi) * preset["depth"]
        distance = np.abs(vn - cy - bend)
        aperture = _modulated(preset, "blinds", "aperture", p["aperture"], t, .03, .95)
        aperture_pos = _modulated(preset, "blinds", "aperture_position", p.get("aperture_position", 0), t, -1, 1)
        # `aperture` is expressed as a frame-width fraction. Coordinates are
        # in [-1, 1], so its half-width is close to the fraction itself.
        half_aperture = max(.01, aperture * .9)
        asym = p["asymmetry"] * .28 + aperture_pos * .45
        absu = np.abs(u - asym)
        # A shallow plateau creates the broad white patches; the outer ramp
        # preserves the pinched/tapered ends seen in the reference.
        shoulder = max(.01, half_aperture * (.12 + p["taper"] * .24))
        envelope = np.clip((half_aperture - absu) / shoulder, 0, 1)
        envelope = np.power(envelope, .72)
        vertical_center = .5 + float(p.get("aperture_vertical", 0)) * .35
        vertical_half = max(.04, float(p.get("aperture_height", .64)) / 2)
        vertical_window = np.clip((vertical_half - np.abs(vn - vertical_center)) / max(.02, vertical_half * .22), 0, 1)
        vertical_window = np.power(vertical_window, .65)
        envelope *= vertical_window
        shape = int(p.get("shape", 0))
        if shape != 0 or p.get("rotation", 0) != 0:
            if shaped_envelope is None:
                rx, ry = half_aperture, vertical_half * 2
                if shape in (2, 3):
                    rx, ry = p["diameter"] * h / w, p["diameter"]
                # Place the aperture in image space so rotating the ray stack
                # cannot stretch a circle on a non-square canvas.
                aperture_y = (vertical_center - .5) * 2
                center_x = asym * math.cos(theta) - aperture_y * math.sin(theta)
                center_y = asym * math.sin(theta) + aperture_y * math.cos(theta)
                aperture_distance, _, _ = _shape_distance(xn - center_x, yn2 - center_y, rx, ry, shape, p["sides"], p["rotation"] + math.degrees(theta), w / h)
                shaped_envelope = np.clip(-aperture_distance / max(.005, min(rx, ry) * (.12 + p["taper"] * .24)), 0, 1) ** .72
            envelope = shaped_envelope
        taper = 1 - p["taper"] * (1 - envelope)
        outer = p["thickness"] * .4 + .12 / (p["rows"] ** 2 + 1) * np.exp(-((u - asym) / .96) ** 2)
        if p.get("tail_spread", 0) > 0:
            outer += p["tail_spread"] * .07 / p["rows"] * np.exp(-((u - asym) / .7) ** 2)
        local_thickness = outer * np.clip(taper, .35, 1.2) + p["swelling"] * envelope * .36 / p["rows"]
        irregular = 1 + p["irregularity"] * .18 * _smooth(preset["seed"], "blind-width", row + clock, preset["variation_mode"])
        edge_power = 2 + (1 - np.clip(p.get("edge_softness", .06) / .4, 0, 1)) * 6
        mask = np.exp(-((distance / np.maximum(.001, local_thickness * irregular)) ** edge_power))
        # Thin rays remain visible to the edges while the aperture holds a
        # near-rectangular bright section.
        mask *= .62 + .32 * envelope
        white = np.array((1.0, .985, .98), dtype=np.float32)
        _add(arr, mask * p.get("intensity", 1), white)
        edge = np.exp(-((distance / np.maximum(.001, local_thickness + .002 + p["edge_softness"] * .10)) ** 2)) - mask
        edge *= np.clip(.35 + envelope, 0, 1) * (1 + p.get("edge_softness", .06) * 2)
        edge = np.clip(edge, 0, 1) * p["magenta"]
        if p.get("edge_bias", 0) != 0:
            edge *= 1 + p["edge_bias"] * np.tanh((asym - u) * 5)
        color = _hsv(base_hue + .004 * row, .82, .8)
        _add(arr, edge * p.get("intensity", 1), color)


def _render_flare(arr, p, t, preset, module_index):
    if p["strength"] <= 0:
        return
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    x /= max(1, w - 1); y /= max(1, h - 1)
    distance = y - p["position_y"]
    if p.get("bend", 0) != 0:
        distance = distance - p["bend"] * .24 * ((x - p["position_x"]) / p["reach"]) ** 2
    spread = p["spread"]
    if p.get("asymmetry", 0) != 0:
        spread = spread * (1 + p["asymmetry"] * .75 * np.sign(distance))
    sweep = np.exp(-(distance / spread) ** 2)
    sweep *= .12 + 1.15 * np.exp(-((x - p["position_x"]) / p["reach"]) ** 2)
    rng = np.random.default_rng(_seed(preset["seed"], "flare", round(t * preset["treatment_fps"])))
    boundary = np.exp(-((sweep - .28) / .16) ** 2)
    _add(arr, boundary * np.clip(rng.normal(.2, .3, (h, w)), 0, 1) * p["fringe"], np.array((.8, .08, 1.0)))
    _add(arr, sweep * p["strength"], np.array((.96, .98, .94)))


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
    if p.get("softness", 0) > 0:
        signal = Image.fromarray(np.clip(result * 255, 0, 255).astype(np.uint8))
        result = np.asarray(signal.filter(ImageFilter.GaussianBlur(p["softness"] * w / 720)), dtype=np.float32) / 255
    result[::2] *= 1 - p["lines"]
    rng = np.random.default_rng(_seed(seed, "raster", treatment_frame))
    luminance = np.mean(result, axis=2, keepdims=True)
    result += rng.normal(0, p["grain"], result.shape).astype(np.float32) * np.sqrt(np.clip(luminance, 0, 1))
    chroma = rng.normal(0, p["chroma"], (h, w, 1)).astype(np.float32)
    result[..., 0] += chroma[..., 0]
    result[..., 2] -= chroma[..., 0]
    if p.get("line_noise", 0) > 0:
        streaks = _signal_noise(seed, "line-grain", treatment_frame, (w, h), (120, 576))
        result += streaks[..., None] * p["line_noise"] * np.sqrt(np.clip(luminance, 0, 1))
    return result


def _interference(arr, p, t, preset):
    if p["mix"] == 0:
        return arr
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    y /= max(1, h - 1)
    x /= max(1, w - 1)
    clock = t * preset["speed"] * p["speed"]
    background = np.array((.055, .067, .055), dtype=np.float32)
    signal = np.maximum(arr - background, 0)
    phase = math.tau * (y * p["bands"] - clock * .7 + x * p["bend"])
    phase += p["bend"] * np.sin(y * 17 + clock * 2.3) * 3
    gain = 1 - p["depth"] * (.5 + .5 * np.sin(phase))
    color_phase = y * 9 + x * 3 + np.sin(y * 13 - clock) + clock * .8
    colors = .25 + .75 * (.5 + .5 * np.cos(color_phase[..., None] + np.array((0., 2.1, 4.2))))
    tinted = signal * (1 - p["chroma"]) + signal.mean(axis=2, keepdims=True) * colors * 1.6 * p["chroma"]
    comb = .5 + .5 * np.sin(x * math.tau * p["columns"] + np.sin(y * 27 + clock * 3) * p["bend"] * 5)
    treated = background + tinted * (gain * (1 - p["comb"] * comb))[..., None]
    return arr * (1 - p["mix"]) + treated * p["mix"]


def _breakup(arr, p, t, preset):
    if p["mix"] == 0 or (p["amount"] == 0 and p["dropout"] == 0):
        return arr
    h, w = arr.shape[:2]
    rng = np.random.default_rng(_seed(preset["seed"], "breakup", math.floor(t * p["rate"] + 1e-9)))
    bands = int(p["bands"])
    band = np.minimum(np.arange(h) * bands // h, bands - 1)
    shifts = np.rint(rng.uniform(-1, 1, bands) * p["amount"] * w).astype(int)[band]
    x = np.arange(w)[None, :] - shifts[:, None]
    result = arr[np.arange(h)[:, None], np.clip(x, 0, w - 1)].copy()
    background = np.array((.055, .067, .055), dtype=np.float32)
    result[(x < 0) | (x >= w)] = background
    result[rng.random(bands)[band] < p["dropout"]] = background
    return arr * (1 - p["mix"]) + result * p["mix"]


RENDERERS = {
    "slab": lambda arr, params, t, preset, index: _render_slab(arr, params, t, preset, index),
    "blinds": lambda arr, params, t, preset, index: _render_blinds(arr, params, t, preset, index),
    "particles": lambda arr, params, t, preset, index: render_particles(arr, params, t, preset, _seed(preset["seed"], "particles")),
    "flare": lambda arr, params, t, preset, index: _render_flare(arr, params, t, preset, index),
    "warp": lambda arr, params, t, preset, index: _warp(arr, params, t, preset),
    "separation": lambda arr, params, t, preset, index: _separate(arr, params, t, preset),
    "smear": lambda arr, params, t, preset, index: _smear(arr, params),
    "interference": lambda arr, params, t, preset, index: _interference(arr, params, t, preset),
    "bloom": lambda arr, params, t, preset, index: _bloom(arr, params),
    "raster": lambda arr, params, t, preset, index: _raster(arr, params, preset["seed"], round(t * preset["treatment_fps"])),
    "breakup": lambda arr, params, t, preset, index: _breakup(arr, params, t, preset),
    "tape": lambda arr, params, t, preset, index: render_tape_damage(arr, params, t, preset["speed"], _seed(preset["seed"], "tape")),
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
    # The reference has a lifted green-black field rather than zero RGB.
    arr[..., 0] = .055
    arr[..., 1] = .067
    arr[..., 2] = .055
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
    for item in slab["modules"]:
        if item["id"] == "slab":
            item["params"].update({"height": .62, "position_x": .18, "position_y": .04, "width": .24, "edge_hardness": .88, "notch": .12, "intensity": .92, "ghost_width": .56, "ghost_offset": .30, "ghost_opacity": .38})
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
