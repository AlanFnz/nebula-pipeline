import copy
import numpy as np
import pytest

from media import Cancellation
from synth_composition import compile_composition,load_composition,save_composition
from synth_lattice_recipes import lattice_composition
from synth_lattice_sound import color_wave_sound,color_notes,ColorWaveVoice,color_blocks
from synth_visual_sound import normalize_sound,visual_signals,RATE,sound_for_sequence
from synth_visual_sound_live import LiveInstrument
from synth_sequence import render_sequence_frame


def study(duration=10.):
    p=lattice_composition();p['generated_sound']=normalize_sound(color_wave_sound())
    seq=compile_composition(p);seq['duration']=duration;seq['cues']=[c for c in seq['cues'] if c['time']<duration]
    return seq


def test_color_events_share_the_renderer_phase_and_ascend():
    from synth_lattice import color_wave_phase
    seq=study();signals=visual_signals(seq);notes=color_notes(signals,seq['generated_sound'])
    for voice,threshold in (('strum',.06),('steps',.35)):
        first=[n for n in notes if n['voice']==voice and n['time']<4]
        assert len(first)>5
        assert [n['level'] for n in first]==sorted(n['level'] for n in first)
        assert [n['semitones'] for n in first]==sorted(n['semitones'] for n in first)
        for note in first:
            phase=color_wave_phase(note['level']+.5,note['time']/10,{'color_spread':.8})
            assert phase==pytest.approx(threshold,abs=.0001)
    assert max(n['time'] for n in notes if n['voice']=='strum' and n['time']<4)<.61
    assert max(n['time'] for n in notes if n['voice']=='steps' and n['time']<4)>3.3


def test_timing_follows_color_speed_phase_and_connections():
    seq=study();signals=visual_signals(seq);original=color_notes(signals,seq['generated_sound'])
    fast=copy.deepcopy(seq)
    for state in fast['states'].values():
        state['overrides'].update({'chromatic_lattice.color_period':5.,'chromatic_lattice.period':2.5})
    changed=color_notes(visual_signals(fast),seq['generated_sound'])
    a=[n for n in original if n['voice']=='strum' and n['time']<1]
    b=[n for n in changed if n['voice']=='strum' and n['time']<.5]
    assert [n['level'] for n in a]==[n['level'] for n in b]
    assert np.allclose([n['time']/2 for n in a],[n['time'] for n in b],atol=.001)
    config=copy.deepcopy(seq['generated_sound']);config['connections']['strum']['enabled']=False
    assert all(n['voice']=='steps' for n in color_notes(signals,config))
    config['connections']['steps']['enabled']=False
    assert color_notes(signals,config)==[]
    for state in seq['states'].values():state['enabled']=[]
    assert color_notes(visual_signals(seq),seq['generated_sound'])==[]


def test_save_reload_does_not_change_visuals(tmp_path):
    p=lattice_composition();before=compile_composition(p)
    assert sound_for_sequence(before)['version']==4
    p['generated_sound']=normalize_sound(color_wave_sound());save_composition(tmp_path/'sound.json',p)
    saved=load_composition(tmp_path/'sound.json');assert saved['generated_sound']==p['generated_sound']
    after=compile_composition(saved)
    for t in (.25,1.7,3.4):
        assert render_sequence_frame(before,t,(90,160)).tobytes()==render_sequence_frame(after,t,(90,160)).tobytes()


def test_pcm_is_deterministic_looped_and_matches_live_blocks():
    seq=study(2.);c=seq['generated_sound'];s=visual_signals(seq);n=2*RATE
    offline=np.concatenate(list(color_blocks(seq,c,s,Cancellation(),block_size=613)))
    voice=ColorWaveVoice(seq,c,s)
    repeated=np.concatenate([voice.render(i,min(599,2*n-i)) for i in range(0,2*n,599)])
    assert np.array_equal(offline,repeated[:n])
    assert np.max(abs(repeated[:n]-repeated[n:]))<1e-6
    live=LiveInstrument(seq,s,c);played=np.concatenate([live.render(480) for _ in range(n//480)])
    assert np.array_equal(played,offline)
    assert .015<np.sqrt(np.mean(offline*offline))<.4
    assert np.isfinite(offline).all() and np.max(abs(offline))<.9
    # Transport/processing boundaries have no exceptional impulse.
    assert abs(repeated[n]-repeated[n-1]).max()<np.quantile(abs(np.diff(repeated,axis=0)),.999)
    silent=copy.deepcopy(c);silent['enabled']=False
    assert not np.any(ColorWaveVoice(seq,silent,s).render(0,4800))


def test_live_edits_keep_the_clock_and_crossfade_the_previous_voice():
    seq=study(3.);c=seq['generated_sound'];s=visual_signals(seq)
    live=LiveInstrument(seq,s,c);live.render(RATE)
    old=ColorWaveVoice(seq,c,s);old.render(0,RATE)
    changed=copy.deepcopy(c);changed['voices']['steps'].update(decay=.3,brightness=.95)
    live.update(changed);first=live.render(480)
    assert np.array_equal(first[0],old.render(RATE,480)[0])
    parts=[first]+[live.render(480) for _ in range(7)]
    assert live.position==RATE+8*480 and live.old is None
    assert live.voice.config==changed
    assert abs(np.diff(np.concatenate(parts),axis=0)).max()<.1


def test_studio_discovers_lattice_and_applies_an_undoable_sound(studio,monkeypatch):
    from synth_visual_sound_live import LiveSoundMonitor
    from test_synth_visual_sound_live import Output
    from test_synth_composer_ui import wait_until
    import synth_visual_sound_live
    class Monitor(LiveSoundMonitor):
        def __init__(self,parent):super().__init__(parent,backend_factory=Output)
    monkeypatch.setattr(synth_visual_sound_live,'LiveSoundMonitor',Monitor)
    studio.composer.commit(lattice_composition(),'lattice')
    assert studio.visual_sound_button.isEnabled()
    original=copy.deepcopy(studio.composition)
    studio.open_visual_sound();wait_until(lambda:studio.live_signals is not None,seconds=15)
    assert studio.visual_sound_dialog.read_config()['version']==4
    assert any(k.startswith('lattice_phase_') for k in studio.live_signals)
    generation=studio.settings_generation
    d=studio.visual_sound_dialog;d.color_wave.voices['strum']['decay'].setValue(500)
    wait_until(lambda:studio.live_sound.config['voices']['strum']['decay']==.5)
    assert studio.settings_generation==generation and studio.composition==original
    d.apply();assert studio.composition['generated_sound']['voices']['strum']['decay']==.5
    d.close();studio.undo_composition();assert 'generated_sound' not in studio.composition


@pytest.mark.parametrize('path,value',[(('gain',),float('nan')),(('seamless_loop',),1),(('source',),'pleated_field'),(('voices','steps','decay'),0),(('voices','strum','scale'),'oops')])
def test_validation(path,value):
    c=color_wave_sound();entry=c
    for key in path[:-1]:entry=entry[key]
    entry[path[-1]]=value
    with pytest.raises(ValueError):normalize_sound(c)


from test_synth_visual_sound_ui import app,studio


def test_color_panel_controls_undo_and_mixer_roundtrip(app):
    from synth_visual_sound_ui import VisualSoundDialog
    d=VisualSoundDialog();c=normalize_sound(color_wave_sound());d.set_config(c)
    assert d.read_config()==c
    assert not d.tabs.isTabVisible(1) and not d.tabs.isTabVisible(2)
    assert d.mixer.boxes['body'].title()=='Opening'
    d.color_wave.voices['steps']['decay'].setValue(700)
    assert d.read_config()['voices']['steps']['decay']==.7
    d.undo_draft();assert d.read_config()==c
    d.redo_draft();assert d.read_config()['voices']['steps']['decay']==.7
    d.mixer.channels['body']['mute'].setChecked(True)
    assert d.read_config()['mixer']['body']['mute']
    d.close()
