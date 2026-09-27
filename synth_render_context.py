"""Explicit inputs to reusable image treatments; optional coverage is lazy."""
from dataclasses import dataclass

import numpy as np

from synth_regions import LocalFrame


@dataclass(frozen=True)
class RenderContext:
    size: tuple[int, int]
    reference_size: tuple[float, float]
    continuous_time: float
    held_time: float
    speed: float
    seed: int
    reveal_canvas: bool = False


@dataclass(frozen=True)
class SourceOutput:
    image: np.ndarray
    frame: LocalFrame
    coverage: np.ndarray | None = None

    def signal_mask(self, threshold):
        # Preserve the image-derived mask used by all existing studies. Clean
        # source coverage is a separate capability, never an implicit substitute.
        return np.clip((self.image.max(axis=2) - threshold) / max(.001, 1 - threshold), 0, 1)
