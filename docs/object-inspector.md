# Object and source inspectors

[Documentation](README.md) · [Editing scopes](editing.md#scope-and-inherited-settings)

Open **Object** to edit the active generator, text or model. Use the scope selector before
changing a value: Composition sets shared controls; Clip edits the selected
clip. Search and group navigation stay above the scrolling controls.

## Text

Text has **Text / Layout / Motion** pages. Typeface, weight when supported, and
the explicit main-text editor stay together. Subtitle controls have their own
foldable group, initially open for an active framed label. Layout starts with
canvas position and size/spacing; color, letterpress, geometry, repetitions and
frame/subtitle layout are named groups. Motion separates reading, interruptions
and endings, morph character and size motion. Reading timing is not clip length.
Modes that do not render subtitles/frames explain the restriction and link back
to Show in Motion. Stored values remain available when switching back.

## Pleated field

Pleated starts with profile/density/scale. Canvas position, relief,
camera, palette, outline/mirrors, motion/timing and optical finish each have a
group. These controls are directly accessible without opening source details.
Activation & preset retains the existing advanced source editor and its return
to Object, including activation overrides and preset replacement. All registered
Pleated parameters remain represented, including the surface loop duration.

## Other objects

All object families use the same pinned search, group navigation and reversible
**Show all** action. The first group contains the main shape or model controls;
**Canvas position** is folded separately. Each family keeps its own vocabulary:

| Object | Groups include |
| --- | --- |
| Image memory | Memory, shape, path/travel, color/background, optical finish |
| Spectral tunnel | Light geometry, perspective, loop/motion, color/light, optical finish |
| Chromatic lattice | Shape/layout, wave motion, rhythm/timing, color/background, optical finish |
| 3D solid | Model/scale, pose/camera, rotation, material/reflections, die markings, color/light |
| Prismatic field | Shape/layout, folds/motion, color/light |
| Radial bloom | Shape/detail, motion/drift, ray vibration, color/light, optical finish |
| Model silhouette | Model/scale, pose/framing, neck/edges |
| Ink stamps | Stamp/scale, copies/outline, gesture/pose, depth/framing, color/ink |
| Particle model | Model/particles, pose/camera, assembly/motion, orbit/turbulence, depth, color |
| Geometric signal | Shared geometry, followed by the individual Form and Ray base groups |

**Activation & preset** retains source activation and preset replacement. Ink
Stamps keeps **Motion & timing** as a separate, explicitly shared editor: those
changes affect all clips. Particle creative controls remain in the source editor.
Shape, clock and material-specific fields appear only when applicable; Show all
and search do not enable incompatible controls or change the selected mode.

## Video and effects

Video's **Source** page keeps its scope and search above the scrolling groups:
Source file, Clip playback, Trim & ending, Framing, Cadence, Source audio and
Treatment preset. Inherited footage still requires **Edit shared source** or an
independent clip source before trim/framing can be edited.

Effects retain their specialized tabs and color/artwork editors. **Show all**
expands the current tab's groups without changing the saved fold choices. Search
covers all groups in that tab and links to matches in other tabs. Ink's timing
link explicitly names its whole-composition scope. Enter focuses the first match;
clearing the search returns to the previous tab, group and scroll position.

## Find and restore controls

The fixed inspector header contains source type, editing scope/state, search and
Jump to a group. Search matches labels, parameter names and group names across
Text pages. It temporarily opens matching groups without overwriting their saved
fold states. Enter focuses the first editor (or its explicit Use fixed value
action for an animated range). Clearing restores the previous page and scroll.
**Show all** temporarily expands applicable groups on the current page; it does not
enable controls excluded by the current source mode. Group summaries count local
overrides only in the editing scope, and flag animated ranges or timed events.


Use the restore arrow to remove a local parameter override and follow its parent
again. **Base · Study animation** and **Study range** summarize authored changes.
**Monitor** identifies the displayed clip, value and modifiers. **Use fixed value**
replaces only that parameter's study animation in this scope; clip automation and
Perform are kept. **Value sources** explains their order. Text fields keep pending drafts during
navigation; **Apply main text** and **Apply subtitle** commit them. Save validates
and applies retained text drafts. Folding/searching alone does not apply edits.
