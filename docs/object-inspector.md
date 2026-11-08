# Object inspector: Text and Pleated

The 0.76.0 D03 pass reorganizes these two source families. Other object families
and specialized image-effect editors keep their existing controls. The dark
theme remains in place; this is navigation and grouping, not a new visual skin.

Text keeps Text / Layout / Motion pages. Typeface, weight when supported, and
the explicit main-text editor stay together. Subtitle controls have their own
foldable group, initially open for an active framed label. Layout starts with
canvas position and size/spacing; color, letterpress, geometry, repetitions and
frame/subtitle layout are named groups. Motion separates reading, interruptions
and endings, morph character and size motion. Reading timing is not clip length.
Modes that do not render subtitles/frames explain the restriction and link back
to Show in Motion. Stored values remain available when switching back.

Pleated keeps canvas position and profile/density/scale prominent. Relief,
camera, palette, outline/mirrors, motion/timing and optical finish each have a
group. These controls are directly accessible without opening source details.
Activation & preset retains the existing advanced source editor and its return
to Object, including activation overrides and preset replacement. All registered
Pleated parameters remain represented, including the surface loop duration.

The fixed inspector header contains source type, editing scope/state, search and
Jump to a group. Search matches labels, parameter names and group names across
Text pages. It temporarily opens matching groups without overwriting their saved
fold states. Enter focuses the first editor (or its explicit Use fixed value
action for an animated range). Clearing restores the previous page and scroll.
Show all temporarily expands applicable groups on the current page; it does not
enable controls excluded by the current source mode. Group summaries count local
overrides only in the editing scope, and flag animated ranges or timed events.

Groups reuse the existing parameter widgets, value provenance, per-parameter
restore, animation actions and text-draft handling. Search and folding are view
state only. No JSON, defaults, recipes, renderer or DSP changes are involved.
Tests cover all registered paths, inherited/local counts, keyboard focus,
search/fold/scroll restoration, hidden drafts, undo, representative pixel equality
and real workspaces at 1280×800, 1440×900 and 1024×768.
