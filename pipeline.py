#!/usr/bin/env python3
"""
pipeline.py — phase 1: extract frames → wobble + grain
after this completes, apply your Photoshop batch action to frames_wobbled/
then run assemble.py to produce the final video
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analog_wobble import process as wobble_process
from assemble import assemble_video
from grade import process as grade_process

FOLDERS = ["source", "frames_raw", "frames_wobbled", "frames_treated", "output"]


def require_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except FileNotFoundError:
        raise SystemExit("error: ffmpeg not found — install it and ensure it's on PATH")


def extract_frames(video: Path, frames_raw: Path, fps: float) -> int:
    frames_raw.mkdir(parents=True, exist_ok=True)
    pattern = frames_raw / "frame_%05d.png"
    print(f"extracting frames at {fps}fps → {frames_raw}")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vf", f"fps={fps}", str(pattern)],
        check=True,
    )
    return len(list(frames_raw.glob("*.png")))


def setup_project(project: Path) -> None:
    for folder in FOLDERS:
        (project / folder).mkdir(parents=True, exist_ok=True)
    print(f"project structure created at {project}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="phase 1 — extract frames and apply wobble+grain",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("input", type=Path,
                   help="source video (e.g. project/source/clip.mp4)")
    p.add_argument("project", type=Path,
                   help="project root directory")
    p.add_argument("--fps", type=float, default=10.0,
                   help="extraction frame rate")
    p.add_argument("--px", nargs=2, type=float, default=[3.0, 6.0],
                   metavar=("MIN", "MAX"), help="wobble translation range in pixels")
    p.add_argument("--deg", nargs=2, type=float, default=[0.3, 0.8],
                   metavar=("MIN", "MAX"), help="wobble rotation range in degrees")
    p.add_argument("--grain", nargs=2, type=float, default=[0.3, 0.8],
                   metavar=("LO", "HI"), help="grain intensity range 0–1")
    p.add_argument("--blur", nargs=2, type=float, default=[0.0, 0.0],
                   metavar=("MIN", "MAX"), help="gaussian blur radius range (breathing effect)")
    p.add_argument("--aberration", type=float, default=0.0,
                   help="chromatic aberration strength in pixels")
    p.add_argument("--vignette", type=float, default=0.0,
                   help="vignette strength 0–1")
    p.add_argument("--bands", type=float, default=0.0,
                   help="horizontal scan band intensity 0–1")
    p.add_argument("--texture", type=float, default=0.0,
                   help="paper texture strength 0–1")
    p.add_argument("--warm", type=float, default=0.0,
                   help="warm toning strength 0–1")
    p.add_argument("--dust", type=float, default=0.0,
                   help="dust speck density 0–1")
    p.add_argument("--dust-opacity", type=float, default=1.0,
                   help="dust speck opacity 0–1")
    p.add_argument("--scanlines",    type=float, default=0.0,
                   help="scanline darkness 0–1")
    p.add_argument("--bloom",        type=float, default=0.0,
                   help="phosphor bloom strength 0–1")
    p.add_argument("--curvature",    type=float, default=0.0,
                   help="barrel distortion strength 0–1")
    p.add_argument("--brightness",   type=float, default=1.0,
                   help="global brightness multiplier (1.0 = no change)")
    p.add_argument("--drift", type=float, default=0.0,
                   help="temporal drift 0–1 — how much bands, aberration, brightness, warm vary frame to frame")
    p.add_argument("--seed", type=int, default=None,
                   help="RNG seed for reproducible wobble")
    p.add_argument("--grade", action="store_true",
                   help="run python color grade pass after wobble (skips manual Photoshop step)")
    p.add_argument("--contrast",   type=float, default=0.4,
                   help="grade: S-curve contrast 0–1")
    p.add_argument("--shadows",    type=float, default=0.15,
                   help="grade: shadow crush 0–1")
    p.add_argument("--highlights", type=float, default=0.05,
                   help="grade: highlight boost 0–1")
    p.add_argument("--toning",     type=float, default=0.4,
                   help="grade: split toning strength 0–1")
    p.add_argument("--setup", action="store_true",
                   help="create project folder structure and exit")
    args = p.parse_args()

    if args.setup:
        setup_project(args.project)
        return

    require_ffmpeg()

    if not args.input.exists():
        raise SystemExit(f"error: input video not found: {args.input}")

    frames_raw     = args.project / "frames_raw"
    frames_wobbled = args.project / "frames_wobbled"
    frames_wobbled.mkdir(parents=True, exist_ok=True)

    count = extract_frames(args.input, frames_raw, args.fps)
    print(f"extracted {count} frames")

    print("\napplying wobble + grain...")
    wobble_process(
        frames_raw,
        frames_wobbled,
        px_range=(args.px[0], args.px[1]),
        deg_range=(args.deg[0], args.deg[1]),
        grain_range=(args.grain[0], args.grain[1]),
        blur_range=(args.blur[0], args.blur[1]),
        aberration=args.aberration,
        vignette=args.vignette,
        bands=args.bands,
        texture=args.texture,
        warm=args.warm,
        dust=args.dust,
        dust_opacity=args.dust_opacity,
        scanlines=args.scanlines,
        bloom=args.bloom,
        curvature=args.curvature,
        brightness=args.brightness,
        seed=args.seed,
        drift=args.drift,
    )

    treated = args.project / "frames_treated"

    if args.grade:
        print("\ngrading frames...")
        grade_process(
            frames_wobbled, treated,
            contrast=args.contrast, shadows=args.shadows,
            highlights=args.highlights, toning=args.toning,
        )
        final_output = args.project / "output" / "final.mp4"
        print("\nassembling final video...")
        assemble_video(treated, final_output, fps=args.fps)
        print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  pipeline complete

  output: {final_output}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    else:
        preview_output = args.project / "output" / "preview_wobbled.mp4"
        print("\ngenerating preview...")
        assemble_video(frames_wobbled, preview_output, fps=args.fps)
        print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  phase 1 complete

  preview: {preview_output}

  next: apply your Photoshop batch action to
        {frames_wobbled}
        → save treated frames to
        {treated}

  then run:
        python assemble.py {args.project} --fps {args.fps}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    main()
