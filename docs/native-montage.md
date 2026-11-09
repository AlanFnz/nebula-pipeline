# Montage

[Documentation](README.md) · [Sound and export](sound.md#audio-in-montage)

Open **Montage** or **File → Open in Montage** to arrange the current study
alongside footage. It becomes an embedded, editable copy in the same window.

## Choose material and a target

Import videos or composition JSON files into Material. Choose material, then
**Insert range…** to set In/Out. Insertion goes after selected blocks, or at the
end with none selected; dropping material uses the drop position.

Material and Target block are separate selections. To replace a shot, select
one block and a Material item, then **Replace target block…**. Pick the source
In point; the block keeps its duration, speed and treatment. The range must fit.

## Find short blocks

The **Block list** tab finds cuts too narrow to read on the timeline. Select a
row to reveal its block; Enter or double-click opens its editor. Search changes
only the list. **Show selected block** adjusts the view; **Previous view** restores it.

## Edit timing

Drag blocks to reorder or their right edges to resize. Split uses the playhead;
Duplicate preserves the selected sequence's order. Source In slips the source
range without moving the cut. Edits support Undo/Redo.

Typing In, Duration or Speed creates a draft. **Apply timing** updates the block;
**Revert timing draft** drops the draft. Preview uses applied timing. Resolve
a pending draft before switching target, saving, exporting or leaving.

## Replace or edit a block

Double-click a timeline block or choose **Edit study / effects**. The breadcrumb
names it. **Back to montage** (Command-[) keeps its edits and returns to the
assembly; Montage Undo reverses the block edit. Its source duration must still
cover the chosen range. **Copy treatment / Apply treatment to selection** copies
the look without copying text or source objects.

Save and Export from the block editor include the complete Montage. Editing one
block does not change the library study or other blocks.

## Sound, preview and export

Montage has one soundtrack on an absolute timeline. Music markers stay in place
when blocks move. Export uses that soundtrack or silence; it does not mix audio
from blocks, even if you hear it while editing a block.

Preview resolution affects only the monitor. Prepare range caches a bounded
region; export uses the full canvas. Source media remain external, so keep them
with the project. For a personal assembly example, see
[Guerrilla Radio](guerrilla-radio-study.md).
