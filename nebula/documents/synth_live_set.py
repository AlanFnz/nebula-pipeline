"""Optional Live Set links are document metadata, never rendering inputs."""
from pathlib import Path

LIVE_SET = 'ableton_live_set'


def normalize_live_set(path):
    if not isinstance(path, str) or not path.strip() or '\0' in path or Path(path).suffix.lower() != '.als':
        raise ValueError('Choose an Ableton Live Set (.als).')
    return path


def linked_documents(document):
    if not isinstance(document, dict): return
    if LIVE_SET in document: yield document
    yield from linked_documents(document.get('source'))
    for item in document.get('snapshots', ()):
        yield from linked_documents(item.get('document'))
    for item in document.get('assets', {}).values():
        yield from linked_documents(item.get('document'))
    for item in document.get('clips', ()):
        yield from linked_documents(item.get('document'))


def live_set_paths(document):
    for item in linked_documents(document):
        if item[LIVE_SET] is not None: yield normalize_live_set(item[LIVE_SET])


def resolve_live_set_paths(document, directory):
    for item in linked_documents(document):
        if item[LIVE_SET] is None: continue
        path = Path(normalize_live_set(item[LIVE_SET])).expanduser()
        item[LIVE_SET] = str((Path(directory) / path).absolute())
