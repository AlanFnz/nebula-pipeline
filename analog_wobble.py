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
from PIL import Image, ImageChops, ImageFilter


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


def add_chromatic_aberration(img: Image.Image, strength: float) -> Image.Image:
    """subtle per-frame R/B channel shift"""
    if strength <= 0:
        return img
    
    r, g, b = img.split()
    
    # Random direction for shift
    theta = random.uniform(0, 2 * math.pi)
    dx = int(strength * math.cos(theta))
    dy = int(strength * math.sin(theta))
    
    # Shift R and B in opposite directions
    r = ImageChops.offset(r, dx, dy)
    b = ImageChops.offset(b, -dx, -dy)
    
    return Image.merge("RGB", (r, g, b))


def add_luminous_grain(img: Image.Image, sigma: float) -> Image.Image:
    """overlay-style grain: affects mids more than blacks"""
    if sigma <= 0:
        return img
        
    arr = np.asarray(img, dtype=np.float32)
    # Generate noise centered at 0
    noise = np.random.normal(0.0, sigma, arr.shape).astype(np.float32)
    
    # Simple soft-light-ish blend approximation: 
    # Weighted by luminance to prevent grain in pure blacks
    luminance = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
    luminance = np.stack([luminance] * 3, axis=-1)
    
    # Apply noise scaled by luminance
    result = arr + (noise * (luminance ** 0.5))
    
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def smooth_walk(n: int, lo: float, hi: float, step: float = 0.15) -> list[float]:
    """random walk drifting slowly within [lo, hi]"""
    if lo == hi:
        return [lo] * n
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
    blur_range: tuple[float, float],
    aberration: float,
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

    # Pre-calculate drifting parameters for "breathing"
    grain_sigmas = [v * 25 for v in smooth_walk(n, *grain_range)]
    blur_radii = smooth_walk(n, *blur_range)

    print(f"processing {n} frames\n  input : {input_dir}\n  output: {output_dir}")

    for i, src in enumerate(frames):
        img = Image.open(src).convert("RGB")

        # 1. wobble (translation + rotation)
        mag = random.uniform(*px_range)
        theta = random.uniform(0, 2 * math.pi)
        dx = int(mag * math.cos(theta))
        dy = int(mag * math.sin(theta))
        rot = random.uniform(*deg_range) * random.choice((-1, 1))
        img = wobble(img, dx, dy, rot)

        # 2. chromatic aberration
        if aberration > 0:
            img = add_chromatic_aberration(img, aberration)

        # 3. breathing blur
        if blur_radii[i] > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur_radii[i]))

        # 4. luminous grain
        img = add_luminous_grain(img, grain_sigmas[i])
        
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
        help="grain intensity range 0–1",
    )
    p.add_argument(
        "--blur",
        nargs=2,
        type=float,
        default=[0.0, 0.0],
        metavar=("MIN", "MAX"),
        help="gaussian blur radius range (breathing effect)",
    )
    p.add_argument(
        "--aberration",
        type=float,
        default=0.0,
        help="chromatic aberration strength in pixels",
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
        blur_range=(args.blur[0], args.blur[1]),
        aberration=args.aberration,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
