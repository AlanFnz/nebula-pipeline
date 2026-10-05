"""Timeline footage addition is atomic and follows stable section identities."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog

from synth_add_section_ui import AddVideoSectionDialog
from synth_composition import load_composition, save_composition
from synth_effects import effect_preset
from synth_section_sources import video_source_at
from synth_video import video_composition
from test_synth_effects_editor_integration import make_window
from test_synth_section_sources import clip, other_clip, two_sources
from test_synth_automation import gesture
from test_synth_compact_workspace import inside


def choose_look(index=None, reject=False):
    def choose():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, AddVideoSectionDialog)
        if index is not None: dialog.look.setCurrentIndex(index)
        if reject: dialog.reject()
        else: dialog.choose.click()
    QTimer.singleShot(0, choose)


def test_add_via_timeline_copies_look_and_keeps_new_media_local(make_window, clip, other_clip, monkeypatch, tmp_path):
    p = two_sources(clip, other_clip)
    p['effects']['bloom'] = effect_preset('bloom', 0)
    template = p['sections'][1]
    template.update(duration=.5, loops=2, video_rate=2., effects_rate=1.5,
                    automations=[gesture()], effects={'tape': effect_preset('tape', 0)})
    template['footage'].update({'in': .25, 'out': .75, 'rotation': 12., 'x': 20.})
    window = make_window(composition=p); panel = window.composer
    window.document_path = tmp_path / 'composition.json'
    original = copy.deepcopy(window.composition)
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (clip['path'], ''))
    # Insert after first, but copy the second section's look.
    choose_look(2); window.add_footage_section.click()
    job = window.import_job
    assert window.composition == original and not window.undo_compositions
    assert job.add_section == dict(after_id=original['sections'][0]['id'], copy_from_id=original['sections'][1]['id'])
    panel.select_section(1)  # Changing selection during preparation cannot redirect it.
    window.video_imported(job, clip, False)
    assert len(window.composition['sections']) == 3
    added = window.composition['sections'][1]
    assert [window.composition['sections'][i] for i in (0, 2)] == original['sections']
    assert added['id'] not in {s['id'] for s in original['sections']}
    assert added['effects'] == template['effects'] and added['automations'] == template['automations']
    assert added['effects_rate'] == 1.5 and added['duration'] == .5 and added['loops'] == 1
    assert 'video_rate' not in added
    assert added['footage']['path'] == clip['path']
    assert (added['footage']['in'], added['footage']['out']) == (0., 1.)
    assert added['footage']['x'] == 20. and added['footage']['rotation'] == 12.
    assert video_source_at(window.sequence, .5) == (added['footage'], 0.)
    assert window.composition['effects'] == original['effects']
    assert window.composition['canvas'] == original['canvas'] and window.composition['fps'] == original['fps']
    assert panel.scope == 1 and panel.index == 1 and panel.look_tabs.currentWidget() is panel.video_panel
    assert window.section_timeline.selected_ids == {added['id']}
    assert window.document_path == tmp_path / 'composition.json' and len(window.undo_compositions) == 1
    after = copy.deepcopy(window.composition)
    save_composition(window.document_path, after)
    assert load_composition(window.document_path) == after
    window.undo_composition(); assert window.composition == original
    window.redo_composition(); assert window.composition == after


def test_shared_look_has_no_local_overrides_and_uses_footage_duration(make_window, clip, other_clip):
    p = video_composition(clip); p['effects']['tape'] = effect_preset('tape', 0)
    p['sections'][0].update(duration=.5, effects={'bloom': effect_preset('bloom', 0)}, automations=[gesture()])
    window = make_window(composition=p); original = copy.deepcopy(window.composition)
    identifier = window.composer.add_video_section(other_clip, p['sections'][0]['id'])
    new = window.composition['sections'][1]
    assert identifier == new['id'] and new['duration'] == 1. and new['loops'] == 1
    assert new['effects'] == {} and 'automations' not in new
    assert new['footage'] == other_clip
    assert window.composition['effects'] == original['effects']
    assert window.composition['sections'][0] == original['sections'][0]


@pytest.mark.parametrize('cancel_at', ['look', 'file', 'preparation', 'failure', 'stale', 'removed'])
def test_cancel_failure_or_stale_import_never_leaves_a_section(make_window, clip, other_clip, monkeypatch, cancel_at):
    p = two_sources(clip, other_clip); window = make_window(composition=p)
    original = copy.deepcopy(window.composition)
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    files = []
    def select_file(*args):
        files.append(args)
        return ('', '') if cancel_at == 'file' else (clip['path'], '')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', select_file)
    choose_look(reject=cancel_at == 'look'); window.add_footage_section.click()
    if cancel_at in ('look', 'file'):
        assert window.import_job is None
        assert bool(files) == (cancel_at == 'file')
    else:
        job = window.import_job
        if cancel_at == 'preparation': window.cancel_video_import()
        elif cancel_at == 'failure': window.video_import_failed(job, 'Bad footage')
        elif cancel_at == 'stale': window.document_identity = object()
        elif cancel_at == 'removed':
            window.composer.remove_section(); original = copy.deepcopy(window.composition)
        if cancel_at != 'failure': window.video_imported(job, clip, False)
    assert window.composition == original
    assert len(window.composition['sections']) == len(original['sections'])


def test_section_limit_and_generated_timeline_do_not_offer_footage_add(make_window, clip):
    generated = make_window(); assert not generated.add_footage_section.isVisible()
    p = video_composition(clip)
    p['sections'] = [dict(copy.deepcopy(p['sections'][0]), id=f'section-{i}') for i in range(64)]
    window = make_window(composition=p); before = copy.deepcopy(window.composition)
    window.add_footage_section.click()
    assert '64 sections' in window.status.text() and window.import_job is None
    assert window.composition == before


def test_timeline_add_controls_wrap_in_a_narrow_monitor(make_window, clip):
    window = make_window(composition=video_composition(clip))
    window.splitter.setSizes([380, 880]); QApplication.processEvents()
    for control in (window.section_hint, window.add_footage_section, window.section_resize_mode):
        assert control.isVisible() and inside(control, window.section_tools)
        assert inside(control, window.preview_controls_scroll.viewport())
