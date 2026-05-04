#!/usr/bin/env python3
"""
analog-wobble.py
apply per-frame analog degradation to a PNG sequence

two-pass pipeline mirrors the physical process:

  PRINT PASS  — blur · paper texture · warm toning
  SCAN PASS   — aberration · bands · vignette · grain · dust
  VIDEO       — wobble
"""

import argparse
import math
import random
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter
from tqdm import tqdm


def sorted_frames(folder: Path) -> list[Path]:
    files = list(folder.glob("*.png"))

    def key(f: Path) -> int | str:
        nums = re.findall(r"\d+", f.stem)
        return int(nums[-1]) if nums else f.stem

    return sorted(files, key=key)


# ── PRINT PASS ────────────────────────────────────────────────────────────────

def add_blur(img: Image.Image, radius: float) -> Image.Image:
    if radius <= 0:
        return img
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def add_paper_texture(img: Image.Image, strength: float) -> Image.Image:
    """low-frequency luminance variation — paper substrate baked into the print"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # coarse noise upsampled smoothly — reads as surface, not grain
    scale = 10
    nh, nw = max(2, h // scale), max(2, w // scale)
    coarse = np.random.uniform(0, 1, (nh, nw)).astype(np.float32)
    texture = Image.fromarray((coarse * 255).astype(np.uint8), mode="L")
    texture = texture.resize((w, h), resample=Image.BILINEAR)
    t = np.asarray(texture, dtype=np.float32) / 255.0
    # only darkens — paper surface absorbs light unevenly
    multiplier = 1.0 - strength * (1.0 - t) * 0.5
    multiplier = np.stack([multiplier] * 3, axis=-1)
    return Image.fromarray(np.clip(arr * multiplier, 0, 255).astype(np.uint8))


def add_warm_toning(img: Image.Image, strength: float) -> Image.Image:
    """shift toward warm — aged ink and paper"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    arr[..., 0] = np.clip(arr[..., 0] * (1.0 + strength * 0.10), 0, 255)  # lift R
    arr[..., 2] = np.clip(arr[..., 2] * (1.0 - strength * 0.08), 0, 255)  # pull B
    return Image.fromarray(arr.astype(np.uint8))


# ── SCAN PASS ─────────────────────────────────────────────────────────────────

def add_chromatic_aberration(img: Image.Image, strength: float) -> Image.Image:
    """per-frame R/B channel shift — scan misregistration"""
    if strength <= 0:
        return img
    r, g, b = img.split()
    theta = random.uniform(0, 2 * math.pi)
    dx = int(strength * math.cos(theta))
    dy = int(strength * math.sin(theta))
    r = ImageChops.offset(r, dx, dy)
    b = ImageChops.offset(b, -dx, -dy)
    return Image.merge("RGB", (r, g, b))


def add_scan_bands(img: Image.Image, strength: float) -> Image.Image:
    """horizontal exposure banding — scanner light source artifact"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    h = arr.shape[0]
    bands = np.random.normal(1.0, strength * 0.12, h).astype(np.float32)
    bands = np.clip(bands, 1.0 - strength * 0.4, 1.0 + strength * 0.15)
    arr = arr * bands[:, np.newaxis, np.newaxis]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def add_vignette(img: Image.Image, strength: float) -> Image.Image:
    """darken corners — print/scanner edge falloff"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cy, cx = h / 2.0, w / 2.0
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
    mask = 1.0 - strength * np.clip(dist, 0, 1) ** 1.5
    mask = np.stack([mask] * 3, axis=-1)
    return Image.fromarray(np.clip(arr * mask, 0, 255).astype(np.uint8))


def add_luminous_grain(img: Image.Image, sigma: float) -> Image.Image:
    """overlay-style grain weighted by luminance — no grain in pure blacks"""
    if sigma <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    noise = np.random.normal(0.0, sigma, arr.shape).astype(np.float32)
    luminance = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
    luminance = np.stack([luminance] * 3, axis=-1)
    result = arr + (noise * (luminance ** 0.5))
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def add_dust(img: Image.Image, strength: float, opacity: float = 1.0) -> Image.Image:
    """sparse bright specks — dust on scanner glass"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32).copy()
    h, w = arr.shape[:2]
    n = int(strength * h * w * 0.00015)
    ys = np.random.randint(0, h, n)
    xs = np.random.randint(0, w, n)
    brightness = np.random.uniform(160, 255, n)
    arr[ys, xs] = arr[ys, xs] * (1 - opacity) + brightness[:, np.newaxis] * opacity
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ── VIDEO PASS ────────────────────────────────────────────────────────────────

def wobble(img: Image.Image, dx: int, dy: int, angle: float) -> Image.Image:
    """rotate then translate — the compiled object moves in its frame"""
    w, h = img.size
    rotated = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(0, 0, 0))
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(rotated, (dx, dy))
    return canvas


# ── WALK ──────────────────────────────────────────────────────────────────────

def smooth_walk(n: int, lo: float, hi: float, step: float = 0.15) -> list[float]:
    if lo == hi:
        return [lo] * n
    v = random.uniform(lo, hi)
    span = hi - lo
    out = []
    for _ in range(n):
        out.append(v)
        v = max(lo, min(hi, v + random.gauss(0, span * step)))
    return out


# ── PROCESS ───────────────────────────────────────────────────────────────────

def process(
    input_dir: Path,
    output_dir: Path,
    px_range: tuple[float, float],
    deg_range: tuple[float, float],
    grain_range: tuple[float, float],
    blur_range: tuple[float, float],
    aberration: float,
    vignette: float,
    bands: float,
    texture: float,
    warm: float,
    dust: float,
    dust_opacity: float,
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

    grain_sigmas = [v * 25 for v in smooth_walk(n, *grain_range)]
    blur_radii   = smooth_walk(n, *blur_range)

    print(f"processing {n} frames\n  input : {input_dir}\n  output: {output_dir}")

    for i, src in tqdm(enumerate(frames), total=n, unit="frame", dynamic_ncols=True):
        img = Image.open(src).convert("RGB")

        # ── print pass ────────────────────────────────────────────────────────
        img = add_blur(img, blur_radii[i])
        img = add_paper_texture(img, texture)
        img = add_warm_toning(img, warm)

        # ── scan pass ─────────────────────────────────────────────────────────
        img = add_chromatic_aberration(img, aberration)
        img = add_scan_bands(img, bands)
        img = add_vignette(img, vignette)
        img = add_luminous_grain(img, grain_sigmas[i])
        img = add_dust(img, dust, dust_opacity)

        # ── video pass ────────────────────────────────────────────────────────
        mag   = random.uniform(*px_range)
        theta = random.uniform(0, 2 * math.pi)
        dx    = int(mag * math.cos(theta))
        dy    = int(mag * math.sin(theta))
        rot   = random.uniform(*deg_range) * random.choice((-1, 1))
        img   = wobble(img, dx, dy, rot)

        img.save(output_dir / src.name)

    print("done")


def main() -> None:
    p = argparse.ArgumentParser(
        description="apply analog degradation to a PNG frame sequence",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("input",  type=Path, help="source frame folder (frames_raw/)")
    p.add_argument("output", type=Path, help="output folder (frames_wobbled/)")
    p.add_argument("--px",          nargs=2, type=float, default=[3.0, 6.0],  metavar=("MIN", "MAX"), help="translation range in pixels")
    p.add_argument("--deg",         nargs=2, type=float, default=[0.3, 0.8],  metavar=("MIN", "MAX"), help="rotation range in degrees")
    p.add_argument("--grain",       nargs=2, type=float, default=[0.3, 0.8],  metavar=("LO",  "HI"),  help="scan grain intensity 0–1")
    p.add_argument("--blur",        nargs=2, type=float, default=[0.0, 0.0],  metavar=("MIN", "MAX"), help="ethereal base blur radius range")
    p.add_argument("--aberration",  type=float, default=0.0,  help="chromatic aberration in pixels")
    p.add_argument("--vignette",    type=float, default=0.0,  help="vignette strength 0–1")
    p.add_argument("--bands",       type=float, default=0.0,  help="scan band intensity 0–1")
    p.add_argument("--texture",     type=float, default=0.0,  help="paper texture strength 0–1")
    p.add_argument("--warm",        type=float, default=0.0,  help="warm toning strength 0–1")
    p.add_argument("--dust",         type=float, default=0.0,  help="dust speck density 0–1")
    p.add_argument("--dust-opacity", type=float, default=1.0,  help="dust speck opacity 0–1 (blends with underlying pixel)")
    p.add_argument("--seed",         type=int,   default=None, help="RNG seed for reproducible output")
    args = p.parse_args()

    process(
        args.input,
        args.output,
        px_range   = (args.px[0],    args.px[1]),
        deg_range  = (args.deg[0],   args.deg[1]),
        grain_range= (args.grain[0], args.grain[1]),
        blur_range = (args.blur[0],  args.blur[1]),
        aberration = args.aberration,
        vignette   = args.vignette,
        bands      = args.bands,
        texture    = args.texture,
        warm       = args.warm,
        dust         = args.dust,
        dust_opacity = args.dust_opacity,
        seed         = args.seed,
    )


if __name__ == "__main__":
    main()
