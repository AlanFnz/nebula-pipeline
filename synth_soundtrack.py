"""One imported audio track on the independent, absolute project clock."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

import numpy as np

from media import Cancellation
from synth_video import run_ffmpeg


def _number(value, label, low=0., high=None):
    try:
        number = float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) else float('nan')
    except OverflowError:
        number = float('nan')
    if not math.isfinite(number) or number < low or high is not None and number > high:
        raise ValueError(f'Soundtrack {label} is outside the supported range')
    return number


def normalize_soundtrack(raw):
    """Validate authored data without opening files or changing its identity."""
    if not isinstance(raw, dict):
        raise ValueError('Soundtrack must be an object')
    path = raw.get('path')
    if not isinstance(path, str) or not path.strip() or '\0' in path:
        raise ValueError('Soundtrack needs a local file path')
    identifier = raw.get('id')
    if not isinstance(identifier, str) or not identifier.strip() or '\0' in identifier:
        raise ValueError('Soundtrack needs a stable id; import or relink the audio')
    name = raw.get('name', Path(path).name)
    if not isinstance(name, str) or '\0' in name:
        raise ValueError('Soundtrack name must be text')
    result = dict(id=identifier, name=name, path=path)
    result['duration'] = _number(raw.get('duration'), 'duration', .001, 86400.)
    for key, high in (('sample_rate', 768000), ('channels', 64)):
        value = _number(raw.get(key), key, 1, high)
        if not value.is_integer():
            raise ValueError(f'Soundtrack {key} must be an integer')
        result[key] = int(value)
    result['in'] = _number(raw.get('in', 0.), 'In', 0., result['duration'])
    result['out'] = _number(raw.get('out', result['duration']), 'Out', 0., result['duration'])
    if result['out'] <= result['in']:
        raise ValueError('Soundtrack Out must be after In')
    result['offset'] = _number(raw.get('offset', 0.), 'Start')
    result['gain'] = _number(raw.get('gain', 1.), 'gain', 0., 1.)
    for key, default, choices in (('end_mode', 'silence', ('silence', 'loop')),
                                 ('export_audio', 'soundtrack', ('soundtrack', 'footage', 'silent'))):
        value = raw.get(key, default)
        if value not in choices:
            raise ValueError(f'Unknown soundtrack {key}')
        result[key] = value
    if 'identity' in raw:
        identity = raw['identity']
        if (not isinstance(identity, dict) or any(isinstance(identity.get(k), bool) or
                not isinstance(identity.get(k), int) or identity[k] < 0 for k in ('size', 'mtime_ns'))):
            raise ValueError('Soundtrack file identity is invalid; import or relink the audio')
        result['identity'] = {key: identity[key] for key in ('size', 'mtime_ns')}
    return result


def _finish_process(proc, cancel):
    if proc.poll() is None:
        proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    if proc.stdout is not None:
        proc.stdout.close()
    cancel.detach(proc)


def probe_soundtrack(path, cancel=None):
    """Cancellably inspect the first audio stream in a local media file."""
    cancel = cancel or Cancellation()
    cancel.check()
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError('Choose a local audio file')
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
            '-show_streams', '-show_format', '-of', 'json', str(path)],
            stdout=subprocess.PIPE, stderr=errors)
        cancel.attach(proc)
        try:
            output, _ = proc.communicate(timeout=30)
            cancel.check()
            if proc.returncode:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors='replace')[-2000:] or 'Cannot read this soundtrack')
        except subprocess.TimeoutExpired:
            raise ValueError('Soundtrack inspection timed out') from None
        finally:
            _finish_process(proc, cancel)
    try:
        data = json.loads(output)
        if not data.get('streams'):
            raise ValueError('No audio stream found in this file')
        stream = data['streams'][0]
        duration = float(stream.get('duration') or data.get('format', {}).get('duration') or 0.)
        sample_rate = int(stream['sample_rate'])
        channels = int(stream['channels'])
    except (KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('Cannot read this soundtrack’s audio metadata') from None
    stat = path.stat()
    cancel.check()
    return normalize_soundtrack(dict(id=str(uuid.uuid4()), name=path.name, path=str(path),
        duration=duration, sample_rate=sample_rate, channels=channels,
        identity={'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}))


def check_soundtrack(track):
    """Return the local media path, or an actionable relink error."""
    track = normalize_soundtrack(track)
    path = Path(track['path'])
    try:
        stat = path.stat()
        if not path.is_file():
            raise OSError()
    except OSError:
        raise ValueError(f'Soundtrack is missing: {path.name}. Use Soundtrack → Relink audio.') from None
    identity = track.get('identity')
    if identity and (stat.st_size != identity['size'] or stat.st_mtime_ns != identity['mtime_ns']):
        raise ValueError(f'Soundtrack has changed: {path.name}. Use Soundtrack → Relink audio to confirm the new file.')
    return path


def soundtrack_source_time(track, project_time):
    """Resolve the source clock; before Start and after a silent ending return None."""
    track = normalize_soundtrack(track)
    time = _number(project_time, 'project time', low=-float('inf'))
    elapsed = time - track['offset']
    if elapsed < 0.:
        return None
    span = track['out'] - track['in']
    if track['end_mode'] == 'loop':
        elapsed %= span
    elif elapsed >= span:
        return None
    return track['in'] + elapsed


def waveform_peaks(track, cancel=None, bins=1000):
    """Stream the full source into bounded peak bins, independent of trim/gain.

    All channels contribute, so opposite-phase stereo cannot hide its waveform.
    Decoding and allocation stay bounded even for a long recording.
    """
    track = normalize_soundtrack(track)
    cancel = cancel or Cancellation()
    cancel.check()
    path = check_soundtrack(track)
    if isinstance(bins, bool) or not isinstance(bins, int) or not 1 <= bins <= 10000:
        raise ValueError('Waveform bins must be between 1 and 10000')
    rate = 12000
    channels = track['channels']
    expected = max(1, math.ceil(track['duration'] * rate))
    peaks = np.zeros(bins, dtype=np.float32)
    position = 0
    frame_bytes = channels * 4
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path),
            '-map', '0:a:0', '-vn', '-ar', str(rate), '-ac', str(channels),
            '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1'], stdout=subprocess.PIPE, stderr=errors)
        cancel.attach(proc)
        try:
            while True:
                cancel.check()
                block = proc.stdout.read(max(frame_bytes, (65536 // frame_bytes) * frame_bytes))
                cancel.check()
                if not block:
                    break
                if len(block) % frame_bytes:
                    raise ValueError('FFmpeg returned incomplete soundtrack samples')
                samples = np.abs(np.frombuffer(block, dtype='<f4').reshape(-1, channels)).max(axis=1)
                indices = np.minimum(bins - 1, (np.arange(len(samples)) + position) * bins // expected)
                np.maximum.at(peaks, indices, samples)
                position += len(samples)
            code = proc.wait()
            cancel.check()
            if code:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors='replace')[-2000:] or 'Cannot decode this soundtrack')
        finally:
            _finish_process(proc, cancel)
    # Decoders can return excursions above unity; keep waveform UI values finite.
    return np.nan_to_num(peaks, nan=0., posinf=1., neginf=0.).clip(0., 1.).astype(float).tolist()


def _same_path(left, right):
    left, right = Path(left), Path(right)
    return left.resolve() == right.resolve() or (left.exists() and right.exists() and os.path.samefile(left, right))


def mux_soundtrack_audio(video, destination, track, start, duration, cancel=None):
    """Atomically replace destination with video plus the absolute project audio.

    Video packets are copied. A partial export begins at ``start`` on the same
    project clock as preview. Loop repeats only In..Out, with silence until Start.
    """
    track = normalize_soundtrack(track)
    start = _number(start, 'export start')
    duration = _number(duration, 'export duration', .000001)
    cancel = cancel or Cancellation()
    cancel.check()
    source = check_soundtrack(track)
    destination = Path(destination)
    if _same_path(destination, source) or _same_path(destination, video):
        raise ValueError('Soundtrack export cannot overwrite its source media; choose another output')
    destination.parent.mkdir(parents=True, exist_ok=True)
    span = track['out'] - track['in']
    delay = min(duration, max(0., track['offset'] - start))
    elapsed = max(0., start - track['offset'])
    silent = delay >= duration or track['gain'] == 0. or (track['end_mode'] == 'silence' and elapsed >= span)
    with tempfile.TemporaryDirectory(prefix='.nebula-soundtrack-', dir=destination.parent) as folder:
        folder = Path(folder)
        result = folder / 'mux.mp4'
        args = ['-i', str(video)]
        if silent:
            args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
            audio_filter = f'atrim=duration={duration},asetpts=PTS-STARTPTS'
        else:
            if track['end_mode'] == 'loop':
                trimmed = folder / 'trim.wav'
                run_ffmpeg(['-i', str(source), '-map', '0:a:0', '-vn', '-af',
                    f"atrim=start={track['in']}:end={track['out']},asetpts=PTS-STARTPTS,aresample=48000,apad",
                    '-t', str(span), '-c:a', 'pcm_s16le', str(trimmed)], cancel)
                elapsed %= span
                args += ['-stream_loop', '-1', '-i', str(trimmed)]
                # Input seeking is reapplied by stream_loop and would repeat
                # only the tail. Trim the continuous repeated stream instead.
                audio_filter = f'atrim=start={elapsed},asetpts=PTS-STARTPTS'
            else:
                args += ['-ss', str(track['in'] + elapsed), '-i', str(source)]
                audio_filter = f'atrim=duration={span - elapsed},asetpts=PTS-STARTPTS'
            # Sample delay preserves sub-millisecond project placement exactly.
            delay_samples = round(delay * 48000)
            audio_filter += f",aresample=48000,volume={track['gain']},adelay={delay_samples}S:all=1,apad,atrim=duration={duration}"
        args += ['-map', '0:v:0', '-map', '1:a:0', '-af', audio_filter,
            '-t', str(duration), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', str(result)]
        run_ffmpeg(args, cancel)
        cancel.check()
        os.replace(result, destination)
    return destination
