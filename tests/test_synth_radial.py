import copy

import numpy as np

from synth import curated_presets, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_effects import describe_effects
from synth_radial_recipes import radial_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_starters import starter_composition
from synth_subject import active_subjects, scope_states, select_subject


def test_radial_study_is_editable_seek_deterministic_and_roundtrips(tmp_path):
    project = starter_composition('radial-bloom')
    assert active_subjects(describe_effects(scope_states(project))) == ('radial',)
    sequence = compile_composition(project)
    first = render_sequence_frame(sequence, 1.3, (144,256)).tobytes()
    later = render_sequence_frame(sequence, 4.1, (144,256)).tobytes()
    assert first != later
    assert first == render_sequence_frame(sequence, 1.3, (144,256)).tobytes()
    path = tmp_path/'radial.json'; save_composition(path, project)
    assert first == render_sequence_frame(compile_composition(load_composition(path)),1.3,(144,256)).tobytes()


def test_canvas_resize_crops_without_stretching_or_empty_borders():
    preset = resolve_sequence_frame(compile_composition(radial_composition()), .7)[-1]
    preset.update(width=180,height=320)
    settings = next(m['params'] for m in preset['modules'] if m['id']=='radial_bloom')
    settings.update(grain=0.,softness=0.)
    original = np.asarray(render_synth_frame(preset,time_seconds=.7))
    changed = copy.deepcopy(preset)
    changed.update(resize_canvas(preset,dict(width=300,height=320)))
    reframed = np.asarray(render_synth_frame(changed,time_seconds=.7))
    assert np.array_equal(original,reframed[:,60:240])
    assert reframed[:,:60].std()>8 and reframed[:,-60:].std()>8


def test_old_presets_never_enable_radial_and_source_switch_retains_treatments():
    for preset in curated_presets().values():
        assert not next(m for m in preset['modules'] if m['id']=='radial_bloom')['enabled']
    project=starter_composition('text-night')
    changed=select_subject(project,'radial')
    summary=describe_effects(scope_states(changed))
    assert active_subjects(summary)==('radial',)
    assert summary['bloom']['active']
    assert project['sections']==changed['sections']
    sequence=compile_composition(changed)
    with_bloom=render_sequence_frame(sequence,.5,(144,256))
    changed['effects']['bloom']={'mode':'off','params':{}}
    assert with_bloom.tobytes()!=render_sequence_frame(compile_composition(changed),.5,(144,256)).tobytes()
