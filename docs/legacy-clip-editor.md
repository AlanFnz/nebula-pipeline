# Earlier Print / Scan clip editor

[Documentation](README.md) · [Development](development.md)

The following workflow and limits apply to the separate input-clip editor,
opened with `studio.py` or the installed app's `--clip-studio` option. The
default Synth composer supports the clip, footage and automation workflows
documented in the [editing guide](editing.md).

## Experimenting

1. **Open clip…** loads a local video. The source is read-only. The initial loop is two seconds at the existing default treatment rate of 12 fps.
2. Adjust the controls on the right. **Lo / Hi** values define temporal ranges, not separate still variants. Translation, blur and channel offset are expressed in source pixels. Setting one bound across the other moves the other bound with it.
3. **Enabled** bypasses a stage. The **View** selector shows the source or the output after print, scan, motion or grade. Export always renders the final enabled treatment, regardless of the inspection view.
4. Scrub the timeline, use **Set here** for the loop start, and choose one, two or three seconds. **Play loop** (or Space) plays the prepared frames and holds while buffering. Lower **Frames per second** gives longer frame holds in preview and export.
5. **Capture A** stores the current settings. Edit B, enable **Compare A / B**, and drag the divider. Both sides follow the same clip and exact source frame as you scrub; A retains its seed and settings. Capture again to replace A. Opening a different clip, changing fps, loading a preset or resetting clears A.
6. **Fast** and **Detailed** select maximum proxy dimensions of 480 and 720 pixels. **Full-size still** renders the current frame at original resolution. It pauses playback; Play returns to the proxy loop. The viewer fits the frame to the window.
7. **Load preset…** accepts existing flat JSON presets and project `tune_params.json`. **Save preset…** defaults to `~/.nebula_pipeline/presets`. Settings are saved explicitly, not automatically. Stage bypass is stored under `_stages`; the legacy `grade` key remains authoritative for grade enablement.
8. **Export MP4…** exports either the loop or the entire clip at full source resolution and the chosen fps. It snapshots the current B settings when started, so you may keep experimenting during export. Cancel stops the job; closing the app also cancels background work. The destination is replaced only when encoding succeeds, and the source path cannot be used as the destination.

## Rendering contract

All processing follows **print → scan → wobble → grade**. `engine.render_frame` is used by the desktop preview/export and the legacy analog sequence processor. The legacy grading pass uses the same `grade_frame` function. The TUI's external preview now renders its selected frame rather than a low/mid/high sheet.

Randomness is keyed by seed, effect name and absolute output-frame index. Parameter changes, stage bypass and scrub order do not consume a shared random stream. Motion, rotation, paper, channel direction, bands, grain and dust have separate streams. Smooth temporal variation uses deterministic interpolated knots every eight treatment frames; it is independent of clip length. Existing preset values remain usable, but historical seeded output changes because the old global random walk has been replaced. A missing/null seed resolves to 42.

Preview and export use the same FFmpeg fps grid, including selected-range exports. The full-size pixels **before encoding** match for the same source/frame/settings. MP4 export uses H.264 CRF 18 with 4:2:0 chroma, which is lossy; odd source dimensions are padded by up to one pixel for encoding. Export is silent, as in the existing pipeline.

Proxy blur, translation, channel offset, bloom and paper scale follow image scale. Grain and row noise use reduced variance, and subpixel scanlines converge toward average darkness. Fine dust/noise locations and subpixel shifts are approximations at proxy resolution; use Full-size still to judge fine texture. No real-time full-resolution promise is made.

## Responsiveness and limits

A 100 ms debounce coalesces edits. The preview worker prioritizes the selected frame, then prepares the loop. New requests cancel obsolete FFmpeg work; generation IDs discard late results and errors. Source and rendered-frame caches have 64 MiB and 128 MiB budgets, and the displayed loop has a 128 MiB budget. A/B and high-fps loops automatically use smaller proxies to fit. Export uses a separate worker and an atomic temporary output.

For accurate variable-rate seeking, decoding starts from the beginning of the clip before selecting the requested frame. Seeking late in a long clip can therefore take longer. This editor uses CPU rendering, silent MP4 output, one input clip at a time, fixed stage order and no audio playback. Frame-count estimates depend on container duration; malformed duration metadata may require choosing an earlier loop position. It has no node graph or multi-clip editing. Undo/redo is available in the Synth composer; the detailed editor and input-clip workflow do not yet have undo history.

The existing `nebula.py`, `_pipeline.py`, `analog_wobble.py`, `grade.py`,
`assemble.py` and generation entry points remain available. Their pipeline is
separate from the Synth composer; desktop dependencies include the core
requirements. For tests and measurements, see [Development](development.md).

## Historical validation and measurements

The pre-review README recorded the following local Print / Scan measurements
with a 720×1280, 29.56-second reference clip, a 270×480 proxy and a two-second,
24-frame loop. It did not identify an exact build/date for this table. These are
retained observations, not current performance claims.

| Action | Current frame | Loop prepared |
| --- | ---: | ---: |
| Cold clip open, including probe/debounce/decode | 275 ms | 734 ms |
| Blur edit with source cache | 124 ms | 518 ms |
| Rapid edits, scrub and A/B with print bypass | 150 ms | 849 ms |
| Full-size A/B still | 283 ms | One still |

The measurement tool is [tests/measure_preview.py](../tests/measure_preview.py):

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/measure_preview.py /path/to/reference.mp4
```

It measures a supplied clip and writes `.validation/timings.json`, a window
capture at `.validation/studio.png` and a QA preset. It is an opt-in measurement,
not an installation check. Source media stays read-only. Existing tests also
cover deterministic scrubbing, isolated random streams, source-grid and pre-encode
pixel parity, destination protection, cancellation, A/B, stale results and preset
round trips. See [Development](development.md) for ordinary test commands.
