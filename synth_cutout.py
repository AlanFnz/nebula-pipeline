"""Optional local Vision masks and a source-independent cutout compositor.

Only the mask acquisition depends on macOS. Framing, edge controls and the
composite are ordinary image operations; neither changes the input video.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter


def mask_helper():
    root = Path(__file__).resolve().parent
    candidates = (root / 'native/nebula-mask', root / 'build/native/nebula-mask')
    helper = next((path for path in candidates if path.is_file()), None)
    if sys.platform != 'darwin' or helper is None:
        raise ValueError('Subject cutout needs the macOS mask helper. Build it with python scripts/build_mask_helper.py, or turn off Subject cutout.')
    return helper


def subject_mask(image, mode, cancel, directory=None):
    """Cache canonical framed input, independent of preview/export resolution.

    Frames are never uploaded. Atomic cache writes are safe if preview and
    export request the same mask concurrently. A cancelled result is discarded.
    """
    cancel.check()
    root = Path(directory) if directory else Path.home() / 'Library/Caches/Nebula Studio/masks-v1'
    key = hashlib.sha256(f'vision-v1:{mode}:{image.size}'.encode() + image.tobytes()).hexdigest()
    target = root / (key + '.png')
    if target.exists():
        try:
            with Image.open(target) as cached: return cached.convert('L')
        except OSError:
            target.unlink(missing_ok=True)
    helper = mask_helper()
    encoded = io.BytesIO(); image.save(encoded, format='PNG')
    proc = subprocess.Popen([str(helper), ('foreground', 'people', 'crowd')[mode]],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cancel.attach(proc)
    try:
        try: data, errors = proc.communicate(encoded.getvalue(), timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.communicate()
            raise ValueError('Subject mask timed out. Turn off Subject cutout or try a different frame.') from None
        cancel.check()
        if proc.returncode: raise ValueError(errors.decode(errors='replace')[-1500:] or 'Local subject mask failed')
        with Image.open(io.BytesIO(data)) as decoded:
            mask = decoded.convert('L').resize(image.size, Image.Resampling.BILINEAR)
    finally:
        if proc.poll() is None: proc.kill()
        proc.wait(); cancel.detach(proc)
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.mask-', suffix='.png', dir=root)
    os.close(fd)
    try:
        mask.save(name); cancel.check(); os.replace(name, target)
    finally: Path(name).unlink(missing_ok=True)
    # Regenerable disk cache, bounded independently of the video proxy cache.
    files = []
    for path in root.glob('*.png'):
        try: files.append((path.stat().st_mtime, path))
        except FileNotFoundError: pass
    total = 0
    for _, path in sorted(files, reverse=True):
        try:
            total += path.stat().st_size
            if total > 512 * 1024**2 and path != target: path.unlink(missing_ok=True)
        except FileNotFoundError: pass  # Another renderer can evict old entries.
    return mask


def retain_mask(image, mask, neighbors, strength):
    """Fill short detection holes only where both neighbors agree in color.

    No accumulated state or optical trails: source changes and real occlusions
    veto the borrowed mask, and random seeks return the same result as export.
    """
    if strength <= 0 or len(neighbors) != 2: return mask
    current = np.asarray(image, dtype=np.float32) / 255
    support = []
    for frame, adjacent in neighbors:
        difference = np.max(np.abs(current - np.asarray(frame, dtype=np.float32) / 255), axis=2)
        confidence = np.clip(1 - difference / .16, 0, 1)
        support.append(np.asarray(adjacent, dtype=np.float32) * confidence)
    recovered = np.minimum(*support) * strength
    return Image.fromarray(np.uint8(np.maximum(np.asarray(mask), recovered)))


def render_cutout(image, mask, p):
    if p['mix'] == 0: return image
    w, h = image.size
    scale = min(w, h) / 720
    mask = mask.resize(image.size, Image.Resampling.BILINEAR)
    radius = round(abs(p['expand']) * scale)
    if radius:
        mask = mask.filter((ImageFilter.MaxFilter if p['expand'] > 0 else ImageFilter.MinFilter)(radius * 2 + 1))
    if p['feather']: mask = mask.filter(ImageFilter.GaussianBlur(p['feather'] * scale))
    alpha = np.asarray(mask, dtype=np.float32) / 255
    alpha = np.clip((alpha - p['threshold']) / max(.001, 1 - p['threshold']), 0, 1)
    if p['invert']: alpha = 1 - alpha
    source = np.asarray(image, dtype=np.float32) / 255
    subject = source * (1 - p['silhouette'])
    background = source * p['background_detail'] + p['paper'] * (1 - p['background_detail'])
    if p['shadow']:
        ground = p['ground'] * h
        if p['shadow_anchor']:
            rows = np.flatnonzero(np.max(alpha, axis=1) > .5)
            if len(rows): ground = float(rows[-1])
        length = p['shadow_length']
        skew = p['shadow_slant']
        # Project the same mask onto a configurable ground plane. This stays
        # attached to the subject and creates no independent graphic layer.
        shadow = mask.transform((w, h), Image.Transform.AFFINE,
            (1, skew / length, -skew * ground / length,
             0, -1 / length, ground * (1 + 1 / length)), Image.Resampling.BILINEAR)
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(.3, 2 * scale)))
        background *= 1 - (np.asarray(shadow, dtype=np.float32) / 255 * p['shadow'])[..., None]
    composite = subject * alpha[..., None] + background * (1 - alpha[..., None])
    result = source * (1 - p['mix']) + composite * p['mix']
    return Image.fromarray(np.uint8(np.clip(result * 255, 0, 255)))
