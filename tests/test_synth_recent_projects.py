"""Recent projects: persistent covers, stale-result safety and document ownership."""
import copy
from io import BytesIO
import json
import os
from pathlib import Path
import threading
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from nebula.core.media import Cancellation
from nebula.documents.synth_composition import blank_composition, save_composition
from nebula.documents.synth_recent_projects import RecentProjects, RecentProjectStore, packet_png, render_project_cover
from nebula.ui.synth_recent_projects_ui import RecentProjectsDialog, ENTRY, STATE
from nebula.ui.synth_studio import SynthStudio
from nebula.ui.synth_montage_ui import MontageWindow


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def project_file(tmp_path, name='Saved project'):
    project = blank_composition(); project['name'] = name
    project['canvas'].update(width=96, height=64); project['sections'][0]['duration'] = 1.
    path = tmp_path / (name+'.json'); save_composition(path, project)
    return path, project


def png(color='red'):
    image = Image.new('RGB', (96,64), color)
    return packet_png((image.size, image.tobytes()))


def wait_for(app, predicate):
    limit = time.monotonic()+5
    while not predicate() and time.monotonic()<limit:
        app.processEvents(); time.sleep(.01)
    assert predicate()


def test_persistent_cover_identity_dedup_and_remove_keeps_file(tmp_path):
    path, _ = project_file(tmp_path)
    store = RecentProjectStore(tmp_path/'library')
    entry = store.remember(path, .5); key = store.cover_key(entry)
    assert store.accept(str(path), key, entry['revision'], png())
    entry = store.remember(path.parent/'.'/path.name)
    assert entry['seconds'] == .5 and store.current_cover(entry)
    assert len(store.records()) == 1
    reloaded = RecentProjectStore(store.directory)
    assert reloaded.cover(reloaded.records()[0]) == png()
    reloaded.remove(path)
    assert path.exists() and not RecentProjectStore(store.directory).records()


def test_damaged_library_is_ignored_without_blocking_valid_projects(tmp_path):
    path, _ = project_file(tmp_path)
    store = RecentProjectStore(tmp_path/'library')
    entry = store.remember(path, .5)
    index = store.directory/'index.json'
    for invalid in ([], None, {'version': 1, 'projects': None}):
        index.write_text(json.dumps(invalid))
        assert not RecentProjectStore(store.directory).records()
    damaged = [dict(entry, signature=None), dict(entry, seconds='broken'),
               dict(entry, updated=float('nan')), dict(entry, updated=1e100)]
    index.write_text(json.dumps({'version': 1, 'projects': damaged+[entry]}))
    assert RecentProjectStore(store.directory).records() == [entry]


def test_old_revision_or_old_time_never_replaces_new_saved_cover(tmp_path):
    path, project = project_file(tmp_path)
    store = RecentProjectStore(tmp_path/'library')
    old = store.remember(path, .1).copy(); old_key = store.cover_key(old)
    project['name'] = 'Edited'; save_composition(path, project)
    new = store.remember(path, .1)
    assert not store.accept(str(path),old_key,old['revision'],png('red'))
    key = store.cover_key(new); revision = new['revision']
    newer = store.remember(path,.8)
    assert not store.accept(str(path),key,revision,png('red'))
    assert store.accept(str(path),store.cover_key(newer),revision,png('blue'))
    assert store.cover(newer) == png('blue')
    # An external modification also rejects a still-running render.
    path.write_text(path.read_text()+' ')
    assert not store.accept(str(path),store.cover_key(newer),revision,png('red'))


def test_gallery_reads_cached_images_without_scheduling_renders(app,tmp_path,monkeypatch):
    path, _ = project_file(tmp_path)
    store = RecentProjectStore(tmp_path/'library')
    entry = store.remember(path,.5)
    store.accept(str(path),store.cover_key(entry),entry['revision'],png())
    calls=[]
    library = RecentProjects(store.directory, renderer=lambda *args: calls.append(args) or png())
    monkeypatch.setattr(library,'schedule',lambda *args: pytest.fail('Gallery must never render'))
    dialog = RecentProjectsDialog(library); dialog.show(); app.processEvents()
    try:
        assert not calls and dialog.grid.count()==1
        item=dialog.grid.item(0); assert item.data(STATE)=='ready'
        dialog.search.setText(path.stem); assert not item.isHidden()
        dialog.search.setText('missing title'); assert item.isHidden()
        dialog.search.clear(); path.unlink(); dialog.refresh()
        dialog.grid.setCurrentRow(0); assert dialog.open.text()=='Locate file'
        dialog.remove.click(); assert dialog.grid.count()==0
    finally: dialog.close(); library.close()


def test_background_save_render_uses_saved_snapshot_and_survives_restart(app,tmp_path):
    path, project = project_file(tmp_path)
    started=threading.Event(); release=threading.Event(); calls=[]
    def render(path,seconds,cancel):
        calls.append((json.loads(Path(path).read_text())['name'],seconds))
        started.set(); release.wait(3); return png('blue')
    library=RecentProjects(tmp_path/'library',renderer=render)
    try:
        assert library.remember(path,.2)
        assert started.wait(2)
        project['name']='Latest'; save_composition(path,project)
        library.remember(path,.7)
        release.set()
        wait_for(app,lambda: library.store.current_cover(library.store.records()[0]))
        assert calls[-1]==('Latest',.7)
        assert library.store.cover(library.store.records()[0])==png('blue')
        assert RecentProjectStore(library.store.directory).records()[0]['seconds']==.7
    finally: release.set(); library.close()


@pytest.mark.parametrize('kind',['Composition','Sequence','Preset','Montage'])
def test_actual_cover_render_supports_each_document_type(tmp_path,kind):
    from nebula.render.synth import default_synth_preset, save_synth
    from nebula.documents.synth_sequence import save_sequence
    from nebula.documents.synth_composition import compile_composition
    from nebula.documents.synth_montage import add_asset,insert_clip,new_montage,save_montage
    path,project=project_file(tmp_path)
    before=copy.deepcopy(project)
    if kind=='Sequence': save_sequence(path,compile_composition(project))
    elif kind=='Preset':
        preset=default_synth_preset(); preset.update(width=96,height=64); save_synth(path,preset)
    elif kind=='Montage':
        doc,key=add_asset(new_montage(project['canvas'],30),'Study',study=project)
        doc,_=insert_clip(doc,key); save_montage(path,doc)
    original=path.read_bytes()
    data=render_project_cover(path,None,Cancellation())
    image=Image.open(BytesIO(data))
    assert image.width<=448 and image.height<=288 and image.mode=='RGB'
    assert project==before and path.read_bytes()==original


class SpyLibrary:
    def __init__(self): self.calls=[]
    def remember(self,*args,**kwargs): self.calls.append((args,kwargs))


@pytest.fixture
def window(app,monkeypatch):
    monkeypatch.setattr(SynthStudio,'request_frame',lambda *_:None)
    monkeypatch.setattr(SynthStudio,'schedule_auto_preparation',lambda *_:None)
    monkeypatch.setattr(MontageWindow,'request_frame',lambda *_:None)
    monkeypatch.setattr(MontageWindow,'initialize_media',lambda *_:None)
    spy=SpyLibrary(); win=SynthStudio(composition=blank_composition(),recent_projects=spy)
    yield win,spy
    monkeypatch.setattr(QMessageBox,'question',lambda *_:QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(QMessageBox,'warning',lambda *_:QMessageBox.StandardButton.Discard)
    win.close(); app.processEvents()


def test_open_save_and_stale_or_bypassed_monitor_covers(window,tmp_path,monkeypatch):
    win,spy=window; path,project=project_file(tmp_path)
    assert win.open_document_path(path)
    assert spy.calls[-1][0][0]==path
    win.current_time=.5; win.cover_frame=(win.settings_generation,.5)
    win.viewer.packet=((2,2),bytes(12)); win.preview_image_stale=False
    assert win.save_sequence_dialog()
    assert spy.calls[-1][0][1:]==(.5,win.viewer.packet)
    win.preview_image_stale=True
    assert win.save_sequence_dialog() and spy.calls[-1][0][2] is None
    win.preview_image_stale=False; win.source_preview.setChecked(True)
    assert win.save_sequence_dialog() and spy.calls[-1][0][2] is None
    count=len(spy.calls)
    def fail(*_): raise OSError('No space')
    monkeypatch.setattr('nebula.ui.synth_studio.save_composition',fail)
    monkeypatch.setattr(QMessageBox,'critical',lambda *_:None)
    assert not win.save_sequence_dialog() and len(spy.calls)==count
    assert project['name']==json.loads(path.read_text())['name']


def test_cancel_replacement_does_not_register_an_unopened_project(window,tmp_path,monkeypatch):
    win,spy=window; path,_=project_file(tmp_path)
    win.composition['name']='Unsaved'
    monkeypatch.setattr(win,'confirm_replacement',lambda *args:False)
    assert not win.open_document_path(path)
    assert not spy.calls and win.composition['name']=='Unsaved'


def test_montage_open_and_save_registers_outer_document(window,tmp_path):
    from nebula.documents.synth_montage import new_montage,add_asset,insert_clip,save_montage
    win,spy=window; _,project=project_file(tmp_path)
    doc,key=add_asset(new_montage(project['canvas'],30),'Study',study=project)
    doc,_=insert_clip(doc,key); path=tmp_path/'montage.json'; save_montage(path,doc)
    assert win.open_document_path(path)
    montage=win.workspace_navigation.montage
    assert montage.recent_projects is spy
    editor=montage.edit_clip(montage.document['clips'][0]['id'])
    editor.composition['name']='Changed block'
    assert editor.save_sequence_dialog()
    assert all(Path(call[0][0])==path for call in spy.calls)
    assert json.loads(path.read_text())['clips'][0]['document']['name']=='Changed block'


def test_folder_import_skips_unrelated_json_and_preserves_timestamps(app,tmp_path):
    path,_=project_file(tmp_path)
    native = tmp_path/'Native.NEBULA'; native.write_bytes(path.read_bytes())
    (tmp_path/'unrelated.json').write_text('{"hello": "world"}')
    (tmp_path/'broken.json').write_text('broken')
    library=RecentProjects(tmp_path/'library',renderer=lambda *_:png())
    try:
        library.import_folder(tmp_path)
        wait_for(app,lambda:not library.import_timer.isActive())
        entries=library.store.records(); assert len(entries)==2
        assert {e['path'] for e in entries}=={str(path), str(native)}
        assert all(e['updated']==Path(e['path']).stat().st_mtime_ns/1e9 for e in entries)
        wait_for(app,lambda:library.store.current_cover(library.store.records()[0]))
    finally: library.close()
