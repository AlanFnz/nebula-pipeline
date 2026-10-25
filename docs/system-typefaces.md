# System typefaces

Object → Text → Typeface opens a searchable picker with Nebula and System font
filters, family/style names and an editable preview sample. Use typeface commits
the choice in the current project or clip scope; Cancel leaves the document alone.
Refresh reads newly enabled fonts. The six bundled families remain available.

All text objects share this picker: whole phrases, individual words, type-on,
reading montage, liquid word morphs and framed labels with optional subtitles.
The label's main wording and subtitle share the chosen font. Stretch echo and
Optical print's alternate fragment typography also use the picker. Source pixels
retains its previous meaning in these two effects.

The macOS catalog comes from Core Text's active fonts, not an unfiltered scan of
font folders. Disabled fonts and private system UI families are excluded. TTF,
OTF and TTC faces are resolved by PostScript identity and face index. Named
variable styles retain their installed variation coordinates. The existing
Font weight slider continues to adjust bundled variable fonts; a system font
uses the style selected in the picker. Unsupported formats/styles display an
explanation in the picker instead of enabling Use typeface.

System fonts are not copied into the project or application. The saved reference
contains family/style, PostScript name, local path, face index, variation axes and
a SHA-256 fingerprint. A relocated font is accepted only when its original bytes
are available. A missing or changed font is identified in the control and rendering
fails with a replacement instruction; preview/export never silently substitutes
another face. Choose an installed replacement or reinstall the original. The
exported video needs no installed fonts to play.

## Compatibility and verification

Existing integer font identifiers, paths to bundled font files, variable-weight
rules, layout and pixel generation remain unchanged. Choosing a system font is
explicit. The same renderer and exact face are used by picker samples, monitor
and export; font changes are discrete across cue transitions and remain undoable.
Saved system-font references require Nebula 0.37 or later. Other platforms can
render a referenced file at its saved path; native catalog discovery currently
targets the macOS desktop app.

Validation covers every built-in text study, source and effect font selectors,
clip scope, drafts, save/reload, undo, collection faces, variable styles, missing
and changed files, relocation, malformed references and mixed font ranges.
Representative pixel snapshots cover all 17 text studies, including original
versions, at three times each against 0.36.3.

Core Text API references:
[available fonts](https://developer.apple.com/documentation/coretext/ctfontcollectioncreatefromavailablefonts(_:)),
[descriptor attributes](https://developer.apple.com/documentation/coretext/font-attributes).
