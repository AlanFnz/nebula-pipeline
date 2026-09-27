"""Built-in studies and independent local snapshots, including their video source."""
from __future__ import annotations

import copy
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from media import Cancellation
from synth_composition import load_composition, normalize_composition, save_composition, section_ranges
from synth_starters import STARTERS, starter_composition
from synth_video import check_source

PERSONAL_PREFIX = 'personal:'


def studies_directory():
    return Path.home() / 'Library/Application Support/Nebula Studio/Studies'


def study_catalogue(directory=None):
    """Return selectable IDs and labels; user files never replace bundled recipes."""
    entries = [(key, label) for key, label, _factory in STARTERS]
    root = Path(directory) if directory else studies_directory()
    personal = []
    if root.exists():
        for folder in root.iterdir():
            if not re.fullmatch(r'[0-9a-f]{32}', folder.name) or not folder.is_dir(): continue
            try:
                project = load_composition(folder / 'study.json')
                duration = section_ranges(project)[-1][1]
                personal.append((PERSONAL_PREFIX + folder.name, f"{project['name']} · {duration:.1f}s"))
            except (OSError, ValueError, TypeError, KeyError):
                # An incomplete or manually edited local file must not prevent
                # the rest of the library or the app from opening.
                continue
    return entries + sorted(personal, key=lambda entry: (entry[1].casefold(), entry[0]))


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
        cancel.check()
        staged.rename(destination)
    return PERSONAL_PREFIX + key
