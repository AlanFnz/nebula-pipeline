# Your first piece

[Documentation](README.md) · [Local setup](development.md#run-from-source)

Open the locally built app, or run `.venv/bin/python studio.py --synth` from a
prepared checkout. The composer starts with Refined signal. You can replace
that starting piece without changing the built-in study.

## Make a short text piece

1. Choose **New piece… → Text**, enter a phrase and accept the dialog. Nebula
   creates one six-second clip using the current output canvas and timeline FPS.
2. In **Object → Text**, change **Main text** and press **Apply main text**.
   Choose a **Typeface**. **Layout** holds size, spacing and position;
   **Motion** holds word reveals and animation. See the
   [Object inspector](object-inspector.md) for finding controls.
3. Open **Effects → Add project effect…**, choose a treatment and wait for its
   preview. Compare **Before / Preview**, then choose **Apply effect**. Start
   with one treatment so its contribution is easy to see. **Intensity** changes
   how much it contributes; **Bypass / Resume** compares without losing settings.
4. Press Play. If playback skips, choose **Preview resolution → 360 px** or
   **720 px** and use **Prepare all frames**. Preparing does not start playback.
   **View zoom / Fit view** changes only how large the image looks on screen.
5. Drag the clip's right edge to change its duration. For generated material,
   the animation and its timed effects stretch with the clip. **Timeline FPS**
   sets frame cadence, not playback speed.
6. Press **Save** (Command-S on macOS), choose a name and save the editable JSON
   project. Use **Save As…** to keep another version.
7. Open **Details** beside **Export MP4** to check the complete document,
   dimensions, FPS, duration and audio route. Choose **Export MP4** and a
   destination. The movie uses the output canvas regardless of monitor quality.
   Exporting does not save your editable project.

## Start from a study instead

Choose an entry under **Studies**, then press **Load**. Selection alone does
not load it. **Browse…** opens previews, search, categories and favorites.
Loading creates an independent editable copy with the study's own canvas and
timing. Your changes do not replace its library recipe.

Try **Text / reading print** for ordered words, **Memory / afterimage garden**
for moving traces, or **Pleated signal / acid motion** for a visual piece with
generated sound. Other examples and their editing controls are in
[Sources and studies](sources-and-studies.md).

Use **Editing: Entire project** for a shared change. Double-click a timeline
clip to edit that clip; an ordinary click selects/seeks without changing the
editing scope. Explicit clip overrides take priority over shared values.
**Animated · Study** means the recipe changes a parameter over time. Choose
**Use fixed value** only when you want to replace that parameter's animation.

## Keep your work and media

**Save** writes the editable document. **Save ▾ → Save as study…** creates a
separate library snapshot, including local copies of referenced video and
soundtrack media. **Export MP4** creates a finished movie. These serve different
purposes; a movie cannot be reopened as the original editable composition.

Ordinary project files reference imported video and audio. Keep those files
with the project when moving it. Imported static model geometry and processed
stamp artwork are embedded. System fonts are not; choose bundled fonts when
sharing a project that must render without an additional font installation.

Before replacing or closing unsaved work, Nebula offers Save, Discard or Cancel.
Pending sound has its own decision: **Apply sound** changes the project,
**Save project** writes it to disk, and **Listen** may still be auditioning a
draft. Follow the [sound guide](sound.md#listen-apply-save-and-export) before
exporting a piece with generated audio.

Continue with [editing and animation](editing.md), [video](video.md),
[Montage](native-montage.md) or [monitor and export](monitor-and-export.md).
