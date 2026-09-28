"""Editable, portable typography. Rasterization and motion need no GUI runtime."""
from functools import lru_cache
from pathlib import Path
import colorsys
import math
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from synth_canvas import content_size, object_offset

FONTS = ('Archivo Black', 'Anton / condensed', 'Space Mono Bold')
FONT_FILES = ('ArchivoBlack-Regular.ttf', 'Anton-Regular.ttf', 'SpaceMono-Bold.ttf')


def validate_text(value):
    if not isinstance(value, str) or len(value) > 512 or value.count('\n') > 7:
        raise ValueError('Text supports up to 512 characters and eight lines.')
    if any(unicodedata.category(c) in ('Cc', 'Cs') and c != '\n' for c in value):
        raise ValueError('Text contains unsupported control characters.')
    return value


def color(hue, saturation, value):
    return np.array(colorsys.hsv_to_rgb(hue % 1, saturation, value), dtype=np.float32)


def text_pose(p, time, speed):
    clock = time * speed
    if p['cadence']: clock = math.floor(clock * p['cadence'] + 1e-8) / p['cadence']
    phase = (clock / p['period'] + p['phase']) % 1
    if p['motion'] == 1:
        zoom = p['zoom_end'] + (p['zoom_start'] - p['zoom_end']) * (1 - phase) ** p['ease']
    elif p['motion'] == 2:
        zoom = p['zoom_end'] + (p['zoom_start'] - p['zoom_end']) * (.5 + .5 * math.cos(phase * math.tau))
    else: zoom = 1.
    return clock, zoom


@lru_cache(maxsize=24)
def glyph_mask(text, font_index, tracking, leading, alignment, visible=None):
    """Bounded canonical masks keep preview/export type and spacing identical."""
    validate_text(text)
    if not text.strip(): return Image.new('L', (1, 1))
    path = Path(__file__).parent / 'assets/fonts' / FONT_FILES[font_index]
    lines = text.split('\n')
    font_size = 256
    font = ImageFont.truetype(str(path), font_size)
    def line_width(line):
        return max(0., font.getlength(line) + max(0, len(line) - 1) * tracking * font_size)
    extent = max(max(map(line_width, lines)), len(lines) * leading * font_size, 1)
    if extent > 3800:
        font_size = max(4, int(font_size * 3800 / extent))
        font = ImageFont.truetype(str(path), font_size)
    widths = [line_width(line) for line in lines]
    # Extra room preserves negative bearings, descenders and diacritics.
    padding = font_size
    width = max(1, math.ceil(max(widths)))
    image = Image.new('L', (min(4096, width + padding * 2), min(4096, math.ceil(len(lines) * leading * font_size + padding * 2))))
    draw = ImageDraw.Draw(image)
    partial = Image.new('L', image.size) if visible is not None else None
    revealed = ImageDraw.Draw(partial) if partial is not None else None
    index = 0
    for row, (line, length) in enumerate(zip(lines, widths)):
        x = padding + (width - length) * (alignment / 2)
        y = padding + font_size + row * font_size * leading
        # Pair advances preserve the font's kerning while adding tracking.
        for i, character in enumerate(line):
            draw.text((x, y), character, font=font, fill=255, anchor='ls')
            if revealed is not None and index < visible:
                revealed.text((x, y), character, font=font, fill=255, anchor='ls')
            index += 1
            advance = font.getlength(character)
            if i + 1 < len(line): advance = font.getlength(character + line[i + 1]) - font.getlength(line[i + 1])
            x += advance + tracking * font_size
        index += 1  # Newline consumes a character in the reveal clock.
    bounds = image.getbbox()
    if bounds:
        top = min(bounds[1], padding + font_size + font.getbbox('H', anchor='ls')[1])
        bottom = max(bounds[3], padding + font_size + (len(lines)-1) * leading * font_size)
        bounds = (bounds[0], int(top), bounds[2], math.ceil(bottom))
        return (partial if partial is not None else image).crop(bounds)
    return Image.new('L', (1, 1))


def text_layout(p, time, speed, size):
    cw, ch = size
    clock, zoom = text_pose(p, time, speed)
    text = p['content']; visible = None
    if p['reveal'] == 1:
        words = text.split()
        text = words[int(clock / p['word_seconds']) % len(words)] if words else ''
    elif p['reveal'] == 2:
        visible = int(clock / p['word_seconds']) % (len(text) + 1)
    mask = glyph_mask(text, p['font'], p['tracking'], p['leading'], p['align'], visible)
    # Fit is uniform. The explicit stretch controls are typography choices,
    # independent of changing the canvas aspect ratio.
    height = ch * p['size'] * max(1, text.count('\n') + 1)
    scale = height / max(1, mask.height)
    if p['fit']: scale = min(scale, cw * .9 / max(1, mask.width * p['stretch_x']))
    sx = max(.001, scale * p['stretch_x'] * zoom)
    sy = max(.001, scale * p['stretch_y'] * zoom)
    return mask, sx, sy


def render_text(arr, p, time, preset):
    h, w = arr.shape[:2]
    dx, dy = object_offset(preset, (w, h))
    mask, sx, sy = text_layout(p, time, preset['speed'], content_size(preset, (w, h)))
    angle = math.radians(p['rotation']); c, s = math.cos(angle), math.sin(angle)
    cx, cy = w / 2 + dx, h / 2 + dy
    coefficients = (c / sx, s / sx, mask.width / 2 - (c * cx + s * cy) / sx,
                    -s / sy, c / sy, mask.height / 2 - (-s * cx + c * cy) / sy)
    placed = mask.transform((w, h), Image.Transform.AFFINE, coefficients, Image.Resampling.BICUBIC)
    alpha = np.asarray(placed, dtype=np.float32) / 255 * p['opacity']
    ink = color(p['hue'], p['saturation'], p['brightness'])
    paper = color(p['back_hue'], p['back_saturation'], p['back_brightness'])
    return paper + alpha[..., None] * (ink - paper)
