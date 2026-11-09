"""Editable assemblies of native studies and footage, with source-local clocks.

An assembly owns snapshots, never a path to an executable recipe. Moving a clip
changes its timeline position, not the source's effect phase. Original projects
continue to use the existing composition/sequence renderer without migration.
"""
from __future__ import annotations

import copy
import json
import math
import os
import tempfile
import uuid
from pathlib import Path

from synth_canvas import normalize_canvas
from synth_composition import normalize_composition, compile_composition
from synth_soundtrack import normalize_soundtrack
from synth_video import normalize_footage, video_composition

FORMAT = 'nebula-montage'
MAX_CLIPS = 512


def identifier():
    return uuid.uuid4().hex


def number(value, label, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    if not low <= value <= high or (integer and value != int(value)):
        raise ValueError(f'{label} is outside the supported range')
    return int(value) if integer else float(value)


def new_montage(canvas=None, fps=30):
    return dict(format=FORMAT, version=1, name='Untitled montage', fps=fps,
                canvas=normalize_canvas(canvas), assets={}, clips=[], markers=[])


def asset_project(asset, canvas):
    if asset['kind'] == 'study':
        return copy.deepcopy(asset['document'])
    result = video_composition(asset['footage'])
    result['canvas'] = copy.deepcopy(canvas)
    # Source selection may start beyond the composer's five-minute starter.
    duration = min(3600., asset['footage']['out']-asset['footage']['in'])
    fps = result['fps']; frames = max(1, math.floor(duration*fps+1e-7))
    template = copy.deepcopy(result['sections'][0]); result['sections'] = []
    remaining = frames
    while remaining:
        take = min(remaining, 300*fps)
        result['sections'].append(dict(copy.deepcopy(template), id=f'video-part-{len(result["sections"])+1}', duration=take/fps))
        remaining -= take
    return result


def clip_project(document, clip):
    return copy.deepcopy(clip.get('document') or asset_project(document['assets'][clip['asset']], document['canvas']))


def source_duration(document, clip):
    if clip.get('document') is not None:
        return compile_composition(clip['document'])['duration']
    asset = document['assets'][clip['asset']]
    if asset['kind'] == 'video':
        return min(3600., asset['footage']['out'] - asset['footage']['in'])
    return compile_composition(asset['document'])['duration']


def normalize_montage(raw):
    if not isinstance(raw, dict) or raw.get('format') != FORMAT or raw.get('version') != 1:
        raise ValueError('Unsupported montage document')
    result = new_montage(raw.get('canvas'), number(raw.get('fps', 30), 'FPS', 1, 120, True))
    result['name'] = str(raw.get('name', 'Untitled montage'))[:300]
    assets = raw.get('assets', {})
    if not isinstance(assets, dict) or len(assets) > 512:
        raise ValueError('Use at most 512 library items')
    for key, asset in assets.items():
        if not isinstance(key, str) or not key or not isinstance(asset, dict):
            raise ValueError('Invalid library item')
        item = dict(name=str(asset.get('name', key))[:300], kind=asset.get('kind'))
        if item['kind'] == 'study': item['document'] = normalize_composition(asset.get('document'))
        elif item['kind'] == 'video': item['footage'] = normalize_footage(asset.get('footage'))
        else: raise ValueError('Library items must be videos or native studies')
        result['assets'][key] = item
    clips = raw.get('clips', [])
    if not isinstance(clips, list) or len(clips) > MAX_CLIPS: raise ValueError(f'Use at most {MAX_CLIPS} clips')
    ids = set()
    for clip in clips:
        if not isinstance(clip, dict) or clip.get('asset') not in result['assets']:
            raise ValueError('Clip refers to a missing library item')
        key = clip.get('id')
        if not isinstance(key, str) or not key or key in ids: raise ValueError('Clip IDs must be unique')
        ids.add(key)
        item = dict(id=key, asset=clip['asset'], name=str(clip.get('name', result['assets'][clip['asset']]['name']))[:300],
                    in_frame=number(clip.get('in_frame', 0), 'Source frame', 0, 432000),
                    frames=number(clip.get('frames', 1), 'Clip frames', 1, 432000, True),
                    speed=number(clip.get('speed', 1.), 'Clip speed', .05, 16.))
        if 'document' in clip: item['document'] = normalize_composition(clip['document'])
        # End is exclusive. The last sample, not a rounded duration, must exist.
        last = (item['in_frame'] + (item['frames'] - 1) * item['speed']) / result['fps']
        if last >= source_duration(result, item) - 1e-8:
            raise ValueError(f'“{item["name"]}” extends beyond its source. Shorten the clip or choose an earlier In point.')
        result['clips'].append(item)
    total = sum(c['frames'] for c in result['clips'])
    if total > 3600 * result['fps']: raise ValueError('Montages can be at most one hour')
    markers = raw.get('markers', [])
    if not isinstance(markers, list) or len(markers) > 4096: raise ValueError('Too many markers')
    for marker in markers:
        result['markers'].append(dict(frame=number(marker['frame'], 'Marker frame', 0, 3600*result['fps'], True),
                                      name=str(marker.get('name', 'Marker'))[:120]))
    result['markers'].sort(key=lambda m: m['frame'])
    if raw.get('soundtrack') is not None:
        result['soundtrack'] = normalize_soundtrack(raw['soundtrack'])
        if result['soundtrack']['export_audio'] == 'footage':
            raise ValueError('Montage export supports the project soundtrack or silence')
    return result


def placements(document):
    start = 0
    for clip in document['clips']:
        yield clip, start, start + clip['frames']
        start += clip['frames']


def media_references(document):
    from synth_section_sources import footage_references, soundtrack_references
    if document.get('soundtrack'): yield document['soundtrack']
    for asset in document['assets'].values():
        if asset['kind'] == 'video': yield asset['footage']
        else:
            yield from footage_references(asset['document'])
            yield from soundtrack_references(asset['document'])
    for clip in document['clips']:
        if clip.get('document'):
            yield from footage_references(clip['document'])
            yield from soundtrack_references(clip['document'])


def protect_destination(document, path):
    target = Path(path).expanduser().resolve()
    from synth_live_set import live_set_paths
    for source in (*media_references(document), *({'path': link} for link in live_set_paths(document))):
        original = Path(source['path']).expanduser()
        if original.resolve() == target or (target.exists() and original.exists() and os.path.samefile(target, original)):
            raise ValueError('Choose a destination different from the original media')


def save_montage(path, document):
    normalized = normalize_montage(document)
    protect_destination(normalized, path)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.nebula-montage-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream: json.dump(normalized, stream, ensure_ascii=False, indent=2); stream.write('\n')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_montage(path):
    from synth_section_sources import resolve_media_paths
    path = Path(path)
    raw = json.loads(path.read_text())
    for asset in raw.get('assets', {}).values():
        resolve_media_paths(asset.get('document', asset), path.resolve().parent)
    for clip in raw.get('clips', []): resolve_media_paths(clip.get('document', {}), path.resolve().parent)
    resolve_media_paths(raw, path.resolve().parent)
    return normalize_montage(raw)


def add_asset(document, name, *, footage=None, study=None):
    result = copy.deepcopy(document); key = identifier()
    result['assets'][key] = dict(name=name, kind='video', footage=footage) if footage is not None else dict(name=name, kind='study', document=study)
    return normalize_montage(result), key


def insert_clip(document, asset, at=None, in_frame=0, frames=None):
    result = copy.deepcopy(document)
    clip = dict(id=identifier(), asset=asset, name=result['assets'][asset]['name'], in_frame=in_frame, frames=1, speed=1.)
    clip['frames'] = frames if frames is not None else max(1, round(source_duration(result, clip)*result['fps']) - in_frame)
    result['clips'].insert(len(result['clips']) if at is None else at, clip)
    return normalize_montage(result), clip['id']


def split_clip(document, frame):
    result = copy.deepcopy(document)
    for index, (clip, start, end) in enumerate(placements(result)):
        if start < frame < end:
            right = copy.deepcopy(clip); right['id'] = identifier()
            right['in_frame'] += (frame-start)*clip['speed']; right['frames'] = end-frame
            clip['frames'] = frame-start; result['clips'].insert(index+1, right)
            return normalize_montage(result)
    raise ValueError('Place the playhead inside a clip to split it')


def treatment(document, clip):
    from synth_composition import section_placements
    from synth_effects import merge_effects
    project = clip_project(document, clip)
    seconds = clip['in_frame'] / document['fps']
    index = next((i for i, a, b, _ in section_placements(project) if a <= seconds < b), 0)
    from synth_sequence import resolve_sequence_frame
    from synth_effects import EFFECTS
    from synth_video import VIDEO_EFFECTS
    sequence = compile_composition(project)
    base = resolve_sequence_frame(sequence, seconds, normalized=True)[-1]
    modules = {m['id']: m for m in base['modules']}
    effects = {}
    for effect in EFFECTS:
        if effect.id not in VIDEO_EFFECTS: continue
        active = any(modules.get(module, {}).get('enabled') for module in effect.modules)
        params = {}
        for path in effect.paths:
            module, key = path.split('.', 1)
            if module in modules and key in modules[module]['params']: params[path] = copy.deepcopy(modules[module]['params'][key])
        effects[effect.id] = dict(mode='on' if active else 'off', params=params)
    # Explicit edits retain authored animation; otherwise copy the visible look.
    effects.update({k:v for k,v in merge_effects(project['effects'], project['sections'][index]['effects']).items() if k in VIDEO_EFFECTS})
    return dict(effects=effects, master=project['master'], effect_order=project.get('effect_order'))


def apply_treatment(document, ids, look):
    result = copy.deepcopy(document)
    for clip in result['clips']:
        if clip['id'] not in ids: continue
        project = clip_project(result, clip)
        project['effects'] = copy.deepcopy(look['effects']); project['master'] = copy.deepcopy(look['master'])
        if look.get('effect_order') is not None: project['effect_order'] = list(look['effect_order'])
        for section in project['sections']: section['effects'] = {}
        clip['document'] = project
    return normalize_montage(result)


def replace_clip(document, clip_id, asset, in_frame=0, keep_treatment=True):
    result = copy.deepcopy(document)
    clip = next(c for c in result['clips'] if c['id'] == clip_id)
    look = treatment(result, clip)
    clip.update(asset=asset, in_frame=in_frame, name=result['assets'][asset]['name'])
    clip.pop('document', None)
    result = normalize_montage(result)
    return apply_treatment(result, {clip_id}, look) if keep_treatment else result


class MontageRenderer:
    """Compile once per snapshot. Study-local time survives edits and reordering."""
    def __init__(self, document, cancel=None, preview=False):
        from synth_video import VideoFrameProvider
        self.document = normalize_montage(document)
        self.cancel = cancel
        self.provider = VideoFrameProvider(cancel=cancel, preview=preview)
        self.clips = []
        cache = {}
        for clip, start, end in placements(self.document):
            key = json.dumps(clip.get('document') or {'asset': clip['asset']}, sort_keys=True)
            if key not in cache: cache[key] = compile_composition(clip_project(self.document, clip))
            self.clips.append((clip, start, end, cache[key]))

    def frame(self, frame, size=None):
        from synth_sequence import render_sequence_frame
        from PIL import Image, ImageOps
        if not self.clips: raise ValueError('Add a clip before rendering')
        frame = min(max(0, int(frame)), self.clips[-1][2]-1)
        clip, start, end, sequence = next(c for c in self.clips if c[1] <= frame < c[2])
        time = (clip['in_frame'] + (frame-start)*clip['speed']) / self.document['fps']
        canvas = self.document['canvas']; size = size or (canvas['width'], canvas['height'])
        child = sequence['canvas']; ratio = min(size[0]/child['width'], size[1]/child['height'])
        child_size = (max(1, round(child['width']*ratio)), max(1, round(child['height']*ratio)))
        im = render_sequence_frame(sequence, time, child_size, self.provider, cancel=self.cancel)
        if im.size == size: return im
        return ImageOps.pad(im, size, method=Image.Resampling.LANCZOS, color='black')

    def close(self): self.provider.close()
    def __enter__(self): return self
    def __exit__(self, *_): self.close()


def export_montage(document, path, cancel=None, progress=None):
    """Use the same frame renderer as the monitor; encode once, mux one soundtrack."""
    import subprocess
    from media import Cancellation
    from synth_soundtrack import check_soundtrack, mux_soundtrack_audio
    doc = normalize_montage(document)
    if not doc['clips']: raise ValueError('Add a clip before exporting')
    protect_destination(doc, path)
    cancel = cancel or Cancellation(); path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    total = sum(c['frames'] for c in doc['clips']); fps = doc['fps']
    track = doc.get('soundtrack')
    if track and track['export_audio'] == 'soundtrack': check_soundtrack(track)
    with tempfile.TemporaryDirectory(prefix='.nebula-montage-', dir=path.parent) as folder:
        video = Path(folder)/'video.mp4'; muxed = Path(folder)/'muxed.mp4'
        with MontageRenderer(doc, cancel) as renderer, tempfile.TemporaryFile() as errors:
            w,h = doc['canvas']['width'], doc['canvas']['height']
            proc = subprocess.Popen(['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24',
                '-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0','-an','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE,stderr=errors)
            cancel.attach(proc)
            try:
                for frame in range(total):
                    cancel.check(); proc.stdin.write(renderer.frame(frame).tobytes())
                    if progress: progress(frame+1,total)
                proc.stdin.close(); code=proc.wait(); cancel.check()
                if code:
                    errors.seek(0); raise ValueError(errors.read().decode(errors='replace')[-2000:] or 'Export failed')
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=2)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                if not proc.stdin.closed:
                    try: proc.stdin.close()
                    except BrokenPipeError: pass
                cancel.detach(proc)
        result = video
        if track and track['export_audio'] == 'soundtrack':
            mux_soundtrack_audio(video,muxed,track,0,total/fps,cancel); result=muxed
        cancel.check(); os.replace(result,path)
    return path
