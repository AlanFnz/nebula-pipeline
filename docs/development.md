# Run, test and build Nebula

[Documentation](README.md) · [Versioning](../VERSIONING.md)

Reference studies should reuse or extend existing sources and effects before
adding parallel tools. Keep useful controls editable and preserve earlier study
recipes. See [the development guidelines](../AGENTS.md).

## Run from source

Run these commands from the repository root. The recorded macOS development
environment uses Python 3.14 and PySide6 6.11.2. Dependencies are defined by
[requirements-desktop.txt](../requirements-desktop.txt), which includes
[requirements.txt](../requirements.txt). The repository does not establish a
verified minimum Python version or a Windows/Linux support matrix.

You need Python, FFmpeg and `ffprobe` on PATH. On a Mac using Homebrew, the
installation step is `brew install python ffmpeg`. Then create the environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python studio.py --version
.venv/bin/python studio.py --synth
```

`--synth` opens the composer. `studio.py` without it opens the earlier
[Print / Scan editor](legacy-clip-editor.md). Its optional input arguments are:

```sh
.venv/bin/python studio.py /path/to/clip.mp4 --preset /path/to/settings.json
```

`--synth-preset` accepts a standalone synth preset through `load_synth`.
`--project /path/to/file.nebula` opens a composition, sequence, preset or Montage;
legacy JSON documents also work. These extensions share the existing payload
formats and schema versions. **Open** uses the same document loaders.
The Finder app uses [mac_app.py](../mac_app.py): with no arguments it opens the
composer, and `--clip-studio` selects the older editor.

The macOS bundle declares only `.nebula` as its owned document type; it does not
take over JSON associations. Qt `QFileOpenEvent` requests are queued by
`synth_project_files.py` before the workspace is ready and use its replacement
guards. Packaging includes the app icon and `nebula-document.icns`, generated
from the source assets by the build script.

Foreground extraction requires macOS 14+ and the Swift helper. For source
runs, compile it with Apple's command-line developer tools installed:

```sh
.venv/bin/python scripts/build_mask_helper.py
```

Other image treatments do not require this helper. macOS system-font discovery
uses Core Text; see [System typefaces](system-typefaces.md).

## Build a local macOS app

The build requires macOS, the desktop dependencies, FFmpeg/ffprobe and Apple's
command-line tools. It compiles the mask helper, generates the icon, checks
version metadata, bundles with PyInstaller and verifies the ad hoc signature.

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python scripts/build_macos.py
```

The result is `dist/Nebula Studio.app`. This is a local build, not a notarized
installer for distribution to other computers. It bundles Python, Qt, renderers,
assets and presets; FFmpeg remains an external dependency. The launcher adds
Homebrew's usual executable directories to its PATH.

To install a completed build locally, first save work and quit that installed
app, then run:

```sh
.venv/bin/python scripts/build_macos.py --install
```

This command builds again and installs into `~/Applications`, preserving the
previous installation as a dated backup. It refuses to replace a running copy
at that destination. A built app is a source snapshot; editing the checkout does
not update it. Build products are ignored by Git. Startup errors go to
`~/Library/Logs/Nebula Studio/studio.log`.

## Test without using the installed app

Install pytest in the development environment if it is absent. Choose tests
for the behavior you change; the complete suite includes rendering and media
work and can take time.

```sh
.venv/bin/python -m pip install pytest
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_synth_sound_session.py tests/test_synth_output_ui.py
.venv/bin/python scripts/sync_version.py --check
.venv/bin/python studio.py --version
```

The full-suite command is `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`.
Offscreen Qt tests exercise test windows, not an open user session. MIDI unit
tests inject fake ports; they do not establish DAW compatibility or audio latency.
Native UI inspection, audio-device tests and performance measurements are separate
checks and should be coordinated with anyone using the machine.

Frozen render contracts live in `tests/fixtures/` and `presets/compat-v1.json`.
[requirements-render-v1.txt](../requirements-render-v1.txt) records the Python
3.14.6/macOS arm64 NumPy/Pillow baseline. Install those pins only in an environment
intended for reproducing it. A version tag alone does not pin every dependency.
Do not replace pixel baselines to hide a rendering change.

The [performance runner](preview-performance-audit-runner.md) is an opt-in native
measurement tool with local fixture requirements. It opens a visible window,
writes results and performs substantial rendering; it is not a routine smoke test.
The historical [results](preview-performance-audit-results.md) are measurements
of their recorded build and machine, not current throughput guarantees.

## Code map and compatibility

| Directory | Responsibility |
| --- | --- |
| `nebula/ui/` | Windows, inspector, timeline, preview controls and workspace navigation |
| `nebula/documents/` | Projects, sequences, recipes, study library, recent projects and automation |
| `nebula/sources/` | Text, shapes, meshes, Blender scenes and other source generators |
| `nebula/effects/` | Reusable image treatments and their metadata |
| `nebula/render/` | Render composition, source adapters and preview caches |
| `nebula/audio/` | Synthesis, soundtracks, audio response and live MIDI |
| `nebula/core/` | Shared media, timing, canvas, parameters and diagnostics |
| `nebula/legacy/` | Earlier terminal pipeline and its processing tools |

The root `studio.py`, `mac_app.py` and earlier command-line scripts remain
launchers. Application imports use explicit package paths, such as
`from nebula.ui.synth_studio import SynthStudio`. Existing `synth_*` filenames
remain recognizable inside their areas. New modules belong in the appropriate
package rather than the repository root.

`nebula/resources.py` locates bundled `assets/`, `presets/` and the native mask
helper consistently in a checkout and a frozen app. Never locate these relative
to an individual component's `__file__`. The folders remain at the bundle/root
level; project paths, saved parameter IDs and historical rendering contracts
are unchanged. See the [organization review](repository-organization.md).

Check actual source filenames before extending an area. Render algorithms have
compatibility versions independent of document schemas and the app version.
Preserve frozen recipes and stable module/parameter IDs. Composition compilation
resolves inherited/local settings into the sequence consumed by both preview
and export. New effects register metadata and renderer callbacks; source modules
and effects with fixed roles need their own integration as well.

Generated compositions begin at schema 1; shared video uses 2, independent
footage 3, soundtrack 4, audio responses 5, generated sound 6 and visual
performance 7. Optional fields can raise the required schema; these numbers
are not app releases. A generated-sound instrument has its own versioned DSP
contract. Follow the loaders/normalizers and compatibility tests when adding data.

Keep dependencies, caches, generated media, personal study files and local QA
outputs out of commits. [VERSIONING.md](../VERSIONING.md) defines milestone
preparation. Historical design decisions and validation records are indexed in
[History and plans](history.md).

## Commit messages

Use a lowercase conventional subject, for example:

```text
feat(projects): add native file opening
fix(preview): preserve the prepared loop
refactor: organize application packages
```

The optional scope describes the area. Types are `feat`, `fix`, `refactor`,
`perf`, `docs`, `test`, `build`, `ci`, `chore`, `revert` and `merge`.
The entire subject is lowercase; bodies may preserve filenames, class names
and other case-sensitive identifiers. Use a custom conventional subject for a
merge or revert too. Keep independent changes in separate commits.

Enable the local check once per clone:

```sh
git config core.hooksPath .githooks
```

The same checker runs on commits introduced by pull requests and pushes to
`main`. It checks new history only; existing published commits and release tags
are preserved. To check a branch manually:

```sh
python3 scripts/check_commit_message.py --range origin/main..HEAD
```
