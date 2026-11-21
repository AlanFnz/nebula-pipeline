"""Portable stamp silhouettes. Documents embed pixels, never source-file paths."""
from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ARTWORK_PREFIX = 'data:image/png;base64,'
MAX_ARTWORK_EDGE = 2048
MAX_ARTWORK_BYTES = 8_000_000


def encode_artwork(image, mode='auto'):
    """Crop a transparency/luminance mask and retain its native proportions."""
    if mode not in {'auto', 'light', 'dark'}:
        raise ValueError('Choose transparency, light on dark, or dark on light.')
    rgba = ImageOps.exif_transpose(image).convert('RGBA')
    alpha = rgba.getchannel('A')
    if mode == 'auto' and alpha.getextrema()[0] < 255:
        mask = alpha
    else:
        mask = ImageOps.grayscale(rgba)
        if mode == 'dark': mask = ImageOps.invert(mask)
        mask = Image.fromarray((np.asarray(mask, dtype=np.float32) * np.asarray(alpha) / 255).astype(np.uint8))
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError('The artwork is empty. Use visible pixels on transparency or a contrasting silhouette.')
    mask = mask.crop(bounds)
    mask.thumbnail((MAX_ARTWORK_EDGE, MAX_ARTWORK_EDGE), Image.Resampling.LANCZOS)
    buffer = BytesIO(); mask.save(buffer, format='PNG')
    return ARTWORK_PREFIX + base64.b64encode(buffer.getvalue()).decode('ascii')


@lru_cache(maxsize=16)
def decode_artwork(value):
    """Validate once per asset; the returned cached mask must not be mutated."""
    if not isinstance(value, str) or not value.startswith(ARTWORK_PREFIX) or len(value) > MAX_ARTWORK_BYTES:
        raise ValueError('Artwork must be an embedded PNG silhouette.')
    try:
        raw = base64.b64decode(value[len(ARTWORK_PREFIX):], validate=True)
        with Image.open(BytesIO(raw)) as image:
            if image.format != 'PNG' or image.mode != 'L' or max(image.size) > MAX_ARTWORK_EDGE:
                raise ValueError('Artwork must be a grayscale PNG, at most 2048 pixels per edge.')
            image.load()
            if image.getbbox() is None: raise ValueError('The embedded artwork is empty.')
            return image.copy()
    except (binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Cannot read the embedded artwork.') from exc


def validate_artwork(value):
    if value == '': return value
    if not isinstance(value, str): raise ValueError('Artwork must be an embedded PNG silhouette.')
    decode_artwork(value)
    return value


def project_artwork(mask, xy, size):
    """Project a flat cutout through the same four 3D corners as its stamp."""
    # A plane seen exactly edge-on has no area; do not invert its homography.
    area = abs(np.dot(xy[:, 0], np.roll(xy[:, 1], 1)) - np.dot(xy[:, 1], np.roll(xy[:, 0], 1))) / 2
    if area < .05: return Image.new('L', size)
    uvs = ((0, 0), (mask.width, 0), (mask.width, mask.height), (0, mask.height))
    matrix, target = [], []
    for (x, y), (u, v) in zip(xy, uvs):
        matrix.extend(((x, y, 1, 0, 0, 0, -u*x, -u*y), (0, 0, 0, x, y, 1, -v*x, -v*y)))
        target.extend((u, v))
    try: coefficients = np.linalg.solve(np.asarray(matrix), np.asarray(target))
    except np.linalg.LinAlgError: return Image.new('L', size)
    return mask.transform(size, Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BILINEAR, fillcolor=0)
