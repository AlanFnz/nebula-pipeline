"""Ordering is authored separately from module identity, timing and scope."""
import copy

import numpy as np
import pytest
from PIL import Image

import synth
from synth_composition import (compile_composition, composition_from_sequence,
                               load_composition, normalize_composition, save_composition)
from synth_effect_order import normalize_order, order_for_states, resolved_order
from synth_effects import effect_preset
from synth_exploration import capture_snapshot, restore_snapshot
from synth_intensity import PATHS, intensity_path
from synth_sequence import (load_sequence, render_sequence_frame, resolve_sequence_frame,
                            save_sequence)
from synth_starters import STARTERS, starter_composition


def preset(*enabled, order=None):
    result = synth.default_synth_preset()
    for entry in result['modules']: entry['enabled'] = entry['id'] in enabled
    if order is not None: result['effect_order'] = order
    return result


@pytest.mark.parametrize('bad', ['broadcast', {}, ['text'], ['low_res'], ['cloud'],
                                  ['subject_cutout'], ['unknown'], ['tape', 'tape'], [False]])
def test_invalid_or_source_orders_are_rejected(bad):
    with pytest.raises(ValueError): normalize_order(bad)


@pytest.mark.parametrize('video', [False, True])
def test_noncommuting_image_passes_really_follow_list_order(monkeypatch, video):
    monkeypatch.setitem(synth.RENDERERS, 'bloom', lambda arr, *args: arr * .5)
    monkeypatch.setitem(synth.RENDERERS, 'raster', lambda arr, *args: arr + .25)
    p = preset('bloom', 'raster', order=['bloom', 'raster'])
    source = Image.new('RGB', (96, 72), (100, 70, 30)) if video else None
    first = np.asarray(synth.render_synth_frame(p, size=(96, 72), source_image=source))
    p['effect_order'].reverse()
    second = np.asarray(synth.render_synth_frame(p, size=(96, 72), source_image=source))
    assert np.all((first.astype(int) - second.astype(int)) >= 31)
    # Render identity is independent of list position, including random seeds.
    indices = []
    monkeypatch.setitem(synth.RENDERERS, 'raster', lambda arr, params, t, p, index: indices.append(index) or arr)
    synth.render_synth_frame(p, size=(96, 72), source_image=source)
    assert indices == [next(i for i, m in enumerate(p['modules']) if m['id'] == 'raster')]


@pytest.mark.parametrize('early', [0, 1])
@pytest.mark.parametrize('amount', [0., 35., 100.])
def test_optical_print_and_broadcast_are_independent_ordered_passes(monkeypatch, early, amount):
    monkeypatch.setattr(synth, 'render_optical_print', lambda arr, *args: arr + .3)
    monkeypatch.setitem(synth.RENDERERS, 'broadcast', lambda arr, *args: arr * .5)
    monkeypatch.setattr(synth, 'render_broadcast_exposure', lambda arr, *args: arr * .8)
    p = preset('optical_print', 'broadcast', order=['broadcast', 'optical_print'])
    b = next(m['params'] for m in p['modules'] if m['id'] == 'broadcast')
    b.update(reverse_stage=early, reverse=1., mix=1., effect_intensity=amount)
    first = np.asarray(synth.render_synth_frame(p, size=(96, 72)))
    p['effect_order'].reverse()
    second = np.asarray(synth.render_synth_frame(p, size=(96, 72)))
    expected_difference = .3 * .5 * amount / 100 * 255
    assert np.max(abs(first.astype(float) - second.astype(float) - expected_difference)) <= 1


def test_original_source_survives_reordered_treatments(monkeypatch):
    captured = []
    monkeypatch.setattr(synth, 'render_optical_print', lambda arr, *args: arr + .3)
    def scan(arr, params, time, speed, seed, reference, original):
        captured.append((arr.copy(), original.copy())); return arr
    monkeypatch.setattr(synth, 'render_scan_modulation', scan)
    p = preset('optical_print', 'scan_modulation', order=['optical_print', 'scan_modulation'])
    next(m['params'] for m in p['modules'] if m['id'] == 'scan_modulation')['input'] = 1
    synth.render_synth_frame(p, size=(96, 72))
    assert len(captured) == 1
    assert np.allclose(captured[0][0] - captured[0][1], .3)


def test_order_roundtrips_sequence_composition_and_snapshots_without_rewriting_settings(tmp_path):
    project = starter_composition('text-dark-print')
    project['effects']['broadcast'] = effect_preset('broadcast')
    project['effects']['tape@2'] = effect_preset('tape@2', 3)
    project['sections'][0]['automations'] = [dict(id='pull', path='tape@2.pull', amount=.2,
        enabled=True, easing='smooth', start_fraction=.2, attack_fraction=.1,
        hold_fraction=.1, recovery_fraction=.1)]
    previous = copy.deepcopy(project)
    project['effect_order'] = ['optical_print', 'tape@2', 'broadcast']
    project = normalize_composition(project)
    path = tmp_path/'composition.json'; save_composition(path, project)
    assert load_composition(path) == project
    seq = compile_composition(project)
    save_sequence(tmp_path/'sequence.json', seq)
    assert load_sequence(tmp_path/'sequence.json') == seq
    assert compile_composition(composition_from_sequence(seq))['effect_order'] == project['effect_order']
    saved, identifier = capture_snapshot(project, 'Layer order')
    saved['effect_order'].reverse()
    assert restore_snapshot(saved, identifier)['effect_order'] == project['effect_order']
    assert project['effects'] == previous['effects']
    assert project['sections'][0]['automations'] == previous['sections'][0]['automations']
    assert project['source'] == previous['source']
    p = resolve_sequence_frame(seq, 1.)[-1]
    old = resolve_sequence_frame(compile_composition(previous), 1.)[-1]
    assert p['modules'] == old['modules'] and p['seed'] == old['seed']
    assert render_sequence_frame(seq, 1., (128, 96)).tobytes() == render_sequence_frame(load_sequence(tmp_path/'sequence.json'), 1., (128, 96)).tobytes()


def test_project_order_applies_to_clip_overrides_without_changing_ownership():
    project = starter_composition('text-dark-print')
    second = copy.deepcopy(project['sections'][0]); second['id'] = 'second'
    project['sections'].append(second)
    project['effects']['broadcast'] = effect_preset('broadcast')
    second['effects']['broadcast'] = dict(mode='off', params={})
    project['effect_order'] = ['optical_print', 'broadcast']
    seq = compile_composition(project)
    first = resolve_sequence_frame(seq, 1.)[-1]
    second = resolve_sequence_frame(seq, 8.5)[-1]
    assert first['effect_order'] == second['effect_order']
    assert next(m for m in first['modules'] if m['id'] == 'broadcast')['enabled']
    assert not next(m for m in second['modules'] if m['id'] == 'broadcast')['enabled']


@pytest.mark.parametrize('identifier', [key for key, _, _ in STARTERS])
def test_all_studies_can_opt_into_ordering_without_mutating_recipe(identifier):
    project = starter_composition(identifier)
    before = copy.deepcopy(project)
    seq = compile_composition(project)
    project['effect_order'] = list(reversed(order_for_states(seq['states'].values())))
    frame = render_sequence_frame(compile_composition(project), seq['duration'] * .65, (96, 72))
    assert frame.size == (96, 72)
    assert project['source'] == before['source']
    project.pop('effect_order')
    assert project == before


def test_builtin_optical_order_precedes_finishing_by_default():
    seq = compile_composition(starter_composition('text-dark-print'))
    p = resolve_sequence_frame(seq, 0)[-1]
    assert resolved_order(p).index('optical_print') < resolved_order(p).index('broadcast')


@pytest.mark.parametrize('effect', [key for key in PATHS if key != 'subject_cutout'])
def test_custom_order_zero_intensity_matches_removal(effect):
    from synth_effect_order import movable
    project = starter_composition('refined')
    project['effects'][effect] = effect_preset(effect)
    project['effect_order'] = [effect] if movable(effect) else ['bloom']
    project['effects'][effect]['params'][intensity_path(effect)] = 0.
    zero = render_sequence_frame(compile_composition(project), .4, (96, 72))
    project['effects'][effect]['mode'] = 'off'
    removed = render_sequence_frame(compile_composition(project), .4, (96, 72))
    assert zero.tobytes() == removed.tobytes()
