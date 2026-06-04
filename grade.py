#!/usr/bin/env python3
"""
grade.py — color grade pass: frames_wobbled/ → frames_treated/

can be run standalone or chained via pipeline.py --grade

effects applied in order:
  contrast     S-curve — darken shadows, brighten highlights
  shadows      crush dark regions toward black
  highlights   boost bright regions toward white
  toning       split toning — teal shadows + amber highlights
"""

import argparse
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path

import numpy as np
from PIL import Image
from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress,
    TextColumn, TimeElapsedColumn, TimeRemainingColumn,
)

_console = Console()

# teal shadows, amber highlights — warm/cold color tension
_SHADOW_COLOR    = np.array([-25.0,  10.0,  25.0], dtype=np.float32)
_HIGHLIGHT_COLOR = np.array([ 25.0,   8.0, -20.0], dtype=np.float32)


def apply_contrast(arr: np.ndarray, strength: float) -> np.ndarray:
    """S-curve contrast — pivot at midtone, shadows darker, highlights brighter"""
    if strength <= 0:
        return arr
    x = arr / 255.0
    delta = strength * x * (1.0 - x) * (2.0 * x - 1.0) * 4.0
    return np.clip((x + delta) * 255.0, 0.0, 255.0)


def apply_shadow_crush(arr: np.ndarray, strength: float) -> np.ndarray:
    """push dark regions toward black — quadratic weight, no effect on highlights"""
    if strength <= 0:
        return arr
    x = arr / 255.0
    return np.clip((x - strength * (1.0 - x) ** 2) * 255.0, 0.0, 255.0)


def apply_highlight_boost(arr: np.ndarray, strength: float) -> np.ndarray:
    """lift bright regions toward white — quadratic weight, no effect on shadows"""
    if strength <= 0:
        return arr
    x = arr / 255.0
    return np.clip((x + strength * x ** 2) * 255.0, 0.0, 255.0)


def apply_split_toning(arr: np.ndarray, strength: float) -> np.ndarray:
    """teal shadows + amber highlights — luminance-weighted color push"""
    if strength <= 0:
        return arr
    lum         = (arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114) / 255.0
    shadow_w    = ((1.0 - lum) ** 2)[..., np.newaxis]
    highlight_w = (lum ** 2)[..., np.newaxis]
    result      = arr + strength * (_SHADOW_COLOR * shadow_w + _HIGHLIGHT_COLOR * highlight_w)
    return np.clip(result, 0.0, 255.0)


def process(
    input_dir:  Path,
    output_dir: Path,
    contrast:   float = 0.4,
    shadows:    float = 0.15,
    highlights: float = 0.05,
    toning:     float = 0.4,
    progress: Progress | None = None,
    task_id: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = sorted(input_dir.glob("*.png"))
    if not frames:
        raise SystemExit(f"no PNG frames in {input_dir}")

    _own = progress is None
    if _own:
        if on_progress is not None:
            from rich.console import Console as _C
            progress = Progress(console=_C(quiet=True))
        else:
            progress = Progress(
                TextColumn("  [dim]{task.description}[/]"),
                BarColumn(bar_width=40, style="color(238)", complete_style="color(214)"),
                MofNCompleteColumn(),
                TextColumn("[dim]fr[/]"),
                TimeElapsedColumn(),
                TextColumn("[dim]·[/]"),
                TimeRemainingColumn(),
                console=_console,
            )

    with (progress if _own else nullcontext()):
        if task_id is not None:
            progress.update(task_id, total=len(frames))
            task = task_id
        else:
            task = progress.add_task("grading", total=len(frames))
        for src in frames:
            img = Image.open(src).convert("RGB")
            arr = np.asarray(img, dtype=np.float32)
            arr = apply_contrast(arr, contrast)
            arr = apply_shadow_crush(arr, shadows)
            arr = apply_highlight_boost(arr, highlights)
            arr = apply_split_toning(arr, toning)
            Image.fromarray(arr.astype(np.uint8)).save(output_dir / src.name)
            progress.advance(task)
            if on_progress is not None:
                on_progress(i + 1, len(frames))


def main() -> None:
    p = argparse.ArgumentParser(
        description="color grade — frames_wobbled/ → frames_treated/",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("project",      type=Path,  help="project root directory")
    p.add_argument("--contrast",   type=float, default=0.4,  help="S-curve contrast 0–1")
    p.add_argument("--shadows",    type=float, default=0.15, help="shadow crush 0–1")
    p.add_argument("--highlights", type=float, default=0.05, help="highlight boost 0–1")
    p.add_argument("--toning",     type=float, default=0.4,  help="split toning strength 0–1")
    args = p.parse_args()

    wobbled = args.project / "frames_wobbled"
    treated = args.project / "frames_treated"

    if not wobbled.exists():
        raise SystemExit(f"error: {wobbled} not found — run pipeline.py first")

    print(f"grading {wobbled} → {treated}")
    process(
        wobbled, treated,
        contrast=args.contrast, shadows=args.shadows,
        highlights=args.highlights, toning=args.toning,
    )

    count = len(list(treated.glob("*.png")))
    print(f"\ngraded {count} frames → {treated}")
    print(f"run:  python assemble.py {args.project}")


if __name__ == "__main__":
    main()
