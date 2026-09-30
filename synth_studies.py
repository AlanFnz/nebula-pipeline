"""Built-in studies and independent local snapshots, including their video source."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from media import Cancellation
from synth_composition import load_composition, normalize_composition, save_composition, section_ranges
from synth_starters import STARTERS, STARTER_DATES, starter_composition
from synth_video import check_source

PERSONAL_PREFIX = 'personal:'
LIBRARY_FILE = '.library.json'


@dataclass(frozen=True)
class Study:
    identifier: str
    name: str
    date: str
    personal: bool = False
    removed: bool = False
    estimated_date: bool = False

    @property
    def label(self):
        return f'{self.name} · {self.date}'

    @property
    def date_hint(self):
        if not self.personal: return 'Date first added to the built-in library.'
        if self.estimated_date: return 'Original file creation date (file modification date where creation is unavailable).'
        return 'Date this independent study was saved.'


def studies_directory():
    return Path.home() / 'Library/Application Support/Nebula Studio/Studies'


def _removed_ids(root, strict=False):
    try:
        raw = json.loads((root / LIBRARY_FILE).read_text())
        if not isinstance(raw, dict) or raw.get('schema_version') != 1:
            raise ValueError('Invalid study library index')
        removed = raw.get('removed')
        if not isinstance(removed, list) or not all(isinstance(key, str) for key in removed):
            raise ValueError('Invalid removed study IDs')
        return set(removed)
    except FileNotFoundError:
        return set()
    except (OSError, ValueError, TypeError) as error:
        if strict: raise ValueError(f'Could not read the study library index: {error}') from error
        return set()


def _saved_date(folder):
    try:
        saved_at = json.loads((folder / 'metadata.json').read_text())['saved_at']
        return datetime.fromisoformat(saved_at).date().isoformat(), False
    except (OSError, ValueError, TypeError, KeyError):
        stat = (folder / 'study.json').stat()
        timestamp = getattr(stat, 'st_birthtime', stat.st_mtime)
        return datetime.fromtimestamp(timestamp).date().isoformat(), True


def study_records(directory=None, include_removed=False):
    """Read library metadata without changing compositions or media paths."""
    root = Path(directory) if directory else studies_directory()
    removed = _removed_ids(root)
    entries = [Study(key, label, STARTER_DATES[key], removed=key in removed)
               for key, label, _factory in STARTERS]
    personal = []
    if root.exists():
        for folder in root.iterdir():
            if not re.fullmatch(r'[0-9a-f]{32}', folder.name) or not folder.is_dir(): continue
            try:
                project = load_composition(folder / 'study.json')
                duration = section_ranges(project)[-1][1]
                identifier = PERSONAL_PREFIX + folder.name
                date, estimated = _saved_date(folder)
                personal.append(Study(identifier, f"{project['name']} · {duration:.1f}s",
                                      date, True, identifier in removed, estimated))
            except (OSError, ValueError, TypeError, KeyError):
                # An incomplete or manually edited local file must not prevent
                # the rest of the library or the app from opening.
                continue
    entries += sorted(personal, key=lambda entry: (entry.name.casefold(), entry.identifier))
    return [entry for entry in entries if include_removed or not entry.removed]


def study_catalogue(directory=None):
    """Return selectable IDs and dated labels; bundled recipes stay independent."""
    return [(entry.identifier, entry.label) for entry in study_records(directory)]


def set_studies_removed(identifiers, removed=True, directory=None):
    """Remove or restore library entries atomically, retaining files and references.

    The reversible index handles bundled and personal studies alike. Media stays
    at its original path, so open compositions and documents saved separately
    continue to work even after their library entry has been removed.
    """
    root = Path(directory) if directory else studies_directory()
    identifiers = set(identifiers)
    available = {entry.identifier for entry in study_records(root, include_removed=True)}
    if identifiers - available: raise ValueError('Unknown study')
    if not identifiers: return
    hidden = _removed_ids(root, strict=True)
    hidden = hidden | identifiers if removed else hidden - identifiers
    root.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', prefix='.library-', suffix='.tmp', dir=root,
                                         encoding='utf-8', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'schema_version': 1, 'removed': sorted(hidden)}, stream, indent=2)
            stream.write('\n')
        temporary.replace(root / LIBRARY_FILE)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def study_composition(identifier, directory=None):
    if not identifier.startswith(PERSONAL_PREFIX):
        return starter_composition(identifier)
    key = identifier.removeprefix(PERSONAL_PREFIX)
    if not re.fullmatch(r'[0-9a-f]{32}', key): raise ValueError('Unknown personal study')
    root = Path(directory) if directory else studies_directory()
    return load_composition(root / key / 'study.json')


def save_study(project, name, directory=None, cancel=None):
    """Atomically publish a new snapshot, never mutate the working composition.

    Video stays local and travels with its JSON document. Separate saves get
    unique IDs even if their display names match. No source assets enter Git.
    """
    cancel = cancel or Cancellation()
    cancel.check()
    name = str(name).strip()
    if not name or len(name) > 80: raise ValueError('Use a study name between 1 and 80 characters')
    document = normalize_composition(copy.deepcopy(project))
    document['name'] = name
    root = Path(directory) if directory else studies_directory()
    root.mkdir(parents=True, exist_ok=True)
    key = uuid.uuid4().hex
    destination = root / key
    with tempfile.TemporaryDirectory(prefix='.saving-', dir=root) as staging:
        staged = Path(staging)
        if 'footage' in document:
            footage = document['footage']
            original = check_source(footage)
            media = staged / 'media'; media.mkdir()
            copied = media / ('source' + original.suffix.lower())
            with original.open('rb') as source, copied.open('wb') as target:
                while chunk := source.read(1024 * 1024):
                    cancel.check()
                    target.write(chunk)
            shutil.copystat(original, copied)
            check_source(footage)
            stat = copied.stat()
            if stat.st_size != footage['identity']['size']:
                raise ValueError('Video changed while saving the study; please try again')
            footage['path'] = copied.relative_to(staged).as_posix()
            footage['identity'] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
            if 'footage' in document['source']:
                document['source']['footage'] = copy.deepcopy(footage)
        save_composition(staged / 'study.json', document)
        (staged / 'metadata.json').write_text(json.dumps({
            'schema_version': 1, 'saved_at': datetime.now().astimezone().isoformat(),
        }, indent=2) + '\n')
        cancel.check()
        staged.rename(destination)
    return PERSONAL_PREFIX + key
