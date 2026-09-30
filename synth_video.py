"""Video-source documents and deterministic, reusable frame decoding.

Footage owns an absolute composition clock. Image treatments never change the
source frame or invalidate its cache. Preview uses a lossless, seekable proxy;
export decodes the original on the same constant timestamp grid.
"""
from __future__ import annotations

from collections import OrderedDict
from fractions import Fraction
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from PIL import Image
from media import Cancellation, decode_frames, dimensions, frame_count, probe
from synth_portrait_recipes import PORTRAIT_EFFECTS, EXPOSURE_EFFECTS, FRACTURED_EFFECTS, CRT_BARS_EFFECTS, UNSTABLE_CRT_EFFECTS
from synth_modulation_recipes import MODULATED_CRT_EFFECTS, GRAIN_CRT_EFFECTS

VIDEO_EFFECTS = ('subject_cutout', 'photocopy', 'broadcast', 'stretch_echo', 'signal_etch', 'chroma_print', 'slice_echo', 'screen_mesh', 'signal_background', 'scan_drag', 'ghosts', 'breakup', 'tape',
                 'drift', 'flare', 'separation', 'interference', 'frame_jitter',
                 'bloom', 'raster', 'print_surface', 'low_res')
VIDEO_MODULES = frozenset(('subject_cutout', 'photocopy', 'broadcast', 'stretch_echo', 'signal_etch', 'chroma_print', 'slice_echo', 'screen_mesh', 'signal_background', 'scan_drag', 'smear', 'breakup', 'tape',
                          'warp', 'flare', 'separation', 'interference', 'frame_jitter',
                          'bloom', 'raster', 'print_surface', 'low_res'))
PROXY_EDGE = 720
VIDEO_EFFECTS += ('scan_modulation', 'crt_capture')
VIDEO_MODULES |= {'scan_modulation', 'crt_capture'}
_PROXY_LOCK = threading.Lock()


def _number(value, key, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Video {key} must be between {low} and {high}')
    return float(value)


def normalize_footage(raw):
    if not isinstance(raw, dict) or raw.get('version') != 1 or raw.get('kind') != 'video':
        raise ValueError('Unsupported video source')
    path = raw.get('path')
    if not isinstance(path, str) or not path or '\0' in path:
        raise ValueError('Video source needs a file path')
    result = dict(version=1, kind='video', path=path)
    for key in ('width', 'height'):
        value = _number(raw.get(key), key, 1, 32768)
        if not value.is_integer(): raise ValueError(f'Video {key} must be an integer')
        result[key] = int(value)
    result['duration'] = _number(raw.get('duration'), 'duration', .001, 86400)
    result['fps'] = _number(raw.get('fps'), 'frame rate', .01, 1000)
    # Bound the proxy sampling rate independently of the delivery frame rate.
    result['sample_fps'] = min(120., result['fps'])
    result['in'] = _number(raw.get('in', 0.), 'in point', 0., result['duration'])
    result['out'] = _number(raw.get('out', result['duration']), 'out point', 0., result['duration'])
    if result['out'] <= result['in']:
        raise ValueError('Video Out must be after In')
    for key, default, choices in (('end_mode', 'loop', ('loop', 'hold')),
                                  ('fit', 'contain', ('contain', 'cover', 'original')),
                                  ('audio', 'keep', ('keep', 'mute'))):
        result[key] = raw.get(key, default)
        if result[key] not in choices: raise ValueError(f'Unknown video {key}')
    for key, default, low, high in (('zoom', 1., .05, 8.), ('x', 0., -100000., 100000.),
                                   ('y', 0., -100000., 100000.), ('rotation', 0., -180., 180.),
                                   ('treatment_fps', 30., 1., 120.), ('motion_fps', 0., 0., 120.)):
        result[key] = _number(raw.get(key, default), key, low, high)
    result['has_audio'] = bool(raw.get('has_audio', False))
    identity = raw.get('identity')
    if not isinstance(identity, dict) or any(isinstance(identity.get(k), bool) or not isinstance(identity.get(k), int) or identity[k] < 0 for k in ('size', 'mtime_ns')):
        raise ValueError('Video source needs its file identity; import or relink the clip')
    result['identity'] = {key: identity[key] for key in ('size', 'mtime_ns')}
    return result


def inspect_video(path):
    if not Path(path).is_file(): raise ValueError('Choose a local video file')
    info = probe(path)
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', info['path']],
                            capture_output=True, text=True, timeout=30)
    if result.returncode: raise ValueError(result.stderr.strip() or 'Cannot inspect video')
    streams = json.loads(result.stdout)['streams']
    video = next(s for s in streams if s.get('codec_type') == 'video')
    try: fps = float(Fraction(video.get('avg_frame_rate', '0/1')))
    except (ValueError, ZeroDivisionError): fps = 0.
    if fps <= 0: fps = 30.
    stat = Path(info['path']).stat()
    return normalize_footage(dict(info, version=1, kind='video', fps=fps,
        has_audio=any(s.get('codec_type') == 'audio' for s in streams),
        identity={'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}))


def check_source(footage):
    path = Path(footage['path'])
    try: stat = path.stat()
    except OSError:
        raise ValueError(f'Video is missing: {path.name}. Use Source → Relink video.') from None
    if stat.st_size != footage['identity']['size'] or stat.st_mtime_ns != footage['identity']['mtime_ns']:
        raise ValueError(f'Video has changed: {path.name}. Use Source → Relink video to confirm the new file.')
    return path


def relink_footage(old, new):
    """Replace media metadata, retaining valid trim and treatment controls."""
    result = copy.deepcopy(new)
    for key in ('in', 'out', 'end_mode', 'fit', 'zoom', 'x', 'y', 'treatment_fps', 'motion_fps', 'audio'):
        result[key] = old[key]
    result['rotation'] = old.get('rotation', 0.)
    result['in'] = min(old['in'], max(0., new['duration'] - 1 / new['sample_fps']))
    result['out'] = min(old['out'], new['duration'])
    if result['out'] <= result['in']: result['out'] = new['duration']
    return normalize_footage(result)


def source_index(footage, time_seconds):
    span = footage['out'] - footage['in']
    elapsed = max(0., float(time_seconds))
    cadence = footage.get('motion_fps', 0.)
    if cadence: elapsed = math.floor(elapsed * cadence + 1e-8) / cadence
    elapsed = elapsed % span if footage['end_mode'] == 'loop' else min(elapsed, span)
    fps = footage['sample_fps']
    last = min(frame_count(footage, fps) - 1, math.ceil(footage['out'] * fps - 1e-8) - 1)
    return max(0, min(last, math.floor((footage['in'] + elapsed) * fps + 1e-8)))


def frame_on_canvas(image, footage, canvas, size):
    """Uniform scale, rotation and translation without stretching the footage."""
    width, height = size
    cw, ch = canvas['width'], canvas['height']
    sw, sh = footage['width'], footage['height']
    ratio = min(cw / sw, ch / sh) if footage['fit'] == 'contain' else max(cw / sw, ch / sh) if footage['fit'] == 'cover' else 1.
    # One sampling scale for both axes, including rounded portrait proxies.
    scale = ratio * footage['zoom'] * min(width / cw, height / ch)
    w, h = sw * scale, sh * scale
    x = (width - w) / 2 + footage['x'] * width / cw
    y = (height - h) / 2 + footage['y'] * height / ch
    # Transform directly to the viewport so zooming an 8K source never allocates
    # an enormous intermediate image. Black margins belong to the image stage.
    if footage.get('rotation', 0.):
        angle = math.radians(footage['rotation'])
        cosine, sine = math.cos(angle), math.sin(angle)
        anchor_x, anchor_y = x+w/2, y+h/2
        sx, sy = image.width/w, image.height/h
        # Inverse sampling for a clockwise output rotation about the source's
        # positioned center. The proxy's rounded dimensions retain the original
        # footage proportions, exactly as in the neutral framing path below.
        affine = (cosine*sx, sine*sx,
                  image.width/2-(cosine*anchor_x+sine*anchor_y)*sx,
                  -sine*sy, cosine*sy,
                  image.height/2+(sine*anchor_x-cosine*anchor_y)*sy)
        return image.transform(size,Image.Transform.AFFINE,affine,
                               Image.Resampling.BICUBIC,fillcolor=(0,0,0))
    return image.transform(size, Image.Transform.AFFINE,
        (image.width / w, 0, -x * image.width / w, 0, image.height / h, -y * image.height / h),
        Image.Resampling.BICUBIC, fillcolor=(0, 0, 0))


def run_ffmpeg(args, cancel):
    cancel.check()
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-y', *args], stdout=subprocess.DEVNULL, stderr=errors)
        cancel.attach(proc)
        try:
            code = proc.wait()
            cancel.check()
            if code:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors='replace')[-2000:] or 'FFmpeg failed')
        finally:
            if proc.poll() is None: proc.terminate()
            proc.wait()
            cancel.detach(proc)


def proxy_directory():
    return Path.home() / 'Library/Caches/Nebula Studio/video-v1'


def prepare_proxy(footage, cancel=None, directory=None):
    cancel = cancel or Cancellation()
    check_source(footage)
    root = Path(directory) if directory else proxy_directory()
    root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([footage['path'], footage['identity'], footage['sample_fps'], PROXY_EDGE, 1], sort_keys=True).encode()).hexdigest()
    target = root / (key + '.mkv')
    # Import, preview and export can overlap. Publish only complete proxies.
    while not _PROXY_LOCK.acquire(timeout=.1): cancel.check()
    try:
        cancel.check()
        if target.exists():
            target.touch()
            return target
        fd, name = tempfile.mkstemp(prefix='.building-', suffix='.mkv', dir=root)
        os.close(fd)
        temporary = Path(name)
        try:
            w, h = dimensions(footage, PROXY_EDGE)
            run_ffmpeg(['-i', footage['path'], '-map', '0:v:0', '-an', '-vf',
                f"fps={footage['sample_fps']},scale={w}:{h}:flags=lanczos,setsar=1", '-c:v', 'ffv1', '-pix_fmt', 'bgr0', str(temporary)], cancel)
            check_source(footage)
            os.replace(temporary, target)
            # A regenerable disk cache; retain the most recent clips up to 2 GiB.
            files = sorted(root.glob('*.mkv'), key=lambda p: p.stat().st_mtime, reverse=True)
            total = 0
            for path in files:
                total += path.stat().st_size
                if total > 2 * 1024**3 and path != target: path.unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        _PROXY_LOCK.release()
    return target


def _proxy_frames(path, footage, start, edge, cancel):
    w, h = dimensions(footage, min(edge, PROXY_EDGE))
    # The proxy has a constant frame grid and intra frames. Seek to that grid,
    # then retain a sequential decoder during playback instead of reopening it.
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-ss', f"{start / footage['sample_fps']:.9f}",
            '-i', str(path), '-map', '0:v:0', '-an', '-vf', f'scale={w}:{h}:flags=lanczos',
            '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], stdout=subprocess.PIPE, stderr=errors)
        cancel.attach(proc)
        try:
            index = start
            while True:
                cancel.check()
                raw = proc.stdout.read(w * h * 3)
                cancel.check()
                if not raw: break
                if len(raw) != w * h * 3: raise ValueError('Incomplete proxy frame')
                yield index, Image.frombytes('RGB', (w, h), raw)
                index += 1
            if proc.wait():
                errors.seek(0)
                raise ValueError(errors.read().decode(errors='replace')[-2000:])
        finally:
            if proc.poll() is None: proc.terminate()
            proc.stdout.close()
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            cancel.detach(proc)


class VideoFrameProvider:
    """One worker's reader, with a bounded cache independent of effect settings."""
    def __init__(self, preview=False, cancel=None, directory=None, budget=64 * 1024**2):
        self.preview = preview
        self.cancel = cancel or Cancellation()
        self.directory = directory
        self.budget = budget
        self.cache = OrderedDict()
        self.bytes = 0
        self.reader = None
        self.reader_key = None
        self.next_index = 0
        self.decode_count = 0
        self.mask_provider = None
        self.masks = OrderedDict()
        self.mask_bytes = 0

    def frame(self, footage, time_seconds, edge=None):
        self.cancel.check()
        check_source(footage)
        if not self.preview: edge = None
        index = source_index(footage, time_seconds)
        proxy = self.preview and edge is not None and edge <= PROXY_EDGE
        identity = (footage['path'], footage['identity']['size'], footage['identity']['mtime_ns'], footage['sample_fps'], edge, proxy)
        key = (*identity, index)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key].copy()
        if identity != self.reader_key or index < self.next_index or index - self.next_index > footage['sample_fps'] * 2:
            self.close_reader()
        if self.reader is None:
            if proxy:
                path = prepare_proxy(footage, self.cancel, self.directory)
                self.reader = _proxy_frames(path, footage, index, edge, self.cancel)
            else:
                # Original decoder uses exactly the grid that created the proxy.
                self.reader = decode_frames(footage, footage['sample_fps'], index,
                    frame_count(footage, footage['sample_fps']) - index, edge, self.cancel)
            self.reader_key, self.next_index = identity, index
        for decoded, image in self.reader:
            self.next_index = decoded + 1
            self.decode_count += 1
            if decoded != index: continue
            self.cache[key] = image
            self.bytes += image.width * image.height * 3
            while self.bytes > self.budget and len(self.cache) > 1:
                _, removed = self.cache.popitem(last=False)
                self.bytes -= removed.width * removed.height * 3
            return image.copy()
        self.close_reader()
        raise ValueError('Video ended before its advertised duration. Try trimming the Out point.')

    def mask(self, footage, time_seconds, canvas, mode, retention=0., retention_seconds=.12):
        self.cancel.check()
        check_source(footage)
        key = (footage['path'], footage['identity']['size'], footage['identity']['mtime_ns'],
               footage['sample_fps'], source_index(footage, time_seconds), footage['in'], footage['out'],
               footage['width'], footage['height'], footage['fit'], footage['zoom'], footage['x'], footage['y'], footage.get('rotation', 0.),
               canvas['width'], canvas['height'], mode, retention, retention_seconds)
        if key in self.masks:
            self.masks.move_to_end(key)
            return self.masks[key].copy()
        result = self._mask(footage, time_seconds, canvas, mode, retention, retention_seconds)
        self.masks[key] = result; self.mask_bytes += result.width*result.height
        while self.mask_bytes > 32*1024**2 and self.masks:
            removed = self.masks.popitem(last=False)[1]; self.mask_bytes -= removed.width*removed.height
        return result.copy()

    def _mask(self, footage, time_seconds, canvas, mode, retention, retention_seconds):
        from synth_cutout import subject_mask, retain_mask
        # One canonical crop for every monitor/export size. Detection sees the
        # same composition that the user sees, including scale, position and rotation.
        if self.mask_provider is None:
            self.mask_provider = VideoFrameProvider(preview=True, cancel=self.cancel, directory=self.directory)
        source = self.mask_provider.frame(footage, time_seconds, edge=PROXY_EDGE)
        ratio = PROXY_EDGE / max(canvas['width'], canvas['height'])
        size = tuple(max(1, round(canvas[key] * ratio)) for key in ('width', 'height'))
        framed = frame_on_canvas(source, footage, canvas, size)
        directory = Path(self.directory) / 'masks' if self.directory else None
        mask = subject_mask(framed, mode, self.cancel, directory)
        if retention <= 0: return mask
        # Sample around the held source frame, never around preview call order
        # or across a trim/loop boundary. At either boundary use the original.
        fps = footage['sample_fps']
        index = source_index(footage, time_seconds)
        step = max(1, round(retention_seconds * fps))
        first = math.floor(footage['in'] * fps + 1e-8)
        last = min(frame_count(footage, fps) - 1, math.ceil(footage['out'] * fps - 1e-8) - 1)
        if index - step < first or index + step > last: return mask
        adjacent_footage = dict(footage, motion_fps=0., end_mode='hold')
        neighbors = []
        for adjacent in (index - step, index + step):
            t = max(0., adjacent / fps - footage['in']) + 1e-7
            source = self.mask_provider.frame(adjacent_footage, t, edge=PROXY_EDGE)
            frame = frame_on_canvas(source, footage, canvas, size)
            neighbors.append((frame, subject_mask(frame, mode, self.cancel, directory)))
        return retain_mask(framed, mask, neighbors, retention)

    def close_reader(self):
        if self.reader is not None: self.reader.close()
        self.reader = None
        self.reader_key = None

    def close(self):
        if self.mask_provider is not None:
            self.mask_provider.close()
            self.mask_provider = None
        self.close_reader()
        self.cache.clear()
        self.bytes = 0
        self.masks.clear(); self.mask_bytes = 0

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


def video_composition(footage):
    from synth_composition import blank_composition, normalize_composition
    from synth_canvas import normalize_canvas
    result = blank_composition()
    duration = min(300., footage['out'] - footage['in'])
    fps = max(1, min(120, round(footage['fps'])))
    result.update(schema_version=2, render_version=2, name=Path(footage['path']).stem,
                  footage=normalize_footage(footage), fps=fps)
    scale = min(1., 4096 / max(footage['width'], footage['height']))
    result['canvas'] = normalize_canvas({key: max(64, round(footage[key] * scale)) for key in ('width', 'height')})
    result['source']['duration'] = max(.1, duration)
    result['source']['render_version'] = 2
    result['phrases']['custom'].update(name='Video treatment', end=max(.1, duration))
    result['sections'][0]['duration'] = max(1 / fps, round(duration * fps) / fps)
    return normalize_composition(result)


TREATMENTS = (
    ('Clean / start from source', {}),
    ('Worn tape', {
        'tape': {'tape.tracking': .018, 'tape.dropouts': .18, 'tape.chroma_delay': .006, 'tape.bleed': .012},
        'raster': {'raster.grain': .055, 'raster.chroma': .025},
        'low_res': {'low_res.resolution': 360}}),
    ('Printed motion', {
        'frame_jitter': {'frame_jitter.x': 2., 'frame_jitter.y': 1.5, 'frame_jitter.rotation': .10, 'frame_jitter.scale': .05},
        'print_surface': {'print_surface.background_mode': 1, 'print_surface.ink_wear': .2},
        'low_res': {'low_res.resolution': 360}}),
    ('Soft signal', {
        'separation': {}, 'bloom': {},
        'raster': {'raster.grain': .04, 'raster.chroma': .02},
        'low_res': {'low_res.resolution': 720}}),
    ('Cold photocopy', {
        'subject_cutout': {'subject_cutout.silhouette': .46},
        'photocopy': {'photocopy.light_depth': .97, 'photocopy.light_width': .32,
                      'photocopy.light_x': .55, 'photocopy.blackout': .57,
                      'photocopy.tint': .75, 'photocopy.exposure': .1,
                      'photocopy.grain_size': 2.5, 'photocopy.grain': 1.15,
                      'photocopy.edge_wear': 2.3, 'photocopy.threshold': .43,
                      'photocopy.halftone': .32},
        'frame_jitter': {'frame_jitter.x': 3., 'frame_jitter.y': 2., 'frame_jitter.rotation': .2},
        'low_res': {'low_res.resolution': 720}}),
    ('Cyan / slice screen', PORTRAIT_EFFECTS),
    ('Cyan / filmed exposures', EXPOSURE_EFFECTS),
    ('Cyan / fractured CRT', FRACTURED_EFFECTS),
    ('Cyan / CRT bars', CRT_BARS_EFFECTS),
    ('Cyan / unstable CRT', UNSTABLE_CRT_EFFECTS),
    ('Cyan / modulated CRT', MODULATED_CRT_EFFECTS),
    ('Cyan / grain CRT', GRAIN_CRT_EFFECTS),
)


def apply_treatment(project, index):
    from synth_effects import effect_preset
    from synth_composition import normalize_composition
    from synth_master import normalize_master
    result = copy.deepcopy(project)
    if 'footage' not in result: raise ValueError('Video treatments need an imported video')
    result['effects'] = {}
    result['master'] = normalize_master()
    for effect, params in TREATMENTS[index][1].items():
        entry = effect_preset(effect)
        entry['params'].update(params)
        result['effects'][effect] = entry
    for section in result['sections']: section['effects'] = {}
    return normalize_composition(result)
