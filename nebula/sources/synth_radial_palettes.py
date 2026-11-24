"""Color-only presets for a repeating, eight-stop gradient."""
from nebula.sources.synth_palettes import Palette, hsv
from nebula.sources.synth_radial_gradients import CHANNELS, STOP_KEYS


def palette(key, name, colors):
    return Palette(key, name, tuple(map(hsv, colors.split())))


PALETTES = (
    palette('petrol', 'Petrol / copper',
            '#F4BF87 #D68255 #924835 #402C31 #0B1E27 #145763 #368D92 #A9CBBB'),
    palette('ultraviolet', 'Ultraviolet / ice',
            '#E6CCFF #AC83E4 #7544B7 #40206D #15132E #244679 #4F9BB7 #B3E0E8'),
    palette('ember', 'Ember / amber',
            '#FFD480 #FF9B40 #D55434 #7C2631 #281629 #512039 #A84A49 #F2A373'),
    palette('jade', 'Jade / celadon',
            '#E1EAC1 #AFCC94 #629D79 #306B62 #153A40 #245861 #638F8B #B4D5BA'),
    palette('silver', 'Silver / graphite',
            '#EAEBE7 #C6CBCC #8E989E #48515A #191D24 #373B42 #767676 #BBBBB3'),
)
COLOR_PATHS = tuple(f'radial_bloom.{stop}_{channel}' for stop in STOP_KEYS for channel in CHANNELS)


def palette_values(selected):
    return dict(zip(COLOR_PATHS, (value for color in selected.colors for value in color), strict=True))
