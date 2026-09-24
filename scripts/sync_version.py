#!/usr/bin/env python3
"""Synchronize the macOS wrapper metadata with the canonical Python version."""
import argparse
import plistlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _version import __version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report stale metadata without editing it")
    args = parser.parse_args()
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", __version__):
        parser.error("Use a stable MAJOR.MINOR.PATCH version for this macOS wrapper")
    path = ROOT / "Nebula Studio.app" / "Contents" / "Info.plist"
    metadata = plistlib.loads(path.read_bytes())
    keys = ("CFBundleVersion", "CFBundleShortVersionString")
    if args.check:
        if any(metadata.get(key) != __version__ for key in keys):
            parser.exit(1, "Version metadata differs; run python scripts/sync_version.py\n")
        print(f"Version metadata matches {__version__}")
        return
    metadata.update({key: __version__ for key in keys})
    path.write_bytes(plistlib.dumps(metadata, sort_keys=False))
    print(f"Updated macOS metadata to {__version__}")


if __name__ == "__main__":
    main()
