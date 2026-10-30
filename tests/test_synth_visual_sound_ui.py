import copy
import os
from pathlib import Path
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QObject, Signal, QThreadPool
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition
from synth_exploration import capture_snapshot, restore_snapshot
from synth_pleated_recipes import pleated_composition
from synth_preview import _visual_document
from synth_visual_sound import default_sound, sound_key
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
    dialog.connections['friction'][0].setChecked(False);dialog.apply()
    assert spy.count()==1
    config=spy.at(0)[0]
    assert config['pitch']==90 and not config['connections']['friction']['enabled']
    assert config['gain']==.7
    dialog.set_config(default_sound());assert dialog.pitch.value()==62
    dialog.close()


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
