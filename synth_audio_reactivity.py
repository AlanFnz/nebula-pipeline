"""Deterministic band energy and envelopes on the absolute project clock.

Decoded PCM is streamed in 40 ms native-rate windows; only the portion of the
trim reachable by this (at most one-hour) sequence is analyzed. Fixed amplitude
scaling avoids amplifying quiet recordings or numerical leakage. Derived data
is disposable and held in a bounded in-memory cache, never in project files.
"""
from __future__ import annotations

from collections import OrderedDict
import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import threading

import numpy as np

from media import Cancellation
from synth_soundtrack import normalize_soundtrack, check_soundtrack, _finish_process

ANALYSIS_VERSION = 1
RESPONSE_FPS = 50
NOISE_FLOOR = 1e-4
MAX_MAPPINGS = 16
CACHE_BYTES = 64 * 1024 * 1024
CACHE_ENTRIES = 8
_TARGETS = (
    ('radial_bloom.expansion', 'Radial bloom · Expansion'),
    ('radial_bloom.detail', 'Radial bloom · Detail'),
    ('radial_bloom.light', 'Radial bloom · Light'),
    ('radial_bloom.vibration', 'Radial bloom · Ray vibration'),
    ('bloom.strength', 'Bloom · Strength'), ('raster.grain', 'Raster · Grain'),
    ('warp.amount', 'Warp · Amount'), ('tape.pull', 'Tape · Pull'),
    ('frame_jitter.strength', 'Frame jitter · Strength'),
    ('tape.mix', 'Tape damage · Mix'),
    ('separation.amount', 'Separation · Amount'),
    ('signal_repetition.mix', 'Signal repetition · Mix'),
)
_cache = OrderedDict()
_lock = threading.RLock()
_prepare_lock = threading.Lock()


def reactivity_targets():
    return _TARGETS


def target_parameter(path):
    from synth import MODULE_BY_ID
    from synth_instances import base_path
    if not isinstance(path, str) or path.count('.') != 1 or base_path(path) not in dict(_TARGETS):
        raise ValueError(f'Unsupported audio mapping target: {path}')
    module, key = path.split('.')
    try:
        spec = next(p for p in MODULE_BY_ID[module].params if p.key == key)
    except (KeyError, StopIteration):
        raise ValueError(f'Audio mapping target is not installed: {path}') from None
    if spec.kind != 'float':
        raise ValueError(f'Audio mapping target must be continuous: {path}')
    return spec


def _number(value, name, low, high):
    try:
        number = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else float('nan')
    except OverflowError:
        number = float('nan')
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f'Audio mapping {name} must be between {low} and {high}')
    return number


def normalize_reactivity(raw, track=None):
    if not isinstance(raw, dict):
        raise ValueError('Audio reactivity must be an object')
    enabled = raw.get('enabled', True)
    if not isinstance(enabled, bool):
        raise ValueError('Audio reactivity enabled must be a boolean')
    mappings = raw.get('mappings', [])
    if not isinstance(mappings, list) or len(mappings) > MAX_MAPPINGS:
        raise ValueError('Audio reactivity supports at most 16 mappings')
    track = normalize_soundtrack(track) if track is not None else None
    nyquist = track['sample_rate'] / 2 if track else 384000.
    result = {'enabled': enabled, 'mappings': []}
    ids = set()
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ValueError('Audio mapping must be an object')
        item = {}
        for key in ('id', 'track_id'):
            value = mapping.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 256 or '\0' in value:
                raise ValueError(f'Audio mapping needs a stable {key}')
            item[key] = value
        if item['id'] in ids:
            raise ValueError('Audio mapping ids must be unique')
        ids.add(item['id'])
        if track and item['track_id'] != track['id']:
            raise ValueError('Audio mapping belongs to a different soundtrack; relink or remove the mapping')
        item['path'] = mapping.get('path')
        spec = target_parameter(item['path'])
        span = spec.maximum - spec.minimum
        item['low_hz'] = _number(mapping.get('low_hz', 0.), 'low Hz', 0., nyquist)
        item['high_hz'] = _number(mapping.get('high_hz', nyquist), 'high Hz (Nyquist)', 0., nyquist)
        if item['high_hz'] <= item['low_hz']:
            raise ValueError('Audio mapping high Hz must be above low Hz')
        item['amount'] = _number(mapping.get('amount', 0.), 'amount', -span, span)
        item['sensitivity'] = _number(mapping.get('sensitivity', 1.), 'sensitivity', 0., 16.)
        item['attack'] = _number(mapping.get('attack', .05), 'attack seconds', 0., 10.)
        item['release'] = _number(mapping.get('release', .2), 'release seconds', 0., 10.)
        item['enabled'] = mapping.get('enabled', True)
        if not isinstance(item['enabled'], bool):
            raise ValueError('Audio mapping enabled must be a boolean')
        if track is None and enabled and item['enabled'] and item['amount'] != 0 and item['sensitivity'] != 0:
            raise ValueError('Active audio mappings need a soundtrack; import or relink audio')
        result['mappings'].append(item)
    return result


def _configuration(sequence):
    track = sequence.get('soundtrack')
    raw = sequence.get('audio_reactivity')
    config = normalize_reactivity(raw, track) if raw is not None else {'enabled': False, 'mappings': []}
    active = [m for m in config['mappings'] if config['enabled'] and m['enabled'] and m['amount'] != 0. and m['sensitivity'] != 0.]
    states = sequence.get('states')
    if states and all('enabled' in state for state in states.values()):
        enabled_modules = {module for state in states.values() for module in state['enabled']}
        active = [m for m in active if m['path'].split('.')[0] in enabled_modules]
    duration = _number(sequence.get('duration', 0.), 'project duration', 0., 3600.)
    # Monitor/output levels are deliberately excluded from analysis identity.
    source = {k: track[k] for k in ('id', 'path', 'identity', 'sample_rate', 'channels', 'duration', 'in', 'out', 'offset', 'end_mode') if k in track} if track else None
    payload = {'version': ANALYSIS_VERSION, 'track': source, 'mappings': active, 'duration': duration}
    key = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return config, active, duration, key


@dataclass(frozen=True)
class ReactivityAnalysis:
    key: str
    responses: dict
    fps: int = RESPONSE_FPS
    offset: float = 0.
    fingerprint: tuple | None = None

    @property
    def nbytes(self):
        return sum(value.nbytes for value in self.responses.values())


def _source_energy(track, mappings, length, cancel):
    """Streaming native-channel FFT, with bounded window and band envelopes."""
    rate, channels = track['sample_rate'], track['channels']
    hop = max(1, round(rate / RESPONSE_FPS))
    window_size = 2 * hop
    count = math.ceil(length * rate / hop) + 1
    bands = list(dict.fromkeys((m['low_hz'], m['high_hz']) for m in mappings))
    energies = {band: np.zeros(count, dtype=np.float32) for band in bands}
    window = np.hanning(window_size).astype(np.float32)
    frequencies = np.fft.rfftfreq(window_size, 1 / rate)
    masks = {band: (frequencies >= band[0]) & (frequencies <= band[1]) for band in bands}
    weights = np.full(len(frequencies), 2., dtype=np.float64)
    weights[0] = weights[-1] = 1.
    scale = window_size * float(np.sum(window ** 2))
    ring = np.zeros((window_size, channels), dtype=np.float32)
    # Center the first analysis window on the trim's In point, padded with zero.
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(track['in']),
            '-i', track['path'], '-t', str(length), '-map', '0:a:0', '-vn',
            '-ar', str(rate), '-ac', str(channels), '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1'],
            stdout=subprocess.PIPE, stderr=errors)
        cancel.attach(proc)
        try:
            for index in range(count):
                cancel.check()
                raw = proc.stdout.read(hop * channels * 4)
                cancel.check()
                if len(raw) % (channels * 4):
                    raise ValueError('Audio analysis received incomplete samples')
                ring[:hop] = ring[hop:]
                ring[hop:] = 0.
                samples = np.frombuffer(raw, dtype='<f4').reshape(-1, channels)
                if not np.isfinite(samples).all():
                    raise ValueError('Soundtrack contains invalid audio samples; relink audio and retry')
                ring[hop:hop + len(samples)] = samples
                fft = np.fft.rfft(ring * window[:, None], axis=0)
                power = np.mean(np.abs(fft) ** 2, axis=1) * weights / scale
                for band, mask in masks.items():
                    energies[band][index] = math.sqrt(max(0., float(np.sum(power[mask]))))
            # Drain at most a window's rounding remainder; ffmpeg -t bounds input.
            while proc.stdout.read(hop * channels * 4):
                cancel.check()
            code = proc.wait()
            cancel.check()
            if code:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors='replace')[-2000:] or 'Soundtrack analysis failed')
        finally:
            _finish_process(proc, cancel)
    return energies


def _project_responses(track, mappings, duration, energies, cancel):
    count = math.ceil(duration * RESPONSE_FPS) + 1
    times = np.arange(count, dtype=np.float64) / RESPONSE_FPS
    span = track['out'] - track['in']
    elapsed = times - track['offset']
    audible = elapsed >= 0.
    if track['end_mode'] == 'loop':
        elapsed = np.maximum(elapsed, 0.) % span
    else:
        audible &= elapsed < span
    responses = {}
    for mapping in mappings:
        cancel.check()
        energy = energies[(mapping['low_hz'], mapping['high_hz'])]
        source_rate = track['sample_rate'] / max(1, round(track['sample_rate'] / RESPONSE_FPS))
        raw = np.interp(elapsed * source_rate, np.arange(len(energy)), energy, left=0., right=0.)
        raw[~audible] = 0.
        # Fixed reference: RMS .125 corresponds to unity at sensitivity 1.
        raw = np.where(raw <= NOISE_FLOOR, 0., np.minimum(1., raw * 8. * mapping['sensitivity']))
        envelope = np.zeros(count, dtype=np.float32)
        previous = 0.
        attack = math.exp(-1 / (RESPONSE_FPS * mapping['attack'])) if mapping['attack'] else 0.
        release = math.exp(-1 / (RESPONSE_FPS * mapping['release'])) if mapping['release'] else 0.
        for index, value in enumerate(raw):
            if index % 1024 == 0: cancel.check()
            coefficient = attack if value > previous else release
            previous = float(value) + coefficient * (previous - float(value))
            if abs(previous) < 1e-12: previous = 0.
            envelope[index] = previous
        envelope.flags.writeable = False
        responses[mapping['id']] = envelope
    return responses


def _source_fingerprint(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def prepare_reactivity(sequence, cancel=None):
    """Prepare once in a cancellable worker. Never return neutral on failure."""
    cancel = cancel or Cancellation()
    cancel.check()
    _, mappings, duration, key = _configuration(sequence)
    if not mappings:
        return ReactivityAnalysis(key, {})
    track = normalize_soundtrack(sequence['soundtrack'])
    path = check_soundtrack(track)
    stat = path.stat()
    fingerprint = _source_fingerprint(stat)
    cache_key = (key, fingerprint)
    while not _prepare_lock.acquire(timeout=.1):
        cancel.check()
    try:
        cancel.check()
        with _lock:
            if cache_key in _cache:
                _cache.move_to_end(cache_key)
                return _cache[cache_key]
        length = min(track['out'] - track['in'], max(0., duration - track['offset']))
        energies = _source_energy(track, mappings, length, cancel) if length > 0 else {
            (m['low_hz'], m['high_hz']): np.zeros(1, dtype=np.float32) for m in mappings}
        analysis = ReactivityAnalysis(key, _project_responses(track, mappings, duration, energies, cancel), offset=track['offset'], fingerprint=fingerprint)
        cancel.check()
        # Detect source replacement during analysis even without authored identity.
        current = path.stat()
        if _source_fingerprint(current) != fingerprint:
            raise ValueError('Soundtrack changed during analysis; relink audio and retry')
        with _lock:
            _cache[cache_key] = analysis
            while len(_cache) > CACHE_ENTRIES or sum(a.nbytes for a in _cache.values()) > CACHE_BYTES:
                _cache.popitem(last=False)
        return analysis
    finally:
        _prepare_lock.release()


def _cached_analysis(key):
    with _lock:
        for cache_key in reversed(_cache):
            if cache_key[0] == key:
                return _cache[cache_key]
    return None


def _responses_at(analysis, seconds):
    seconds = _number(seconds, 'project time', 0., 3600.)
    if seconds < analysis.offset:
        return {identifier: 0. for identifier in analysis.responses}
    position = seconds * analysis.fps
    result = {}
    for identifier, values in analysis.responses.items():
        left = min(len(values) - 1, int(position))
        right = min(len(values) - 1, left + 1)
        fraction = max(0., min(1., position - left))
        result[identifier] = float(values[left] * (1. - fraction) + values[right] * fraction)
    return result


def cached_responses(sequence, seconds):
    """Read prepared responses without touching media or initiating analysis."""
    _, mappings, _, key = _configuration(sequence)
    if not mappings:
        return {}
    analysis = _cached_analysis(key)
    return _responses_at(analysis, seconds) if analysis is not None else None


def apply_reactivity(preset, sequence, seconds, *, analysis=None, cancel=None):
    """Add responses to the resolved animated base, summing before one clamp."""
    _, mappings, _, key = _configuration(sequence)
    modules = {m['id']: m for m in preset['modules']}
    mappings = [m for m in mappings if modules.get(m['path'].split('.')[0], {}).get('enabled', False)]
    if not mappings:
        return preset
    if analysis is None:
        # Worker-side preparation validates actual media even on a cache hit.
        analysis = prepare_reactivity(sequence, cancel)
    if not isinstance(analysis, ReactivityAnalysis) or analysis.key != key:
        raise ValueError('Audio analysis is stale; prepare soundtrack mappings again')
    path = check_soundtrack(sequence['soundtrack'])
    stat = path.stat()
    if analysis.fingerprint != _source_fingerprint(stat):
        raise ValueError('Audio analysis is stale after soundtrack replacement; relink audio and prepare again')
    values = _responses_at(analysis, seconds)
    if any(m['id'] not in values for m in mappings):
        raise ValueError('Audio analysis is unavailable; prepare soundtrack mappings again')
    deltas = {}
    for mapping in mappings:
        delta = mapping['amount'] * values[mapping['id']]
        if delta != 0.:
            deltas.setdefault(mapping['path'], []).append(delta)
    deltas = {path: math.fsum(values) for path, values in deltas.items()}
    if not any(deltas.values()):
        return preset
    result = copy.deepcopy(preset)
    edited = {m['id']: m for m in result['modules']}
    for path, delta in deltas.items():
        module, parameter = path.split('.')
        spec = target_parameter(path)
        original = modules[module]['params'][parameter]
        edited[module]['params'][parameter] = max(spec.minimum, min(spec.maximum, original + delta))
    return result
