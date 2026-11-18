#!/usr/bin/env python3
"""
assemble.py — phase 2: reassemble treated frames into final video
run after applying the Photoshop batch action to frames_treated/
"""

import argparse
import subprocess
from pathlib import Path


def require_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except FileNotFoundError:
        raise SystemExit("error: ffmpeg not found — install it and ensure it's on PATH")


def assemble_video(
    input_dir: Path,
    output_path: Path,
    fps: float = 10.0,
    crf: int = 18,
) -> None:
    if not input_dir.exists() or not list(input_dir.glob("*.png")):
        raise FileNotFoundError(f"error: no PNG frames found in {input_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pattern = input_dir / "frame_%05d.png"

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(pattern),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf),
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(
        description="phase 2 — reassemble treated frames into final video",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("project", type=Path, help="project root directory")
    p.add_argument("--fps", type=float, default=10.0,
                   help="output frame rate — should match extraction fps")
    p.add_argument("--output", type=Path, default=None,
                   help="output file path (default: project/output/final.mp4)")
    p.add_argument("--crf", type=int, default=18,
                   help="H.264 CRF quality (0=lossless, 23=default, lower=better)")
    args = p.parse_args()

    require_ffmpeg()

    frames_treated = args.project / "frames_treated"
    output_dir = args.project / "output"
    output = args.output or output_dir / "final.mp4"

    try:
        assemble_video(frames_treated, output, fps=args.fps, crf=args.crf)
        print(f"done → {output}")
    except FileNotFoundError as e:
        raise SystemExit(e)


if __name__ == "__main__":
    main()
