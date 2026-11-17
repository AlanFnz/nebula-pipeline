"""Stateless line-by-line typography; the ordinary Text source owns the wording."""
import math

import numpy as np
from PIL import Image, ImageChops


def scroll_mask(p, time, speed, size, reference_size, offset):
    from synth_text import glyph_mask, letterpress_settings, text_pose
    w, h = size; cw, ch = reference_size
    clock, zoom = text_pose(p, time, speed)
    position = max(0., p['scroll_position'] + clock * p['scroll_rate'])
    lines = p['content'].split('\n')
    position = min(len(lines), position)
    press = letterpress_settings(p, clock)
    masks = [glyph_mask(line, p['font'], p['tracking'], 1., p['align'],
                        weight=p['weight'], press=press) for line in lines]
    cap = glyph_mask('H', p['font'], 0., 1., 1, weight=p['weight']).height
    sy = ch * p['size'] * p['stretch_y'] * zoom / cap
    sx = sy * p['stretch_x'] / p['stretch_y']
    width = max(m.width for m in masks)
    if p['fit'] == 1:
        fit = min(1., cw * p['fit_width'] / max(1., width * sx))
        sx *= fit; sy *= fit
    elif p['fit'] == 2:
        sx = cw * p['block_width'] * zoom / max(1., width)
    height = cap * sy
    stride = height * p['leading']
    bottom = h / 2 + offset[1] + ch * p['scroll_bottom']
    top = bottom - stride * p['scroll_window']
    cx = w / 2 + offset[0]
    result = Image.new('L', (w, h))
    for index, mask in enumerate(masks):
        arrival = position - index
        if arrival <= 0: break
        opacity = min(1., max(0., (arrival - .65) / .35))
        y = bottom - (position - index - 1) * stride - mask.height * sy
        if y + mask.height * sy < top or y > bottom or not opacity: continue
        mw, mh = mask.width*sx, mask.height*sy
        x = cx - width * sx / 2 + (width * sx - mw) * p['align'] / 2
        left, above = max(0, math.floor(x)), max(0, math.floor(y))
        right, below = min(w, math.ceil(x+mw)), min(h, math.ceil(y+mh))
        if right<=left or below<=above: continue
        # Only allocate the visible footprint, even at maximum size/stretch.
        stamp = mask.transform((right-left, below-above), Image.Transform.AFFINE,
            (1/sx,0,(left-x)/sx,0,1/sy,(above-y)/sy), Image.Resampling.BICUBIC)
        if opacity < 1: stamp = stamp.point(lambda v: round(v * opacity))
        box = (left, above, right, below)
        result.paste(ImageChops.lighter(result.crop(box), stamp), box[:2])
    rows = np.arange(h, dtype=np.float32)
    feather = max(.25, ch * p['scroll_edge'])
    clip = np.clip((rows-top)/feather, 0, 1) * np.clip((bottom-rows)/feather, 0, 1)
    result = Image.fromarray((np.asarray(result)*clip[:, None]).astype(np.uint8))
    if p['rotation']:
        result = result.rotate(-p['rotation'], Image.Resampling.BICUBIC, center=(cx, h/2+offset[1]))
    return result
