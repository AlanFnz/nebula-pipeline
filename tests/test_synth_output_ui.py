"""Monitor state and output disclosures cannot author or retime a document."""
import copy
import json
import os
import subprocess
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QEvent, Qt, QThreadPool
from PySide6.QtWidgets import QApplication
from synth import default_synth_preset
from synth_canvas import preview_size
from synth_composition import blank_composition
from synth_media import export_synth_video
from synth_montage import new_montage, add_asset, insert_clip
from synth_montage_ui import MontageWindow
from synth_output_ui import export_rows, export_audio_label, cache_caption
from synth_studio import SynthStudio
from synth_visual_sound import instrument_sound


@pytest.fixture
def editor(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda *_: None)
    project = blank_composition(); project['canvas'].update(width=113, height=65)
    project['sections'][0]['duration'] = .2; project['fps'] = 30
    window = SynthStudio(composition=project)
    window.auto_prepare.setChecked(False); window.show(); app.processEvents()
    yield window
    window.visual_sound_dialog = None
    window.close(); QThreadPool.globalInstance().waitForDone(5000)
    window.deleteLater(); app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_longest_edge_is_bounded_without_upscaling():
    for canvas, expected in [({'width':1080,'height':1920},(202,360)),
                             ({'width':1920,'height':1080},(360,202)),
                             ({'width':113,'height':65},(113,65))]:
        assert preview_size(canvas,360) == expected
        assert preview_size(canvas,None) == (canvas['width'],canvas['height'])


def test_optional_summary_zoom_and_quality_do_not_change_recipe(editor):
    before = copy.deepcopy(editor.composition); sequence = copy.deepcopy(editor.sequence)
    for quality in (2,0,1):
        editor.quality.setCurrentIndex(quality)
        editor.viewer.set_zoom(.05); editor.fit_view_button.click()
        editor.export_summary.refresh_summary()
        rows = dict(editor.export_summary.rows)
        assert rows['Canvas'] == '113 × 65 px'
        assert rows['MP4 size'].startswith('114 × 66 px')
        assert rows['Timing'] == '30 FPS · 0.200 s · 6 frames'
        assert rows['Range'] == 'Entire composition'
        assert editor.viewer.zoom == 0
    assert editor.composition == before and editor.sequence == sequence
    assert not editor.has_unsaved_changes()


def test_preview_scope_complete_does_not_claim_full_document(editor):
    doc = copy.deepcopy(editor.composition)
    doc['sections'].append(dict(doc['sections'][0], id='second'))
    editor.set_composition(doc); editor.preview_frames.clear()
    editor.section_timeline.select_at(0); editor.preview_scope.setCurrentIndex(1)
    scope = editor.active_preview_scope()
    for f in range(scope.count): editor.preview_frames.put(f,((1,1),b'abc'))
    editor.preparation_target = tuple(range(scope.count))
    editor._preparation_ready()
    assert editor.cache_status.text() == 'Selected clips: 6/6 frames · complete'
    assert editor.preview_status.text().startswith('Selected clips fully prepared')
    editor.preview_scope.setCurrentIndex(0); editor._preparation_ready()
    assert editor.cache_status.text() == 'Timeline: 6/12 frames · partial'
    assert 'fully prepared' not in editor.preview_status.text()
    editor.invalidate(force_clear=True)
    assert editor.cache_status.text() == 'Timeline: 0/12 frames · not prepared'
    assert 'outdated' in editor.preview_status.text()


def test_auto_window_is_partial_even_when_memory_would_fit_timeline(editor):
    editor.preview_frames.clear()
    for frame in (0,1): editor.preview_frames.put(frame,((1,1),b'abc'))
    editor.preparation_target = (0,1); editor.preparation_limited = False
    editor._preparation_ready()
    assert editor.preview_status.text() == 'Preview partially prepared · prepared range ready'
    editor.preview_frames.clear(); editor._preparation_ready()
    assert editor.preview_status.text() == 'Preview not prepared'
    assert 'complete' not in cache_caption('Timeline',0,0)


def test_summary_warns_about_sound_draft_without_applying_it(editor):
    doc = copy.deepcopy(editor.composition); doc['generated_sound'] = instrument_sound()
    editor.set_composition(doc); before = copy.deepcopy(editor.composition)
    editor.visual_sound_dialog = SimpleNamespace(has_sound_draft=lambda:True)
    editor.export_summary.refresh_summary()
    assert dict(editor.export_summary.rows)['Audio'] == 'Generated sound · applied settings'
    assert 'Sound draft' in dict(editor.export_summary.rows)
    assert editor.composition == before
    editor.visual_sound_dialog = None


def test_audio_summary_matches_export_routes():
    sound = instrument_sound(); doc = {'generated_sound':sound}
    assert export_audio_label(doc).startswith('Generated sound')
    sound['enabled'] = False; assert export_audio_label(doc).startswith('Silent')
    sound['output'] = 'existing'
    doc['soundtrack'] = {'export_audio':'soundtrack','path':'/example/guide.wav'}
    assert export_audio_label(doc) == 'Soundtrack · guide.wav'
    assert export_audio_label(doc,montage=True) == 'Soundtrack · guide.wav'
    doc['soundtrack']['export_audio'] = 'silent'
    assert export_audio_label(doc).startswith('Silent')
    assert export_audio_label({'generated_sound':instrument_sound()},montage=True).startswith('Silent')
    assert export_audio_label({}).startswith('Silent')
    source = {'audio':'keep','has_audio':True}
    assert export_audio_label({'footage':source}).startswith('Original footage')
    source['audio'] = 'mute'
    assert export_audio_label({'footage':source}).startswith('Silent')


def test_legacy_sequence_summary_falls_back_to_preset_canvas():
    p = default_synth_preset()
    rows = dict(export_rows({'name':'Legacy','duration':1,'fps':25},preset=p))
    assert rows['Canvas'] == f"{p['width']} × {p['height']} px"


def test_export_at_different_preview_settings_has_identical_frames(editor,tmp_path):
    hashes = []
    for quality, zoom in [(0,.05),(2,1.5)]:
        editor.quality.setCurrentIndex(quality); editor.viewer.set_zoom(zoom)
        path = tmp_path / f'quality-{quality}.mp4'
        export_synth_video(editor.preset,path,sequence=editor.sequence)
        info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams'][0]
        assert (info['width'],info['height'],info['nb_frames'],info['r_frame_rate']) == (114,66,'6','30/1')
        hashes.append(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','framemd5','-']))
    assert hashes[0] == hashes[1]


@pytest.fixture
def montage(editor,monkeypatch):
    monkeypatch.setattr(MontageWindow,'request_frame',lambda *_:None)
    monkeypatch.setattr(MontageWindow,'initialize_media',lambda *_:None)
    doc,key = add_asset(new_montage({'width':1080,'height':1920},30),'Study',study=editor.composition)
    doc,_ = insert_clip(doc,key,frames=6)
    window = editor.open_montage(document=doc)
    yield window
    window.revert_timing()


def test_montage_counts_only_current_revision_and_resolution(montage):
    size = montage.preview_size(); key = (montage.revision,size,0)
    montage.cache_packet(key,((1,1),b'abc'))
    assert montage.cache_status.text() == 'Montage: 1/6 frames · partial'
    montage.detail.setCurrentIndex(2)
    assert montage.cache_status.text() == 'Montage: 0/6 frames · not prepared'
    montage.detail.setCurrentIndex(0)
    assert '1/6' in montage.cache_status.text()
    montage.invalidate()
    assert '0/6' in montage.cache_status.text()


def test_old_montage_preparation_cannot_report_new_resolution_ready(montage,monkeypatch):
    callbacks = []; progress_callbacks = []
    def task(work,done,failed=None,**kwargs):
        result = SimpleNamespace(cancel=SimpleNamespace(cancel=lambda:None),
                                 signals=SimpleNamespace(progress=SimpleNamespace(connect=progress_callbacks.append)))
        callbacks.append(done)
        return result
    monkeypatch.setattr(montage,'task',task)
    montage.prepare()
    montage.detail.setCurrentIndex(2)
    status = montage.status.text()
    progress_callbacks[0](6,6)
    callbacks[0]([(0,((1,1),b'old'))])
    assert montage.status.text() == status
    assert montage.cache_status.text() == 'Montage: 0/6 frames · not prepared'
    assert montage.prepare_task is None


def test_block_preview_and_montage_export_have_different_scopes(montage):
    before = copy.deepcopy(montage.document)
    editor = montage.edit_clip(montage.document['clips'][0]['id'])
    editor.export_summary.refresh_summary(); editor.refresh_cache_status()
    rows = dict(editor.export_summary.rows)
    assert rows['Range'] == 'Entire montage'
    assert rows['Canvas'] == '1080 × 1920 px'
    assert editor.cache_status.text().startswith('Block composition:')
    assert montage.document == before
    assert editor.workspace_navigation.return_to_montage()
    montage.select_clip(montage.document['clips'][0]['id']); montage.length.setValue(5)
    montage.export_summary.refresh_summary()
    assert 'Timing draft' in dict(montage.export_summary.rows)
    assert dict(montage.export_summary.rows)['Timing'] == '30 FPS · 0.200 s · 6 frames'
    assert montage.document == before


@pytest.mark.parametrize('size',[(1280,800),(1440,900),(1024,768)])
def test_monitor_controls_and_summary_fit_workspace(editor,size):
    from studio_theme import apply_theme
    apply_theme(QApplication.instance())
    editor.resize(*size); QApplication.processEvents()
    assert editor.width() == size[0]
    assert editor.quality.isVisible() and editor.cache_status.isVisible()
    assert editor.quality.geometry().right() < editor.quality.parentWidget().width()
    editor.export_summary.refresh_summary()
    assert editor.export_summary.menu().sizeHint().height() < size[1]-60
