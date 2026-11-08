# Nebula Studio

Nebula is a desktop workspace for making moving images from text, shapes,
3D models and video. It is useful for typographic films, abstract loops, music
visuals and experiments with print, light and damaged signals. Start with an
editable study or your own material, combine effects, animate controls and
arrange clips into a piece.

For example, you can:

- Turn a phrase into a sequence of printed words, optical exposures or liquid
  letterforms, with editable wording and timing.
- Animate a folded color field, a particle head or a static imported 3D model,
  then treat it with grain, phosphors, trails or tape damage.
- Trim and treat footage, give clips independent sources, and assemble video
  and generated studies in Montage.
- Make visuals respond to an imported soundtrack, or generate sound from
  Pleated field motion and Chromatic lattice color waves.

## Start here

This repository provides source code and a **local macOS app build**. It does
not provide a public, notarized installer through these instructions. If you
already have a locally built Nebula Studio.app, open it in Finder. Otherwise,
follow [local setup](docs/development.md#run-from-source).

From a prepared checkout, launch the composer with:

```sh
.venv/bin/python studio.py --synth
```

Choose **New piece… → Text** to make something from scratch, or choose a study
and press **Load**. Follow [Your first piece](docs/getting-started.md) through
editing, saving and exporting. Running `studio.py` without `--synth` opens the
separate, earlier Print / Scan clip editor.

## Find your way

| I want to… | Read |
| --- | --- |
| Edit a piece, arrange clips, animate effects or keep variations | [Editing guide](docs/editing.md) |
| Choose text, shapes, models or a study | [Sources and studies](docs/sources-and-studies.md) |
| Understand a treatment and its controls | [Effects reference](docs/effects-reference.md) |
| Import, trim or retime footage | [Video guide](docs/video.md) |
| Add a soundtrack, generate sound or edit a pattern | [Sound guide](docs/sound.md) |
| Send visual notes to Ableton or another DAW | [Experimental live MIDI](LIVE_MIDI.md) |
| Assemble studies and footage | [Montage](docs/native-montage.md) |
| Understand preview quality, canvas size and output | [Monitor and export](docs/monitor-and-export.md) |
| Run, test or build the app | [Development](docs/development.md) |

The [documentation index](docs/README.md) also lists focused guides, technical
references and historical plans.

## Project status and limits

This documentation describes **0.84.0**, reviewed against the source at
`979d940` on 2026-11-08. The canonical version is in [_version.py](_version.py).
See the [changelog](CHANGELOG.md) for release history and
[versioning](VERSIONING.md) for compatibility and milestone rules. A development
branch can contain work beyond the latest release or `main`.

macOS is the documented development and local packaging platform. The Python
entry point uses PySide6 and FFmpeg; other platforms do not have a verified
support matrix here. System-font discovery and foreground extraction use macOS
services; foreground extraction requires macOS 14 or later.

Preview can drop frames under load; export renders every output frame. The
video path is 8-bit RGB/SDR, and MP4 delivery uses lossy H.264. Imported video and
audio remain file dependencies unless packaged into a personal study. System
fonts are referenced, not embedded.

Generated sound currently follows two supported visual sources, not arbitrary
finished images. Live MIDI is experimental and only changes monitoring: the
DAW owns its instruments and mix, and its audio is not captured by Nebula's MP4
export. Montage exports its own soundtrack or silence; it does not mix block
sound. General audio mixing, live audio input and independent text-over-video
layers remain outside the current workflow.
