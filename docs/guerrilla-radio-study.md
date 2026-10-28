# Text / Guerrilla Radio — spoken intro

A personal study derived from the frozen `text-dye-transfer-v7.json` recipe,
authored for the user's 28-second Ableton bounce. Only the spoken introduction
is illustrated. The user supplies the separate footage montage after the band
entrance. No existing study, renderer, or app default changes.

## Delivery and timing

- Portrait 1080 × 1920, 30 fps; 281 frames / 9.366667 seconds.
- Frame 281 (`00:00:09:11` at 30 fps) is the footage handoff. The first large
  band transient occurs around 9.36 seconds in this particular bounce.
- The guide MP4 includes the supplied audio from source time zero, at original
  speed. The silent MP4 contains the identical video stream without audio.
- The complete 28-second bounce remains attached to the editable project.
  Extending the composition can reveal its remaining audio. No protest footage
  or continuation is generated.

The timing was estimated with local Whisper word alignment, isolated-word
checks, and waveform inspection, then quantized to 30 fps. This is authored
synchronization to this specific bounce, not a general speech-sync feature.
The first consonants of the four phrases are near 0.0, 2.29, 4.50, and 6.77 s.
The decisive HERE and NOW cuts are at frames 173 and 250. Small cut adjustments
remain possible if the user wants a different perceived emphasis.

## Look and editing

Pink condensed type opens the piece, followed by an ivory impression with a
slight tilt, pale lettering on black, and an orange/pink NOW ending. Brief
exposure flips and directional ink trails retain the One more try language.
Low erosion and fine grain preserve solid, readable strokes. Small smooth
scale gestures emphasize selected words. There are no unreadable silhouette
inserts between the sung words.

All 32 cuts are independent clips in **Shots** view. Double-click a card and use
**Object → Text** for wording, typeface, and layout. **Effects → Dye transfer**
edits paper, ink, texture, and exposure motion. **Duration** edits a selected
cut; **Timeline** exposes proportional lengths and automation. Changing a
duration shifts following text while the soundtrack remains on its independent
clock, so recheck synchronization afterward. Undo restores those edits.

Each cut retains its own authored source state. Changing the text on one card
does not automatically change later cards repeating that wording. Project
effects remain available for shared finishing. The text fits the authored
portrait canvas; substantially longer replacement wording may need resizing.

## Reproduction

Run from the repository with its existing virtual environment:

```sh
.venv/bin/python scripts/create_guerrilla_study.py \
  --audio '/absolute/path/to/the/supplied/bounce.wav' \
  --output output/guerrilla-radio-v1 --render --save-study
```

The script copies the audio into the output's `media` folder, writes a portable
relative media reference, checks the composition round trip and frame count,
and produces a contact sheet, cut table, and both MP4 variants. `--save-study`
creates a new personal-library entry with its own audio copy; omit it on
subsequent render-only runs to avoid duplicate library entries.

Audio and rendered media stay local, outside Git. The built-in 15-second
One more try study remains untouched. This recipe needs Nebula 0.47.1 and the
existing Text, Dye transfer, soundtrack, Shots, and automation capabilities;
no new app release is needed.
