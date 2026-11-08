# Object inspector: Text and Pleated

[Documentation](README.md) · [Editing scopes](editing.md#scope-and-inherited-settings)

Open **Object** to edit text or a Pleated field. Use the scope selector before
changing a value: Entire project sets shared controls; Clip edits the selected
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

Pleated keeps canvas position and profile/density/scale prominent. Relief,
camera, palette, outline/mirrors, motion/timing and optical finish each have a
group. These controls are directly accessible without opening source details.
Activation & preset retains the existing advanced source editor and its return
to Object, including activation overrides and preset replacement. All registered
Pleated parameters remain represented, including the surface loop duration.

## Find and restore controls

The fixed inspector header contains source type, editing scope/state, search and
Jump to a group. Search matches labels, parameter names and group names across
Text pages. It temporarily opens matching groups without overwriting their saved
fold states. Enter focuses the first editor (or its explicit Use fixed value
action for an animated range). Clearing restores the previous page and scroll.
Show all temporarily expands applicable groups on the current page; it does not
enable controls excluded by the current source mode. Group summaries count local
overrides only in the editing scope, and flag animated ranges or timed events.


Use the restore arrow to remove a local parameter override and follow its parent
again. **Animated · Study** ranges summarize authored changes; **Use fixed value**
replaces only that parameter's animation. Text fields keep pending drafts during
navigation; **Apply main text** and **Apply subtitle** commit them. Save validates
and applies retained text drafts. Folding/searching alone does not apply edits.
