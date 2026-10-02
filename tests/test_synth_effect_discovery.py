import copy
import pytest
from synth_starting_points import new_piece
from synth_effect_discovery import effect_candidate, preset_entry
from synth_composition import compile_composition
from synth_sequence import render_sequence_frame
from synth_exploration import capture_snapshot


def test_candidates_preserve_complete_document_and_exact_committed_pixels():
    original, _ = capture_snapshot(new_piece('shape'), 'Original')
    frozen = copy.deepcopy(original)
    candidate = effect_candidate(original, None, 'tape', 'add', 1)
    committed = copy.deepcopy(original)
    committed['effects']['tape'] = preset_entry('tape', 1)
    assert original == frozen and candidate['snapshots'] == original['snapshots']
    for t in (0., .2, 1.):
        assert render_sequence_frame(compile_composition(candidate), t, (64, 64)).tobytes() == render_sequence_frame(compile_composition(committed), t, (64, 64)).tobytes()


def test_replace_neutralizes_inherited_creative_and_preserves_bypass_precedence():
    doc = new_piece('shape')
    doc['effects']['tape'] = {'mode': 'on', 'params': {}, 'bypassed': True,
                              'creative': {'version': 1, 'values': {'damage': 1.8}}}
    sid = doc['sections'][0]['id']
    candidate = effect_candidate(doc, sid, 'tape', 'replace', 0)
    entry = candidate['sections'][0]['effects']['tape']
    assert entry['creative']['values']['damage'] == 1
    assert 'bypassed' not in entry  # inherited bypass remains inherited
    doc['sections'][0]['effects']['tape'] = {'mode': 'off', 'params': {}, 'bypassed': False}
    assert effect_candidate(doc, sid, 'tape', 'replace')['sections'][0]['effects']['tape']['bypassed'] is False
    without = effect_candidate(doc, None, 'tape', 'without')
    assert without['sections'] == doc['sections']  # local Resume wins globally
    assert without['effects']['tape']['bypassed']


@pytest.mark.parametrize('effect,operation,preset,sid', [('forms','add',0,None), ('tape','no',0,None), ('tape','add',90,None), ('tape','add',0,'missing'), ('subject_cutout','add',0,None)])
def test_invalid_candidates_are_rejected(effect, operation, preset, sid):
    with pytest.raises(ValueError): effect_candidate(new_piece('shape'), sid, effect, operation, preset)


def test_sampled_window_uses_absolute_frames_and_discontinuous_scope():
    from synth_preview import PreviewScope
    from synth_effect_preview import sampled_window
    scope = PreviewScope(((30, 45), (100, 180)), 2)
    frames = sampled_window(scope, 40, 30)
    assert len(frames) <= 24 and len(set(frames)) == len(frames)
    assert all(scope.contains(frame) for frame in frames)
    assert max(frames) >= 100
    assert sampled_window(scope, 0, 30) == ()


def test_preview_session_cancel_and_exact_apply_in_real_studio(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QThreadPool
    from synth_studio import SynthStudio
    from synth_effect_preview import EffectPreviewSession
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    studio = SynthStudio(composition=new_piece('shape'))
    studio.auto_prepare.setChecked(False)
    original = copy.deepcopy(studio.composition)
    clean = studio.clean_document
    try:
        session = EffectPreviewSession(studio)
        session.select('tape', 0)
        assert not studio.audition_pending() and not studio.has_unsaved_changes()
        assert studio.preview_size()[0] <= 360
        session.close()
        assert studio.composition == original and studio.clean_document == clean
        session = EffectPreviewSession(studio)
        session.select('tape', 1); session.accept_packet()
        candidate = copy.deepcopy(session.candidate)
        session.apply()
        assert studio.composition == candidate
        studio.undo_composition()
        assert studio.composition == original
    finally:
        studio.clean_document = studio.document_state()
        studio.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()
