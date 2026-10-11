"""Authored responses, stale workers and pixel dependencies in Studio."""
import copy
import os
from pathlib import Path

import pytest
from PIL import Image

from synth_audio_reactivity_studio import AudioReactivityJob
from synth_composition import compile_composition, normalize_composition
from synth_preview import RenderValidity, retained_frame_predicate, preview_context
from synth_studio import RenderJob, PreparePreviewJob
from synth_starting_points import new_piece
from test_synth_soundtrack_integration import studio, soundtrack


def mapping_config(track, **updates):
    mapping = dict(id='response-one', track_id=track['id'], path='bloom.strength',
                   low_hz=40., high_hz=180., amount=.1, sensitivity=1.,
                   attack=.05, release=.2, enabled=True)
    mapping.update(updates)
    return {'enabled': True, 'mappings': [mapping]}


def reactive_project(track):
    project = new_piece('text')
    project.update(soundtrack=copy.deepcopy(track), audio_reactivity=mapping_config(track))
    return normalize_composition(project)


class HeldJobs:
    def __init__(self):
        self.jobs = []

    def start(self, job, *args):
        self.jobs.append(job)

    def waitForDone(self, *args):
        return True


@pytest.fixture
def editor(studio, soundtrack):
    studio.apply_soundtrack(soundtrack)
    studio.jobs = HeldJobs()
    return studio


def test_edit_bypass_remove_and_undo_preserve_track(editor, soundtrack):
    track = copy.deepcopy(editor.composition['soundtrack'])
    config = mapping_config(track)
    editor.apply_audio_reactivity(config)
    assert editor.composition['audio_reactivity'] == config
    assert editor.sequence['audio_reactivity'] == config
    assert editor.composition['schema_version'] == 5
    assert editor.has_unsaved_changes()
    assert isinstance(editor.audio_reactivity_job, AudioReactivityJob)
    first = editor.audio_reactivity_job
    editor.apply_audio_reactivity(dict(config, enabled=False))
    assert first.cancel.event.is_set()
    assert editor.audio_reactivity_job is None
    assert not editor.composition['audio_reactivity']['enabled']
    editor.undo_composition()
    assert editor.composition['audio_reactivity'] == config
    editor.apply_soundtrack(None)
    assert 'soundtrack' not in editor.composition and 'audio_reactivity' not in editor.composition
    assert 'audio_reactivity' not in editor.sequence
    editor.undo_composition()
    assert editor.composition['soundtrack'] == track
    assert editor.composition['audio_reactivity'] == config
    editor.apply_audio_reactivity({'enabled': True, 'mappings': []})
    assert 'audio_reactivity' not in editor.composition
    assert editor.composition['schema_version'] == 4
    assert editor.composition['soundtrack'] == soundtrack


def test_monitor_and_output_levels_dont_restart_analysis(editor):
    track = copy.deepcopy(editor.authored_soundtrack())
    editor.apply_audio_reactivity(mapping_config(track))
    job = editor.audio_reactivity_job
    key = copy.deepcopy(editor.audio_reactivity_key)
    editor.mark_document_clean()
    editor.set_soundtrack_monitor_volume(.2)
    editor.set_soundtrack_monitor_muted(True)
    assert not editor.has_unsaved_changes()
    assert editor.audio_reactivity_job is job
    editor.apply_soundtrack(dict(track, gain=.3, name='Renamed', export_audio='silent'))
    assert editor.audio_reactivity_key == key and editor.audio_reactivity_job is job
    assert not job.cancel.event.is_set()


def test_stale_analysis_and_close_cannot_update_current_document(editor):
    editor.apply_audio_reactivity(mapping_config(editor.authored_soundtrack()))
    old = editor.audio_reactivity_job
    editor.apply_audio_reactivity(mapping_config(editor.authored_soundtrack(), attack=.3))
    current = editor.audio_reactivity_job
    assert current is not old and old.cancel.event.is_set()
    status = editor.audio_reactivity_status
    editor.audio_reactivity_prepared(old, error='Old decode failed')
    assert editor.audio_reactivity_job is current and editor.audio_reactivity_status == status
    editor.set_composition(new_piece('shape'))
    assert current.cancel.event.is_set() and editor.audio_reactivity_job is None
    editor.audio_reactivity_prepared(current, result=object())
    assert 'audio_reactivity' not in editor.composition
    assert editor.audio_reactivity_status == ''


def test_worker_cancellation_reaches_decoder_and_suppresses_done(soundtrack, monkeypatch):
    seen = []
    job = AudioReactivityJob(compile_composition(reactive_project(soundtrack)), object(), 'key')
    def prepare(sequence, *, cancel):
        seen.append(cancel)
        cancel.cancel()
        return object()
    monkeypatch.setattr('synth_audio_reactivity_studio.prepare_reactivity', prepare)
    done, errors = [], []
    job.signals.done.connect(done.append)
    job.signals.failed.connect(errors.append)
    job.run()
    assert seen == [job.cancel] and done == []
    assert errors == ['Audio analysis cancelled']


def test_meters_only_read_cached_responses(editor, monkeypatch):
    editor.apply_audio_reactivity(mapping_config(editor.authored_soundtrack()))
    editor.open_audio_reactivity()
    def forbidden(*args, **kwargs):
        raise AssertionError('UI meter must not start analysis or read media identity')
    monkeypatch.setattr('synth_audio_reactivity_studio.prepare_reactivity', forbidden)
    monkeypatch.setattr('synth_audio_reactivity_studio._file_fingerprint', forbidden)
    monkeypatch.setattr('synth_audio_reactivity_studio.cached_responses', lambda sequence, seconds: {'response-one': .625})
    editor.audio_reactivity_available = True
    editor.sync_audio_reactivity(1.3)
    assert editor.audio_reactivity_dialog.response_meter.value() == 625
    assert editor.audio_reactivity_dialog.target_hint.text()  # Bloom remains disabled.
    editor.audio_reactivity_dialog.close()
    assert editor.audio_reactivity_job is None


def test_failed_analysis_never_shows_stale_cached_meter(editor, monkeypatch):
    editor.apply_audio_reactivity(mapping_config(editor.authored_soundtrack()))
    editor.open_audio_reactivity()
    job = editor.audio_reactivity_job
    editor.audio_reactivity_prepared(job, error='Media identity changed')
    monkeypatch.setattr('synth_audio_reactivity_studio.cached_responses', lambda *args: {'response-one': 1.})
    editor.sync_audio_reactivity(.8)
    assert editor.audio_reactivity_dialog.response_meter.value() == 0
    assert 'Media identity changed' in editor.audio_reactivity_dialog.status_label.text()


def test_hidden_dialog_does_not_resolve_or_sample_responses(editor, monkeypatch):
    editor.open_audio_reactivity()
    editor.audio_reactivity_dialog.close()
    def forbidden(*args, **kwargs):
        raise AssertionError('Closed response editor must not perform meter work')
    monkeypatch.setattr('synth_audio_reactivity_studio.cached_responses', forbidden)
    monkeypatch.setattr('synth_sequence.resolve_sequence_frame', forbidden)
    editor.sync_audio_reactivity(.8)


def test_open_editor_checks_changed_audio_before_accepting_cached_meter(editor, monkeypatch):
    editor.apply_audio_reactivity(mapping_config(editor.authored_soundtrack()))
    old = editor.audio_reactivity_job
    editor.audio_reactivity_prepared(old, result=object())
    assert editor.audio_reactivity_available
    monkeypatch.setattr('synth_audio_reactivity_studio.cached_responses', lambda *args: {'response-one': 1.})
    path = Path(editor.authored_soundtrack()['path'])
    path.write_bytes(b'different media')
    editor.open_audio_reactivity()
    assert editor.audio_reactivity_job is not None
    assert not editor.audio_reactivity_available
    assert editor.audio_reactivity_dialog.response_meter.value() == 0


def validity(project, identity):
    sequence = compile_composition(project)
    context = preview_context(sequence, (80, 60), False)
    return RenderValidity.capture(identity, project, sequence, None, context)


@pytest.mark.parametrize('field,value', [('in', 1.), ('out', 4.), ('offset', .5), ('end_mode', 'loop')])
def test_reactive_timing_edits_invalidate_pixels(soundtrack, field, value):
    project = reactive_project(soundtrack)
    after = copy.deepcopy(project)
    after['soundtrack'][field] = value
    identity = object()
    assert retained_frame_predicate(validity(project, identity), validity(after, identity)) is None


def test_mapping_edits_invalidate_but_gain_name_export_retain(soundtrack):
    project = reactive_project(soundtrack)
    identity = object()
    baseline = validity(project, identity)
    output = copy.deepcopy(project)
    output['soundtrack'].update(gain=.1, name='Different name', export_audio='footage')
    retain = retained_frame_predicate(baseline, validity(output, identity))
    assert retain is not None and retain(20)
    mapped = copy.deepcopy(project)
    mapped['audio_reactivity']['mappings'][0]['sensitivity'] = 2.
    assert retained_frame_predicate(baseline, validity(mapped, identity)) is None


@pytest.mark.parametrize('change', ['bypass', 'mapping_disabled', 'zero_amount', 'zero_sensitivity'])
def test_inactive_audio_mappings_restore_original_visual_signatures(soundtrack, change):
    project = reactive_project(soundtrack)
    if change == 'bypass': project['audio_reactivity']['enabled'] = False
    elif change == 'mapping_disabled': project['audio_reactivity']['mappings'][0]['enabled'] = False
    elif change == 'zero_amount': project['audio_reactivity']['mappings'][0]['amount'] = 0.
    else: project['audio_reactivity']['mappings'][0]['sensitivity'] = 0.
    base = copy.deepcopy(project)
    base.pop('audio_reactivity')
    base.pop('soundtrack')
    identity = object()
    original = validity(normalize_composition(base), identity)
    inactive = validity(normalize_composition(project), identity)
    assert inactive.context == original.context
    assert inactive.composition == original.composition
    assert inactive.sequence == original.sequence


def test_actual_audio_identity_change_invalidates_only_reactive_preview(soundtrack):
    project = reactive_project(soundtrack)
    sequence = compile_composition(project)
    before = preview_context(sequence, (80, 60), False)
    inactive = dict(sequence, audio_reactivity=dict(sequence['audio_reactivity'], enabled=False))
    unreactive = preview_context(inactive, (80, 60), False)
    path = Path(soundtrack['path'])
    stat = path.stat()
    with path.open('r+b') as stream:
        stream.seek(1000)
        stream.write(b'\x01\x02')
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert preview_context(sequence, (80, 60), False) != before
    assert preview_context(inactive, (80, 60), False) == unreactive


@pytest.mark.parametrize('job_type', ['foreground', 'prepare'])
def test_render_worker_threads_cancellation_through_audio(job_type, soundtrack, monkeypatch):
    sequence = compile_composition(reactive_project(soundtrack))
    seen = []
    def render(sequence, seconds, size, provider, bypass, *, cancel):
        seen.append(cancel)
        cancel.cancel()
        return Image.new('RGB', size)
    monkeypatch.setattr('synth_studio.render_sequence_frame', render)
    if job_type == 'foreground':
        job = RenderJob({}, 0., (2, 2), 1, 1, sequence=sequence)
    else:
        job = PreparePreviewJob({}, sequence, (2, 2), [0, 1], 25, 1, False)
    done, errors = [], []
    job.signals.done.connect(done.append)
    job.signals.failed.connect(errors.append)
    job.run()
    assert seen == [job.cancel] and job.cancel.event.is_set()
    assert done == [] and len(errors) == 1


def test_obsolete_foreground_is_cancelled_by_edit_and_close(editor):
    job = RenderJob({}, 0., (2, 2), editor.settings_generation, 1, sequence=editor.sequence)
    editor.render_job = job
    editor.render_running = True
    editor.invalidate()
    assert job.cancel.event.is_set()
    job = RenderJob({}, 0., (2, 2), editor.settings_generation, 2, sequence=editor.sequence)
    editor.render_job = job
    editor.close()
    assert job.cancel.event.is_set()
