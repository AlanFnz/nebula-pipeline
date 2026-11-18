"""Shared legacy-compatible settings, independent of either UI."""
import json
import math
from pathlib import Path

DEFAULTS: dict = {
    "blur":         (3.0, 7.0),
    "texture":      0.7,
    "warm":         0.8,
    "aberration":   3.0,
    "bands":        0.45,
    "vignette":     0.75,
    "grain":        (0.7, 1.1),
    "dust":         0.6,
    "dust_opacity": 1.0,
    "scanlines":    0.0,
    "bloom":        0.0,
    "curvature":    0.0,
    "brightness":   1.0,
    "px":           (2.0, 5.0),
    "deg":          (0.2, 0.6),
    "fps":          12.0,
    "seed":         42,
    "contrast":     0.4,
    "shadows":      0.15,
    "highlights":   0.05,
    "toning":       0.4,
    "grade":        1,
    "drift":        0.0,
}


RANGES = {"blur", "grain", "px", "deg"}
STAGES = ("source", "print", "scan", "wobble", "grade")
PRESETS_DIR = Path.home() / ".nebula_pipeline" / "presets"
LIMITS = {"blur": 30, "grain": 3, "px": 50, "deg": 10,
          "aberration": 30, "brightness": 3, "fps": 60, "seed": 2147483647}


def normalize(raw=None):
    """Accept existing flat JSON presets; reject malformed/nonfinite values."""
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ValueError("Preset must contain a JSON object")
    p = dict(DEFAULTS)
    for key in DEFAULTS:
        value = raw.get(key, p[key])
        if key == "seed" and value is None:
            value = 42
        values = value if key in RANGES else [value]
        if key in RANGES and (not isinstance(values, (tuple, list)) or len(values) != 2):
            raise ValueError(f"{key} needs two values")
        out = []
        for v in values:
            v = float(v)
            if not math.isfinite(v):
                raise ValueError(f"{key} must be finite")
            if not (0 <= v <= LIMITS.get(key, 1)) or (key == "fps" and v < 1):
                raise ValueError(f"{key} is outside the supported range")
            out.append(v)
        p[key] = tuple(sorted(out)) if key in RANGES else out[0]
    p["seed"] = int(p["seed"])
    p["grade"] = int(bool(p["grade"]))
    stages = raw.get("_stages", {})
    if not isinstance(stages, dict):
        raise ValueError("Stage settings must be an object")
    p["_stages"] = {s: bool(stages.get(s, True)) for s in STAGES[1:]}
    p["_stages"]["grade"] = bool(p["grade"])
    return p


def load(path):
    return normalize(json.loads(Path(path).read_text()))


def save(path, params):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize(params), indent=2) + "\n")
