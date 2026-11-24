"""Named palettes in the same HSV coordinates as the object controls."""
import colorsys
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    key: str
    label: str
    colors: tuple


def hsv(hex_color):
    return colorsys.rgb_to_hsv(*(int(hex_color[i:i+2], 16)/255 for i in (1, 3, 5)))


def matches_ranges(values, ranges):
    return all(path in ranges and all(abs(sample - value) < 1e-9 for sample in ranges[path])
               for path, value in values.items())
