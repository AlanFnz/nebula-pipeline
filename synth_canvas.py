"""Canvas formats and framing, kept separate from the authored effects."""
import math


CANVAS_FORMATS = (
    ("original", "Original · 5:4", 720, 576),
    ("stories", "Stories / Reels · 9:16", 1080, 1920),
    ("portrait", "Portrait feed · 4:5", 1080, 1350),
    ("square", "Square · 1:1", 1080, 1080),
    ("photo", "Portrait · 3:4", 1080, 1440),
    ("landscape", "Landscape feed · 1.91:1", 1080, 566),
    ("wide", "Widescreen · 16:9", 1920, 1080),
)


def normalize_canvas(raw=None):
    raw = {} if raw is None else raw
    if not isinstance(raw, dict):
        raise ValueError("Canvas must be an object")
    result = {}
    for key, default in (("width", 720), ("height", 576)):
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 64 <= value <= 4096 or value != int(value):
            raise ValueError(f"Canvas {key} must be an integer between 64 and 4096")
        result[key] = int(value)
    result["framing"] = raw.get("framing", "native")
    if result["framing"] not in ("native", "adaptive", "preserve", "fit"):
        raise ValueError("Unknown canvas framing")
    if 'reference' in raw:
        reference = raw['reference']
        if not isinstance(reference, dict) or reference.get('framing', 'native') not in ('native', 'adaptive') or 'reference' in reference:
            raise ValueError('Canvas reference must be an original canvas')
        result['reference'] = normalize_canvas(reference)
    if result['framing'] in ('preserve', 'fit') and 'reference' not in result:
        raise ValueError('Preserved canvas needs an artwork reference')
    return result


def format_canvas(identifier):
    for key, _label, width, height in CANVAS_FORMATS:
        if key == identifier:
            return {"width": width, "height": height, "framing": "adaptive"}
    raise ValueError(f"Unknown canvas format: {identifier}")


def preview_size(canvas, edge=360):
    """A bounded proxy; the export always uses the document's full canvas."""
    width, height = canvas["width"], canvas["height"]
    scale = min(1., edge / max(width, height)) if edge else 1.
    return max(1, round(width * scale)), max(1, round(height * scale))


def resize_canvas(current, target, fit=False):
    """Change the viewport, retaining the original artwork's pixel dimensions."""
    current = normalize_canvas(current); target = normalize_canvas(target)
    reference = current.get('reference', {key: current[key] for key in ('width', 'height', 'framing')})
    return normalize_canvas(dict(width=target['width'], height=target['height'],
                                 framing='fit' if fit else 'preserve', reference=reference))


def content_size(canvas, output):
    """Artwork size in working pixels; one scale for both axes, never stretch."""
    if 'reference' not in canvas:
        return output
    reference = canvas['reference']
    scale = min(output[0] / canvas['width'], output[1] / canvas['height'])
    if canvas['framing'] == 'fit':
        scale *= min(canvas['width'] / reference['width'], canvas['height'] / reference['height'])
    return reference['width'] * scale, reference['height'] * scale


def source_framing(canvas):
    return canvas.get('reference', canvas).get('framing', 'native')


def particle_framing(width, height, framing):
    # Keep head proportions uniform and leave room for ears/profile turns on
    # narrow canvases. Native framing keeps every earlier document's pixels.
    return min(1., width / height / .8) if framing == "adaptive" else 1.


def object_offset(preset, output):
    """Canvas-pixel translation, scaled only for preview/working resolution."""
    return (preset.get('object_x', 0.) * output[0] / preset['width'],
            preset.get('object_y', 0.) * output[1] / preset['height'])
