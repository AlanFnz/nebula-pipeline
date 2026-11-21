"""Discover an optional, local catalogue of editable study documents."""
import json
import os
from pathlib import Path
import re


def library_directory():
    configured = os.environ.get("NEBULA_STUDY_LIBRARY")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library/Application Support/Nebula Studio/Study Library"


def catalogue():
    try:
        data = json.loads((library_directory() / "catalog.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported study catalogue")
    return data


def study_entries():
    seen = set()
    for item in catalogue().get("studies", []):
        key = item["id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", key) or key in seen:
            raise ValueError("Invalid or duplicate study identifier")
        seen.add(key)
        yield key, item
