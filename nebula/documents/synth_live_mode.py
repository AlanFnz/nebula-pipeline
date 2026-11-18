"""Saved playback destination; independent of the optional .als association."""

LIVE_OUTPUT = 'ableton_live'


def supports_live(config):
    return bool(config and config.get('version') in (3, 4))


def is_live(config):
    return supports_live(config) and config.get('output') == LIVE_OUTPUT


def normalize_output(value, version):
    choices = ('generated', 'existing', 'silent')
    if version in (3, 4): choices += (LIVE_OUTPUT,)
    if value not in choices:
        raise ValueError('Choose a supported playback destination')
    return value
