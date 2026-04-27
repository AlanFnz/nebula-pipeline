#!/usr/bin/env python3
"""
analog-wobble.py
apply per-frame geometric wobble and variable film grain to a PNG sequence
"""

import argparse
import math
import random
import re
from pathlib import Path

import numpy as np
from PIL import Image


def sorted_frames(folder: Path) -> list[Path]:
    files = list(folder.glob("*.png"))

    def key(f: Path) -> int | str:
        nums = re.findall(r"\d+", f.stem)
        return int(nums[-1]) if nums else f.stem

    return sorted(files, key=key)


def wobble(img: Image.Image, dx: int, dy: int, angle: float) -> Image.Image:
    """rotate then translate, filling revealed edges with black"""
    w, h = img.size
    rotated = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(0, 0, 0))
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(rotated, (dx, dy))
    return canvas


def add_grain(img: Image.Image, sigma: float) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32)
    noise = np.random.normal(0.0, sigma, arr.shape).astype(np.float32)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def smooth_walk(n: int, lo: float, hi: float, step: float = 0.15) -> list[float]:
    """random walk drifting slowly within [lo, hi] — gives temporal grain fluctuation"""
    v = random.uniform(lo, hi)
    span = hi - lo
    out = []
    for _ in range(n):
        out.append(v)
        v = max(lo, min(hi, v + random.gauss(0, span * step)))
    return out


def process(
    input_dir: Path,
    output_dir: Path,
    px_range: tuple[float, float],
    deg_range: tuple[float, float],
    grain_range: tuple[float, float],
    seed: int | None,
) -> None:
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    frames = sorted_frames(input_dir)
    if not frames:
        raise SystemExit(f"no PNG files found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    n = len(frames)

    # grain sigma drifts smoothly; intensity 0–1 maps to std dev 0–25
    grain_sigmas = [v * 25 for v in smooth_walk(n, *grain_range)]

    print(f"processing {n} frames\n  input : {input_dir}\n  output: {output_dir}")

    for i, src in enumerate(frames):
        img = Image.open(src).convert("RGB")

        # translation: random direction, magnitude within px_range
        mag = random.uniform(*px_range)
        theta = random.uniform(0, 2 * math.pi)
        dx = int(mag * math.cos(theta))
        dy = int(mag * math.sin(theta))

        # rotation: random sign, magnitude within deg_range
        rot = random.uniform(*deg_range) * random.choice((-1, 1))

        img = wobble(img, dx, dy, rot)
        img = add_grain(img, grain_sigmas[i])
        img.save(output_dir / src.name)

        if (i + 1) % 50 == 0 or i + 1 == n:
            pct = (i + 1) / n * 100
            print(f"  {i + 1}/{n}  ({pct:.0f}%)")

    print("done")


def main() -> None:
    p = argparse.ArgumentParser(
        description="apply wobble and film grain to a PNG frame sequence",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("input", type=Path, help="source frame folder (frames_raw/)")
    p.add_argument("output", type=Path, help="output folder (frames_wobbled/)")
    p.add_argument(
        "--px",
        nargs=2,
        type=float,
        default=[3.0, 6.0],
        metavar=("MIN", "MAX"),
        help="translation magnitude range in pixels",
    )
    p.add_argument(
        "--deg",
        nargs=2,
        type=float,
        default=[0.3, 0.8],
        metavar=("MIN", "MAX"),
        help="rotation magnitude range in degrees",
    )
    p.add_argument(
        "--grain",
        nargs=2,
        type=float,
        default=[0.3, 0.8],
        metavar=("LO", "HI"),
        help="grain intensity range 0–1 (maps to gaussian std dev 0–25)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducible output",
    )
    args = p.parse_args()

    process(
        args.input,
        args.output,
        px_range=(args.px[0], args.px[1]),
        deg_range=(args.deg[0], args.deg[1]),
        grain_range=(args.grain[0], args.grain[1]),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
