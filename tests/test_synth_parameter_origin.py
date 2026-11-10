"""Origin inspection must explain the current renderer without authoring edits."""
import copy
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition, load_composition
from synth_parameter_origin import FrameOrigins, performance_summary
from synth_performance import defaults, source_time
from synth_sequence import resolve_sequence_frame
from test_synth_automation import project
from test_synth_effects_editor_integration import make_window


def inspect(document, seconds, path='bloom.strength', **kwargs):
    sequence = compile_composition(document)
    clock = source_time(sequence.get('visual_performance'), seconds, sequence['duration'], sequence['fps'])
    frame = resolve_sequence_frame(sequence, clock, normalized=True)
    return FrameOrigins(document, sequence, seconds, frame).describe(path, **kwargs)


def test_clip_and_project_precedence_and_gesture_return():
    doc = project()
    doc['effects']['bloom'] = dict(mode='on', params={'bloom.strength': .2})
    doc['sections'][0]['effects']['bloom'] = dict(mode='recipe', params={'bloom.strength': .4})
    before = copy.deepcopy(doc)
    text, hint = inspect(doc, 4.2, automation_count=1)
    assert '1.20' in text and 'Clip 1 base → Clip automation' in text
    text, hint = inspect(doc, 5., automation_count=1)
    assert '0.40' in text and 'Clip automation idle' in text
    assert 'keeps clip automation and Perform' in hint
    doc['sections'][0]['effects'].clear()
    assert 'Project base → Clip automation' in inspect(doc, 4.2)[0]
    doc['effects'].clear()
    assert 'Study → Clip automation' in inspect(doc, 4.2)[0]
    assert before['sections'][0]['automations'] == doc['sections'][0]['automations']


def test_disabled_automation_bypass_and_other_selected_clip_are_explicit():
    doc = project()
    doc['sections'][0]['automations'][0]['enabled'] = False
    assert 'Clip automation disabled' in inspect(doc, 4.2, automation_count=1)[0]
    doc['sections'][0]['automations'][0]['enabled'] = True
    doc['effects']['bloom'] = dict(mode='off', params={})
    text, _ = inspect(doc, 4.2, automation_count=1)
    assert 'effect off' in text
    text, _ = inspect(doc, 4.2, selected_id='another-clip')
    assert 'outside this clip' in text and 'Clip 1' in text


def test_perform_surface_and_retiming_are_described_without_changing_study():
    doc = load_composition(Path(__file__).parents[1] / 'presets/pleated-signal-acid-v4.json')
    doc['visual_performance'] = defaults()
    doc['visual_performance']['values']['pace'] = 200
    doc['visual_performance']['tracks']['opening'] = [[0, 10], [1, 60]]
    before = copy.deepcopy(doc)
    text, hint = inspect(doc, 2., path='pleated_field.aperture', animated=True)
    assert 'Perform Opening (recorded)' in text and 'visual source 4.00s' in hint
    assert doc == before
    title, detail = performance_summary(doc['visual_performance'])
    assert title == 'Perform · 1 recorded · 1 fixed'
    assert 'Recorded: Opening' in detail and 'Fixed: Pace' in detail
    doc['visual_performance']['enabled'] = False
    assert 'bypassed' in performance_summary(doc['visual_performance'])[0]
    assert 'Perform Opening' not in inspect(doc, 2., path='pleated_field.aperture', animated=True)[0]


def test_repeated_clips_use_the_current_occurrence_not_the_first():
    doc = project(); doc['sections'][0]['loops'] = 2
    assert 'Clip automation idle' in inspect(doc, 12, automation_count=1)[0]
    assert 'Clip automation idle' not in inspect(doc, 14.2, automation_count=1)[0]
    assert 'Clip automation' in inspect(doc, 14.2, automation_count=1)[0]


def test_audio_response_is_never_misrepresented_as_a_final_sample():
    doc = project(); seq = compile_composition(doc)
    seq['audio_reactivity'] = dict(enabled=True, mappings=[
        dict(path='bloom.strength', enabled=True, amount=.5, sensitivity=1)])
    frame = resolve_sequence_frame(seq, 4.2, normalized=True)
    text, detail = FrameOrigins(doc, seq, 4.2, frame).describe('bloom.strength')
    assert 'before audio response' in text and 'not sampled here' in detail


def test_inspector_navigation_and_base_edits_preserve_events_and_undo(make_window):
    window = make_window(composition=project())
    window.auto_prepare.setChecked(False)
    panel = window.composer.effects_panel
    panel.inspect_effect('bloom')
    panel.reveal_control('bloom.strength'); QApplication.processEvents()
    before = copy.deepcopy(window.composition)
    sequence = copy.deepcopy(window.sequence)
    undo_count = len(window.undo_compositions)
    window.refresh_effect_explanations(4.2)
    row = panel.controls['bloom.strength']
    assert 'Clip automation' in row.frame_value.text()
    assert row.input.value() != 1.2  # Monitor result is never copied into the base.
    window.composer.value_sources_button.click()
    QApplication.processEvents()
    assert window.composition == before and window.sequence == sequence
    assert len(window.undo_compositions) == undo_count
    row.input.setValue(.3)
    assert window.composition['sections'][0]['automations'] == before['sections'][0]['automations']
    window.undo_composition()
    assert window.composition == before


def test_fixing_a_study_range_keeps_clip_automation_and_restores_with_undo(make_window):
    doc = project()
    doc['source']['states']['bright'] = copy.deepcopy(doc['source']['states']['blank'])
    doc['source']['states']['bright']['overrides']['bloom.strength'] = .7
    doc['source']['cues'].append(dict(time=2., state='bright', transition='morph', duration=1.))
    window = make_window(composition=doc)
    window.auto_prepare.setChecked(False)
    panel = window.composer.effects_panel; panel.inspect_effect('bloom')
    panel.reveal_control('bloom.strength'); QApplication.processEvents()
    before = copy.deepcopy(window.composition)
    row = panel.controls['bloom.strength']
    assert row.study_animated and row.use_fixed.isVisible()
    row.use_fixed.click()
    assert not row.study_animated
    assert window.composition['sections'][0]['automations'] == before['sections'][0]['automations']
    window.refresh_effect_explanations(4.2)
    assert 'Clip automation' in row.frame_value.text()
    row.reset_button.click()
    assert row.study_animated
    window.undo_composition(); assert not row.study_animated
    window.undo_composition(); assert window.composition == before


def test_perform_labels_and_navigation_do_not_record_or_fix_knobs(make_window):
    doc = project(); doc['visual_performance'] = defaults()
    doc['visual_performance']['tracks']['scale'] = [[0, 100], [1, 150]]
    window = make_window(composition=doc)
    window.auto_prepare.setChecked(False)
    before = copy.deepcopy(window.composition)
    window.refresh_effect_explanations(2.)
    assert '1 recorded' in window.composer.performance_notice.text()
    window.composer.performance_notice.linkActivated.emit('perform')
    QApplication.processEvents()
    assert window.composer.look_tabs.currentWidget() is window.performance_panel
    assert window.performance_panel.origins['scale'].text() == 'Recorded movement'
    assert window.performance_panel.origins['rotation'].text() == 'Fixed adjustment'
    window.performance_panel.set_playhead(5., 10.)
    assert window.composition == before


@pytest.mark.parametrize('comparison', [False, True])
def test_other_preview_modes_do_not_claim_working_values_are_on_screen(make_window, monkeypatch, comparison):
    window = make_window(composition=project())
    panel = window.composer.effects_panel; panel.inspect_effect('bloom')
    before = copy.deepcopy(window.composition)
    if comparison:
        monkeypatch.setattr(window, 'comparison', {'side': 'a'})
    else:
        monkeypatch.setattr(window, 'preview_bypass', lambda: True)
    window.refresh_effect_explanations(4.2)
    text = panel.controls['bloom.strength'].frame_value.text()
    assert ('A/B preview' if comparison else 'source preview') in text
    assert '4.20s' not in text
    assert window.composition == before
    monkeypatch.setattr(window, 'comparison', None)


@pytest.mark.parametrize('filename', ['pleated-signal-acid-v4.json', 'chromatic-lattice-v1.json'])
def test_study_inspection_keeps_the_entire_compiled_document_identical(filename):
    path = Path(__file__).parents[1] / 'presets' / filename
    doc = load_composition(path)
    before = copy.deepcopy(doc); sequence = compile_composition(doc); compiled = copy.deepcopy(sequence)
    for seconds in (0, sequence['duration'] / 2, sequence['duration'] - .04):
        frame = resolve_sequence_frame(sequence, seconds, normalized=True)
        sources = FrameOrigins(doc, sequence, seconds, frame)
        for name in ('text.size', 'pleated_field.aperture', 'chromatic_lattice.size'):
            sources.describe(name, animated=True)
    assert doc == before and sequence == compiled
    assert compile_composition(doc) == compiled
