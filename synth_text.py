"""Editable, portable typography. Rasterization and motion need no GUI runtime."""
from functools import lru_cache
from pathlib import Path
import colorsys
import math
import textwrap
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from synth_canvas import content_size, object_offset

FONTS = ('Archivo Black', 'Anton / condensed', 'Space Mono Bold', 'Bodoni Moda / serif', 'Fraunces / soft serif', 'Fredoka / rounded')
FONT_FILES = ('ArchivoBlack-Regular.ttf', 'Anton-Regular.ttf', 'SpaceMono-Bold.ttf', 'BodoniModa.ttf', 'Fraunces.ttf', 'Fredoka.ttf')


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
    elif p['motion'] == 3:
        # Constant travel in depth produces a fast initial apparent retreat.
        zoom = 1 / ((1-phase) / p['zoom_start'] + phase / p['zoom_end'])
    else: zoom = 1.
    return clock, zoom


@lru_cache(maxsize=24)
def glyph_mask(text, font_index, tracking, leading, alignment, visible=None, wrapped=False, weight=400):
    """Bounded canonical masks keep preview/export type and spacing identical."""
    # Layout can insert up to seven breaks into a valid 512-character source.
    validate_text(text.replace('\n', '') if wrapped else text)
    if text.count('\n') > 7: raise ValueError('Text supports up to eight lines.')
    if not text.strip(): return Image.new('L', (1, 1))
    path = Path(__file__).parent / 'assets/fonts' / FONT_FILES[font_index]
    lines = text.split('\n')
    font_size = 256
    font = ImageFont.truetype(str(path), font_size)
    if font_index == 3 and weight != 400: font.set_variation_by_axes([weight, 11])
    if font_index == 4: font.set_variation_by_axes([24, weight, 100, 1])
    if font_index == 5: font.set_variation_by_axes([min(700, weight), 100])
    def line_width(line):
        return max(0., font.getlength(line) + max(0, len(line) - 1) * tracking * font_size)
    extent = max(max(map(line_width, lines)), len(lines) * leading * font_size, 1)
    if extent > 3800:
        font_size = max(4, int(font_size * 3800 / extent))
        font = ImageFont.truetype(str(path), font_size)
        if font_index == 3 and weight != 400: font.set_variation_by_axes([weight, 11])
        if font_index == 4: font.set_variation_by_axes([24, weight, 100, 1])
        if font_index == 5: font.set_variation_by_axes([min(700, weight), 100])
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


@lru_cache(maxsize=64)
def wrapped_text(text, columns):
    """Keep source-character indices so inserted breaks do not consume reveal beats."""
    lines = text.split('\n')
    while True:
        wrapper = textwrap.TextWrapper(width=max(1, columns), replace_whitespace=False, break_on_hyphens=False)
        pieces = [wrapper.wrap(line) or [''] for line in lines]
        if sum(map(len, pieces)) <= 8: break
        columns += 1
    result = []; indices = []; offset = 0
    for line, chunks in zip(lines, pieces):
        cursor = 0
        for chunk in chunks:
            if result:
                result.append('\n'); indices.append(None)
            start = line.find(chunk, cursor)
            result.append(chunk)
            indices.extend(range(offset + start, offset + start + len(chunk)))
            cursor = start + len(chunk)
        offset += len(line) + 1
    return ''.join(result), tuple(indices)


def text_layout(p, time, speed, size):
    cw, ch = size
    clock, zoom = text_pose(p, time, speed)
    if p['reveal'] == 3:
        from synth_word_morph import morph_layout
        return morph_layout(p, clock, size, zoom)
    if p['reveal'] == 4:
        from synth_reading_montage import reading_beat
        beat = reading_beat(p, clock)
        mask = glyph_mask(beat.text, p['font'], p['tracking'], p['leading'], p['align'], weight=p.get('weight', 400))
        sx, sy = p['stretch_x'], p['stretch_y']
        # Fit complete units inside the authored canvas. Explicit line breaks
        # survive in the finale; long phrases are not silently wrapped.
        scale = min(ch * p['size'] * zoom / max(1, mask.height),
                    cw * min(.94, p.get('fit_width', .9)) / max(1, mask.width * sx),
                    ch * .65 / max(1, mask.height * sy))
        return mask, max(.001, scale * sx), max(.001, scale * sy)
    text = p['content']; visible = None
    if p['reveal'] == 1:
        words = text.split()
        text = words[int(clock / p['word_seconds']) % len(words)] if words else ''
    elif p['reveal'] == 2:
        visible = int(clock / p['word_seconds']) % (len(text) + 1)
    if p.get('wrap_columns', 0):
        text, indices = wrapped_text(text, p['wrap_columns'])
        if visible is not None:
            visible = max((i+1 for i, source in enumerate(indices) if source is not None and source < visible), default=0)
    mask = glyph_mask(text, p['font'], p['tracking'], p['leading'], p['align'], visible, bool(p.get('wrap_columns', 0)), p.get('weight', 400))
    if p.get('badge', 0):
        mask = badge_mask(mask, p.get('badge_subtitle', ''), p['font'],
                          p.get('weight', 400), p.get('badge_border', .022),
                          shape=p.get('badge_shape', 0),
                          padding_x=p.get('badge_padding_x', 90.),
                          padding_y=p.get('badge_padding_y', 72.5),
                          keep_proportions=bool(p.get('badge_type_fit', 0)),
                          subtitle_scale=p.get('badge_subtitle_scale', .3),
                          gap=p.get('badge_gap', 35.), radius=p.get('badge_radius', .12),
                          main_lines=text.count('\n') + 1, leading=p['leading'],
                          alignment=p['align'], show_subtitle=bool(p.get('badge_show_subtitle', 1)))
    height = ch * p['size'] * max(1, text.count('\n') + 1)
    copies = p.get('copies', 1)
    if copies > 1:
        original = mask
        while True:
            mask = repeat_mask(original, copies, p['copy_gap']) if copies > 1 else original
            wanted = height / max(1, mask.height)
            fitted = min(wanted, cw * p.get('fit_width', .9) / max(1, mask.width * p['stretch_x']))
            if copies == 1 or p['fit'] != 1 or fitted >= wanted * p.get('copy_floor', 0.): break
            copies -= 1
    # Fit is uniform. The explicit stretch controls are typography choices,
    # independent of changing the canvas aspect ratio.
    scale = height / max(1, mask.height)
    if p['fit'] == 2:
        # Explicit poster lettering: fill an authored rectangle. Both axes
        # still use content_size, so changing the canvas never stretches it.
        return mask, max(.001, cw * p['block_width'] / mask.width * p['stretch_x'] * zoom), max(.001, scale * p['stretch_y'] * zoom)
    if p['fit']: scale = min(scale, cw * p.get('fit_width', .9) / max(1, mask.width * p['stretch_x']))
    sx = max(.001, scale * p['stretch_x'] * zoom)
    sy = max(.001, scale * p['stretch_y'] * zoom)
    return mask, sx, sy


def badge_mask(main, subtitle, font, weight, border, *, shape=0, padding_x=90.,
               padding_y=72.5, keep_proportions=False, subtitle_scale=.3, gap=35.,
               radius=.12, main_lines=1, leading=1., alignment=1, show_subtitle=True):
    """Bounded multiline label; defaults preserve the original FAC51 pixels."""
    def fitted(mask, width, height):
        width, height = max(1, round(width)), max(1, round(height))
        if keep_proportions:
            factor = min(width / mask.width, height / mask.height)
            width, height = max(1, round(mask.width * factor)), max(1, round(mask.height * factor))
        return mask.resize((width, height), Image.Resampling.LANCZOS)

    main = fitted(main, 800, 200 * main_lines)
    sub = None
    if show_subtitle and subtitle.strip():
        sub = glyph_mask(subtitle, font, .12, leading, alignment, weight=min(700, weight+150))
        sub = fitted(sub, 780, 200 * subtitle_scale * (subtitle.count('\n') + 1))
    # The reference deliberately reserves the lower line even in positive flashes.
    sub_height = sub.height if sub is not None else (0 if keep_proportions or not show_subtitle else round(200 * subtitle_scale))
    gap = gap if sub_height else 0
    content_height = main.height + gap + sub_height
    content = Image.new('L', (800, math.ceil(content_height)))
    content.paste(main, ((800-main.width)//2, 0))
    if sub is not None:
        content.paste(sub, ((800-sub.width)//2, round(main.height + gap)))

    # Preserve the reference's small optical baseline correction for rectangles.
    baseline = min(8.5, padding_y) if show_subtitle and not keep_proportions and shape in (0, 5) else 0.
    inner_width = 800 + 2 * padding_x
    inner_height = content.height + 2 * padding_y
    if shape == 2:
        inner_width = inner_height = math.hypot(inner_width, inner_height)
    elif shape == 3:
        inner_width = inner_height = max(inner_width, inner_height)
    elif shape == 4:
        inner_width = inner_height = inner_width + inner_height
    width, height = math.ceil(inner_width + 20), math.ceil(inner_height + 20)
    factor = min(1., 4096 / max(width, height))
    width, height = max(1, round(width*factor)), max(1, round(height*factor))
    result = Image.new('L', (width, height))
    if factor != 1:
        content = content.resize((max(1,round(content.width*factor)), max(1,round(content.height*factor))), Image.Resampling.LANCZOS)
    # Draw behind the text, so padding zero never erases strokes.
    draw = ImageDraw.Draw(result)
    stroke = max(1, round(border * 1000 * factor))
    inset = max(10 * factor, stroke/2 + 1) if shape == 4 else 10 * factor
    bounds = (inset, inset, width-inset, height-inset)
    if border and shape != 5:
        if shape == 2:
            draw.ellipse(bounds, outline=255, width=stroke)
        elif shape == 4:
            points = [(width/2,inset), (width-inset,height/2), (width/2,height-inset), (inset,height/2), (width/2,inset)]
            draw.line(points, fill=255, width=stroke, joint='curve')
        else:
            corner = min(inner_width,inner_height)*radius*factor if shape == 1 else 7*factor
            draw.rounded_rectangle(bounds, radius=corner, outline=255, width=stroke)
    result.paste(content, ((width-content.width)//2, round((height-content.height)/2 + baseline*factor)))
    return result


def repeat_mask(mask, copies, gap):
    """One bounded group so placement, rotation and attached effects agree."""
    stride = mask.width + round(mask.height * gap)
    width = stride * (copies - 1) + mask.width
    if width > 4096:
        scale = 4096 / width
        mask = mask.resize((max(1, round(mask.width * scale)), max(1, round(mask.height * scale))), Image.Resampling.LANCZOS)
        stride = max(mask.width, int(stride * scale))
    result = Image.new('L', (stride * (copies - 1) + mask.width, mask.height))
    for index in range(copies): result.paste(mask, (index * stride, 0))
    return result


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
