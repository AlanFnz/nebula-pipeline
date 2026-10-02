import copy
import pytest
from synth_starting_points import new_piece
from synth_composition import compile_composition
from synth_effect_discovery import effect_candidate
from synth_effect_diagnostics import explain_effect
from synth_sequence import resolve_sequence_frame, render_sequence_frame


def facts(effect, params=None):
    doc = effect_candidate(new_piece('shape'), None, effect)
    doc['effects'][effect]['params'].update(params or {})
    return explain_effect(doc, compile_composition(doc), effect, 0)


def test_zero_rules_do_not_guess_visibility_or_compound_inactivity():
    assert any(f.code=='zero' for f in facts('bloom', {'bloom.strength':0}))
    assert any(f.code=='brightness-guidance' and f.evidence=='guidance' for f in facts('bloom'))
    assert not any(f.code=='zero' for f in facts('scan_drag', {'scan_drag.amount':0}))
    assert not any(f.code=='zero' for f in facts('ghosts', {'smear.amount':0}))
    assert any(f.code=='zero' for f in facts('ghosts', {'smear.amount':0,'slab.ghost_opacity':0}))
    assert not any(f.code=='zero' for f in facts('frame_jitter', {'frame_jitter.rate':0}))


def test_bypass_scope_and_missing_dependency_are_distinct():
    doc = effect_candidate(new_piece('text'), None, 'cloud')
    assert any(f.code=='dependency' for f in explain_effect(doc, compile_composition(doc), 'cloud', 0))
    doc['effects']['cloud']['bypassed']=True
    assert any(f.scope=='In this scope' and f.code=='bypassed' for f in explain_effect(doc, compile_composition(doc), 'cloud', 0))


@pytest.mark.parametrize('transition', ['cut','morph','flash','sweep'])
def test_resolution_matches_renderer_at_transition_boundaries(monkeypatch, transition):
    import synth_sequence
    from synth_composition import composition_from_sequence
    from synth_sequence import reference_sequence
    sequence = reference_sequence()
    sequence['cues'][1].update(transition=transition, duration=.5)
    captured=[]
    actual=synth_sequence.render_synth_frame
    def capture(base, *args, **kwargs):
        captured.append(copy.deepcopy(base)); return actual(base,*args,**kwargs)
    monkeypatch.setattr(synth_sequence,'render_synth_frame',capture)
    onset=sequence['cues'][1]['time']
    for seconds in (onset-1/sequence['fps'], onset, onset+.25, onset+.5):
        base=resolve_sequence_frame(sequence,seconds)[-1]
        render_sequence_frame(sequence,seconds,(32,32))
        assert captured[-1]==base
