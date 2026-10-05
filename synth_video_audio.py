"""Explicit, cancellable audio assembly for treated footage exports."""
from pathlib import Path
import math
import tempfile
from synth_video import check_source, run_ffmpeg


def mux_source_audio(video, destination, footage, start, duration, cancel, *, time_map=None):
    """Keep source audio aligned to optional piecewise video clocks.

    Without a map, repeat only the trimmed range or pad Hold with silence.
    Map video starts are relative to the trimmed clip; effect clocks never
    affect audio. Each intersected piece preserves pitch at its video rate.
    """
    check_source(footage)
    if time_map is not None:
        target = Path(destination)
        if (target.resolve() == Path(footage['path']).resolve() or
                target.exists() and target.samefile(footage['path'])):
            raise ValueError('Audio export cannot overwrite its source video')
    if time_map is not None and any(segment['video_rate'] != 1. or
            segment['video_start'] != segment['start'] for segment in time_map):
        return _mux_mapped_audio(video, destination, footage, start, duration, cancel, time_map)
    span = footage['out'] - footage['in']
    with tempfile.TemporaryDirectory(prefix='.nebula-audio-', dir=Path(video).parent) as folder:
        trimmed = Path(folder) / 'trim.wav'
        run_ffmpeg(['-i', footage['path'], '-map', '0:a:0', '-vn',
            '-af', f"atrim=start={footage['in']}:end={footage['out']},asetpts=PTS-STARTPTS,aresample=48000,apad",
            '-t', str(span), '-c:a', 'pcm_s16le', str(trimmed)], cancel)
        args = ['-i', str(video)]
        if footage['end_mode'] == 'loop':
            args += ['-stream_loop', '-1', '-i', str(trimmed)]
            # A full-cycle offset is equivalent and avoids decoding hours of
            # repeated audio when exporting a range late in the timeline.
            offset = start % span
        else:
            args += ['-i', str(trimmed)]
            offset = start
        args += ['-map', '0:v:0', '-map', '1:a:0', '-af',
            f'apad,atrim=start={offset}:duration={duration},asetpts=PTS-STARTPTS',
            '-t', str(duration), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', str(destination)]
        run_ffmpeg(args, cancel)


def _tempo_filters(rate):
    """Keep each atempo factor in its accurate, pitch-preserving range."""
    factors = []
    while rate > 2.:
        factors.append(2.)
        rate /= 2.
    while rate < .5:
        factors.append(.5)
        rate *= 2.
    factors.append(rate)
    return ','.join(f'atempo={factor:.12g}' for factor in factors)


def _coalesce_video_segments(time_map):
    """Effect-clock boundaries do not require separate audio tempo passes."""
    segments = []
    for entry in time_map:
        if segments:
            previous = segments[-1]
            expected = previous['video_start']+(entry['start']-previous['start'])*previous['video_rate']
            if (previous['video_rate'] == entry['video_rate'] and
                    previous.get('footage') == entry.get('footage') and
                    math.isclose(previous['end'], entry['start'], rel_tol=0., abs_tol=1e-9) and
                    math.isclose(expected, entry['video_start'], rel_tol=0., abs_tol=1e-9)):
                previous['end'] = entry['end']
                continue
        segments.append(dict(entry))
    return segments


def _mux_mapped_audio(video, destination, footage, start, duration, cancel, time_map):
    with tempfile.TemporaryDirectory(prefix='.nebula-audio-', dir=Path(video).parent) as folder:
        folder = Path(folder)
        trims = {}
        pieces = []
        for segment in _coalesce_video_segments(time_map):
            left = max(start, segment['start'])
            right = min(start+duration, segment['end'])
            if right <= left: continue
            length = right-left
            offset = segment['video_start']+(left-segment['start'])*segment['video_rate']
            rate = segment['video_rate']
            source = segment.get('footage', footage)
            span = source['out']-source['in']
            piece = folder/f'piece-{len(pieces)}.wav'
            if source['audio'] != 'keep' or not source['has_audio'] or (source['end_mode'] == 'hold' and offset >= span):
                args = ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', str(length)]
            else:
                key = (source['path'], source['in'], source['out'])
                if key not in trims:
                    check_source(source)
                    trimmed = folder/f'trim-{len(trims)}.wav'
                    run_ffmpeg(['-i', source['path'], '-map', '0:a:0', '-vn',
                        '-af', f"atrim=start={source['in']}:end={source['out']},asetpts=PTS-STARTPTS,aresample=48000,apad",
                        '-t', str(span), '-c:a', 'pcm_s16le', str(trimmed)], cancel)
                    trims[key] = trimmed
                args = []
                if source['end_mode'] == 'loop':
                    args += ['-stream_loop', '-1']
                    offset %= span
                args += ['-i', str(trims[key]), '-af',
                    f'atrim=start={offset}:duration={length*rate},asetpts=PTS-STARTPTS,'
                    f'{_tempo_filters(rate)},apad,atrim=duration={length},asetpts=PTS-STARTPTS']
            # A common format makes concatenation independent of the source's
            # channel layout; AAC encoding happens only once after assembly.
            args += ['-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(piece)]
            run_ffmpeg(args, cancel)
            pieces.append(piece)
        args = ['-i', str(video)]
        if pieces:
            listing = folder/'pieces.txt'
            listing.write_text(''.join(f"file '{piece.name}'\n" for piece in pieces))
            args += ['-f', 'concat', '-safe', '0', '-i', str(listing)]
        else:
            args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
        args += ['-map', '0:v:0', '-map', '1:a:0', '-af',
            f'apad,atrim=duration={duration},asetpts=PTS-STARTPTS',
            '-t', str(duration), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', str(destination)]
        run_ffmpeg(args, cancel)


def mux_section_audio(video, destination, segments, start, duration, cancel):
    for segment in segments:
        source = check_source(segment['footage'])
        target = Path(destination)
        if target.resolve() == source.resolve() or (target.exists() and target.samefile(source)):
            raise ValueError('Audio export cannot overwrite a source video')
    return _mux_mapped_audio(video, destination, segments[0]['footage'], start, duration, cancel, segments)
