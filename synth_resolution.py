"""Artistic working resolution, independent of preview and export dimensions."""
from PIL import Image

from synth_canvas import preview_size


def render_resolution(preset, size=None):
    """Return output size, working size and reconstruction filter.

    Use the saved canvas to round the working raster once. A 360 px preview
    and a full-size export then share the same geometry and random texture.
    This is a render boundary, not a downsample of an already finished image.
    """
    output = tuple(size or (preset["width"], preset["height"]))
    for entry in preset["modules"]:
        if entry.get("id") == "low_res" and entry.get("enabled", True):
            params = entry["params"]
            working = preview_size(preset, params["resolution"])
            sampling = Image.Resampling.NEAREST if params["sampling"] == 1 else Image.Resampling.BILINEAR
            return output, working, sampling
    return output, output, Image.Resampling.BILINEAR


def finish_resolution(image, output, sampling):
    return image if image.size == output else image.resize(output, sampling)
