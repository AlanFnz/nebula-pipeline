"""Section-owned footage and compiled video clocks; shared sources stay legacy."""
import copy
import math
from pathlib import Path

from synth_video import normalize_footage


def footage_references(document):
    """Yield every authored media reference, including detailed copies/snapshots."""
    if not isinstance(document, dict): return
    if isinstance(document.get('footage'), dict): yield document['footage']
    for key in ('sections', 'video_segments'):
        for item in document.get(key, ()):
            yield from footage_references(item)
    yield from footage_references(document.get('source'))
    for snapshot in document.get('snapshots', ()):
        yield from footage_references(snapshot.get('document'))


def resolve_media_paths(document, directory):
    for footage in footage_references(document):
        source = Path(footage['path'])
        if not source.is_absolute(): footage['path'] = str((Path(directory) / source).resolve())


def normalize_video_segments(raw, duration):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 65536:
        raise ValueError('Video segments must be a non-empty list')
    result = []; end = 0.
    for entry in raw:
        if not isinstance(entry, dict): raise ValueError('Invalid video segment')
        item = {}
        for key in ('start', 'end', 'video_start', 'video_rate'):
            value = entry.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'Video segment {key} must be finite')
            item[key] = float(value)
        if abs(item['start'] - end) > 1e-8 or item['end'] <= item['start']:
            raise ValueError('Video segments must be contiguous and ordered')
        if item['video_start'] < 0 or not 1e-12 <= item['video_rate'] <= 1e12:
            raise ValueError('Video segment clock is outside the supported range')
        item['footage'] = normalize_footage(entry.get('footage'))
        result.append(item); end = item['end']
    if abs(end - duration) > 1e-8: raise ValueError('Video segments must cover the timeline')
    return result


def video_source_at(sequence, time, video_time=None):
    segments = sequence.get('video_segments')
    if segments:
        segment = next((s for s in segments if time < s['end'] - 1e-10), segments[-1])
        return segment['footage'], round(segment['video_start'] + (time-segment['start'])*segment['video_rate'], 12)
    if video_time is None:
        from synth_retime import mapped_time
        video_time = mapped_time(sequence.get('time_map'), time, 'video')
    return sequence.get('footage'), video_time


def rendered_footage(sequence):
    """Only sources actually consumed by the compiled timeline."""
    if sequence.get('video_segments'):
        return [segment['footage'] for segment in sequence['video_segments']]
    return [sequence['footage']] if 'footage' in sequence else []


def compile_video_segments(project, placements, clocks, time_map):
    """Flatten local clips and inherited detailed clocks into one video track."""
    inner = project['source'].get('video_segments')
    if not inner and not any('footage' in section for section in project['sections']): return None
    result = []
    for (index, start, end, _repeat), clock in zip(placements, clocks):
        section = project['sections'][index]
        if 'footage' in section:
            for loop in range(section['loops']):
                left = start + loop * section['duration']
                result.append(dict(start=left, end=left+section['duration'], video_start=0.,
                                   video_rate=section.get('video_rate', 1.), footage=copy.deepcopy(section['footage'])))
            continue
        if inner:
            # Detailed copies map their original timeline through this section's
            # video clock. Beyond the original end the final clock continues.
            boundaries = {start, end}
            for segment in inner[:-1]:
                boundary = start + (segment['end']-clock['video_start'])/clock['video_rate']
                if start < boundary < end: boundaries.add(boundary)
            boundaries = sorted(boundaries)
            for left, right in zip(boundaries, boundaries[1:]):
                original = clock['video_start']+(left-start)*clock['video_rate']
                segment = next((s for s in inner if original < s['end']-1e-10), inner[-1])
                result.append(dict(start=left, end=right,
                    video_start=segment['video_start']+(original-segment['start'])*segment['video_rate'],
                    video_rate=clock['video_rate']*segment['video_rate'], footage=copy.deepcopy(segment['footage'])))
        else:
            for segment in time_map or clocks:
                left, right = max(start, segment['start']), min(end, segment['end'])
                if right <= left: continue
                result.append(dict(start=left, end=right,
                    video_start=segment['video_start']+(left-segment['start'])*segment['video_rate'],
                    video_rate=segment['video_rate'], footage=copy.deepcopy(project['footage'])))
    return normalize_video_segments(result, placements[-1][2])
