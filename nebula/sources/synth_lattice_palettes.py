"""Color-only starting points for the printed lattice; authored as existing values.

The warm and mineral palettes are artistic interpretations inspired by Buddhist
painting materials, not prescribed religious color schemes. No render defaults
or effect activation change when the menu is opened.
"""
from dataclasses import dataclass
from nebula.sources.synth_palettes import Palette, hsv, matches_ranges


@dataclass(frozen=True)
class LatticePalette(Palette):
    accents: tuple  # Existing Broadcast wear field, halo and edge hues.


def palette(key, label, colors, accents):
    return LatticePalette(key, label, tuple(map(hsv, colors)), accents)


PALETTES = (
    LatticePalette('original', 'Original · Jade / violet',
                   ((.39,.46,.64),(.87,.56,.97),(.16,.24,.145),(.19,.15,.87),(.16,.34,.055)),
                   (.55,.84,.8)),
    palette('saffron', 'Saffron / garnet',
            ('#DDA343','#B95F6A','#23141C','#F0DCA9','#1D1017'),(.03,.10,.06)),
    palette('indigo', 'Indigo / gold',
            ('#6689D6','#D9B45A','#131B35','#E7DEC2','#10172B'),(.63,.12,.62)),
    palette('jade', 'Jade / copper',
            ('#6BAC91','#D68D64','#142723','#E8DFC3','#0E1B17'),(.36,.38,.08)),
    palette('lotus', 'Lotus / ivory',
            ('#CC83A2','#DDD0AC','#30212F','#F0DFCF','#21131D'),(.94,.94,.09)),
    palette('mineral', 'Turquoise / vermilion',
            ('#4BA8AE','#D16C52','#172831','#E6D3A5','#102129'),(.58,.50,.04)),
)


def palette_values(key, *, eye=True, broadcast=False):
    selected = next(p for p in PALETTES if p.key == key)
    names = ('face_a','face_b','paper','eye','eye_ink')[:5 if eye else 3]
    values = {f'chromatic_lattice.{name}_{channel}': value
              for name, color in zip(names, selected.colors)
              for channel, value in zip(('hue','saturation','light'), color)}
    if broadcast:
        values.update(zip(('broadcast.hue','broadcast.halo_hue','broadcast.edge_hue'),selected.accents))
    return values


def matching_palette(ranges, *, eye=True, broadcast=False):
    """Custom/animated if any authored color differs across the editing scope."""
    for candidate in PALETTES:
        values = palette_values(candidate.key, eye=eye, broadcast=broadcast)
        if matches_ranges(values, ranges):
            return candidate.key
    return None
