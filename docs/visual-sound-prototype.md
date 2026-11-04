# Visual sound / Pleated signal

The first visual-to-sound instrument uses the 20-second **Pleated signal**
study. Open **Pleated signal / acid motion** in Studies, then use
**Generated sound…** beside Soundtrack in the timeline toolbar. Other Pleated
field projects start with **Generate sound…**. Live audition can be heard before
Apply; Apply saves it into the project.

## Current instrument: layered resonant synth

Version 0.57 uses a new version-3 instrument contract. The Sound tab exposes
rotary controls for base pitch, density, drive, stereo width and level, plus
manual filter opening, resonance, closed/open frequencies and response smoothing.
Opening is a manual bias in the filter's logarithmic frequency range; visual
movement adds to it. Disable Movement → filter opening for a fixed setting.

**Mixer** balances **Drone** and **Arpeggio** independently. Each channel has a
-60 to +6 dB level, Mute, Solo and an EQ on/off switch. Muting a channel takes
priority over Solo; soloing both plays both. These are authored controls and
affect export. **Mute monitor** and **Listen level** only affect listening.

Each EQ offers Low, Mid and High gain (-18 to +18 dB), with frequency entry
below each knob. Low is a shelf (40–600 Hz, initially 120 Hz), Mid a broad bell
(200–6000 Hz, initially 1 kHz, Q 0.8), and High a shelf (1–16 kHz, initially
4 kHz). EQ off retains the band's settings. Channel EQ precedes channel level;
both channels then feed the existing shared Drive and visual Filter. A closed
shared filter can therefore remove highs even when a channel's High EQ is raised.
Mute/Solo do not change the visual modulation or note schedule.

The filters use the [W3C/RBJ Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/)
biquad equations, with shelf slope 1 and persistent stereo state between blocks.
Unchanged upstream EQ stages retain state during live edits; changed stages
settle under the existing 40 ms voice crossfade. Zero-gain bands bypass all
filter arithmetic, retaining exact original PCM with neutral mixer defaults.
Old version-3 documents acquire those defaults; versions 1 and 2 keep their
original sound and do not expose Mixer. Mixer edits use the existing draft,
Apply, Undo/Redo and save/load workflows, without invalidating prepared video.

Oscillators contains three stable slots, each with on/off, sine/triangle/saw/square,
level, semitone tuning and fine tuning in cents. Unison chooses 1–5 voices per
enabled oscillator; Detune spreads those voices, and Stereo controls their pan.
Density blends additional waveform harmonics into each fundamental. It does not
add noise. The demo layers triangle, quiet saw and an upper triangle with three
unison voices and modest detuning. Level normalization bounds the oscillator sum.

**Base pitch** and **Arpeggio root** each offer **Free · Hz** or **Notes**.
Free mode retains fractional frequencies; Notes locks to equal-tempered pitches
(A4 = 440 Hz) and offers C/Do through B/Si, sharps and octave labels. Both roots
remain independent. Oscillator Tune adds semitones; Fine adds fractional cents.
Changing the tuning mode is an audible edit, so it is also undoable.

**Arpeggio → Visual arpeggio · original** contains an independent **Arpeggio root** (65–440 Hz), **Notes**
(1–8 distinct scale degrees per phrase), **Steps** (1–16, or **Auto (3–4)**),
and a pattern selector: Visual motif, Up, Down, or Up & down. Notes controls the
pitch palette; Steps controls how many notes are played, cycling through that
palette. Short phrases may use only part of the palette. The visual gesture still
selects the starting degree and onset. Fixed-length phrases finish before another
gesture starts one; they do not become a free-running timeline sequencer. Original
documents initialize the melody root from their saved shared pitch. Defaults keep
the original alternating 3–4-note motifs and sample-identical output.

Switch **Arpeggio mode** to **Step sequencer** for 1–16 editable steps.
Each column has an on/rest switch, pitch (-12 to +24 semitones from the melody
root), velocity (0–100%) and gate (10–100% of its time slot, plus the release
tail). The note label shows the nearest chromatic pitch; its tooltip also shows
the actual frequency for a freely tuned root. Shortening the pattern retains
hidden steps so lengthening it restores their settings.

Tempo is 30–240 BPM, with quarter, eighth, sixteenth and triplet divisions.
**Visual gestures** starts one pattern on the next timeline grid boundary when
the image makes a gesture, and lets it finish before retriggering. **Loop with
timeline** repeats it from time zero, scheduling every enabled step regardless
of object size. Shrinking below the visual-gesture threshold never removes
notes from this clock. In either mode the image still gates audible output
through its smoothed presence envelope and modulates intensity/filter through
the existing connections. An entirely absent image remains silent; the loop
keeps its phase while silent, ready for the image to return.
BPM changes the sound rhythm, never the video speed. The active-step indicator
follows the same scheduled events, including rests. Pitch, velocity, gate and
rhythm use the same implementation for live audition and export. Original
studies default to Visual arpeggio and retain their previous PCM exactly.

The Arpeggio tab also contains Attack/Release, plus pace and scale for the original arpeggio. **Motion** keeps
the three visual connections and Continuity. Notes begin and end with zero value and
zero slope; their filter accent is smoothed separately over 35 ms. This addresses
the sharp note/filter attacks heard as clicks in the original acid experiment.
Timeline ends use smooth 60/80 ms fades; synthesis carries filter state between
blocks. A test compares different block sizes sample-for-sample while a note
crosses a boundary.

Drag knobs vertically, hold Shift for finer changes, use arrow keys, or type the
number beneath them. Scrolling over a knob does not edit it. Changes are drafts
until **Apply**. With **Live audition** enabled, **Listen/Pause** plays the main
video transport and knob changes are heard immediately, without preparing a new
track or stopping the video. Closing without Apply restores the saved sound.
**Cmd-Z / Shift-Cmd-Z**, the **Edit → Undo/Redo** menu and the dialog's Undo/Redo
buttons restore instrument drafts, including note modes, sequencer steps,
connections and instrument changes. A complete rotary/slider drag is one edit.
Apply commits the draft as one project edit; Undo can then restore the previously
applied sound. A new edit after Undo clears the redo branch. Monitor volume/mute
remain listening preferences, separate from the authored instrument history.
Disabling Live audition, or choosing an original instrument, uses **Apply &
prepare** and the prepared waveform instead. Live gestures are not recorded as
automation: Apply saves the current settings, which are used for export.

Use **Prepare all video frames** before listening to cache the complete timeline
at the selected preview resolution. The same action is below the main timeline.
A resizable video monitor beside the knobs shows the same cached frames; there
is no second render or separate playback clock.
The frame counter shows readiness and dimensions; preparation does not start
playback or change quality. Lossless temporary disk storage extends the bounded
RAM cache. Cancel/resume keeps completed frames. Audio edits, including Apply and
Undo, preserve prepared visuals; visual or resolution changes invalidate them.

Live monitoring uses the same stateful oscillator/filter implementation as
export, in 10 ms blocks on a dedicated worker. At most four packets plus the
40 ms device buffer are queued. Parameter changes use 40 ms smooth crossfades,
retaining filter state and the video clock. Seeks reconstruct a short filter
history and fade in. Actual latency depends on the output device and machine;
fixed-settings export still renders the complete deterministic history from zero.
The original 20-second v4 PCM is sample-identical after the shared-DSP refactor.
Monitor volume/mute are independent of saved instrument level. Unsupported audio
outputs report an error and can use the prepared-waveform fallback.

The latest starter is frozen in `presets/pleated-signal-acid-v4.json`. Earlier
snapshots and version-1/2 instruments remain selectable and load unchanged.

## Audible contraction (acid v4)

**Motion → Visual dynamics → Continuity** softens the volume drop when
only a small portion of the object remains visible. At 0%, gain follows visible
area directly, preserving all prior version-3 audio sample-for-sample. At 100%,
it follows `presence ** 0.1`, before the existing 35 ms smoothing envelope.
Intermediate settings interpolate the exponent from 1 to 0.1. Full presence
still has unity gain; zero presence is still zero. Disabled oscillators, sources
and sound connections remain silent. The control is saved, undoable and shared
by preview and export; it stays a draft until Apply.

The acid v4 study uses 100% Continuity. V3's small central nucleus previously
reached roughly -57 dBFS RMS around 9 seconds: nonzero, but perceived as silence.
V4 keeps every 100 ms window in that contraction above -38 dBFS in both the
prepared waveform and AAC export. The visible contraction and all 240 frames
are unchanged from v3. Existing snapshots retain their original sound settings.

## Current study motion (acid v3)

The 20-second acid study keeps a small elliptical nucleus visible through the
contraction around 9 seconds. Its width and height breathe independently before
the sheet opens again. The existing visibility signal therefore keeps the synth
quietly present; there is no artificial audio floor or change to the instrument.

The final movement follows reference frames 175–239, beginning at the existing
14.58-second cut so the approach to second 15 stays continuous. A mirrored
retreat leads into a half-turn that keeps rotating, followed by the unmirrored
view at 17.67 seconds and diagonal pass at 17.92 seconds. That pass approaches,
retreats briefly and pushes forward again. It does not return to a previous shot
or add a terminal hold. Camera curves remain ordinary editable frame samples.

Only frames 106–118 and 175–239 change. The original silent/electric recipes and
both earlier acid snapshots retain their choreography. The original triangle
recipe (`layered=False`) also remains unchanged. Sound settings, duration,
canvas, palettes and effect algorithms are preserved. Surface details remain a
procedural approximation of the reference.

## Listening and editing: acid triangle

The second instrument replaces the low/noisy electric voice with a stable
D3 triangle, a resonant low-pass filter and brief pentatonic phrases. There is
no noise oscillator or movement-to-pitch ramp in this instrument.

- **Expansion → triangle voice** controls the principal triangle's level.
- **Movement → filter opening** sweeps between Filter closed and Filter open
  frequencies, responding to camera/surface movement and expansion.
- **Gestures → short arpeggios** adds 3–4-note phrases on expansion turns,
  movement surges and optical reopening. Hysteresis and a 1.25-second minimum
  separation leave gaps; a held/uniformly moving image is not a free sequencer.

Each connection has an enable checkbox and amount. **Base pitch**, **Resonance**,
both filter frequencies, **Arpeggio pace**, and **Arpeggio scale** are editable.
Scale choices are minor pentatonic, natural minor and Dorian. Musical pitches
are intervals above the chosen base pitch. Apply & prepare commits through Undo.
The arpeggio activity meter follows actual note envelopes.

**Instrument** also selects **Electric / tape (original)**. Changing this selector
loads the other instrument's starting settings as a draft; Apply commits them.
The original study and saved version-1 documents still produce their prior sound.

## Original electric / tape instrument

- **Expansion → tonal body** links camera scale to pitch and harmonics.
- **Movement → friction** responds to camera rotation, orbit, zoom and surface
  travel, including procedural flow when its slider is held constant.
- **Reopening → resonant attack** sounds when the optical field returns after
  disappearing. On the bundled study this happens at approximately 9.75 s.

Each connection has an enable checkbox and amount. Base pitch, response
smoothing and sound level are editable. Apply & prepare saves the change through
the ordinary undo history; then use the main timeline Play button. The small
meters show the source behavior while scrubbing or playing.

**Audio output** explicitly chooses generated sound, existing soundtrack/footage,
or silence. Generated sound replaces other audible sources; it does not mix them.
Mute monitor and Listen level affect only monitoring. The output selector and
sound level are saved and also control MP4 export. The imported soundtrack and
its audio-response mappings remain authored, including when not heard.

## Shared signal and timing contract

`generated_sound` is optional schema-6 composition/sequence data with a versioned
instrument definition. Its source is the stable `pleated_field` generator ID;
version 1 connection IDs are body, friction and return; version 2/3 IDs are body,
filter and arpeggio. Replacing or disabling that generator yields silence rather
than redirecting to another object.

The source reads the same resolved presets, section clocks, morphs, automations
and imported-audio modulation as the renderer. Shared surface-clock, relief
intersection and optical-gate functions prevent independent animation formulas.
A fixed 16 × 12 probe grid measures the internal optical gate; it does not analyze
the finished image. Subsequent project effects are not sound sources in this
prototype. Gate sampling is approximate near very thin edges.

Controls are evaluated at 120 Hz, independent of video/export FPS. Backward
differences of resolved camera/flow coordinates produce movement speed. A 60 ms
causal smoothing stage precedes soft compression, avoiding identical impulse
bursts from stepped 12-fps poses. Expansion uses log camera scale. Reopening arms
below 2.5% gate coverage, triggers above 12%, and has a 400 ms retrigger minimum.
The original instrument's event decays over 240 ms. Continuous response
smoothing is 10–500 ms.

The version-1 voice combines a low oscillator with controlled harmonics, filtered seeded
noise and a short harmonic attack. Oscillator/filter/RNG state carries across
one-second blocks. PCM is 48 kHz stereo; temporary WAVs are 24-bit. Saturation and
a conservative output gain bound levels; 45 ms edge fades keep tails inside the
timeline. Disabling a source releases through the gate envelope. Neither
instrument automatically normalizes away the authored sound level.

Version 2 uses an additive triangle (odd harmonics weighted by inverse square,
omitting partials above the Nyquist margin), mild pre-filter saturation and a
state-variable low-pass filter. The filter uses Andrew Simper's
[trapezoidal SVF formulation](https://www.cytomic.com/files/dsp/SvfLinearTrapOptimised2.pdf)
with sample-interpolated cutoff and positive damping (Q 0.7–7.5). The principal
pitch remains constant; visual expression changes level and spectrum. Arpeggio
notes have 6 ms attacks, short decays, light stereo placement and stable scale
intervals. No phrase starts in the final 450 ms. The final timeline fade also
contains the filter tail. Version-1 oscillator/filter arithmetic is unchanged.

Preparation runs in a cancellable worker with a document identity and settings
key. An edit immediately disconnects obsolete audio, then prepares the new
waveform after a short debounce. A three-entry temporary cache supports Undo.
Generation does not depend on rendered preview frames. The full timeline is
reconstructed from zero, so seeking and partial export retain oscillator history.
Clip repetitions follow the compiled visual clocks; oscillator phase continues
through them. A transport loop restarts the complete waveform at the loop point.

Preview uses Nebula's existing native media transport with the same WAV that
export synthesis produces. Native player seeks remain approximate, as with an
imported soundtrack; this is not a sample-accurate hardware sequencer. Generated
audio never becomes an audio-reactivity input. General audio mixing and Montage
asset-audio mixing are not included in this first instrument.

## Preservation and validation

The silent 20-second starter stays unchanged. The audible study is separately
frozen in `presets/pleated-signal-sound-v1.json`; the acid variation is frozen in
`presets/pleated-signal-acid-v1.json`. Existing documents keep their
original audio choice. Sound-only edits are excluded from visual cache identity.

Checks cover deterministic PCM, FPS independence, silence and bypass, real flow
with constant sliders, optical disappearance/reopening, saved/compiled/snapshot
round trips, Undo, stale-worker rejection, monitor/export independence, partial
export alignment, atomic cancellation and unchanged pixels. The shared relief
refactor was also compared pixel-for-pixel with 0.54.0 over both camera models,
all four mirror arrangements and three different times.

The acid instrument additionally checks stationary pitch/no noise, no repeated
notes during held geometry, event-triggered phrases and scale intervals, filter
response/resonance, extreme settings, version-specific UI round trips, and full
versus partial native MP4 audio. The original 20-second PCM hash was compared
before/after the implementation and remained identical.
