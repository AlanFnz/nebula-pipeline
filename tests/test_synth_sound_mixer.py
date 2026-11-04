"""Channel isolation, frequency response, stream continuity and authored editing."""
import copy
import numpy as np
import pytest
from PySide6.QtTest import QSignalSpy
from synth_sound_mixer import mixer_defaults, MixerChannel, eq_coefficients
from synth_visual_sound import RATE, instrument_sound, normalize_sound
from synth_visual_sound_instrument import InstrumentVoice
from synth_visual_sound_live import LiveInstrument, BLOCK
from synth_visual_sound_ui import VisualSoundDialog
from test_synth_visual_sound_instrument import signals
from test_synth_visual_sound_ui import app, studio
from test_synth_arpeggio import render


def configured():
    c = instrument_sound(); c.update(arp_mode='sequence', sequence_trigger='loop')
    c['mixer']['body'].update(level_db=-9., low_db=-6., mid_db=3., high_db=-2.)
    c['mixer']['arpeggio'].update(level_db=-3., low_db=-9., mid_db=5., high_db=3.)
    return c


def test_legacy_defaults_are_exact_bypass_and_round_trip():
    c = instrument_sound(); legacy = copy.deepcopy(c); legacy.pop('mixer')
    assert normalize_sound(legacy) == c
    source = np.random.default_rng(2).normal(size=(2048, 2))
    assert MixerChannel(c['mixer']['body']).process(source) is source
    s = signals(1.); s['opening'][12] = 1
    assert np.array_equal(render(c, s), render(legacy, s))
    assert normalize_sound(configured()) == configured()


@pytest.mark.parametrize('field,value', [('level_db', 7), ('level_db', True), ('mid_db', float('nan')),
    ('high_hz', 24000), ('low_hz', 0), ('solo', 1), ('mute', None), ('eq_enabled', 'yes')])
def test_invalid_channel_controls_fail(field, value):
    c = instrument_sound(); c['mixer']['body'][field] = value
    with pytest.raises(ValueError): normalize_sound(c)


@pytest.mark.parametrize('bad', [None, [], {}, {'body': {}}, {'body': [], 'arpeggio': {}}])
def test_invalid_channel_structure_fails(bad):
    c = instrument_sound(); c['mixer'] = bad
    with pytest.raises(ValueError): normalize_sound(c)


def test_gain_silence_solo_and_each_eq_are_independent():
    c = configured(); s = signals(1.)
    both = render(c, s)
    c['mixer']['body']['mute'] = True; arp = render(c, s)
    assert arp.any() and not np.array_equal(arp, both)
    c['mixer']['body'].update(level_db=6., low_db=18., mid_db=-18., high_db=18.)
    assert np.array_equal(render(c, s), arp)
    c['mixer']['body']['mute'] = False; c['mixer']['arpeggio']['solo'] = True
    assert np.array_equal(render(c, s), arp)
    c['mixer']['body']['solo'] = True
    all_solo = render(c, s)
    c['mixer']['body']['solo'] = c['mixer']['arpeggio']['solo'] = False
    assert np.array_equal(render(c, s), all_solo)
    c['mixer']['arpeggio']['mute'] = True; drone = render(c, s)
    c['mixer']['arpeggio'].update(level_db=6., low_db=18., high_db=-18.)
    assert np.array_equal(render(c, s), drone)
    c['mixer']['body']['mute'] = True
    assert not render(c, s).any()
    c['mixer']['body']['solo'] = True  # Mute still takes precedence.
    assert not render(c, s).any()


def test_three_eq_bands_have_the_expected_response_and_bypass():
    # Measure actual processed sine waves, not the coefficient implementation.
    t = np.arange(RATE)/RATE
    for band, hz, db, expected in [('low', 20, 6, 6), ('mid', 1000, -9, -9), ('high', 18000, 12, 12)]:
        c = mixer_defaults()['body']; c[band+'_db'] = db
        x = np.stack([np.sin(2*np.pi*hz*t)]*2, axis=1)
        y = MixerChannel(c).process(x)
        ratio = 20*np.log10(np.linalg.norm(y[RATE//2:])/np.linalg.norm(x[RATE//2:]))
        assert ratio == pytest.approx(expected, abs=.03)
        c['eq_enabled'] = False
        assert np.array_equal(MixerChannel(c).process(x), x)
    c = mixer_defaults()['body']; c['level_db'] = -12.
    assert np.allclose(MixerChannel(c).process(x), x*10**(-12/20))
    # Shelves retain the opposite end of the spectrum.
    for band, hz in [('low', 12000), ('high', 40)]:
        c = mixer_defaults()['body']; c[band+'_db'] = 18
        x = np.stack([np.sin(2*np.pi*hz*t)]*2, axis=1)
        y = MixerChannel(c).process(x)
        assert np.linalg.norm(y[RATE//2:])/np.linalg.norm(x[RATE//2:]) == pytest.approx(1, abs=.002)


def test_eq_extremes_are_stable_and_final_pcm_is_bounded():
    for band, limits in [('low', (40, 600)), ('mid', (200, 6000)), ('high', (1000, 16000))]:
        for hz in limits:
            for gain in (-18, 18):
                *_, a1, a2 = eq_coefficients(band, hz, gain)
                assert abs(np.roots([1, a1, a2])).max() < 1
    c = configured(); c.update(gain=1., resonance=1., opening=1.)
    for channel in c['mixer'].values(): channel.update(level_db=6., low_db=18., mid_db=18., high_db=18.)
    pcm = render(c, signals(.7))
    assert np.isfinite(pcm).all() and abs(pcm).max() < .721


def test_mixed_pcm_is_identical_across_live_export_and_irregular_blocks():
    c = configured(); s = signals(1.); seq = dict(duration=1., seed=31)
    expected = render(c, s); live = LiveInstrument(seq, s, c)
    assert np.array_equal(expected, np.concatenate([live.render() for _ in range(100)]))
    voice = InstrumentVoice(seq, c, s)
    irregular = np.concatenate([voice.render(i, min(3571, RATE-i)) for i in range(0, RATE, 3571)])
    assert np.array_equal(expected, irregular)


def test_live_mixer_edits_crossfade_and_preserve_unchanged_eq_history():
    c = configured(); s = signals(2.); seq = dict(duration=2., seed=31)
    live = LiveInstrument(seq, s, c); live.render(12000)
    states = copy.deepcopy(live.voice.mixer['body'].states)
    changed = copy.deepcopy(c); changed['mixer']['body']['level_db'] = -20
    expected = InstrumentVoice(seq, c, s); original = expected.render(0, 12001)[-1]
    live.update(changed); first = live.render(1)
    assert np.array_equal(first[0], original)
    assert live.voice.mixer['body'].states != [[(0., 0.), (0., 0.)]]*3
    assert live.voice.mixer['body'].states == live.old.mixer['body'].states
    assert states != live.voice.mixer['body'].states
    chunks = [first]
    for index in range(50):
        if index % 6 == 0:
            changed['mixer']['body'].update(low_db=18 if index%12 else -18, low_hz=40 if index%12 else 600)
            changed['mixer']['arpeggio']['mute'] = index%12 == 0
            live.update(changed)
        chunks.append(live.render(BLOCK))
    pcm = np.concatenate(chunks)
    assert np.isfinite(pcm).all() and abs(np.diff(pcm, axis=0)).max() < .12


def test_mixer_history_apply_and_save_preserve_all_channels(studio, tmp_path):
    from synth_composition import save_composition, load_composition
    d = VisualSoundDialog(); d.set_config(instrument_sound())
    baseline = d.read_config(); states = [baseline]; spy = QSignalSpy(d.configEdited)
    for key in ('body', 'arpeggio'):
        for field, value in [('level_db', -7.5), ('mute', True), ('solo', True), ('eq_enabled', False),
                             ('low_db', 3.5), ('low_hz', 200), ('mid_db', -5), ('mid_hz', 700),
                             ('high_db', 6), ('high_hz', 9000)]:
            widget = d.mixer.channels[key][field]
            (widget.setChecked if type(value) is bool else widget.setValue)(value)
            states.append(d.read_config())
    assert len(d.sound_undo) == len(states)-1
    for expected in reversed(states[:-1]): assert d.undo_draft() and d.read_config() == expected
    for expected in states[1:]: assert d.redo_draft() and d.read_config() == expected
    d.apply(); assert spy.at(0)[0] == states[-1] and not d.sound_undo
    studio.apply_visual_sound(states[-1]); save_composition(tmp_path/'mix.json', studio.composition)
    loaded = load_composition(tmp_path/'mix.json')['generated_sound']
    assert loaded == states[-1]
    d.set_config(loaded); assert d.read_config() == loaded
    d.tabs.setCurrentIndex(4); d.voice.setCurrentIndex(d.voice.findData(1))
    assert not d.tabs.isTabEnabled(4) and d.tabs.currentIndex() == 0
    d.undo_draft(); assert d.read_config() == loaded
    d.close()
