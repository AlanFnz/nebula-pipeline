import copy

import numpy as np
import pytest

from synth_live_midi import MidiPlan, midi_pitch
from synth_visual_sound import instrument_sound
from synth_visual_sound_acid import gesture_notes
from synth_visual_sound_instrument import InstrumentVoice


def source():
    c = instrument_sound()
    c.update(arp_mode='sequence', sequence_trigger='loop', sequence_length=16,
             seamless_loop=True, pitch=80.63, arp_pitch=130.5, continuity=1.)
    t = np.arange(0, 20 + 1/120, 1/120)
    s = dict(time=t, presence=np.ones_like(t)*.35,
             expansion=.5 + .35*np.sin(t), motion=.4+.3*np.cos(t), opening=t*0)
    return dict(duration=20), s, c


@pytest.mark.parametrize('mode', ['sequence', 'visual'])
def test_authored_notes_and_independent_free_tuning(mode):
    seq, sig, c = source(); c['arp_mode'] = mode
    before = copy.deepcopy(c)
    p = MidiPlan(seq, sig, c)
    original = [n for n in gesture_notes(sig, c) if n['time'] < seq['duration']]
    assert p.sustained == [(0, midi_pitch(c['pitch'])[0], 80)]
    assert len(p.notes) == len(original)
    for n, o in zip(p.notes, original):
        assert n.start == o['time']
        assert n.end - n.start == pytest.approx(o['duration'])
        assert n.pitch == midi_pitch(c['arp_pitch']*2**(o['semitones']/12))[0]
    assert p.bends[0] != p.bends[1]
    assert c == before


def test_sequence_rests_gates_and_loop_boundary():
    seq, sig, c = source()
    c['sequence'][3]['enabled'] = False
    c['sequence'][6]['velocity'] = 0
    c['sequence'][15]['gate'] = 1
    p = MidiPlan(seq, sig, c)
    assert len(p.notes) == 140  # 10 complete bars, 14 audible steps each.
    assert not any(n.start in (.375, .75) for n in p.notes)
    assert p.notes[-1].end == pytest.approx(20.)
    assert p.active(20.01) == p.active(.01)
    assert (0, 40) in p.active(20.)
    assert len(p.attacks(19.99, 20.01)) == 1
    c['seamless_loop'] = False
    assert MidiPlan(seq, sig, c).active(20.) == {}


@pytest.mark.parametrize('key,channel', [('body', 0), ('arpeggio', 1)])
def test_solo_mute_and_motion_links(key, channel):
    seq, sig, c = source(); c['mixer'][key]['solo'] = True
    p = MidiPlan(seq, sig, c)
    assert set(ch for ch, _ in p.active(.01)) == {channel}
    c['connections'][key]['enabled'] = False
    assert not MidiPlan(seq, sig, c).active(.01)
    c['connections'][key]['enabled'] = True
    c['mixer'][key]['mute'] = True
    assert not MidiPlan(seq, sig, c).active(.01)
    c['mixer'][key]['mute'] = False
    c['enabled'] = False
    assert not MidiPlan(seq, sig, c).active(.01)


def test_filter_and_presence_controls_match_internal_voice():
    seq, sig, c = source()
    p = MidiPlan(seq, sig, c)
    v = InstrumentVoice(seq, c, sig, warm_loop=False)
    for t in (0., .5, 9.33, 19.999, 20.1):
        g, e, m, a = [np.interp(t % 20, v.control_times, x) for x in v.control_values]
        expected = round(np.clip(c['opening'] + .36*e+.42*m+.16*a, 0, 1)*127)
        messages = p.controls(t)
        assert abs(next(x[2] for x in messages if x[:2] == (0xB0, 74)) - expected) <= 1
        assert (0xB1, 11, round(g*127)) in messages
        assert {x[0] & 15 for x in messages} == {0, 1}


def test_layered_synth_ui_offers_midi_without_changing_the_recipe():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from synth_visual_sound_ui import VisualSoundDialog
    _, _, c = source()
    before = copy.deepcopy(c)
    dialog = VisualSoundDialog()
    dialog.set_config(c)
    try:
        assert dialog.midi.isEnabled()
        assert '1 Drone' in dialog.midi_hint.text()
        dialog.midi.setChecked(True)
        assert dialog.history_value == before
        assert not dialog.has_sound_draft()
    finally:
        dialog.close()
