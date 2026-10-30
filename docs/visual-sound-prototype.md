# Visual sound / electric motion

The first visual-to-sound instrument uses the 20-second **Pleated signal**
study. Open **Pleated signal / electric motion** in Studies, then use
**Generated sound…** beside Soundtrack in the timeline toolbar. Other Pleated
field projects start with **Generate sound…** and remain silent until Apply.

## Listening and editing

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

## Signal and timing contract, version 1

`generated_sound` is optional schema-6 composition/sequence data with a versioned
instrument definition. Its source is the stable `pleated_field` generator ID;
the three connection IDs are body, friction and return. Replacing or disabling
that generator yields silence rather than redirecting to another object.

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
The event decays over 240 ms. Continuous response smoothing is 10–500 ms.

The voice combines a low oscillator with controlled harmonics, filtered seeded
noise and a short harmonic attack. Oscillator/filter/RNG state carries across
one-second blocks. PCM is 48 kHz stereo; temporary WAVs are 24-bit. Saturation and
a conservative output gain bound levels; 45 ms edge fades keep tails inside the
timeline. Disabling a source releases through the gate envelope. There is no
automatic loudness normalization or melody/beat generator.

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
frozen in `presets/pleated-signal-sound-v1.json`. Existing documents keep their
original audio choice. Sound-only edits are excluded from visual cache identity.

Checks cover deterministic PCM, FPS independence, silence and bypass, real flow
with constant sliders, optical disappearance/reopening, saved/compiled/snapshot
round trips, Undo, stale-worker rejection, monitor/export independence, partial
export alignment, atomic cancellation and unchanged pixels. The shared relief
refactor was also compared pixel-for-pixel with 0.54.0 over both camera models,
all four mirror arrangements and three different times.
