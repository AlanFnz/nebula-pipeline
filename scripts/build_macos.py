#!/usr/bin/env python3
"""Build a local macOS app; optionally install it in ~/Applications."""
from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Nebula Studio.app"


def build_icon():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    folder = ROOT / "build" / "icons"
    iconset = folder / "nebula.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(ROOT / "assets" / "nebula-icon.svg"))
    if not renderer.isValid():
        raise RuntimeError("Invalid application icon")
    for points in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            image = QImage(points * scale, points * scale, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image); renderer.render(painter); painter.end()
            name = f"icon_{points}x{points}{'@2x' if scale == 2 else ''}.png"
            if not image.save(str(iconset / name)):
                raise RuntimeError(f"Could not write {name}")
    subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(folder / "nebula.icns")], check=True)
    app.quit()


def install_app(source):
    destination = Path.home() / "Applications" / APP_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    executable = str(destination / "Contents" / "MacOS" / "nebula-studio")
    running = subprocess.check_output(["/bin/ps", "-axo", "comm="], text=True)
    if executable in running.splitlines():
        raise RuntimeError("Quit the installed Nebula Studio before updating it, then run this command again.")
    if destination.exists():
        metadata = plistlib.loads((destination / "Contents" / "Info.plist").read_bytes())
        if metadata.get("CFBundleIdentifier") != "com.alanfnz.nebula-studio":
            raise RuntimeError(f"A different application already exists at {destination}")
    # Stage a complete copy before touching a previous installation.
    with tempfile.TemporaryDirectory(prefix=".nebula-install-", dir=destination.parent) as temporary:
        staged = Path(temporary) / APP_NAME
        shutil.copytree(source, staged, symlinks=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(staged)], check=True)
        backup = None
        if destination.exists():
            backup = destination.with_name("Nebula Studio.backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup: backup.rename(destination)
            raise
        if backup: print(f"Previous installation preserved at {backup}")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install in ~/Applications; preserve any previous app as a backup")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Build the macOS app on a Mac")
    if importlib.util.find_spec("PyInstaller") is None:
        parser.error("Install build dependencies first: python -m pip install -r requirements-build.txt")
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            parser.error(f"Install FFmpeg first; {binary} is not on PATH")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_version.py"), "--check"], check=True)
    build_icon()
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm",
        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
        str(ROOT / "packaging" / "nebula.spec"),
    ], cwd=ROOT, check=True)
    app = ROOT / "dist" / APP_NAME
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    if args.install: app = install_app(app)
    print(f"Ready: {app}")


if __name__ == "__main__":
    main()
