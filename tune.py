#!/usr/bin/env python3
"""
tune.py — interactive single-frame parameter tuner

open tune_preview.png in macOS Preview — it auto-refreshes on each change

commands:
  <param> <value(s)>   adjust a param, e.g.:  blur 1 4   warm 0.6   grain 0.5 0.9
  show                 print current parameter values
  reset                reset all to defaults
  run                  run the full pipeline with current params
  export               print the equivalent pipeline.py command
  q / quit             exit
"""

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
    add_chromatic_aberration, add_scan_bands, add_vignette,
    add_luminous_grain, add_dust, wobble,
)

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
    "dust":       0.6,
    "px":         (2.0, 5.0),
    "deg":        (0.2, 0.6),
    "fps":        12.0,
    "seed":       42,
}

RANGE_PARAMS  = {"blur", "grain", "px", "deg"}
SINGLE_PARAMS = {"aberration", "vignette", "bands", "texture", "warm", "dust", "fps", "seed"}


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
    img = add_vignette(img, params["vignette"])
    img = add_luminous_grain(img, grain_sigma)
    img = add_dust(img, params["dust"])

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
        ("scan pass",  ["aberration", "bands", "vignette", "grain", "dust"]),
        ("video",      ["px", "deg", "fps"]),
        ("misc",       ["seed"]),
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
        "--dust",       str(p["dust"]),
        "--px",         str(p["px"][0]),         str(p["px"][1]),
        "--deg",        str(p["deg"][0]),         str(p["deg"][1]),
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
            params[key] = int(vals[0]) if key == "seed" else float(vals[0])
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
    print("adjust a param (e.g. 'blur 1 4'), or type 'show' / 'run' / 'export' / 'quit'\n")

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
        if line == "show":
            show(params)
        elif line == "reset":
            params = dict(DEFAULTS)
            apply_and_save(params)
            show(params)
        elif line == "run":
            cmd_args = build_pipeline_args(args.video, args.project, params)
            print(f"\n{export_cmd(args.video, args.project, params)}\n")
            subprocess.run(cmd_args)
        elif line == "export":
            print(f"\n{export_cmd(args.video, args.project, params)}\n")
        else:
            if parse_and_set(line, params):
                apply_and_save(params)


if __name__ == "__main__":
    main()
