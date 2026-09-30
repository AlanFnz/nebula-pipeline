"""Proxy LRU bookkeeping leaves published media stat identities immutable."""
import os
from pathlib import Path
from synth_preview import _file_fingerprint
from synth_video import prepare_proxy, _proxy_use_path, _proxy_last_used, _prune_proxies
from test_synth_video import clip


def stamp(path, value):
    os.utime(path, ns=(value, value))


def test_repeated_proxy_use_updates_sidecar_and_keeps_fingerprint(clip, tmp_path):
    proxy = prepare_proxy(clip, directory=tmp_path)
    original = _file_fingerprint(proxy)
    usage = _proxy_use_path(proxy)
    assert usage.exists() and usage.stat().st_size == 0
    stamp(usage, 100)
    assert prepare_proxy(clip, directory=tmp_path) == proxy
    assert usage.stat().st_mtime_ns > 100 and _file_fingerprint(proxy) == original
    assert prepare_proxy(clip, directory=tmp_path) == proxy
    assert _file_fingerprint(proxy) == original


def test_proxy_fingerprint_is_stat_only_and_detects_file_replacement(tmp_path, monkeypatch):
    proxy = tmp_path/'proxy.mkv'; proxy.write_bytes(b'old proxy')
    original = _file_fingerprint(proxy)
    replacement = tmp_path/'replacement'; replacement.write_bytes(b'new proxy')
    prior = proxy.stat()
    stamp(replacement, prior.st_mtime_ns)
    os.replace(replacement, proxy)
    def fail_open(*args, **kwargs): raise AssertionError('Fingerprint read proxy content')
    monkeypatch.setattr(Path, 'open', fail_open)
    assert _file_fingerprint(proxy) != original
    assert _file_fingerprint(proxy) == _file_fingerprint(proxy)


def test_pruning_uses_usage_metadata_and_removes_evicted_sidecar(tmp_path):
    active, frequent, recent_media = [tmp_path/f'{name}.mkv' for name in ('active', 'frequent', 'recent')]
    for path in (active, frequent, recent_media): path.write_bytes(b'pixels')
    stamp(active, 50); stamp(frequent, 100); stamp(recent_media, 300)
    for path, used in ((active, 600), (frequent, 500), (recent_media, 400)):
        sidecar = _proxy_use_path(path); sidecar.touch(); stamp(sidecar, used)
    original = _file_fingerprint(frequent)
    _prune_proxies(tmp_path, active, budget=12)
    assert active.exists() and frequent.exists() and not recent_media.exists()
    assert not _proxy_use_path(recent_media).exists()
    assert _file_fingerprint(frequent) == original


def test_pruning_accepts_legacy_mtime_and_keeps_oversized_active_proxy(tmp_path):
    active, recent, old = [tmp_path/f'{name}.mkv' for name in ('active', 'recent', 'old')]
    for path in (active, recent, old): path.write_bytes(b'pixels')
    stamp(active, 50); stamp(recent, 300); stamp(old, 100)
    assert _proxy_last_used(recent) == recent.stat().st_mtime_ns
    _prune_proxies(tmp_path, active, budget=12)
    assert active.exists() and recent.exists() and not old.exists()
    _prune_proxies(tmp_path, active, budget=1)
    assert active.exists() and not recent.exists()
