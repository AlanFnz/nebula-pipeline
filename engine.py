"""One deterministic render path for desktop preview, export and legacy tools.

Order is print -> scan -> wobble -> grade. Random streams are keyed by seed,
effect and output-frame index, never by execution order or parameter values.
"""
import hashlib
import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image

import analog_wobble as fx
import grade as grading
from parameters import normalize, STAGES


@lru_cache(maxsize=8192)
def stream_seed(seed, effect, frame):
    key = f"nebula-v1:{seed}:{effect}:{frame}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "little")


def rng(seed, effect, frame):
    return np.random.default_rng(stream_seed(seed, effect, frame))


def temporal(seed, effect, frame, lo, hi):
    """Smooth bounded drift with random access, independent of clip length.

    Interpolated random knots replace the sequential global random walk. This
    intentionally changes old seeded looks, while retaining their ranges.
    """
    knot, fraction = divmod(frame / 8.0, 1)
    a = random.Random(stream_seed(seed, effect, int(knot))).random()
    b = random.Random(stream_seed(seed, effect, int(knot) + 1)).random()
    t = fraction * fraction * (3 - 2 * fraction)
    return lo + (hi - lo) * (a + (b - a) * t)


def frame_values(params, frame):
    p = normalize(params)
    seed = p["seed"]
    values = {k: temporal(seed, k, frame, *p[k]) for k in ("blur", "grain")}
    for k in ("aberration", "bands", "brightness", "warm"):
        half = p[k] * p["drift"] * 0.35
        values[k] = temporal(seed, k, frame, max(0, p[k] - half), p[k] + half)
    motion = random.Random(stream_seed(seed, "position", frame))
    mag = motion.uniform(*p["px"])
    theta = motion.uniform(0, 2 * math.pi)
    values.update(dx=mag * math.cos(theta), dy=mag * math.sin(theta))
    rotation = random.Random(stream_seed(seed, "rotation", frame))
    values["angle"] = rotation.uniform(*p["deg"]) * rotation.choice((-1, 1))
    return values


def grade_frame(img, params):
    arr = np.asarray(img, dtype=np.float32)
    arr = grading.apply_contrast(arr, params["contrast"])
    arr = grading.apply_shadow_crush(arr, params["shadows"])
    arr = grading.apply_highlight_boost(arr, params["highlights"])
    arr = grading.apply_split_toning(arr, params["toning"])
    return Image.fromarray(arr.astype(np.uint8))


def render_frame(source, params, frame=0, stage="grade", scale=1.0):
    """Render an RGB frame. `scale` is proxy width / original source width.

    Full size (scale=1) is the reference. Proxy spatial radii and translations
    follow the source scale; pixel noise is statistically approximated.
    """
    if stage not in STAGES or frame < 0 or not 0 < scale <= 1:
        raise ValueError("Invalid stage, frame index or proxy scale")
    p = normalize(params)
    img = source.convert("RGB")
    if stage == "source":
        return img
    v = frame_values(p, frame)
    seed = p["seed"]
    if p["_stages"]["print"]:
        img = fx.add_blur(img, v["blur"] * scale)
        img = fx.add_paper_texture(img, p["texture"], rng(seed, "paper", frame), scale)
        img = fx.add_warm_toning(img, v["warm"])
    if stage == "print":
        return img
    if p["_stages"]["scan"]:
        img = fx.add_chromatic_aberration(img, v["aberration"] * scale,
                                         random.Random(stream_seed(seed, "aberration-angle", frame)))
        img = fx.add_scan_bands(img, v["bands"] * math.sqrt(scale), rng(seed, "bands-noise", frame))
        # Subpixel CRT rows converge to their mean darkness when downsampled.
        if scale < 0.75:
            img = fx.add_brightness(img, 1 - p["scanlines"] / 2)
        else:
            img = fx.add_scanlines(img, p["scanlines"])
        img = fx.add_bloom(img, p["bloom"], radius=8 * scale)
        img = fx.add_curvature(img, p["curvature"])
        img = fx.add_vignette(img, p["vignette"])
        img = fx.add_luminous_grain(img, v["grain"] * 25 * scale, rng(seed, "grain-noise", frame))
        img = fx.add_dust(img, p["dust"], p["dust_opacity"], rng(seed, "dust", frame))
        img = fx.add_brightness(img, v["brightness"])
    if stage == "scan":
        return img
    if p["_stages"]["wobble"]:
        img = fx.wobble(img, int(v["dx"] * scale), int(v["dy"] * scale), v["angle"])
    if stage == "wobble":
        return img
    if p["_stages"]["grade"]:
        img = grade_frame(img, p)
    return img
