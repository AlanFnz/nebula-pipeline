"""Soundtrack authoring, portable media and project transport integration."""
import copy
import os
import wave
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QObject, Signal, QThreadPool
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition, load_composition, save_composition
from synth_exploration import capture_snapshot
from synth_preview import RenderValidity, retained_frame_predicate
from synth_section_sources import soundtrack_references
from synth_soundtrack import probe_soundtrack, check_soundtrack
from synth_soundtrack_studio import SoundtrackJob
from synth_starting_points import new_piece
from synth_studies import save_study, study_composition
from synth_studio import SynthStudio


@pytest.fixture
def soundtrack(tmp_path):
    path = tmp_path / 'original.wav'
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\0\0' * 80000)
    return probe_soundtrack(path)


class FakeMonitor(QObject):
    statusChanged = Signal(str)
    status = ''

    def __init__(self, parent=None):
        super().__init__(parent)
        self.track = None
        self.syncs = []
        self.volume, self.muted = 1., False
        self.closed = False

    def set_track(self, track): self.track = copy.deepcopy(track)
    def sync(self, seconds, playing, *, force=False): self.syncs.append((seconds, playing, force))
    def set_monitor_volume(self, value): self.volume = value
    def set_monitor_muted(self, value): self.muted = value
    def close(self): self.closed = True


@pytest.fixture
def studio(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr('synth_soundtrack_studio.SoundtrackPreview', FakeMonitor)
    monkeypatch.setattr('synth_soundtrack_studio.waveform_peaks', lambda *args: [.3] * 10)
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    window = SynthStudio(composition=new_piece('text'))
    window.auto_prepare.setChecked(False)
    yield window
    window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()


def test_add_edit_remove_undo_and_monitor_are_independent(studio, soundtrack):
    original = copy.deepcopy(studio.composition)
    duration = studio.sequence['duration']
    studio.apply_soundtrack(soundtrack)
    assert studio.composition['soundtrack'] == soundtrack
    assert studio.sequence['soundtrack'] == soundtrack
    assert studio.sequence['duration'] == duration
    assert studio.has_unsaved_changes()
    assert not studio.soundtrack_lane.isHidden()
    studio.mark_document_clean()
    studio.set_soundtrack_monitor_volume(.4)
    studio.set_soundtrack_monitor_muted(True)
    assert not studio.has_unsaved_changes()
    assert studio.composition['soundtrack']['gain'] == 1
    studio.apply_soundtrack(dict(soundtrack, offset=2, **{'in': 1., 'out': 4.}))
    studio.undo_composition()
    assert studio.composition['soundtrack'] == soundtrack
    studio.redo_composition()
    assert studio.composition['soundtrack']['offset'] == 2
    studio.apply_soundtrack(None)
    assert 'soundtrack' not in studio.sequence
    assert studio.composition == original
    assert studio.soundtrack_lane.isHidden()
    studio.undo_composition()
    assert studio.composition['soundtrack']['offset'] == 2


def test_transport_scrub_and_snapshot_switch_use_absolute_preview_track(studio, soundtrack):
    studio.apply_soundtrack(soundtrack)
    captured, identifier = capture_snapshot(studio.composition, 'Original sound')
    studio.composer.commit(captured, 'snapshot-capture')
    studio.apply_soundtrack(dict(soundtrack, offset=2))
    studio.timeline.setValue(30)
    assert studio.soundtrack_playback.syncs[-1] == (1.2, False, True)
    studio.play.setChecked(True)
    assert studio.soundtrack_playback.syncs[-1][0] == pytest.approx(1.2, abs=.01)
    assert studio.soundtrack_playback.syncs[-1][1:] == (True, True)
    studio.compare_snapshot(identifier)
    assert studio.soundtrack_playback.track['offset'] == 0
    studio.set_comparison_side('b')
    assert studio.soundtrack_playback.track['offset'] == 2
    studio.play.setChecked(False)
    assert not studio.soundtrack_playback.syncs[-1][1]


def test_audio_only_changes_keep_video_cache(soundtrack):
    before = new_piece('text')
    after = dict(before, soundtrack=soundtrack)
    identity = object()
    first = RenderValidity.capture(identity, before, compile_composition(before), None, ())
    second = RenderValidity.capture(identity, after, compile_composition(after), None, ())
    retain = retained_frame_predicate(first, second)
    assert retain is not None
    assert all(retain(frame) for frame in range(150))


def test_portable_study_deduplicates_snapshot_audio_and_survives_move(soundtrack, tmp_path):
    project = new_piece('text')
    project['soundtrack'] = soundtrack
    project, _ = capture_snapshot(project, 'Sound A')
    project['soundtrack']['offset'] = .75
    original = copy.deepcopy(project)
    library = tmp_path / 'Studies'
    identifier = save_study(project, 'Sound piece', library)
    assert project == original
    assert len(list(library.glob('*/media/*'))) == 1
    Path(soundtrack['path']).unlink()
    moved = tmp_path / 'Moved'; library.rename(moved)
    loaded = study_composition(identifier, moved)
    refs = list(soundtrack_references(loaded))
    assert len(refs) == 2 and refs[0]['path'] == refs[1]['path']
    for track in refs: assert check_soundtrack(track).is_file()
    assert loaded['soundtrack']['offset'] == .75
    assert loaded['snapshots'][0]['document']['soundtrack']['offset'] == 0
    saved = tmp_path / 'project.json'
    save_composition(saved, loaded)
    assert load_composition(saved) == loaded


def test_stale_import_cannot_change_replacement_document(studio, soundtrack):
    job = SoundtrackJob(path=soundtrack['path'])
    job.document_identity = studio.document_identity
    job.previous_track = None
    job.relink = False
    studio.soundtrack_import_job = job
    studio.pending_jobs.append(job)
    studio.set_composition(new_piece('shape'))
    studio.soundtrack_imported(job, soundtrack)
    assert 'soundtrack' not in studio.composition
    assert studio.composition['name'] == 'Untitled shape'


def test_source_protection_covers_audio_snapshots_and_hard_links(studio, soundtrack, tmp_path):
    studio.apply_soundtrack(soundtrack)
    project, _ = capture_snapshot(studio.composition, 'Keep soundtrack')
    studio.composer.commit(project, 'snapshot')
    studio.apply_soundtrack(None)
    assert studio.protected_document_destination(soundtrack['path'])
    alias = tmp_path / 'same-audio.mp4'
    os.link(soundtrack['path'], alias)
    assert studio.protected_document_destination(alias)


def test_relink_too_short_keeps_track_and_settings(studio, soundtrack):
    studio.apply_soundtrack(soundtrack)
    job = SoundtrackJob(path=soundtrack['path'])
    job.document_identity = studio.document_identity
    job.previous_track = copy.deepcopy(soundtrack)
    job.relink = True
    studio.soundtrack_import_job = job
    studio.soundtrack_imported(job, dict(soundtrack, duration=2, out=2))
    assert studio.composition['soundtrack'] == soundtrack
    assert 'shorter' in studio.soundtrack_lane.status


def test_low_fps_preserves_fractional_clock_and_same_frame_wrap(studio, soundtrack, monkeypatch):
    clock = [100.]
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    project = copy.deepcopy(studio.composition)
    project['fps'] = 1
    project['sections'][0]['duration'] = 2
    studio.composer.commit(project, 'duration')
    studio.apply_soundtrack(soundtrack)
    studio.play.setChecked(True)
    clock[0] = 101.9
    studio.advance()
    assert studio.timeline.value() == 1
    assert studio.soundtrack_playback.syncs[-1][0] == pytest.approx(1.9)
    clock[0] = 103.9  # Another cycle, same slider frame; audio still seeks.
    studio.advance()
    assert studio.timeline.value() == 1
    assert studio.soundtrack_playback.syncs[-1][0] == pytest.approx(1.9)
    assert studio.soundtrack_playback.syncs[-1][2]
    studio.seek_soundtrack(1.)
    assert studio.soundtrack_playback.syncs[-1][0] == pytest.approx(1.)
    assert studio.soundtrack_playback.syncs[-1][2]


def test_selected_short_gap_forces_audio_seek(studio, soundtrack, monkeypatch):
    from synth_preview import PreviewScope
    clock = [100.]
    monkeypatch.setattr('synth_studio.time.monotonic', lambda: clock[0])
    studio.apply_soundtrack(soundtrack)
    monkeypatch.setattr(studio, 'active_preview_scope', lambda: PreviewScope(((0, 1), (2, 5)), 2))
    studio.play.setChecked(True)
    clock[0] += .01
    studio.advance()
    clock[0] += .04  # Skip just one 40ms frame: below adapter's drift threshold.
    studio.advance()
    assert studio.timeline.value() == 2
    assert studio.soundtrack_playback.syncs[-1][0] == pytest.approx(.09)
    assert studio.soundtrack_playback.syncs[-1][2]


@pytest.mark.parametrize('relink', [False, True])
def test_rejected_lower_sample_rate_import_preserves_project_monitor_and_error(studio, soundtrack, tmp_path, relink):
    assert studio.apply_soundtrack(soundtrack)
    config = {'enabled': True, 'mappings': [dict(
        id='full-range', track_id=soundtrack['id'], path='radial_bloom.expansion',
        low_hz=0., high_hz=soundtrack['sample_rate'] / 2, amount=.5,
        sensitivity=1., attack=.05, release=.2, enabled=True)]}
    studio.apply_audio_reactivity(config)
    before = copy.deepcopy(studio.composition)
    sequence = copy.deepcopy(studio.sequence)
    undo = copy.deepcopy(studio.undo_compositions)
    monitored = copy.deepcopy(studio.soundtrack_playback.track)
    path = tmp_path / 'lower-rate.wav'
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 4000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\0\0' * 40000)
    replacement = probe_soundtrack(path)
    job = SoundtrackJob(path=str(path))
    job.document_identity = studio.document_identity
    job.previous_track = copy.deepcopy(soundtrack)
    job.relink = relink
    studio.soundtrack_import_job = job
    studio.pending_jobs.append(job)
    assert studio.soundtrack_imported(job, replacement) is False
    assert studio.composition == before and studio.sequence == sequence
    assert studio.undo_compositions == undo
    assert studio.soundtrack_playback.track == monitored
    assert studio.soundtrack_import_job is None and job not in studio.pending_jobs
    assert 'Adjust the response frequency range first' in studio.soundtrack_lane.status
    assert 'Adjust the response frequency range first' in studio.status.text()
    assert 'Soundtrack ready' not in studio.status.text()
