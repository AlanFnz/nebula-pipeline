"""One reversible color adjustment on the complete rendered composition."""
import math

import numpy as np
from PIL import Image


DEFAULT_MASTER = {'enabled': True, 'brightness': 0., 'contrast': 1., 'saturation': 1.}


def normalize_master(raw=None):
    if raw is None:
        return DEFAULT_MASTER.copy()
    if not isinstance(raw, dict) or set(raw) - DEFAULT_MASTER.keys():
        raise ValueError('Master must contain brightness, contrast, saturation and enabled settings')
    result = DEFAULT_MASTER.copy()
    enabled = raw.get('enabled', True)
    if not isinstance(enabled, bool):
        raise ValueError('Master enabled must be true or false')
    result['enabled'] = enabled
    for key, low, high in (('brightness', -1., 1.), ('contrast', 0., 3.), ('saturation', 0., 3.)):
        value = raw.get(key, result[key])
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'Master {key} must be between {low:g} and {high:g}')
        result[key] = float(value)
    return result


def apply_master(image, settings=None):
    master = normalize_master(settings)
    # Exact bypass preserves every approved frame and avoids extra rounding.
    if not master['enabled'] or master == DEFAULT_MASTER:
        return image
    rgb = np.asarray(image, dtype=np.float32) / 255
    if master['saturation'] != 1.:
        gray = np.sum(rgb * np.array((.2126, .7152, .0722), dtype=np.float32), axis=-1, keepdims=True)
        rgb = gray + (rgb - gray) * master['saturation']
    rgb = (rgb - .5) * master['contrast'] + .5 + master['brightness']
    return Image.fromarray(np.rint(np.clip(rgb, 0., 1.) * 255).astype(np.uint8), 'RGB')
