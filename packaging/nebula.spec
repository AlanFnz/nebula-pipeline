# Run through scripts/build_macos.py so the .icns is generated first.
from pathlib import Path
import plistlib

root = Path(SPECPATH).parent
metadata = plistlib.loads((root / "packaging" / "Info.plist").read_bytes())
analysis = Analysis(
    [str(root / "mac_app.py")], pathex=[str(root)],
    datas=[(str(root / "assets"), "assets"), (str(root / "presets"), "presets")],
    hiddenimports=["PySide6.QtSvg"],
    excludes=["tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive, analysis.scripts, [], exclude_binaries=True,
    name="nebula-studio", console=False, argv_emulation=False,
)
collection = COLLECT(executable, analysis.binaries, analysis.datas, name="Nebula Studio")
app = BUNDLE(
    collection, name="Nebula Studio.app",
    icon=str(root / "build" / "icons" / "nebula.icns"),
    bundle_identifier=metadata["CFBundleIdentifier"], info_plist=metadata,
)
