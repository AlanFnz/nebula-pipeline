# Earth dreams — dye impressions

New personal study authored from the user's 720 × 406, 30 fps reference.
It lasts 228 frames (7.60 seconds), with 40 independently editable shots.
The reference movie is a visual guide only; rendering needs no source footage
or audio. The phrase is THE EARTH DREAMS THROUGH US.
The opening introduces the words in reading order, starting with THE; the
later poster build restarts at THE before assembling the complete phrase.

Run `python scripts/create_earth_dreams_study.py --output <new-file.json>` to
create the editable composition. Save it in Studies to create a separate
library snapshot. This does not replace any built-in study or existing file.

Double-click a shot to edit its text under Object → Text. Its duration is
editable in the shot strip. The final two-line poster uses main text and
subtitle, both on the Text page. Object → Layout contains the new Letterpress
group: letter height, width, angle and baseline variation, seed, and reprint
rate. Rate zero keeps the impression static; other rates deterministically
reprint it. Whole phrase, one word, type-on and reading montage support these
controls. Morph words retains its existing geometry and hides them.

Dye transfer supplies the stock and ink colors, gate, shutter drag, optical
focus and exposure. New optional controls add colored edge exposure, fine
printed-edge texture and uneven pigment density. Subtitle width supports
left-anchored progressive word builds. Existing defaults preserve old pixels.
This study keeps ink density variation at 4% (0% in the pink negative) so the
letters retain an even ink fill without broad, high-contrast pigment patches.
Fine grain, emulsion, printed edges and shutter trails remain independent.
A separate Dye transfer → Light through ink group adds a smooth optical veil
in the stock hue, with adjustable amount, position and width. It is strongest
in the opening and subtler in the pink reading shots; it does not bring back
coarse pigment patches or affect the bare stock. All three controls support
automation, and the effect defaults to off in other studies.

The 40 cuts track the reference's negative opening, irregular tall lettering,
oversized pink interruptions, pink/ivory reading flashes, red exposure,
two-level poster build and pink negative exit. Anton is the close visual
match used for the main lettering; Archivo Black supplies the wider transient
impressions. The photographic reference does not identify its font, so these
are visual matches, not a verified original typeface. The new phrase has
different word lengths; its layouts preserve the condensed type and reading
holds instead of promising pixel equality.

Validation includes deterministic seeking and cadence, partial reveals with
diacritics, text-mode integration, default rendering compatibility, ordinary
shot text/duration round-tripping, native control editing/undo, and manual
frame comparisons against the reference.
