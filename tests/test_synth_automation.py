import copy
import numpy as np
import pytest
from synth_automation import normalize_automations, envelope, absolute_event, apply_automations
from synth_composition import (blank_composition, normalize_composition, compile_composition,
                               composition_from_sequence, stretch_section, save_composition, load_composition)
from synth_sequence import normalize_sequence, resolve_sequence_frame, render_sequence_frame, save_sequence, load_sequence


def gesture(**values):
    return dict(id='gesture', path='bloom.strength', amount=.8, enabled=True, easing='linear',
                start_fraction=.4, attack_fraction=.02, hold_fraction=.02, recovery_fraction=.06, **values)


def project():
    p = blank_composition(); p['sections'][0]['duration'] = 10.
    p['source']['states']['blank']['enabled'] = ['slab', 'bloom']
    p['sections'][0]['automations'] = [gesture()]
    return p


def value(seq, t, path='bloom.strength'):
    preset = resolve_sequence_frame(seq, t)[-1]; module, key = path.split('.')
    return next(m for m in preset['modules'] if m['id'] == module)['params'][key]


def test_envelope_exact_endpoints_and_zero_stages():
    e = absolute_event(gesture(), 10)
    for t, expected in ((3.9, 0), (4, 0), (4.1, .5), (4.2, 1), (4.4, 1), (4.7, .5), (5, 0), (6, 0)):
        assert envelope(e, t) == pytest.approx(expected)
    e['easing'] = 'smooth'
    assert envelope(e, 4.05) == pytest.approx(.15625)
    assert envelope(dict(e, attack=0, hold=0), 4) == 1
    assert envelope(dict(e, attack=0, recovery=0), 4) == 1
    assert envelope(dict(e, attack=0, recovery=0), 4.2) == 0
    assert envelope(dict(e, enabled=False), 4.2) == 0


@pytest.mark.parametrize('key,value', [('start_fraction', True), ('amount', float('nan')), ('path', 'tape.rate'),
    ('easing', 'elastic'), ('hold_fraction', -.1), ('recovery_fraction', .9), ('enabled', 1), ('id', '')])
def test_validation(key, value):
    event = gesture(); event[key] = value
    with pytest.raises(ValueError): normalize_automations([event])


def test_conflicts_ids_and_bounds():
    e = gesture(); second = dict(e, id='second')
    with pytest.raises(ValueError, match='Overlapping'): normalize_automations([e, second])
    assert len(normalize_automations([e, dict(second, enabled=False)])) == 2
    assert len(normalize_automations([e, dict(second, start_fraction=.5)])) == 2
    assert len(normalize_automations([e, dict(second, path='smear.amount', amount=.5)])) == 2
    with pytest.raises(ValueError, match='identifiers'): normalize_automations([e, e])
    with pytest.raises(ValueError): normalize_automations([dict(e, attack_fraction=0, hold_fraction=0, recovery_fraction=0)])
    with pytest.raises(ValueError): normalize_automations([e] * 131073)


def test_cue_base_return_clamp_and_inactive_precedence():
    p = project(); seq = compile_composition(p)
    baseline = copy.deepcopy(seq); baseline.pop('automations')
    for t in (0, 3.9, 4, 5, 7):
        assert resolve_sequence_frame(seq, t)[-1] == resolve_sequence_frame(baseline, t)[-1]
    assert value(seq, 4.2) == pytest.approx(value(baseline, 4.2) + .8)
    seq['states'][next(iter(seq['states']))]['overrides']['bloom.strength'] = 1.8
    assert value(seq, 4.2) == 2
    preset = resolve_sequence_frame(baseline, 1)[-1]
    assert apply_automations(preset, seq['automations'], 1) is preset
    p['effects']['bloom'] = dict(mode='off', params={})
    assert value(compile_composition(p), 4.2) == value(compile_composition(p), 4)
    p['effects']['bloom'] = dict(mode='on', params={}, bypassed=True)
    assert value(compile_composition(p), 4.2) == value(compile_composition(p), 4)


def test_loops_resize_reorder_duplicate_and_fps():
    p = project(); p['sections'][0]['loops'] = 2
    second = copy.deepcopy(p['sections'][0]); second.update(id='section-2', duration=5, loops=1)
    p['sections'].append(second)
    p['timeline_loops'] = [dict(sections=['section-1', 'section-2'], loops=2)]
    seq = compile_composition(p)
    assert [e['start'] for e in seq['automations']] == [4, 14, 22, 29, 39, 47]
    resized = stretch_section(p, 'section-1', 20)
    events = compile_composition(resized)['automations']
    assert events[0]['start'] == 8 and events[0]['recovery'] == pytest.approx(1.2)
    assert resized['sections'][0]['effects_rate'] == .5
    p['sections'].reverse()
    assert compile_composition(p)['automations'][0]['start'] == 2
    p['fps'] = 60
    assert compile_composition(p)['automations'][0]['start'] == 2


def test_detailed_roundtrip_maps_to_owned_events_without_double_application(tmp_path):
    p = project(); seq = compile_composition(p)
    rebuilt = composition_from_sequence(seq)
    assert 'automations' not in rebuilt['source']
    seq2 = compile_composition(rebuilt)
    for t in (0, 4, 4.1, 4.2, 4.7, 5, 9):
        assert value(seq, t) == value(seq2, t)
        assert np.array_equal(render_sequence_frame(seq, t, (120, 80)), render_sequence_frame(seq2, t, (120, 80)))
    save_composition(tmp_path/'composition.json', p)
    assert compile_composition(load_composition(tmp_path/'composition.json')) == seq
    save_sequence(tmp_path/'sequence.json', seq)
    assert load_sequence(tmp_path/'sequence.json') == seq
    rebuilt['sections'][0]['loops'] = 2
    assert [e['start'] for e in compile_composition(rebuilt)['automations']] == [4, 14]


def test_animated_cue_base_is_preserved_and_outside_frames_identical():
    p = project()
    p['source']['states']['later'] = copy.deepcopy(p['source']['states']['blank'])
    p['source']['states']['later']['overrides']['bloom.strength'] = 1.
    p['source']['cues'].append(dict(time=3., state='later', transition='morph', duration=4.))
    seq = compile_composition(p); baseline = copy.deepcopy(seq); baseline.pop('automations')
    for t in (3.9, 5., 7.):
        assert np.array_equal(render_sequence_frame(seq, t, (120, 80)), render_sequence_frame(baseline, t, (120, 80)))
    assert value(seq, 4.1) == pytest.approx(value(baseline, 4.1) + .4)


def test_many_exported_events_and_repeated_conversion_keep_bounded_ids():
    p = project(); p['sections'][0]['duration'] = 1.; p['sections'][0]['loops'] = 32
    p['sections'][0]['automations'] = [dict(gesture(), id=str(i), start_fraction=i / 8, attack_fraction=.01, hold_fraction=0, recovery_fraction=.02) for i in range(8)]
    seq = compile_composition(p)
    assert len(seq['automations']) == 256
    for _ in range(12):
        seq = compile_composition(composition_from_sequence(seq))
        assert len(seq['automations']) == 256
        assert max(len(e['id']) for e in seq['automations']) < 64


def test_generated_v2_detailed_copy_keeps_render_version_and_pixels():
    from synth_composition import mixed_media_composition
    p = mixed_media_composition(); p['render_version'] = 2
    p['sections'][0]['automations'] = [gesture()]
    seq = compile_composition(p); rebuilt = compile_composition(composition_from_sequence(seq))
    assert rebuilt['render_version'] == 2
    for t in (0, 1.5, 3, 5):
        assert np.array_equal(render_sequence_frame(seq, t, (120, 120)), render_sequence_frame(rebuilt, t, (120, 120)))


def test_snapshots_and_study_retain_events_and_resolved_frames(tmp_path):
    from synth_exploration import capture_snapshot, restore_snapshot
    from synth_studies import save_study, study_composition
    p = project(); snap, sid = capture_snapshot(p, 'Automated base')
    snap['sections'][0]['automations'][0]['enabled'] = False
    restored = restore_snapshot(snap, sid)
    key = save_study(restored, 'Timed automation', tmp_path/'studies')
    loaded = study_composition(key, tmp_path/'studies')
    expected = compile_composition(p)
    actual = compile_composition(loaded)
    for t in (3.9, 4.1, 4.2, 5.):
        assert value(actual,t) == value(expected,t)
        assert np.array_equal(render_sequence_frame(actual,t,(120,80)),render_sequence_frame(expected,t,(120,80)))


@pytest.mark.parametrize('fps',[12,15,24,25,30,60])
def test_frame_grid_endpoints_have_exact_zero_delta(fps):
    for start in range(0,8*fps,max(1,fps//3)):
        for attack,hold,recovery in ((1,0,2),(2,1,7),(3,2,5),(1,0,1)):
            event=dict(gesture(),start_fraction=start/fps/10,attack_fraction=attack/fps/10,
                       hold_fraction=hold/fps/10,recovery_fraction=recovery/fps/10)
            for easing in ('linear','smooth'):
                absolute=absolute_event(dict(event,easing=easing),10)
                assert envelope(absolute,(start+attack+hold+recovery)/fps) == 0
                assert envelope(absolute,start/fps) == 0
                assert 0 <= envelope(absolute,(start+attack+hold)/fps) <= 1


def test_tiny_positive_envelope_keeps_explicit_zero_attack_step():
    event=absolute_event(dict(gesture(),start_fraction=0,attack_fraction=0,hold_fraction=0,recovery_fraction=1e-18),1)
    assert envelope(event,0)==1
    assert envelope(event,1e-18)==0
