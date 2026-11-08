# Your first piece

[Documentation](README.md) · [Local setup](development.md#run-from-source)

1. Open the locally built app, or run `.venv/bin/python studio.py --synth`.
   Choose **New piece… → Text** and enter a phrase. To start from an example,
   select a study and press **Load**.
2. Edit **Object → Text → Main text**, then **Apply main text**. Choose a
   Typeface; Layout and Motion hold the size, position and animation controls.
3. Open **Effects → Add project effect…**, preview a treatment and choose
   **Apply effect**. Intensity adjusts its contribution; Bypass lets you compare.
4. Press Play. If playback skips, lower **Preview resolution** and use
   **Prepare all frames**. Preparation does not start playback or reduce export
   quality. Drag a clip's right edge to change its duration.
5. Press **Save** (Command-S on macOS) to keep the editable JSON project.
6. Check **Details** beside **Export MP4**, then export the movie. Export uses
   the output canvas and does not save your project.

**Editing: Entire project** changes shared settings. Double-click a clip to edit
that clip. **Animated · Study** means a value follows the recipe; **Use fixed
value** replaces that parameter's animation.

Ordinary saves reference imported video and audio files, so keep them with the
project. **Save ▾ → Save as study…** copies those media into a library snapshot.
System fonts remain external; bundled fonts are easier to share.

For generated sound, **Listen** can play a draft. **Apply sound** puts it in the
project; **Save project** writes it to disk. See [Sound](sound.md) before exporting,
or [Live MIDI](../LIVE_MIDI.md) to hear DAW instruments.
