#!/usr/bin/env python3
"""
analog-wobble.py
apply per-frame analog degradation to a PNG sequence

two-pass pipeline mirrors the physical process:

  PRINT PASS  — blur · paper texture · warm toning
  SCAN PASS   — aberration · bands · scanlines · bloom · curvature · vignette · grain · dust
  VIDEO       — wobble
"""

import argparse
import math
import random
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter
from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress,
    TextColumn, TimeElapsedColumn, TimeRemainingColumn,
)

_console = Console()


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


def add_scanlines(img: Image.Image, strength: float, spacing: int = 2) -> Image.Image:
    """darken every Nth row — CRT electron beam gap"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32).copy()
    arr[::spacing] *= (1.0 - strength)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def add_bloom(img: Image.Image, strength: float, radius: float = 8.0) -> Image.Image:
    """bright areas bleed light onto neighbors — phosphor glow"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
    bright_mask = np.clip(lum * 2.0 - 0.5, 0, 1)
    bright = arr * np.stack([bright_mask] * 3, axis=-1)
    blurred = Image.fromarray(np.clip(bright, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=radius)
    )
    blurred_arr = np.asarray(blurred, dtype=np.float32)
    return Image.fromarray(np.clip(arr + blurred_arr * strength, 0, 255).astype(np.uint8))


def add_curvature(img: Image.Image, strength: float) -> Image.Image:
    """barrel distortion + rounded corner mask — CRT curved glass and screen shape"""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cy, cx = h / 2.0, w / 2.0

    Y, X = np.mgrid[0:h, 0:w]
    nx = (X - cx) / cx
    ny = (Y - cy) / cy

    # barrel distortion — center magnified, edges compressed
    r2     = nx ** 2 + ny ** 2
    factor = 1.0 / (1.0 + strength * r2)
    src_x  = nx * factor * cx + cx
    src_y  = ny * factor * cy + cy

    x0 = np.clip(np.floor(src_x).astype(np.int32), 0, w - 1)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y0 = np.clip(np.floor(src_y).astype(np.int32), 0, h - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)

    wx = (src_x - np.floor(src_x))[..., np.newaxis]
    wy = (src_y - np.floor(src_y))[..., np.newaxis]

    result = (
        arr[y0, x0] * (1 - wx) * (1 - wy) +
        arr[y0, x1] * wx       * (1 - wy) +
        arr[y1, x0] * (1 - wx) * wy       +
        arr[y1, x1] * wx       * wy
    )

    # corner mask — distance to nearest corner; straight edges stay untouched
    dist_to_corner = np.sqrt((np.abs(nx) - 1.0) ** 2 + (np.abs(ny) - 1.0) ** 2)
    inner = strength * 0.15
    outer = inner + strength * 0.25
    corner_mask = np.clip((dist_to_corner - inner) / (outer - inner), 0, 1)
    result *= corner_mask[..., np.newaxis]

    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


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


def add_brightness(img: Image.Image, strength: float) -> Image.Image:
    """global brightness multiplier — compensate for cumulative darkening"""
    if strength == 1.0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    return Image.fromarray(np.clip(arr * strength, 0, 255).astype(np.uint8))


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


def _drift_walk(n: int, value: float, drift: float) -> list[float]:
    """smooth_walk around a fixed value — drift 0 = static, 1 = ±35% variation"""
    if drift <= 0 or value == 0:
        return [value] * n
    half = value * drift * 0.35
    return smooth_walk(n, max(0.0, value - half), value + half)


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
    scanlines: float,
    bloom: float,
    curvature: float,
    brightness: float,
    seed: int | None,
    drift: float = 0.0,
) -> None:
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    frames = sorted_frames(input_dir)
    if not frames:
        raise SystemExit(f"no PNG files found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    n = len(frames)

    grain_sigmas    = [v * 25 for v in smooth_walk(n, *grain_range)]
    blur_radii      = smooth_walk(n, *blur_range)
    aberration_vals = _drift_walk(n, aberration, drift)
    bands_vals      = _drift_walk(n, bands,      drift)
    brightness_vals = _drift_walk(n, brightness, drift)
    warm_vals       = _drift_walk(n, warm,       drift)

    _console.print(f"  [dim]input :[/]  {input_dir}")
    _console.print(f"  [dim]output:[/]  {output_dir}\n")

    _progress = Progress(
        TextColumn("  [dim]{task.description}[/]"),
        BarColumn(bar_width=40, style="color(238)", complete_style="color(214)"),
        MofNCompleteColumn(),
        TextColumn("[dim]fr[/]"),
        TimeElapsedColumn(),
        TextColumn("[dim]·[/]"),
        TimeRemainingColumn(),
        console=_console,
    )
    with _progress:
        task = _progress.add_task("wobbling", total=n)
        for i, src in enumerate(frames):
            img = Image.open(src).convert("RGB")

            # ── print pass ────────────────────────────────────────────────────
            img = add_blur(img, blur_radii[i])
            img = add_paper_texture(img, texture)
            img = add_warm_toning(img, warm_vals[i])

            # ── scan pass ─────────────────────────────────────────────────────
            img = add_chromatic_aberration(img, aberration_vals[i])
            img = add_scan_bands(img, bands_vals[i])
            img = add_scanlines(img, scanlines)
            img = add_bloom(img, bloom)
            img = add_curvature(img, curvature)
            img = add_vignette(img, vignette)
            img = add_luminous_grain(img, grain_sigmas[i])
            img = add_dust(img, dust, dust_opacity)
            img = add_brightness(img, brightness_vals[i])

            # ── video pass ────────────────────────────────────────────────────
            mag   = random.uniform(*px_range)
            theta = random.uniform(0, 2 * math.pi)
            dx    = int(mag * math.cos(theta))
            dy    = int(mag * math.sin(theta))
            rot   = random.uniform(*deg_range) * random.choice((-1, 1))
            img   = wobble(img, dx, dy, rot)

            img.save(output_dir / src.name)
            _progress.advance(task)


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
    p.add_argument("--scanlines",    type=float, default=0.0,  help="scanline darkness 0–1")
    p.add_argument("--bloom",        type=float, default=0.0,  help="phosphor bloom strength 0–1")
    p.add_argument("--curvature",    type=float, default=0.0,  help="barrel distortion strength 0–1")
    p.add_argument("--brightness",   type=float, default=1.0,  help="global brightness multiplier (1.0 = no change)")
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
        scanlines    = args.scanlines,
        bloom        = args.bloom,
        curvature    = args.curvature,
        brightness   = args.brightness,
        seed         = args.seed,
    )


if __name__ == "__main__":
    main()
