"""Present only controls that affect outgoing MIDI in saved Live mode."""
from synth_live_mode import LIVE_OUTPUT, is_live


def refresh_live_view(dialog):
    d = dialog
    version = d.voice.currentData()
    live = is_live(dict(version=version, output=d.output.currentData()))
    color, layered = version == 4, version == 3
    d.setWindowTitle('Ableton Live' if live else 'Synthesizer')
    d.enabled.setText('Enable MIDI' if live else 'Enable sound')
    d.voice.setVisible(not live)
    d.output.model().item(d.output.findData(LIVE_OUTPUT)).setEnabled(version in (3, 4))
    d.live.setVisible(not live)
    d.midi.setVisible(not live)
    d.retry.setText('Reconnect MIDI' if live else 'Prepare again')
    d.volume.setVisible(not live);d.volume_label.setVisible(not live)
    d.mute.setText('Mute MIDI' if live else 'Mute monitor')
    d.opening.parentWidget().setTitle('Filter motion · CC 74' if live else 'Filter')
    d.tabs.setTabText(0, 'Notes' if live else 'Sound')
    d.tabs.setTabText(4, 'Channels' if live else 'Mixer')
    d.tabs.setTabText(5, 'Pad' if live else 'Pad && space')
    d.tabs.setTabVisible(1, not color and not live)
    for widget in (d.density, d.drive, d.width, d.attack, d.release):
        widget.setVisible(layered and not live)
    d.seamless_loop.setVisible(layered)
    d.seamless_loop.setText('Hold notes across loop' if live else 'Seamless audio loop')
    d.gain.setVisible(not live)
    for widget in (d.cutoff, d.sweep, d.resonance): widget.setVisible(version >= 2 and not live)
    custom = layered and d.arp_mode.currentData() == 'sequence'
    d.articulation_toggle.setVisible(custom and not live)
    d.articulation_box.setVisible(not custom or (d.articulation_toggle.isChecked() and not live))
    if 'return' in d.connections:
        d.connections['return'][0].parentWidget().setVisible(not live)

    d.mixer.hint.setText('Mute or solo outgoing MIDI channels here. Choose instruments, levels, EQ and effects in Ableton Live.' if live else
                       ('Each layer has independent level, Mute, Solo and EQ.' if color else d.mixer.default_hint))
    d.mixer.foot.setVisible(not live)
    for controls in d.mixer.channels.values():
        for key, control in controls.items(): control.setVisible(not live or key in ('mute', 'solo'))

    if not color: return
    d.color_wave.update_engines()
    for controls in d.color_wave.voices.values():
        for key in ('engine', 'reverb', 'delay'): controls[key].setVisible(not live)
        if live:
            for key in ('analog_box', 'chimes_box', 'brightness', 'character', 'clarity'): controls[key].hide()
    for widget in (d.color_wave.level, d.color_wave.width, d.wave_sine.reverb): widget.setVisible(not live)
    d.color_wave.loop.setText('Hold notes across loop' if live else 'Seamless audio loop')
    for key, knob in d.pad_space.pad.items(): knob.setVisible(not live or key == 'octave')
    for controls in (d.pad_space.space, d.pad_space.delay):
        next(iter(controls.values())).parentWidget().setVisible(not live)
    for key, knob in d.chime_layer.knobs.items(): knob.setVisible(not live or key in ('span', 'decay', 'polyphony', 'trigger'))
    d.chime_layer.tuning.setEnabled(not live)
    for key, knob in d.choir.knobs.items(): knob.setVisible(not live or key == 'octave')
    for key, knob in d.sub.knobs.items(): knob.setVisible(not live or key == 'octaves_below')
