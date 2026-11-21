"""Stable study identifiers, supplied by an optional local library."""
from functools import partial
from nebula.documents.study_library import library_directory, study_entries
from nebula.documents.synth_composition import load_composition


_entries = dict(study_entries())


def starter_composition(identifier):
    if identifier not in _entries:
        raise ValueError(f"Unknown starter: {identifier}")
    return load_composition(library_directory() / "studies" / f"{identifier}.nebula")


STARTERS = tuple((key, entry["name"], partial(starter_composition, key))
                 for key, entry in _entries.items())
STARTER_DATES = {key: entry["date"] for key, entry in _entries.items()}
BUILTIN_CATEGORIES = {key: entry.get("category", "Other") for key, entry in _entries.items()}
