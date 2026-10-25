"""Screen and tape finishes must receive the entire optical composition."""
import copy

import numpy as np
import pytest
from PIL import Image

from synth import _seed, default_synth_preset, render_synth_frame
from synth_broadcast import render_broadcast, render_broadcast_exposure
from synth_composition import compile_composition, load_composition, save_composition
from synth_effects import effect_preset
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_starters import starter_composition


@pytest.mark.parametrize('early', [0, 1])
@pytest.mark.parametrize('strength', [0., 35., 100.])
def test_project_broadcast_treats_complete_optical_image(early, strength, tmp_path):
    project = starter_composition('text-dark-print')
    project['effects']['broadcast'] = effect_preset('broadcast')
    project['effects']['broadcast']['params'].update({
        'broadcast.field': 0., 'broadcast.static': 0., 'broadcast.vignette': 0.,
        'broadcast.curve': .2, 'broadcast.reverse': .6,
        'broadcast.reverse_stage': early, 'broadcast.effect_intensity': strength})
    save_composition(tmp_path/'project.json', project)
    sequence = compile_composition(load_composition(tmp_path/'project.json'))
    t = .9; size = (160, 120)
    preset = resolve_sequence_frame(sequence, t)[-1]
    broadcast = next(m for m in preset['modules'] if m['id'] == 'broadcast')
    settings = broadcast['params']
    dry_preset = copy.deepcopy(preset)
    next(m for m in dry_preset['modules'] if m['id'] == 'broadcast')['enabled'] = False
    dry = np.asarray(render_synth_frame(dry_preset, time_seconds=t, size=size), dtype=np.float32)/255
    signal = render_broadcast_exposure(dry, settings, t, preset['speed']) if early else dry
    wet = render_broadcast(signal, settings, t, preset['speed'], _seed(preset['seed'], 'broadcast'))
    expected = np.clip((dry*(1-strength/100)+wet*strength/100)*255, 0, 255)
    actual = np.asarray(render_sequence_frame(sequence, t, size), dtype=float)
    # The reference render is quantized once before the explicit screen pass.
    assert np.max(abs(actual-expected)) < 2
    if strength == 100:
        assert actual[:8, :8].max() == 0
        assert actual[40:80, 40:120].max() > 30


@pytest.mark.parametrize('source_kind', ['text', 'video'])
def test_screen_noise_is_added_after_optical_layers(source_kind, monkeypatch):
    import synth
    preset = default_synth_preset()
    for module in preset['modules']:
        module['enabled'] = module['id'] in ('optical_print', 'broadcast', 'text')
        if module['id'] == 'broadcast':
            module['params'].update(field=0., static=1., duration=3., period=1.,
                                    curve=0., vignette=0., reverse=0., mix=1.)
    source = None
    if source_kind == 'video':
        next(m for m in preset['modules'] if m['id'] == 'text')['enabled'] = False
        source = Image.new('RGB', (96, 72), (120, 50, 20))
    captured = []
    original = synth.render_optical_print
    def record(*args, **kwargs):
        result = original(*args, **kwargs)
        captured.append(result.copy())
        return result
    monkeypatch.setattr(synth, 'render_optical_print', record)
    # Static at 100% replaces every pixel, independently of lettering/fragments.
    image = render_synth_frame(preset, time_seconds=.25, size=(96, 72), source_image=source)
    settings = next(m['params'] for m in preset['modules'] if m['id'] == 'broadcast')
    expected = render_broadcast(np.zeros((72, 96, 3), np.float32), settings, .25,
                                preset['speed'], _seed(preset['seed'], 'broadcast'))
    assert len(captured) == 1
    assert np.array_equal(np.asarray(image), np.clip(expected*255, 0, 255).astype(np.uint8))


def test_late_tape_instance_and_clip_bypass_remain_independent():
    project = starter_composition('text-dark-print')
    project['effects']['broadcast'] = effect_preset('broadcast')
    project['effects']['tape@2'] = effect_preset('tape@2', 3)
    project['effects']['tape@2']['params']['tape@2.pull'] = .3
    project['sections'][0]['effects']['broadcast'] = dict(mode='off', params={})
    bypass = render_sequence_frame(compile_composition(project), 1., (160, 120))
    del project['effects']['broadcast']
    assert render_sequence_frame(compile_composition(project), 1., (160, 120)).tobytes() == bypass.tobytes()
    del project['effects']['tape@2']
    assert render_sequence_frame(compile_composition(project), 1., (160, 120)).tobytes() != bypass.tobytes()
