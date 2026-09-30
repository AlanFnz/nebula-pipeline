"""Entry point for the Finder/Dock app; development still uses studio.py."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback


def main():
    # Finder launches do not inherit the user's interactive shell PATH.
    paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    paths.extend(os.environ.get("PATH", "").split(os.pathsep))
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(path for path in paths if path))
    log_path = Path.home() / "Library" / "Logs" / "Nebula Studio" / "studio.log"
    if getattr(sys, "frozen", False):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("a", buffering=1)
        sys.stdout = sys.stderr = log
    args = sys.argv[1:]
    if "--clip-studio" in args:
        args.remove("--clip-studio")
    elif not args:
        args = ["--synth"]
    sys.argv = [sys.argv[0], *args]
    try:
        from studio import main as run_studio
        run_studio()
    except Exception:
        traceback.print_exc()
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Nebula Studio", f"The studio could not start. Details are in:\n{log_path}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
