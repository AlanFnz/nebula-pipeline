"""Shared ink colors for renderers, object controls and their menu swatches."""
import colorsys
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    key: str
    label: str
    colors: tuple


def hsv(hex_color):
    return colorsys.rgb_to_hsv(*(int(hex_color[i:i+2], 16)/255 for i in (1, 3, 5)))


def gradient_palette(key, label, hex_colors):
    return Palette(key, label, tuple(hsv(color) for color in hex_colors.split()))


# The eight inks form a cycle: highlight, pale primary, primary, shade,
# deepest ink, secondary shade, secondary, pale secondary. Smaller ink sets
# take specific roles from this cycle. Append new palettes after published ones:
# numbered effect controls store their choice index in the document.
SHARED_PALETTES = (
    gradient_palette('pearl-eclipse', 'Pearl eclipse',
                     '#F7E5DE #F5D8D6 #F3C3B8 #BCAEBA #352D38 #565661 #858396 #DDC7D5'),
    gradient_palette('neon-ridge', 'Neon ridge',
                     '#C7B6DD #C43CB2 #D30FA5 #791154 #050505 #0F343C #3AB2D1 #82A1BE'),
    gradient_palette('sodium-arcade', 'Sodium arcade',
                     '#EBD3A0 #ECA86B #DB7353 #9B2830 #310607 #132D30 #099EBC #67B0A8'),
    gradient_palette('carmine-collage', 'Carmine collage',
                     '#F9C9C6 #EF8093 #DE212A #792632 #190002 #36235F #9E3184 #F278A9'),
    gradient_palette('cobalt-cutout', 'Cobalt cutout',
                     '#BFCAF4 #B7C3F2 #FA3329 #714569 #09347B #146D59 #2B518F #749FAE'),
    gradient_palette('solar-bands', 'Solar bands',
                     '#EFEA9F #EED53A #D61D22 #AE1919 #110A14 #643C2D #42B248 #B0D050'),
    gradient_palette('opal-glass', 'Opal glass',
                     '#F9F4D6 #DBC27C #D5AB4E #957265 #206B96 #249794 #36A553 #A6CDCF'),
    gradient_palette('blue-porcelain', 'Blue porcelain',
                     '#FBDDF6 #BCADFA #5362FB #4355FB #474DFB #8A8AFB #EBC4F7 #F3D2F6'),
)


class PaletteTable:
    """Keep native indices, then append the shared inks used by this renderer."""

    def __init__(self, native, slots=range(8)):
        self.labels = tuple(label for label, _ in native) + tuple(p.label for p in SHARED_PALETTES)
        shared = tuple(tuple(p.colors[i] for i in slots) for p in SHARED_PALETTES)
        self.swatches = tuple(tuple(colorsys.rgb_to_hsv(*c) for c in inks) for _, inks in native) + shared
        self.rgb = tuple(inks for _, inks in native) + tuple(
            tuple(colorsys.hsv_to_rgb(*color) for color in inks) for inks in shared)

    def parameter(self, P, label='Palette', default=0):
        return P('palette', label, default, 0, len(self.labels) - 1, 1,
                 choices=self.labels, swatches=self.swatches)


def matches_ranges(values, ranges):
    return all(path in ranges and all(abs(sample - value) < 1e-9 for sample in ranges[path])
               for path, value in values.items())
