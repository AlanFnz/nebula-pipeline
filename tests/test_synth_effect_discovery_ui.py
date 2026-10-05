"""Observable audition lifecycle, ownership, transport and navigation contracts."""
import copy
import pytest
from PySide6.QtCore import QEvent, QThreadPool, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from synth_starting_points import new_piece
from synth_studio import SynthStudio
from synth_effect_discovery_ui import EffectAuditionDialog
from synth_effect_preview import EffectPreviewSession
from synth_exploration import capture_snapshot
from synth_video import inspect_video, video_composition
from test_synth_video import clip

REAL_REQUEST_FRAME = SynthStudio.request_frame


@pytest.fixture
def window(monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio,'request_frame',lambda self:None)
    w=SynthStudio(composition=new_piece('shape'));w.auto_prepare.setChecked(False)
    w.resize(1280,720);w.show();app.processEvents()
    yield w
    if w.discovery_session: w.discovery_dialog.reject()
    w.mark_document_clean();w.close();QThreadPool.globalInstance().waitForDone(10000)
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def select(dialog,identifier):
    for row in range(dialog.table.rowCount()):
        if dialog.table.item(row,0).data(Qt.ItemDataRole.UserRole)==identifier:
            dialog.table.selectRow(row);return
    raise AssertionError(identifier)


def test_cancel_preserves_snapshot_comparison_quality_history_and_keyboard(window):
    doc,sid=capture_snapshot(window.composition,'Before')
    window.composer.commit(doc,'snapshot-capture');window.mark_document_clean()
    window.compare_snapshot(sid);prior=window.comparison
    window.quality.setCurrentIndex(2);window.timeline.setValue(3)
    before=copy.deepcopy(window.composition);history=copy.deepcopy(window.undo_compositions)
    window.open_effect_discovery()
    d=window.discovery_dialog
    select(d,'tape');d.debounce.stop();d.render_selection()
    d.session.accept_packet();d.refresh_preview()
    assert d.action.isEnabled() and not window.audition_pending()
    d.search.setFocus();QTest.keyClick(d.search,Qt.Key.Key_Return)
    assert window.composition==before
    QTest.keyClick(d,Qt.Key.Key_Escape);QApplication.processEvents()
    assert window.discovery_session is None and window.comparison is prior
    assert window.timeline.value()==3 and window.quality.currentIndex()==2
    assert window.undo_compositions==history and not window.has_unsaved_changes()


def test_selection_invalidates_late_packet_and_apply(window):
    window.open_effect_discovery();d=window.discovery_dialog
    select(d,'tape');d.debounce.stop();d.render_selection()
    old=d.session.owner
    select(d,'bloom')
    assert d.session.owner is None and d.session.candidate is None
    d.session.accept_packet();d.refresh_preview()
    assert not d.action.isEnabled() and not d.session.ready
    d.debounce.stop();d.render_selection();d.session.accept_packet();d.refresh_preview()
    candidate=copy.deepcopy(d.session.candidate);history=len(window.undo_compositions)
    d.action.click()
    assert window.composition==candidate and len(window.undo_compositions)==history+1
    window.undo_composition();assert 'bloom' not in window.composition['effects']
    window.redo_composition();assert window.composition==candidate


def test_applied_effect_restores_working_preview_after_audition(window, monkeypatch):
    window.composer.change_effect('bloom', {'mode': 'on', 'params': {}}, 'effect-add')
    before = copy.deepcopy(window.composition)
    history = copy.deepcopy(window.undo_compositions)
    monkeypatch.setattr(SynthStudio, 'request_frame', REAL_REQUEST_FRAME)
    # The fixture connected the no-render stub when constructing its timer.
    window.preview_debounce.timeout.disconnect()
    window.preview_debounce.timeout.connect(window.request_frame)
    window.open_effect_discovery(); d = window.discovery_dialog
    select(d, 'tape'); d.debounce.stop(); d.render_selection()
    assert window.comparison is not None
    # The old path cleared the viewport and had no comparison/context change
    # left to trigger rendering when browsing another applied effect.
    select(d, 'bloom'); d.debounce.stop(); d.render_selection()
    assert window.comparison is None and d.session.candidate is None
    for _ in range(200):
        QApplication.processEvents()
        if window.viewer.packet is not None: break
        QTest.qWait(25)
    assert window.viewer.packet is not None
    assert window.preview_sequence() == window.sequence
    assert d.action.text() == 'Inspect effect' and d.action.isEnabled()
    assert window.composition == before and window.undo_compositions == history


def test_browsing_applied_effect_keeps_current_picture(window):
    window.composer.change_effect('bloom', {'mode': 'on', 'params': {}}, 'effect-add')
    window.open_effect_discovery(); d = window.discovery_dialog
    d.debounce.stop(); d.render_selection()
    if window.comparison: window.end_comparison()
    packet = ((1, 1), b'\x12\x34\x56')
    window.viewer.set_packet(packet)
    select(d, 'bloom'); d.debounce.stop(); d.render_selection()
    assert window.viewer.packet == packet
    assert window.render_queued and window.preview_debounce.isActive()
    assert d.session.candidate is None


def test_failure_stale_document_export_and_drafts_disable_or_reject(window):
    session=EffectPreviewSession(window);session.select('tape');session.fail('Decode failed')
    with pytest.raises(ValueError):session.apply()
    window.composer.change_effect('bloom',{'mode':'on','params':{}},'edit')
    assert session.closed and window.discovery_session is None
    window.export_job=object()
    with pytest.raises(ValueError,match='export'):EffectPreviewSession(window)
    window.export_job=None


def test_without_is_temporary_and_navigation_creates_no_edit(window):
    before=copy.deepcopy(window.composition);history=copy.deepcopy(window.undo_compositions)
    window.open_effect_discovery('tape',0,'without');d=window.discovery_dialog
    d.debounce.stop();d.render_selection()
    assert d.session.candidate['effects']['tape']['bypassed']
    assert not d.action.isVisible()
    d.reject()
    panel=window.composer.effects_panel
    panel.inspect_effect('bloom');window.refresh_effect_explanations()
    panel.navigate_explanation()
    assert window.composition==before and window.undo_compositions==history


def test_closed_browsers_release_copied_documents(window):
    for _ in range(10):
        window.open_effect_discovery('tape',0,'replace');window.discovery_dialog.reject()
        QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);QApplication.processEvents()
    assert not window.findChildren(EffectAuditionDialog)
    assert window.discovery_dialog is None and window.discovery_session is None


def test_cutout_waits_for_explicit_preparation_and_cannot_apply_previous_effect(window,clip):
    document=video_composition(clip)
    window.set_composition(document,clean=True)
    window.open_effect_discovery();d=window.discovery_dialog
    select(d,'tape');d.debounce.stop();d.render_selection();d.session.accept_packet()
    select(d,'subject_cutout');d.debounce.stop();d.render_selection()
    d.session.accept_packet();d.refresh_preview()
    assert d.session.candidate is None and not d.action.isEnabled()
    assert 'Prepare preview' in d.preview_note.text()


def test_selected_section_explicit_seek_uses_nearest_actual_occurrence(window):
    doc=copy.deepcopy(window.composition)
    second=copy.deepcopy(doc['sections'][0]);second['id']='second';second['loops']=2
    doc['sections'].append(second);window.composer.commit(doc,'sections')
    window.composer.select_section(1)
    window.preview_scope.setCurrentIndex(1)
    window.section_timeline.selected_ids={doc['sections'][0]['id']}
    window.timeline.setValue(0)
    session=EffectPreviewSession(window,'second','replace');session.select('tape')
    assert session.samples==()
    session.seek_selected()
    assert session.target_scope.contains(window.timeline.value()) and session.samples
    assert all(session.target_scope.contains(frame) for frame in session.samples)
    session.close()
    assert window.timeline.value()==0


def test_object_preset_workflow_stays_available(window):
    panel=window.composer.effects_panel
    panel.inspect_effect('forms');panel.apply_look()
    assert window.discovery_session is None
    assert window.composition['effects']['forms']['mode']=='on'


def test_search_and_category_changes_audition_the_current_selected_effect(window):
    window.open_effect_discovery();d=window.discovery_dialog
    select(d,'bloom');d.debounce.stop();d.render_selection();d.session.accept_packet()
    d.search.setText('Tape')
    assert d.session.owner is None and d.debounce.isActive()
    d.debounce.stop();d.render_selection();d.session.accept_packet();d.refresh_preview()
    assert d.session.effect_id=='tape' and d.action.isEnabled()
    assert d.action.text()=='Apply effect' and d.action.accessibleName()=='Apply selected effect'


def test_current_preparation_failure_stops_play_and_offers_retry(window, monkeypatch):
    from types import SimpleNamespace
    window.open_effect_discovery('tape',0,'replace');d=window.discovery_dialog
    d.debounce.stop();d.render_selection();d.session.accept_packet()
    job=SimpleNamespace(generation=window.settings_generation,reserved_bytes=0)
    monkeypatch.setattr(d.session, 'prepare_samples', lambda: None)
    window.preparation_explicit=True
    d.preview_play.setChecked(True)
    # Use the actual current preparation identity after Play's new request.
    window.prepare_job=window.warming_job=job
    window.preparation_finished(job,error='Decode failed in sampled loop')
    d.refresh_preview()
    assert d.session.error and not d.preview_play.isChecked() and not d.transport.isActive()
    assert d.retry.isVisible() and not d.action.isEnabled()


def test_halo_diagnostic_navigation_opens_a_live_editable_parameter(window):
    window.composer.change_effect('cloud',{'mode':'on','params':{'slab.cloud_strength':0}},'halo')
    panel=window.composer.effects_panel;panel.inspect_effect('cloud')
    window.refresh_effect_explanations();panel.navigate_explanation();QApplication.processEvents()
    assert panel.controls['slab.cloud_strength'].isVisible()
    assert panel.controls['slab.cloud_strength'].isEnabled()
