"""Native montage contracts: local clocks, reversible cuts and full export."""
import copy
import json
import os
import subprocess
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication
from synth_composition import blank_composition, compile_composition
from synth_sequence import render_sequence_frame
from synth_video import inspect_video
from synth_montage import *


@pytest.fixture
def project():
    p=blank_composition(); p['canvas'].update(width=96,height=64)
    p['sections'][0]['duration']=2.
    p['effects']={'dye_transfer':{'mode':'on','params':{'dye_transfer.grain':.06}}}
    return p


@pytest.fixture
def montage(project):
    d=new_montage(project['canvas'],30); d,k=add_asset(d,'Study',study=project)
    d,_=insert_clip(d,k,in_frame=3,frames=12)
    d,_=insert_clip(d,k,in_frame=18,frames=10)
    return d


@pytest.fixture
def footage(tmp_path):
    path=tmp_path/'original.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=96x64:rate=30:duration=2',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
    return inspect_video(path)


def test_native_clocks_survive_reorder_and_split(montage,project):
    sequence=compile_composition(project)
    with MontageRenderer(montage) as r:
        for output,source in ((0,3),(11,14),(12,18),(21,27)):
            assert np.array_equal(np.asarray(r.frame(output)),np.asarray(render_sequence_frame(sequence,source/30)))
    split=split_clip(montage,5)
    with MontageRenderer(montage) as before,MontageRenderer(split) as after:
        for frame in (0,4,5,11,12,21): assert np.array_equal(before.frame(frame),after.frame(frame))
    reordered=copy.deepcopy(montage); reordered['clips'].reverse()
    with MontageRenderer(reordered) as r:
        assert np.array_equal(r.frame(0),render_sequence_frame(sequence,18/30))


def test_save_reopen_embeds_study_and_markers(montage,tmp_path):
    montage['markers']=[{'frame':12,'name':'Hit'}]
    path=tmp_path/'edit.json'; save_montage(path,montage)
    assert load_montage(path)==normalize_montage(montage)
    assert len(load_montage(path)['clips'])==2


def test_split_keeps_fractional_source_clock(montage):
    montage['clips'][0]['speed']=.5
    split=split_clip(montage,5)
    assert split['clips'][1]['in_frame']==5.5
    with MontageRenderer(montage) as before,MontageRenderer(split) as after:
        for frame in (4,5,6,11): assert np.array_equal(before.frame(frame),after.frame(frame))


def test_bad_source_bounds_and_duplicate_ids_rejected(montage):
    bad=copy.deepcopy(montage); bad['clips'][0]['in_frame']=60
    with pytest.raises(ValueError,match='beyond'): normalize_montage(bad)
    bad=copy.deepcopy(montage); bad['clips'][1]['id']=bad['clips'][0]['id']
    with pytest.raises(ValueError,match='unique'): normalize_montage(bad)


def test_replacement_keeps_cut_treatment_and_source_untouched(montage,footage):
    before=copy.deepcopy(montage)
    montage,key=add_asset(montage,'Video',footage=footage)
    clip=montage['clips'][0]
    replaced=replace_clip(montage,clip['id'],key,in_frame=20)
    assert [c['frames'] for c in replaced['clips']]==[12,10]
    assert replaced['clips'][0]['in_frame']==20
    assert replaced['clips'][0]['document']['effects']['dye_transfer']['mode']=='on'
    assert montage['clips']==before['clips']
    assert replaced['assets'][key]['footage']==footage


def test_export_counts_and_original_protection(montage,footage,tmp_path):
    montage,key=add_asset(montage,'Video',footage=footage)
    with pytest.raises(ValueError,match='original media'): save_montage(footage['path'],montage)
    with pytest.raises(ValueError,match='original media'): export_montage(montage,footage['path'])
    out=tmp_path/'render.mp4'; export_montage(montage,out)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(out)]))['streams'][0]
    assert (info['width'],info['height'],int(info['nb_frames']))==(96,64,22)
    subprocess.run(['ffmpeg','-v','error','-i',str(out),'-f','null','-'],check=True)


def test_export_cancel_is_atomic(montage,tmp_path):
    from media import Cancellation,Cancelled
    out=tmp_path/'render.mp4'; out.write_bytes(b'previous export')
    cancel=Cancellation()
    def progress(done,total): cancel.cancel()
    with pytest.raises((Cancelled,ValueError,BrokenPipeError)): export_montage(montage,out,cancel,progress)
    assert out.read_bytes()==b'previous export'
    assert not list(tmp_path.glob('.nebula-montage-*'))


def test_native_editor_undo_and_treatment_selection(montage,monkeypatch):
    from synth_montage_ui import MontageWindow
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(MontageWindow,'request_frame',lambda *args:None)
    monkeypatch.setattr(MontageWindow,'initialize_media',lambda *args:None)
    w=MontageWindow(montage); w.select_all(); w.duplicate()
    assert len(w.document['clips'])==4
    w.undo(); assert w.document==normalize_montage(montage)
    w.redo(); assert len(w.document['clips'])==4
    w.select_clip(w.document['clips'][0]['id']); w.copy_look(); w.select_all(); w.paste_look()
    assert all('document' in c for c in w.document['clips'])
    w.undo(); assert all('document' not in c for c in w.document['clips'])
    w.zoom(150); w.wave.show(); w.show(); app.processEvents()
    total=sum(c['frames'] for c in w.document['clips'])
    assert w.wave.width()==round(total/w.document['fps']*150)
    assert w.tracks.minimumWidth()==w.timeline.minimumWidth()
    assert w.wave.mapTo(w.tracks,w.wave.rect().topLeft()).x()==12
    w.soundtrack_dialog(); w.sound_dialog.close()
    w.clean=copy.deepcopy(w.document); w.close(); app.processEvents()


def test_original_studio_opens_native_montage(project,monkeypatch):
    from synth_montage_ui import MontageWindow
    from synth_studio import SynthStudio
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(MontageWindow,'request_frame',lambda *args:None)
    monkeypatch.setattr(MontageWindow,'initialize_media',lambda *args:None)
    monkeypatch.setattr(SynthStudio,'request_frame',lambda *args:None)
    w=SynthStudio(composition=project); native=w.open_montage()
    assert native.document['assets'][native.document['clips'][0]['asset']]['document']==w.composition
    native.close(); w.close(); app.processEvents()


def test_apply_native_clip_edit_is_isolated_and_undoable(montage,monkeypatch):
    from synth_montage_ui import MontageWindow
    from synth_studio import SynthStudio
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(MontageWindow,'request_frame',lambda *args:None)
    monkeypatch.setattr(MontageWindow,'initialize_media',lambda *args:None)
    monkeypatch.setattr(SynthStudio,'request_frame',lambda *args:None)
    window=MontageWindow(montage); original=copy.deepcopy(window.document)
    key=window.document['clips'][0]['id']; window.edit_clip(key)
    editor=window.editors[-1]
    editor.composition['name']='Edited clip copy'
    window.apply_editor(key,editor)
    assert window.document['clips'][0]['document']['name']=='Edited clip copy'
    assert 'document' not in window.document['clips'][1]
    assert window.document['assets']==original['assets']
    assert [c['frames'] for c in window.document['clips']]==[12,10]
    window.undo(); assert window.document==original
    window.close(); app.processEvents()


def test_timeline_drag_trim_snaps_to_absolute_marker(montage,monkeypatch):
    from PySide6.QtCore import QPoint,Qt
    from PySide6.QtTest import QTest
    from synth_montage_ui import MontageWindow
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(MontageWindow,'request_frame',lambda *args:None)
    monkeypatch.setattr(MontageWindow,'initialize_media',lambda *args:None)
    montage['markers']=[dict(frame=18,name='Hit')]
    window=MontageWindow(montage); window.show(); window.zoom(150); app.processEvents()
    timeline=window.timeline; clip=window.document['clips'][0]
    edge=round(timeline.rectangles()[0][-1].right())
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=QPoint(edge,60))
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=QPoint(round(timeline.x(18))+2,60))
    assert window.document['clips'][0]['frames']==18
    assert window.document['markers']==montage['markers']
    window.undo(); assert window.document==normalize_montage(montage)
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=QPoint(round(timeline.x(2)),60))
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=QPoint(round(timeline.x(22)),60))
    assert window.document['clips'][-1]['id']==clip['id']
    window.undo(); window.close(); app.processEvents()
