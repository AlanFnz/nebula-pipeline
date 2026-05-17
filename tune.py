#!/usr/bin/env python3
"""
tune.py — interactive single-frame parameter tuner

open tune_preview.png in macOS Preview — it auto-refreshes on each change

commands:
  <param> <value(s)>   adjust a param, e.g.:  blur 1 4   warm 0.6   grain 0.5 0.9
  show                 print current parameter values
  reset                reset all to defaults
  save <name>          save current params as a named preset
  load <name>          restore a saved preset
  presets              list all saved presets
  run                  run the full pipeline with current params
  export               print the equivalent pipeline.py command
  q / quit             exit
"""

import json
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from analog_wobble import (
    add_blur, add_paper_texture, add_warm_toning,
    add_chromatic_aberration, add_scan_bands,
    add_scanlines, add_bloom, add_curvature,
    add_vignette, add_luminous_grain, add_dust, add_brightness, wobble,
)
from grade import apply_contrast, apply_shadow_crush, apply_highlight_boost, apply_split_toning

PREVIEW    = Path("tune_preview.png")   # 3-panel: lo | mid | hi for range params
SRC_FRAME  = Path("tune_source.png")

DEFAULTS: dict = {
    "blur":       (3.0, 7.0),
    "texture":    0.7,
    "warm":       0.8,
    "aberration": 3.0,
    "bands":      0.45,
    "vignette":   0.75,
    "grain":      (0.7, 1.1),
    "dust":         0.6,
    "dust_opacity": 1.0,
    "scanlines":    0.0,
    "bloom":        0.0,
    "curvature":    0.0,
    "brightness":   1.0,
    "px":           (2.0, 5.0),
    "deg":        (0.2, 0.6),
    "fps":        12.0,
    "seed":       42,
    "contrast":   0.4,
    "shadows":    0.15,
    "highlights": 0.05,
    "toning":     0.4,
    "grade":      1,
    "drift":      0.0,
}

RANGE_PARAMS  = {"blur", "grain", "px", "deg"}
SINGLE_PARAMS = {"aberration", "vignette", "bands", "texture", "warm", "dust", "dust_opacity",
                 "scanlines", "bloom", "curvature", "brightness", "fps", "seed",
                 "contrast", "shadows", "highlights", "toning", "grade", "drift"}


def params_file(project: Path) -> Path:
    return project / "tune_params.json"


def save_params(params: dict, project: Path) -> None:
    params_file(project).parent.mkdir(parents=True, exist_ok=True)
    params_file(project).write_text(json.dumps(params, indent=2))


def load_params(project: Path) -> dict | None:
    f = params_file(project)
    if not f.exists():
        return None
    try:
        return _restore_tuples(json.loads(f.read_text()))
    except Exception:
        return None


PRESETS_DIR = Path.home() / ".nebula_pipeline" / "presets"


def _restore_tuples(raw: dict) -> dict:
    for k in RANGE_PARAMS:
        if k in raw and isinstance(raw[k], list):
            raw[k] = tuple(raw[k])
    return raw


def save_preset(name: str, params: dict) -> None:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    (PRESETS_DIR / f"{name}.json").write_text(json.dumps(params, indent=2))


def load_preset(name: str) -> dict | None:
    f = PRESETS_DIR / f"{name}.json"
    if not f.exists():
        return None
    try:
        return _restore_tuples(json.loads(f.read_text()))
    except Exception:
        return None


def list_presets() -> list[str]:
    if not PRESETS_DIR.exists():
        return []
    return sorted(p.stem for p in PRESETS_DIR.glob("*.json"))


HELP = [
    ("print pass — baked into the printed object", [
        ("blur",        "MIN MAX", "base Gaussian blur — dissolves the source. higher = more ethereal"),
        ("texture",     "0–1",     "paper substrate variation — mottled surface on the blacks"),
        ("warm",        "0–1",     "warm color cast — shifts R up, B down. aged ink and paper feel"),
    ]),
    ("scan pass — digitizing artifacts layered on top", [
        ("aberration",  "px",      "R/B channel shift — color fringing at edges of bright areas"),
        ("bands",       "0–1",     "horizontal exposure banding — uneven scanner lamp artifact"),
        ("scanlines",   "0–1",     "darken every other row — CRT electron beam gap"),
        ("bloom",       "0–1",     "bright areas bleed light onto neighbors — phosphor glow"),
        ("curvature",   "0–1",     "barrel distortion — CRT curved glass. 0.2–0.4 is already strong"),
        ("brightness",  ">0",      "global multiplier applied last — use to recover from cumulative darkening"),
        ("vignette",    "0–1",     "corner darkening — print/scanner edge falloff"),
        ("grain",       "LO HI",   "scan noise weighted by luminance — no grain in pure blacks"),
        ("dust",        "0–1",     "sparse white specks — dust on scanner glass. controls density"),
        ("dust_opacity","0–1",     "how bright each speck is — blends with underlying pixel. lower = subtler"),
    ]),
    ("video pass — the assembled object in motion", [
        ("px",          "MIN MAX", "translation wobble range in pixels"),
        ("deg",         "MIN MAX", "rotation wobble range in degrees"),
        ("fps",         "N",       "frame rate for extraction and assembly"),
    ]),
    ("grade pass — color treatment applied after scan pass", [
        ("grade",      "0/1", "enable or disable the entire grade pass — 0 to compare without it"),
        ("contrast",   "0–1", "S-curve contrast — darken shadows, lift highlights. tightens the image"),
        ("shadows",    "0–1", "shadow crush — push dark regions toward black. deepens the void"),
        ("highlights", "0–1", "highlight boost — lift bright regions toward white. makes light subjects glow"),
        ("toning",     "0–1", "split toning — teal shadows + amber highlights. warm/cold tension"),
    ]),
    ("misc", [
        ("drift", "0–1", "temporal drift — how much bands, aberration, brightness, warm wander frame to frame"),
        ("seed",  "N",   "RNG seed — fix to get reproducible results across runs"),
    ]),
]


def help_text() -> None:
    print()
    for group, params in HELP:
        print(f"  {group}")
        for name, syntax, desc in params:
            print(f"    {name:<14} {syntax:<10}  {desc}")
    print()
    print("  range params take two values: blur 1 4   grain 0.5 0.9")
    print("  single params take one value: warm 0.6   dust 0.2")
    print()


def extract_frame(video: Path, fps: float, index: int) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"fps={fps},select=eq(n\\,{index})",
        "-vframes", "1", str(SRC_FRAME),
    ], check=True, capture_output=True)


def _render(params: dict, blur_r: float, grain_sigma: float,
            px: float, deg: float) -> Image.Image:
    """render a single frame with explicit scalar values (no ranges)"""
    seed = params.get("seed")
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed))

    img = Image.open(SRC_FRAME).convert("RGB")

    img = add_blur(img, blur_r)
    img = add_paper_texture(img, params["texture"])
    img = add_warm_toning(img, params["warm"])

    img = add_chromatic_aberration(img, params["aberration"])
    img = add_scan_bands(img, params["bands"])
    img = add_scanlines(img, params["scanlines"])
    img = add_bloom(img, params["bloom"])
    img = add_curvature(img, params["curvature"])
    img = add_vignette(img, params["vignette"])
    img = add_luminous_grain(img, grain_sigma)
    img = add_dust(img, params["dust"], params["dust_opacity"])
    img = add_brightness(img, params["brightness"])

    if params.get("grade", 1):
        arr = np.asarray(img, dtype=np.float32)
        arr = apply_contrast(arr, params["contrast"])
        arr = apply_shadow_crush(arr, params["shadows"])
        arr = apply_highlight_boost(arr, params["highlights"])
        arr = apply_split_toning(arr, params["toning"])
        img = Image.fromarray(arr.astype(np.uint8))

    theta = random.uniform(0, 2 * math.pi)
    dx    = int(px * math.cos(theta))
    dy    = int(px * math.sin(theta))
    rot   = deg * random.choice((-1, 1))
    return wobble(img, dx, dy, rot)


def apply_and_save(params: dict) -> None:
    """render a 3-panel contact sheet: lo | mid | hi for all range params"""
    blur_lo,  blur_hi  = params["blur"]
    grain_lo, grain_hi = params["grain"]
    px_lo,    px_hi    = params["px"]
    deg_lo,   deg_hi   = params["deg"]

    panels = []
    for blur_r, grain_s, px, deg in [
        (blur_lo,                    grain_lo * 25,                    px_lo, deg_lo),
        ((blur_lo + blur_hi) / 2,   (grain_lo + grain_hi) / 2 * 25,  (px_lo + px_hi) / 2, (deg_lo + deg_hi) / 2),
        (blur_hi,                    grain_hi * 25,                    px_hi, deg_hi),
    ]:
        panels.append(_render(params, blur_r, grain_s, px, deg))

    # stitch horizontally with a 2px black divider
    w, h  = panels[0].size
    sep   = 2
    sheet = Image.new("RGB", (w * 3 + sep * 2, h), (0, 0, 0))
    for i, panel in enumerate(panels):
        sheet.paste(panel, (i * (w + sep), 0))

    sheet.save(PREVIEW)
    blur_range  = f"{blur_lo}–{blur_hi}"
    grain_range = f"{grain_lo}–{grain_hi}"
    print(f"  → {PREVIEW}  [lo | mid | hi]  blur {blur_range}  grain {grain_range}")


def show(params: dict) -> None:
    groups = [
        ("print pass", ["blur", "texture", "warm"]),
        ("scan pass",  ["aberration", "bands", "scanlines", "bloom", "curvature",
                        "vignette", "grain", "dust", "dust_opacity", "brightness"]),
        ("grade pass", ["grade", "contrast", "shadows", "highlights", "toning"]),
        ("video",      ["px", "deg", "fps"]),
        ("misc",       ["drift", "seed"]),
    ]
    print()
    for label, keys in groups:
        print(f"  {label}")
        for k in keys:
            v = params[k]
            val = f"{v[0]}  {v[1]}" if isinstance(v, tuple) else str(v)
            print(f"    {k:<14} {val}")
    print()


def build_pipeline_args(video: Path, project: Path, params: dict) -> list[str]:
    p = params
    args = [
        sys.executable, "pipeline.py", str(video), str(project),
        "--fps",        str(p["fps"]),
        "--blur",       str(p["blur"][0]),       str(p["blur"][1]),
        "--texture",    str(p["texture"]),
        "--warm",       str(p["warm"]),
        "--aberration", str(p["aberration"]),
        "--bands",      str(p["bands"]),
        "--vignette",   str(p["vignette"]),
        "--grain",      str(p["grain"][0]),      str(p["grain"][1]),
        "--dust",         str(p["dust"]),
        "--dust-opacity", str(p["dust_opacity"]),
        "--scanlines",    str(p["scanlines"]),
        "--bloom",        str(p["bloom"]),
        "--curvature",    str(p["curvature"]),
        "--brightness",   str(p["brightness"]),
        "--drift",        str(p["drift"]),
        "--px",         str(p["px"][0]),         str(p["px"][1]),
        "--deg",        str(p["deg"][0]),         str(p["deg"][1]),
    ]
    if p.get("grade", 1):
        args += [
            "--grade",
            "--contrast",   str(p["contrast"]),
            "--shadows",    str(p["shadows"]),
            "--highlights", str(p["highlights"]),
            "--toning",     str(p["toning"]),
        ]
    if p.get("seed") is not None:
        args += ["--seed", str(int(p["seed"]))]
    return args


def export_cmd(video: Path, project: Path, params: dict) -> str:
    args = build_pipeline_args(video, project, params)
    # swap sys.executable back to "python" for display
    args[0] = "python"
    it = iter(args)
    parts, current = [], []
    for tok in it:
        if tok.startswith("--"):
            if current:
                parts.append(" ".join(current))
            current = [tok]
        else:
            current.append(tok)
    if current:
        parts.append(" ".join(current))
    return " \\\n  ".join(parts)


def parse_and_set(line: str, params: dict) -> bool:
    tokens = line.split()
    key, vals = tokens[0], tokens[1:]

    if not vals and key in (RANGE_PARAMS | SINGLE_PARAMS):
        v = params[key]
        print(f"  {key} = {f'{v[0]}  {v[1]}' if isinstance(v, tuple) else v}")
        return False

    if key in RANGE_PARAMS:
        if len(vals) != 2:
            print(f"  {key} takes two values: MIN MAX")
            return False
        try:
            params[key] = (float(vals[0]), float(vals[1]))
        except ValueError:
            print(f"  invalid values for {key}")
            return False

    elif key in SINGLE_PARAMS:
        if len(vals) != 1:
            print(f"  {key} takes one value")
            return False
        try:
            params[key] = int(vals[0]) if key in ("seed", "grade") else float(vals[0])
        except ValueError:
            print(f"  invalid value for {key}")
            return False

    else:
        all_params = sorted(RANGE_PARAMS | SINGLE_PARAMS)
        print(f"  unknown param '{key}' — known: {', '.join(all_params)}")
        return False

    return True


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="interactive single-frame parameter tuner")
    ap.add_argument("video",   type=Path, help="source video (e.g. test-video.mp4)")
    ap.add_argument("project", type=Path, nargs="?", default=Path("test_run"),
                    help="project dir for 'run' (default: test_run)")
    ap.add_argument("--frame", type=int, default=None,
                    help="frame index to tune on (default: midpoint)")
    args = ap.parse_args()

    if not args.video.exists():
        raise SystemExit(f"error: video not found: {args.video}")

    saved = load_params(args.project)
    if saved:
        params = {**DEFAULTS, **saved}   # fill any new keys not yet in the saved file
        print(f"loaded params from {params_file(args.project)}")
    else:
        params = dict(DEFAULTS)

    # determine frame index
    if args.frame is not None:
        frame_idx = args.frame
    else:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(args.video)],
            capture_output=True, text=True,
        )
        try:
            duration = float(result.stdout.strip())
            frame_idx = int(duration * params["fps"] / 2)
        except (ValueError, TypeError):
            frame_idx = 15

    print(f"\nextracting frame {frame_idx} from {args.video}...")
    extract_frame(args.video, params["fps"], frame_idx)
    print(f"open {PREVIEW} in macOS Preview — it auto-refreshes on each change\n")

    apply_and_save(params)
    show(params)
    print("type 'help' for param descriptions, or adjust directly (e.g. 'blur 1 4', 'dust 0.2')\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        if line in ("q", "quit", "exit"):
            break
        if line in ("help", "h", "?"):
            help_text()
        elif line == "show":
            show(params)
        elif line == "reset":
            params = dict(DEFAULTS)
            params_file(args.project).unlink(missing_ok=True)
            apply_and_save(params)
            show(params)
        elif line == "run":
            cmd_args = build_pipeline_args(args.video, args.project, params)
            print(f"\n{export_cmd(args.video, args.project, params)}\n")
            subprocess.run(cmd_args)
        elif line == "export":
            print(f"\n{export_cmd(args.video, args.project, params)}\n")
        elif line == "presets":
            names = list_presets()
            if names:
                print(f"\n  {', '.join(names)}\n")
            else:
                print("  no presets saved yet — use: save <name>\n")
        elif line.startswith("save "):
            name = line[5:].strip()
            if name:
                save_preset(name, params)
                print(f"  saved preset '{name}'")
            else:
                print("  usage: save <name>")
        elif line.startswith("load "):
            name = line[5:].strip()
            preset = load_preset(name)
            if preset is None:
                print(f"  preset '{name}' not found — type 'presets' to list available")
            else:
                params = {**DEFAULTS, **preset}
                save_params(params, args.project)
                apply_and_save(params)
                show(params)
        else:
            if parse_and_set(line, params):
                save_params(params, args.project)
                apply_and_save(params)


if __name__ == "__main__":
    main()
