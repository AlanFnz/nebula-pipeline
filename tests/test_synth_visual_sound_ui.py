import copy
import os
from pathlib import Path
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QObject, Signal, QThreadPool, Qt, QPoint
from PySide6.QtTest import QSignalSpy,QTest
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition
from synth_exploration import capture_snapshot, restore_snapshot
from synth_pleated_recipes import pleated_composition
from synth_preview import _visual_document
from synth_visual_sound import default_sound, acid_sound, instrument_sound, sound_key
from synth_visual_sound_ui import VisualSoundDialog
from synth_visual_sound_studio import VisualSoundJob
from synth_studio import SynthStudio


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


class Monitor(QObject):
    statusChanged=Signal(str)
    status=''
    def __init__(self,parent=None):
        super().__init__(parent);self.track=None;self.syncs=[];self.muted=False;self.volume=1.
    def set_track(self,track): self.track=copy.deepcopy(track)
    def sync(self,t,playing,force=False): self.syncs.append((t,playing,force))
    def set_monitor_volume(self,value): self.volume=value
    def set_monitor_muted(self,value): self.muted=value
    def close(self): self.track=None


@pytest.fixture
def studio(app,monkeypatch):
    monkeypatch.setattr('synth_visual_sound_studio.SoundtrackPreview',Monitor)
    monkeypatch.setattr('synth_soundtrack_studio.SoundtrackPreview',Monitor)
    monkeypatch.setattr(SynthStudio,'request_frame',lambda self:None)
    w=SynthStudio(composition=pleated_composition());w.auto_prepare.setChecked(False)
    # Lifecycle tests explicitly deliver job results, without racing the pool.
    w.visual_sound_debounce.stop()
    monkeypatch.setattr(w,'prepare_visual_sound',lambda:None)
    yield w
    w.close();QThreadPool.globalInstance().waitForDone(5000);app.processEvents()


def test_dialog_draft_and_monitor_are_separate(app):
    dialog=VisualSoundDialog();spy=QSignalSpy(dialog.configEdited)
    dialog.set_config(None);dialog.pitch.setValue(90);dialog.volume.setValue(40)
    dialog.set_config(None) # Playback refresh must not overwrite a draft.
    assert dialog.pitch.value()==90 and spy.count()==0
    dialog.connections['filter'][0].setChecked(False);dialog.apply()
    assert spy.count()==1
    config=spy.at(0)[0]
    assert config['pitch']==90 and not config['connections']['filter']['enabled']
    assert config['gain']==.7
    dialog.set_config(default_sound());assert dialog.pitch.value()==62
    dialog.close()


def test_acid_controls_roundtrip_and_instrument_switch_is_only_a_draft(app):
    dialog=VisualSoundDialog();spy=QSignalSpy(dialog.configEdited)
    config=acid_sound();config.update(cutoff=200.,sweep=3000.,resonance=.6,scale='dorian',arp_rate=1.2)
    config['connections']['arpeggio']['amount']=.5
    dialog.set_config(config);dialog.apply()
    assert spy.at(0)[0]==config
    dialog.voice.setCurrentIndex(dialog.voice.findData(1))
    assert set(dialog.connections)=={'body','friction','return'} and spy.count()==1
    dialog.apply();assert spy.at(1)[0]['version']==1
    dialog.set_config(default_sound());dialog.apply();assert spy.at(2)[0]==default_sound()
    dialog.set_config(config);dialog.apply();assert spy.at(3)[0]==config
    dialog.close()


def test_knobs_drag_keyboard_and_numeric_entry_preserve_a_draft(app):
    dialog=VisualSoundDialog();spy=QSignalSpy(dialog.configEdited);dialog.set_config(instrument_sound());dialog.show();app.processEvents()
    knob=dialog.opening;knob.setValue(40)
    QTest.mousePress(knob.dial,Qt.MouseButton.LeftButton,pos=QPoint(39,55))
    QTest.mouseMove(knob.dial,QPoint(39,25));QTest.mouseRelease(knob.dial,Qt.MouseButton.LeftButton,pos=QPoint(39,25))
    assert knob.value()>40 and spy.count()==0
    knob.number.setValue(52.25);assert knob.value()==52.25
    before=knob.value();QTest.keyClick(knob.dial,Qt.Key.Key_Right)
    assert knob.value()==before+1
    QTest.keyClick(knob.dial,Qt.Key.Key_Left,Qt.KeyboardModifier.ShiftModifier)
    assert knob.value()==pytest.approx(before+.9)
    dialog.unison.setValue(2);QTest.keyClick(dialog.unison.dial,Qt.Key.Key_Right);assert dialog.unison.value()==3
    dialog.oscillators[1][0].setChecked(False);dialog.detune.setValue(12.5);dialog.apply()
    config=spy.at(0)[0];assert config['version']==3 and config['detune']==12.5
    assert not config['oscillators'][1]['enabled'] and config['opening']==pytest.approx(knob.value()/100)
    dialog.set_config(config);dialog.apply();assert spy.at(1)[0]==config
    dialog.close()


def test_layered_instrument_undo_preserves_visual_cache_and_all_controls(studio):
    original=copy.deepcopy(studio.composition);visual=_visual_document(studio.sequence)
    config=instrument_sound();config['oscillators'][2]['wave']='sine';config['unison']=5;config['detune']=15
    studio.apply_visual_sound(config);assert studio.sequence['generated_sound']==config
    assert _visual_document(studio.sequence)==visual
    studio.undo_composition();assert studio.composition==original
    studio.redo_composition();assert studio.sequence['generated_sound']==config


def test_apply_undo_snapshot_and_monitor_never_change_image(studio):
    original=copy.deepcopy(studio.composition);visual=_visual_document(studio.sequence)
    studio.apply_visual_sound(default_sound())
    assert studio.sequence['generated_sound']==default_sound()
    assert _visual_document(studio.sequence)==visual
    studio.mark_document_clean();studio.set_visual_sound_volume(.3);studio.set_visual_sound_muted(True)
    assert not studio.has_unsaved_changes()
    assert studio.visual_sound_player.volume==.3 and studio.visual_sound_player.muted
    assert studio.soundtrack_playback.muted
    snapshot,identifier=capture_snapshot(studio.composition,'Audible')
    assert snapshot['snapshots'][0]['document']['generated_sound']==default_sound()
    restored=restore_snapshot(snapshot,identifier)
    assert restored['generated_sound']==default_sound()
    studio.undo_composition();assert studio.composition==original
    assert studio.visual_sound_player.track is None
    studio.redo_composition();assert studio.composition['generated_sound']==default_sound()
    config=default_sound();config['output']='existing';studio.apply_visual_sound(config)
    assert not studio.soundtrack_playback.muted


def test_stale_preparation_cannot_install_audio_in_another_document(studio):
    studio.apply_visual_sound(default_sound())
    seq=studio.sequence;job=VisualSoundJob(seq,sound_key(seq),studio.document_identity)
    job.folder=tempfile.TemporaryDirectory();folder=Path(job.folder.name)
    studio.visual_sound_job=job;studio.pending_jobs.append(job)
    studio.document_identity=object()
    studio.visual_sound_ready(job,({'path':'stale'},{}))
    assert studio.visual_sound_player.track is None and not folder.exists()
    assert job not in studio.pending_jobs


def test_edit_cancels_old_audio_and_transport_uses_project_clock(studio):
    studio.apply_visual_sound(default_sound())
    seq=studio.sequence;job=VisualSoundJob(seq,sound_key(seq),studio.document_identity)
    studio.visual_sound_job=job
    config=default_sound();config['pitch']=95
    studio.apply_visual_sound(config)
    assert job.cancel.event.is_set() and studio.visual_sound_player.track is None
    studio.sync_soundtrack(force=True,seconds=12.25)
    assert studio.visual_sound_player.syncs[-1]==(12.25,False,True)
    studio.play.setChecked(True)
    studio.sync_soundtrack(force=True,seconds=18.75)
    assert studio.visual_sound_player.syncs[-1]==(18.75,True,True)
    studio.play.setChecked(False)
