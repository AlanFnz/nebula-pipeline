# Nebula Studio

Nebula is a desktop app for making moving images from text, shapes, 3D models
and video. Start with an editable study or your own material, add treatments,
and arrange clips into a piece. Pleated and Chromatic lattice can also generate
sound or send notes to Ableton and other DAWs.

## Start

Open your locally built Nebula Studio.app, or launch from a prepared checkout:

```sh
.venv/bin/python studio.py --synth
```

Need to set it up? See [Run from source](docs/development.md#run-from-source).
The repository supports local macOS builds; these instructions do not provide a
public notarized installer. Running without `--synth` opens the earlier
[Print / Scan editor](docs/legacy-clip-editor.md).

Choose **New piece → Text**, or select a study and press **Load**.
[Your first piece](docs/getting-started.md) covers editing, saving and export.

- [Sound](docs/sound.md): listening, applying changes and choosing export audio.
- [Live MIDI](LIVE_MIDI.md): connect instruments in Ableton or another DAW.
- [Documentation](docs/README.md): editing references, development and history.

## Before exporting

Save keeps the editable project. Export MP4 makes a movie and does not save the
project. Keep imported video and audio files with it; they remain dependencies.

Live playback sends MIDI. Record the DAW's audio separately and import it as a
soundtrack to include it in an MP4. Montage exports its own soundtrack or silence, without
mixing its blocks' audio. Output is 8-bit SDR H.264; preview may drop frames,
while export renders every frame.

Current version: [_version.py](_version.py). [Release history](CHANGELOG.md).
