"""Bounded local operation logs, enabled by the desktop entry point.

No frame pixels, audio, document contents or per-playback-tick events are logged.
Tests and library consumers remain silent unless they explicitly configure it.
"""
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

from _version import __version__

_logger = logging.getLogger('nebula.operations')
_logger.propagate = False
_logger.setLevel(logging.INFO)


class _SafeFileHandler(RotatingFileHandler):
    def handleError(self, record):
        pass  # A full/unwritable log disk must not interrupt editing.


def directory():
    state = os.environ.get('NEBULA_STATE_DIR')
    return Path(state) if state else Path.home() / 'Library' / 'Logs' / 'Nebula Studio'


def configure(folder=None):
    close()
    path = Path(folder or directory()) / 'preview-events.log'
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = _SafeFileHandler(path, maxBytes=512*1024, backupCount=2, encoding='utf-8')
    except OSError:
        return None
    handler.setFormatter(logging.Formatter('%(message)s'))
    _logger.addHandler(handler)
    record('session.started', version=__version__, pid=os.getpid())
    return path


def enabled():
    return bool(_logger.handlers)


def record(event, **fields):
    if not enabled(): return
    try:
        _logger.info(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                                    event=event, **fields), ensure_ascii=False, allow_nan=False))
    except (OSError, TypeError, ValueError):
        pass


def close():
    for handler in _logger.handlers[:]:
        _logger.removeHandler(handler)
        handler.close()
