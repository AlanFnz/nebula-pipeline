"""Poster preview stays on one frame until the editor explicitly opens animation."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from nebula.documents.synth_starting_points import new_piece
from nebula.ui.synth_studio import PreparePreviewJob, RenderJob, SynthStudio


@pytest.fixture
def poster_preview(monkeypatch):
    app = QApplication.instance() or QApplication([])
    jobs = []
    monkeypatch.setattr(QThreadPool.globalInstance(), 'start', jobs.append)
    document = new_piece('poster', {'width': 160, 'height': 200}, fps=24)
    document['sections'][0]['duration'] = 1.
    studio = SynthStudio(composition=document)
    studio.show()
    app.processEvents()
    assert len(jobs) == 1 and isinstance(jobs[0], RenderJob)
    jobs.pop().run()
    try:
        yield studio, jobs
    finally:
        studio.mark_document_clean()
        studio.close()
        for job in jobs:
            job.run()
        app.processEvents()


def test_only_the_poster_frame_is_prepared_until_animation_is_enabled(poster_preview):
    studio, jobs = poster_preview
    assert studio.auto_prepare.isChecked() and studio.timeline.maximum() == 23
    assert studio.still_poster and not studio.warm_debounce.isActive()
    assert set(studio.preview_frames.available()) == {0}
    assert not any(w.isVisible() for w in (studio.transport, studio.cache_status, studio.preview_controls_scroll,
                                           studio.workspace_fps_host))
    studio.play.click()
    studio.step_frame(1)
    studio.prepare_configured_range()
    studio.prepare_full_playback()
    studio.prepare_preview_gap(2)
    studio._automatic_preparation()
    assert not jobs and not studio.play.isChecked() and studio.timeline.value() == 0
    panel = studio.composer.layers_panel
    panel.select('text')
    panel.change('content', 'Another word')
    studio.preview_debounce.stop()
    studio.request_frame()
    assert len(jobs) == 1 and isinstance(jobs[0], RenderJob)
    jobs.pop().run()
    assert set(studio.preview_frames.available()) == {0} and not studio.warm_debounce.isActive()

    studio.poster_animation.click()
    assert studio.transport.isVisible() and studio.preview_controls_scroll.isVisible()
    assert studio.warm_debounce.isActive()
    studio.warm_debounce.stop()
    studio._automatic_preparation()
    batch = jobs.pop()
    assert isinstance(batch, PreparePreviewJob) and batch.frames[0] == 1
    batch.run()
    studio.timeline.setValue(2)
    assert studio.cover_frame == (studio.settings_generation, 2 / 24)
    studio.prepare_full_playback()
    outstanding = jobs.pop()
    studio.loop_preview_range.setChecked(True)
    studio.play.click()
    studio.poster_animation.click()
    assert studio.still_poster and not studio.play_timer.isActive()
    assert outstanding.cancel.event.is_set() and not studio.loop_preview_range.isChecked()
    assert studio.timeline.value() == 2 and studio.auto_prepare.isChecked()
    studio.export_summary.refresh_summary()
    assert dict(studio.export_summary.rows)['Range'] == 'Single frame · Frame 2'
    assert studio.export_summary.export_action.text() == 'Export poster…'
    prepared = set(studio.preview_frames.available())
    outstanding.signals.done.emit((outstanding.generation, [(12, ((1, 1), bytes(3)))]))
    QApplication.processEvents()
    assert set(studio.preview_frames.available()) == prepared
    assert not jobs and not studio.preparation_target and not studio.warm_debounce.isActive()

    studio.auto_prepare.setChecked(False)
    studio.poster_animation.click()
    assert not studio.warm_debounce.isActive()
    studio.set_composition(new_piece('shape'), guard=False)
    assert not studio.still_poster and studio.transport.isVisible() and studio.poster_tools.isHidden()
    studio.set_composition(new_piece('poster'), guard=False)
    assert studio.still_poster and studio.timeline.value() == 0 and not studio.has_unsaved_changes()
