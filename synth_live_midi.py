"""Live, audio-free MIDI pilot. Visual notes keep their original second clock.

This is a monitoring route, not a project render setting. Instruments, FX and
mix levels belong to the receiving DAW. No authored study is rewritten.
"""
from __future__ import annotations

import copy
import math
import threading
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, Signal

PORT_NAME = 'Nebula Visuals'
CHANNELS = {'strum': 0, 'steps': 1, 'pad': 2, 'choir': 3,
            'chimes': 4, 'sub': 5, 'wave': 6}
MIXER_KEYS = dict(strum='body', steps='arpeggio')


def midi_pitch(hz):
    pitch = 69 + 12 * math.log2(hz / 440.)
    note = round(pitch)
    if not 0 <= note <= 127:
        raise ValueError('A pitch is outside the MIDI note range (0–127).')
    return note, pitch - note


def bend_message(channel, semitones, span=2.):
    value = max(0, min(16383, round(8192 + semitones / span * 8192)))
    return (0xE0 | channel, value & 127, value >> 7)


@dataclass(frozen=True)
class MidiNote:
    start: float
    end: float
    channel: int
    pitch: int
    velocity: int


class MidiPlan:
    def __init__(self, sequence, signals, config):
        from synth_lattice_sound import color_notes, articulate_notes, playable_voices
        from synth_sound_analog import PAD_HARMONIES
        from synth_sound_sub import sub_frequency
        from synth_lattice_wave_sound import WaveSine
        if config.get('version') != 4:
            raise ValueError('Live MIDI currently supports Color waves studies.')
        self.duration = float(sequence['duration'])
        self.looping = bool(config['seamless_loop'])
        self.notes = []
        self.sustained = []
        self.bends = {}
        self.wave = None
        self.signals = signals
        self.config = config
        solo = any(c['solo'] for c in config['mixer'].values())

        def audible(key):
            c = config['mixer'][MIXER_KEYS.get(key, key)]
            return config['enabled'] and not c['mute'] and (not solo or c['solo'])

        voices = playable_voices(config)
        notes = articulate_notes(color_notes(signals, config), config, self.duration, self.looping)
        for n in notes:
            key = n['voice']
            if not audible(key): continue
            v = voices[key]
            pitch, fine = midi_pitch(v['pitch'] * 2 ** (n['semitones'] / 12))
            channel = CHANNELS[key]
            self.bends[channel] = fine
            # DAW release is independent. Preserve the visual polyphony gate;
            # an unrestricted voice holds for one authored decay, then releases.
            gate = max(.015, min(n.get('gate', v['decay']), n['duration']))
            velocity = max(1, min(127, round(n['velocity'] * 110)))
            self.notes.append(MidiNote(n['time'], n['time'] + gate, channel, pitch, velocity))
        pad = config['pad']
        root = config['voices']['strum']['pitch'] if pad['follow_root'] else pad['pitch']
        chord = next(intervals for key, _, intervals in PAD_HARMONIES if key == pad['harmony'])
        for key in ('pad', 'choir', 'sub', 'wave'):
            settings = config[key]
            if not settings['enabled'] or not audible(key): continue
            channel = CHANNELS[key]
            if key == 'sub':
                frequencies = [sub_frequency(root, pad['octave'], settings)]
            elif key == 'wave':
                self.wave = WaveSine(signals, settings, self.duration, self.looping)
                # Centre a +/-24 semitone bend range on the authored sweep.
                frequencies = [math.sqrt(settings['low_pitch'] * settings['high_pitch'])]
            else:
                octave = pad['octave'] + (settings['octave'] if key == 'choir' else 0)
                frequencies = [root * 2 ** (octave + degree / 12) for degree in chord]
            for frequency in frequencies:
                pitch, fine = midi_pitch(frequency)
                self.bends[channel] = fine
                self.sustained.append((channel, pitch, 80))
        self.notes.sort(key=lambda n: (n.start, n.channel, n.pitch))

    def active(self, seconds):
        """Unique sounding keys; overlapping equal pitches never end early."""
        if not self.looping and seconds >= self.duration: return {}
        position = seconds % self.duration if self.looping else seconds
        result = {(c, p): v for c, p, v in self.sustained}
        for n in self.notes:
            age = position - n.start
            if self.looping: age %= self.duration
            if 0 <= age < n.end - n.start:
                result[n.channel, n.pitch] = max(result.get((n.channel, n.pitch), 0), n.velocity)
        return result

    def attacks(self, previous, seconds):
        """Exact attacks between worker ticks, including same-pitch retriggers."""
        result = []
        if seconds <= previous: return result
        first = max(0, math.floor(previous / self.duration)) if self.looping else 0
        last = math.floor(seconds / self.duration) if self.looping else 0
        for cycle in range(first, last + 1):
            for n in self.notes:
                at = cycle * self.duration + n.start
                if previous < at <= seconds: result.append((at, n))
        return sorted(result, key=lambda item: item[0])

    def controls(self, seconds):
        position = seconds % self.duration if self.looping else min(seconds, self.duration)
        result = []
        if self.wave is not None:
            hz = float(np.interp(position, self.wave.times, self.wave.frequency))
            base = next(p for c, p, _ in self.sustained if c == CHANNELS['wave'])
            result.append(bend_message(CHANNELS['wave'], 69 + 12 * math.log2(hz / 440) - base, 24))
        for name, cc in (('expansion', 1), ('motion', 74)):
            value = max(0, min(127, round(float(np.interp(position, self.signals['time'], self.signals[name])) * 127)))
            for channel in CHANNELS.values(): result.append((0xB0 | channel, cc, value))
        return result


class MidiOutput:
    def __init__(self):
        import rtmidi
        self.port = rtmidi.MidiOut(name='Nebula Studio')
        self.port.open_virtual_port(PORT_NAME)

    def send(self, message): self.port.send_message(list(message))
    def close(self): self.port.close_port(); self.port.delete()


class MidiEngine:
    """Single-owner port, independent of the GUI and image renderer."""
    def __init__(self, failed, ready, *, output_factory=MidiOutput, clock=time.monotonic):
        self.failed, self.ready = failed, ready
        self.output_factory, self.clock = output_factory, clock
        self.condition = threading.Condition()
        self.commands = []
        self.closed = False
        self.thread = threading.Thread(target=self.run, name='Nebula live MIDI', daemon=True)
        self.thread.start()

    def command(self, name, *args):
        with self.condition:
            if self.closed: return
            if name == 'source': self.commands = [c for c in self.commands if c[0] != 'source']
            self.commands.append((name, args)); self.condition.notify()

    def close(self):
        with self.condition: self.closed = True; self.condition.notify()
        self.thread.join(timeout=5)

    def run(self):
        output = None; plan = None; playing = False; active = {}; controls = {}
        anchor = 0.; previous = 0.; next_controls = 0.

        def silence(hard=False):
            nonlocal active
            for channel, pitch in active: output.send((0x80 | channel, pitch, 0))
            active = {}
            for channel in CHANNELS.values():
                output.send((0xB0 | channel, 64, 0))
                output.send((0xB0 | channel, 123, 0))
                if hard: output.send((0xB0 | channel, 120, 0))

        def restore(seconds):
            nonlocal active, controls, previous, next_controls
            silence(True); controls = {}; previous = seconds; next_controls = 0.
            for channel, fine in plan.bends.items():
                span = 24 if channel == CHANNELS['wave'] else 2
                for cc, value in ((101, 0), (100, 0), (6, span), (38, 0), (101, 127), (100, 127)):
                    output.send((0xB0 | channel, cc, value))
                output.send(bend_message(channel, fine, span))
            for message in plan.controls(seconds): output.send(message)
            active = plan.active(seconds)
            for (channel, pitch), velocity in active.items(): output.send((0x90 | channel, pitch, velocity))

        try:
            output = self.output_factory(); self.ready('MIDI connected · Nebula Visuals · channels 1–7')
            while True:
                with self.condition:
                    if not self.commands and not self.closed: self.condition.wait(.002 if playing else .1)
                    if self.closed: break
                    commands, self.commands = self.commands, []
                for name, args in commands:
                    if name == 'source':
                        plan = MidiPlan(*args)
                        if playing: restore(max(0., self.clock() - anchor))
                    elif name == 'start':
                        seconds, at = args; anchor = at - seconds; playing = plan is not None
                        if playing: restore(max(0., self.clock() - anchor))
                    elif name in ('stop', 'panic'):
                        playing = False; silence(name == 'panic')
                if not playing or plan is None: continue
                seconds = max(0., self.clock() - anchor)
                desired = plan.active(seconds)
                # A scheduler stall must not spray stale notes in a burst.
                if seconds - previous > .10:
                    restore(seconds)
                else:
                    for (channel, pitch) in active.keys() - desired.keys(): output.send((0x80 | channel, pitch, 0))
                    attacks = {(n.channel, n.pitch): n.velocity for _, n in plan.attacks(previous, seconds)}
                    for key, velocity in desired.items():
                        if key not in active or key in attacks:
                            channel, pitch = key
                            if key in active: output.send((0x80 | channel, pitch, 0))
                            output.send((0x90 | channel, pitch, velocity))
                    active = desired; previous = seconds
                if seconds >= next_controls:
                    for message in plan.controls(seconds):
                        key = message[:2] if message[0] & 0xF0 == 0xB0 else message[:1]
                        if controls.get(key) != message: output.send(message); controls[key] = message
                    next_controls = seconds + .02
        except Exception as exc:
            self.failed(str(exc))
        finally:
            if output:
                try: silence(True)
                finally: output.close()


class LiveMidiMonitor(QObject):
    statusChanged = Signal(str)
    failed = Signal(str)
    def __init__(self, parent=None, *, output_factory=MidiOutput, clock=time.monotonic):
        super().__init__(parent)
        self.sequence = self.signals = self.config = None
        self.playing = self.closed = self.muted = self.unavailable = False
        self.anchor = self.seconds = 0.; self.clock = clock
        self.failed.connect(self.fail)
        self.engine = MidiEngine(self.failed.emit, self.statusChanged.emit, output_factory=output_factory, clock=clock)

    def set_source(self, sequence, signals, config):
        self.stop(); self.update_source(sequence, signals, config)

    def update_source(self, sequence, signals, config):
        self.sequence, self.signals, self.config = sequence, signals, copy.deepcopy(config)
        self.engine.command('source', sequence, signals, self.config)

    def set_config(self, config):
        if config != self.config: self.update_source(self.sequence, self.signals, config)

    def set_monitor(self, level, muted):
        # The receiver owns audio volume. Mute stops MIDI notes immediately.
        if muted and not self.muted: self.stop()
        self.muted = muted

    def sync(self, seconds, playing, force=False):
        if self.closed or self.unavailable or self.sequence is None: return
        if not playing or self.muted:
            if self.playing: self.stop()
            return
        now = self.clock(); expected = self.seconds + (now - self.anchor if self.playing else 0)
        error = seconds - expected
        if self.config['seamless_loop']:
            duration = self.sequence['duration']; error = (error + duration / 2) % duration - duration / 2
        if not self.playing or abs(error) > .12:
            self.seconds, self.anchor, self.playing = seconds, now, True
            self.engine.command('start', seconds, now)

    def stop(self):
        self.playing = False
        if not self.closed: self.engine.command('stop')

    def panic(self): self.playing = False; self.engine.command('panic')
    def fail(self, message):
        self.unavailable = True; self.playing = False
        self.statusChanged.emit('MIDI unavailable: ' + message)
    def close(self):
        if not self.closed: self.closed = True; self.engine.close()
