"""Source-agnostic spatial regions. No preset, module IDs or model knowledge."""
from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class LocalFrame:
    origin: tuple[float, float]
    unit: float
    angle: float = 0.


@dataclass(frozen=True)
class DirectionalRegion:
    start: float = 0.
    width: float = .5
    angle: float = 0.
    x: float = 0.
    y: float = 0.
    strength: float = 1.
    smooth: bool = True

    def evaluate(self, size, frame):
        values = (*frame.origin, frame.unit, frame.angle, self.start, self.width,
                  self.angle, self.x, self.y, self.strength)
        if not all(math.isfinite(v) for v in values) or frame.unit <= 0 or self.width <= 0 or not 0 <= self.strength <= 1:
            raise ValueError('Region needs finite coordinates, positive width/scale and strength between 0 and 1')
        w, h = size
        y, x = np.mgrid[:h, :w]
        a = math.radians(frame.angle)
        ox = frame.origin[0] + (self.x * math.cos(a) + self.y * math.sin(a)) * frame.unit
        oy = frame.origin[1] + (-self.x * math.sin(a) + self.y * math.cos(a)) * frame.unit
        angle = math.radians(frame.angle + self.angle)
        distance = ((x - ox) * math.sin(angle) + (y - oy) * math.cos(angle))
        distance /= frame.unit
        blend = np.clip((distance - self.start) / self.width, 0, 1)
        if self.smooth:
            blend = blend * blend * (3 - 2 * blend)
        return blend * self.strength
