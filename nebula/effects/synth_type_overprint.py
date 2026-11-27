"""Independent ink impressions. Lettering and cut plates share the print kernels."""
import math
import numpy as np
from PIL import Image, ImageChops

from nebula.core.synth_canvas import content_size
from nebula.effects.synth_dye_transfer import deposited_plate
from nebula.effects.synth_print import textured_type_mask, type_grain_controls
from nebula.sources.synth_text import FONTS, color, glyph_mask, placed_text_mask


def modules(Module, P, definitions):
    common = (
        P('content', 'Wording', 'STUDIO EDITION', kind='text'),
        P('font', 'Typeface', 0, 0, len(FONTS) - 1, 1, choices=FONTS, kind='font'),
        P('height', 'Type block height', .035, .003, 1., .001, 'Height relative to the artwork. The type keeps its proportions.'),
        P('width', 'Maximum width', .85, .01, 1.5, .01, 'Shrink the whole block proportionally if the wording exceeds this width.'),
        P('x', 'Center X', .5, -.5, 1.5, .001, 'Position within the artwork. 0 is the left edge and 1 is the right edge.'),
        P('y', 'Center Y', .94, -.5, 1.5, .001, 'Position within the artwork. 0 is the top and 1 is the bottom.'),
        P('tracking', 'Letter spacing', 0., -.15, .8, .005),
        P('hue', 'Ink hue', 0., 0, 1, .01),
        P('saturation', 'Ink saturation', 0., 0, 1, .01),
        P('light', 'Ink brightness', .15, 0, 3, .01),
        *type_grain_controls(P),
    )
    excluded = {p.key for p in common} | {'brightness', 'back_hue', 'back_saturation', 'back_brightness',
                                           'paper_grain', 'paper_grain_size'}
    lettering = tuple(p for p in definitions['text'] if p.key not in excluded)
    plate = tuple(p for p in definitions['dye_transfer'] if p.key.startswith('mask_')
                  and p.key != 'mask_target' and not p.key.startswith(('mask_paper_', 'mask_ink_')))
    return (Module('type_overprint', 'Type overprint', 'Print lettering or a separate ink plate over the image.',
                   common + (P('layout', 'Impression', 0, 0, 2, 1,
                               choices=('Type block', 'Source lettering', 'Ink plate')),) + lettering + plate),)


def type_stamp(p, preset, output):
    """Return the scaled glyphs and their origin in canvas coordinates."""
    w, h = output
    cw, ch = content_size(preset, (w, h))
    mask = glyph_mask(p['content'], p['font'], p['tracking'], 1., 1)
    scale = min(ch * p['height'] / mask.height, cw * p['width'] / mask.width)
    size = (max(1, round(mask.width * scale)), max(1, round(mask.height * scale)))
    left = round(w / 2 + (p['x'] - .5) * cw - size[0] / 2)
    top = round(h / 2 + (p['y'] - .5) * ch - size[1] / 2)
    if left >= w or top >= h or left + size[0] <= 0 or top + size[1] <= 0:
        return None, (left, top)
    return mask.resize(size, Image.Resampling.LANCZOS), (left, top)


def impression_stamp(p, preset, size, identity, seconds, *, material=True):
    if p.get('layout') == 1:
        cw, ch = content_size(preset, (preset['width'], preset['height']))
        positioned = dict(preset, object_x=(p['x'] - .5) * cw, object_y=(p['y'] - .5) * ch)
        stamp = placed_text_mask(p, seconds, positioned, size)
        if material and (p.get('ink_grain') or p.get('ink_pinholes')):
            worn = placed_text_mask(p, seconds, positioned, size, print_ink=True)
            stamp = ImageChops.darker(stamp, worn)
        return stamp, (0, 0)
    if not p['content'].strip():
        return None, (0, 0)
    stamp, origin = type_stamp(p, preset, size)
    if stamp is not None and material and (p.get('ink_grain') or p.get('ink_pinholes')):
        impression = int(identity.partition('@')[2] or 1)
        w, h = size
        stamp = textured_type_mask(stamp, p, preset['seed'], content_size(preset, (w, h))[0] / 720,
                                   impression=impression)
    return stamp, origin


def plate_ink(p, preset, size, identity, time, *, material=True):
    from nebula.render.synth import _seed
    w, h = size
    if not p['mask_shape'] or not p['mask_opacity']:
        return np.zeros((h, w, 1), np.float32), 0.
    reference = content_size(preset, size)
    seed = _seed(preset['seed'], identity)
    yy, xx = np.indices((h, w), dtype=np.float32)
    dry = p['mask_dry_ink'] if material else 0.
    tick = math.floor(time * preset['speed'] * preset['treatment_fps'] + 1e-7)
    alpha, density, grain = deposited_plate(xx, yy, p, reference, (0., 0.), seed, tick, dry)
    pigment = color(p['hue'], p['saturation'], p['light'])
    if density is not None:
        pigment = np.power(pigment, density)
    if dry:
        pigment = pigment + (grain * dry * .056)[..., None]
    return alpha, pigment


def render_type_overprint(image, p, time, preset, index):
    h, w = image.shape[:2]
    identity = preset['modules'][index]['id']
    if p.get('layout') == 2:
        if not p['mask_shape'] or not p['mask_opacity']:
            return image
        alpha, pigment = plate_ink(p, preset, (w, h), identity, time)
        return image + alpha * (pigment - image)
    stamp, (left, top) = impression_stamp(p, preset, (w, h), identity, time)
    if stamp is None:
        return image
    x0, y0 = max(0, left), max(0, top)
    x1, y1 = min(w, left + stamp.width), min(h, top + stamp.height)
    alpha = np.asarray(stamp.crop((x0-left, y0-top, x1-left, y1-top)), dtype=np.float32)[..., None] / 255
    if p.get('layout') == 1:
        alpha *= p['opacity']
    result = image.copy()
    region = result[y0:y1, x0:x1]
    region += alpha * (color(p['hue'], p['saturation'], p['light']) - region)
    return result
