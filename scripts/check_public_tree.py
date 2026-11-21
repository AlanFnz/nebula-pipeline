"""Reject artwork documents in the Git index or in trees about to be pushed."""
import argparse
import json
from pathlib import PurePosixPath
import subprocess
import sys


def git(*args):
    return subprocess.check_output(["git", *args])


def artwork(payload):
    if isinstance(payload, list):
        return any(artwork(item) for item in payload)
    if not isinstance(payload, dict):
        return False
    if str(payload.get("format", "")).startswith("nebula-"):
        return True
    if {"states", "cues"} <= payload.keys() or "starters" in payload:
        return True
    return any(artwork(item) for item in payload.values())


def inspect(entries, checked):
    problems = []
    for row in entries.split(b"\0"):
        if not row:
            continue
        metadata, raw = row.split(b"\t", 1)
        fields = metadata.split()
        oid = fields[1] if len(fields[1]) >= 40 else fields[2]
        path = PurePosixPath(raw.decode("utf-8", "surrogateescape").lower())
        if (path.parts[0] in {"studies", "projects", "personal", "presets", "examples", "authoring", "library"} or
                path.suffix in {".nebula", ".als", ".blend", ".mp4", ".mov", ".wav"} or
                path.name.endswith((".nebula.json", "_recipes.py")) or path.name.startswith("create_") and "study" in path.name):
            problems.append(str(path))
            continue
        if oid in checked:
            if checked[oid]:
                problems.append(str(path))
            continue
        # Inspect structured payloads even when an exported project was renamed.
        data = git("cat-file", "blob", oid.decode())
        rejected = False
        if data.lstrip().startswith((b"{", b"[")):
            try:
                rejected = artwork(json.loads(data))
            except (ValueError, RecursionError):
                pass
        checked[oid] = rejected
        if rejected:
            problems.append(str(path))
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commits", action="store_true", help="read commit IDs from stdin")
    args = parser.parse_args()
    trees = (git("ls-tree", "-rz", commit.strip()) for commit in sys.stdin if commit.strip()) if args.commits else [git("ls-files", "--stage", "-z")]
    checked = {}
    for tree in trees:
        problems = inspect(tree, checked)
        if problems:
            sys.exit("Store study material in the private library:\n" + "\n".join(problems))


if __name__ == "__main__":
    main()
