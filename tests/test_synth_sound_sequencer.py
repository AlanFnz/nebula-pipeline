"""Editable rhythm, tuning, live parity, and complete sound-edit history."""
import copy
import numpy as np
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest, QSignalSpy
from synth_visual_sound import instrument_sound, normalize_sound
from synth_visual_sound_acid import gesture_notes
from synth_visual_sound_live import LiveInstrument
from synth_sound_sequence import sequence_defaults, note_frequency, frequency_note, step_seconds
from synth_visual_sound_ui import VisualSoundDialog
from test_synth_visual_sound_instrument import signals
from test_synth_visual_sound_ui import app, studio
from test_synth_arpeggio import render
from test_synth_composer_ui import wait_until


def custom():
    c=instrument_sound();c.update(arp_mode='sequence',bpm=120.,subdivision='1/8',sequence_length=4)
    return c


def test_note_locks_snap_both_roots_but_free_mode_preserves_exact_frequencies():
    c=instrument_sound();c.update(pitch=80.63,arp_pitch=217.9)
    assert normalize_sound(c)==c
    c.update(pitch_mode='note',arp_pitch_mode='note');out=normalize_sound(c)
    assert out['pitch']==note_frequency(40) and out['arp_pitch']==220.
    assert normalize_sound(out)==out
    assert out['sequence']==c['sequence']


def test_legacy_contract_has_no_new_rhythm_or_pcm_changes():
    c=instrument_sound();s=signals(2.);s['opening'][12]=1
    legacy=copy.deepcopy(c)
    for key in (*sequence_defaults(),'pitch_mode','arp_pitch_mode'):legacy.pop(key)
    assert render(legacy,s).tobytes()==render(normalize_sound(legacy),s).tobytes()


def test_gestures_start_on_tempo_grid_and_rests_take_time():
    c=custom();c['sequence'][1]['enabled']=False;c['sequence'][2].update(semitones=-7,velocity=.23,gate=.2)
    s=signals(4.);s['opening'][13]=1
    notes=gesture_notes(s,c)
    assert [n['time'] for n in notes]==[.25,.75,1.]
    assert notes[1]['semitones']==-7 and notes[1]['velocity']==pytest.approx(.23*.85)
    assert notes[1]['duration']==pytest.approx(.05)
    assert [n['step'] for n in gesture_notes(s,c,include_rests=True)]==[0,1,2,3]
    assert not gesture_notes(signals(4.),c)
    c['bpm']=60.
    assert [n['time'] for n in gesture_notes(s,c)]==[.5,1.5,2.]


def test_timeline_loop_is_anchored_and_does_not_sound_when_image_is_absent():
    c=custom();c['sequence_trigger']='loop';s=signals(2.)
    notes=gesture_notes(s,c);assert [n['time'] for n in notes]==list(np.arange(0,2.,.25))
    assert [n['step'] for n in notes]==[0,1,2,3]*2
    assert all(n['time']<s['time'][-1] for n in notes)
    s['presence'][:]=0;assert not gesture_notes(s,c)
    c['subdivision']='1/8T';assert step_seconds(c)==pytest.approx(1/6)


def test_custom_sequence_pcm_live_export_changes_and_gate():
    c=custom();c.update(sequence_trigger='loop',arp_pitch=220.,unison=1);s=signals(1.)
    exported=render(c,s);seq=dict(duration=1.,seed=31);live=LiveInstrument(seq,s,c)
    assert np.array_equal(exported,np.concatenate([live.render() for _ in range(100)]))
    short=copy.deepcopy(c)
    for entry in short['sequence']:entry['gate']=.1
    assert not np.array_equal(exported,render(short,s))
    live=LiveInstrument(seq,s,c);live.render(12000);live.update(short)
    chunk=live.render();assert np.array_equal(chunk[0],exported[12000])
    assert np.isfinite(chunk).all() and abs(np.diff(chunk,axis=0)).max()<.1


@pytest.mark.parametrize('key,value',[('pitch_mode','chromatic'),('arp_pitch_mode',None),('arp_mode','bad'),
    ('bpm',float('nan')),('bpm',True),('bpm',241),('sequence_length',0),('sequence_length',17),
    ('sequence_length',True),('subdivision','1/64'),('sequence_trigger','random'),('sequence',[])])
def test_reject_invalid_sequence_fields(key,value):
    c=custom();c[key]=value
    with pytest.raises(ValueError):normalize_sound(c)


@pytest.mark.parametrize('key,value',[('enabled',1),('semitones',True),('semitones',25),
    ('gate',0),('velocity',float('inf'))])
def test_reject_invalid_step_fields(key,value):
    c=custom();c['sequence'][2][key]=value
    with pytest.raises(ValueError):normalize_sound(c)


def test_every_sound_control_and_entire_voice_switch_can_undo_and_redo(app):
    d=VisualSoundDialog();d.set_config(instrument_sound());d.show();app.processEvents()
    baseline=d.read_config();states=[baseline]
    edits=[lambda:d.opening.setValue(73),lambda:d.pitch.mode.setCurrentIndex(1),
           lambda:d.arp_pitch.mode.setCurrentIndex(1),lambda:d.arp_pitch.note.setCurrentIndex(12),
           lambda:d.arp_mode.setCurrentIndex(1),lambda:d.sequencer.bpm.setValue(97),
           lambda:d.sequencer.length.setValue(12),lambda:d.sequencer.entries[1][1].setChecked(False),
           lambda:d.sequencer.entries[3][4].setValue(-5),lambda:d.sequencer.entries[5][5].setValue(22),
           lambda:d.sequencer.entries[2][6].setValue(31),lambda:d.oscillators[2][1].setCurrentIndex(3),
           lambda:d.connections['filter'][0].setChecked(False),lambda:d.connections['body'][1].setValue(34),
           lambda:d.enabled.setChecked(False),lambda:d.output.setCurrentIndex(2),lambda:d.voice.setCurrentIndex(2)]
    for edit in edits:edit();states.append(d.read_config())
    assert len(d.sound_undo)==len(edits)
    for expected in reversed(states[:-1]):assert d.undo_draft() and d.read_config()==expected
    assert not d.undo_draft()
    for expected in states[1:]:assert d.redo_draft() and d.read_config()==expected
    d.undo_draft();d.gain.setValue(11);assert not d.sound_redo
    d.close()


def test_one_drag_one_undo_and_cmd_z_with_numeric_focus(app):
    d=VisualSoundDialog();d.set_config(instrument_sound());d.show();d.activateWindow();app.processEvents()
    baseline=d.opening.value();dial=d.opening.dial
    QTest.mousePress(dial,Qt.MouseButton.LeftButton,pos=QPoint(39,60))
    for y in (50,40,30):QTest.mouseMove(dial,QPoint(39,y));app.processEvents()
    QTest.mouseRelease(dial,Qt.MouseButton.LeftButton,pos=QPoint(39,30))
    assert d.opening.value()!=baseline and len(d.sound_undo)==1
    d.opening.number.setFocus();app.processEvents()
    QTest.keySequence(d.opening.number,QKeySequence(QKeySequence.StandardKey.Undo));app.processEvents()
    assert d.opening.value()==baseline
    QTest.keySequence(d.opening.number,QKeySequence(QKeySequence.StandardKey.Redo));app.processEvents()
    assert d.opening.value()!=baseline
    d.close()


def test_note_mode_keyboard_and_save_round_trip(app,studio,tmp_path):
    from synth_composition import save_composition,load_composition
    d=VisualSoundDialog();d.set_config(instrument_sound());d.pitch.mode.setCurrentIndex(1)
    before=frequency_note(d.pitch.value());QTest.keyClick(d.pitch.dial,Qt.Key.Key_Right)
    assert frequency_note(d.pitch.value())==before+1
    d.arp_mode.setCurrentIndex(1);d.sequencer.length.setValue(12)
    d.sequencer.entries[9][4].setValue(-9);d.sequencer.entries[10][1].setChecked(False)
    d.sequencer.entries[11][5].setValue(24);d.sequencer.entries[11][6].setValue(53)
    c=d.read_config();studio.apply_visual_sound(c);save_composition(tmp_path/'seq.json',studio.composition)
    loaded=load_composition(tmp_path/'seq.json')['generated_sound'];assert loaded==c
    d.set_config(loaded);assert d.read_config()==c;d.close()


def test_edit_menu_restores_drafts_then_applied_change_and_reauditions(studio,monkeypatch):
    monkeypatch.setattr(studio,'audition_visual_sound',lambda config:None)
    studio.apply_visual_sound(instrument_sound());studio.open_visual_sound();d=studio.visual_sound_dialog
    baseline=copy.deepcopy(studio.composition);draft=QSignalSpy(d.draftChanged)
    d.arp_mode.setCurrentIndex(1);d.sequencer.bpm.setValue(99)
    studio.undo_action.trigger();assert d.sequencer.bpm.value()==120 and d.arp_mode.currentData()=='sequence'
    assert draft.at(draft.count()-1)[0]['bpm']==120
    studio.redo_action.trigger();assert d.sequencer.bpm.value()==99
    d.apply();assert studio.composition['generated_sound']['bpm']==99 and not d.sound_undo
    studio.undo_action.trigger();assert studio.composition==baseline and d.arp_mode.currentData()=='visual'
    studio.redo_action.trigger();assert studio.composition['generated_sound']['bpm']==99
    d.close()


def test_undo_commits_pending_numeric_text_before_restoring_previous_value(app):
    d=VisualSoundDialog();d.set_config(instrument_sound());d.show();d.activateWindow();app.processEvents()
    d.opening.number.setFocus();d.opening.number.selectAll();QTest.keyClicks(d.opening.number,'82')
    QTest.keySequence(d.opening.number,QKeySequence(QKeySequence.StandardKey.Undo));app.processEvents()
    assert d.opening.value()==35.
    d.redo_draft();assert d.opening.value()==82.
    d.close()
