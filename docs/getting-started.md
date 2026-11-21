# Your first piece

[Documentation](README.md) · [Local setup](development.md#run-from-source)

1. Open the locally built app, or run `.venv/bin/python studio.py --synth`.
   Choose **New piece → Text** and enter a phrase. To start from an example,
   select a study and press **Load**.
2. Edit **Object → Text → Main text**, then **Apply main text**. Choose a
   Typeface; Layout and Motion hold the size, position and animation controls.
3. Open **Effects → Add shared effect…**, preview a treatment and choose
   **Apply effect**. Intensity adjusts its contribution; Bypass lets you compare.
4. Press Play. If playback skips, lower **Preview resolution** and use
   **Prepare all frames**. Enable **Loop prepared range** to play the longest
   ready span while preparation continues. This does not reduce export quality.
   See [preview controls](monitor-and-export.md#prepare-frames). Drag a clip's
   right edge to change its duration.
5. Press **Save** (Command-S on macOS) to keep an editable `.nebula` project.
6. Check **Details** beside **Export MP4**, then export the movie. Export uses
   the output canvas and does not save your project.

**Editing: Composition** changes shared settings. Double-click a clip to edit
that clip. **Animated · Study** means a value follows the recipe; **Use fixed
value** replaces that parameter's animation.

Ordinary saves reference imported video and audio files, so keep them with the
project. **Save ▾ → Save as study…** copies those media into a library snapshot.
System fonts remain external; bundled fonts are easier to share.

On macOS, `.nebula` files have their own icon and open in Nebula with a double
click. Existing `.json` projects still open normally and **Save** keeps their
original filename. Use **Save ▾ → Save as** to make a `.nebula` copy, or choose
**Legacy JSON** in the save dialog. Both contain the same editable project data;
`.nebula` does not package media or change the artwork.

**Open** shows recent projects with a preview of their last saved version.
Search by name or filename, then double-click a card. **Browse files** opens a
project outside the list; **Add folder** includes `.nebula` and Nebula JSON files.
Previews are stored on this computer and updated after saving, so reopening the
gallery does not render them again. A first preview may prepare in the background.
If a file moved, select its card and choose **Locate file**. **Remove from
recents** removes only the card, keeping the project on disk.

For generated sound, **Listen** can play a draft. **Apply sound** puts it in the
project; **Save composition** writes it to disk. See [Sound](sound.md) before exporting,
or [Live MIDI](../LIVE_MIDI.md) to hear DAW instruments.
