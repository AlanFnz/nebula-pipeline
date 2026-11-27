"""Poster preview stays on one frame until the editor explicitly opens animation."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PIL import Image
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QFileDialog

from nebula.core.media import Cancellation
from nebula.documents import synth_sequence, synth_study_thumbnails
from nebula.documents.synth_composition import save_composition
from nebula.documents.synth_recent_projects import render_project_cover
from nebula.documents.synth_starting_points import new_piece
from nebula.ui.synth_frame_export_ui import FrameExportDialog
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


def test_still_export_and_effect_preview_leave_animation_off(poster_preview, tmp_path, monkeypatch):
    studio, jobs = poster_preview
    studio.open_effect_discovery('bloom')
    dialog = studio.discovery_dialog
    assert not dialog.session.samples and not dialog.preview_play.isVisible() and not dialog.scrubber.isVisible()
    dialog.session.prepare_samples()
    assert not jobs
    dialog.reject()
    studio.preview_debounce.stop()
    studio.request_frame()
    while jobs:
        jobs.pop(0).run()
    path = tmp_path / 'poster.png'
    monkeypatch.setattr(FrameExportDialog, 'choose', lambda *args: (path, (160, 200), 90))
    studio.export_button.click()
    assert studio.still_poster and studio.export_progress.isVisible() and studio.cancel_export.isVisible()
    assert studio.transport.isHidden() and studio.preview_controls_scroll.isHidden()
    assert len(jobs) == 1 and jobs[0] is studio.export_job
    jobs.pop().run()
    with Image.open(path) as saved:
        assert saved.size == (160, 200)
    assert studio.still_poster and not studio.warm_debounce.isActive()
    assert not jobs and not studio.has_unsaved_changes()

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    studio.export_button.movie_action.trigger()
    assert studio.still_poster and not jobs
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'poster.mp4'), ''))
    studio.export_button.movie_action.trigger()
    assert not studio.still_poster and studio.transport.isVisible()
    job = jobs.pop()
    assert job is studio.export_job
    studio._finish_export(job)


def test_poster_covers_use_one_frame_even_if_the_paper_is_black(tmp_path, monkeypatch):
    frames = []
    def black_frame(sequence, seconds, size, *args, **kwargs):
        frames.append(seconds)
        return Image.new('RGB', size)

    monkeypatch.setattr(synth_sequence, 'render_sequence_frame', black_frame)
    monkeypatch.setattr(synth_study_thumbnails, 'render_sequence_frame', black_frame)
    document = new_piece('poster', {'width': 160, 'height': 200}, fps=24)
    path = tmp_path / 'print.nebula'
    save_composition(path, document)
    synth_study_thumbnails.render_thumbnail(document, (64, 64))
    render_project_cover(path, None, Cancellation())
    render_project_cover(path, 3 / 24, Cancellation())
    assert frames == [0., 0., 3 / 24]
