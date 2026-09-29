"""The refined portrait is an independent, editable video recipe."""
import copy

from synth_composition import compile_composition, load_composition, save_composition
from synth_portrait_recipes import exposure_composition, portrait_composition
from synth_sequence import render_sequence_frame
from synth_video import apply_treatment, video_composition
from test_synth_video import clip
from test_synth_video_ui import window


def test_refined_portrait_is_independent_and_portable(clip, tmp_path):
    old = portrait_composition(clip)
    frozen = copy.deepcopy(old)
    refined = exposure_composition(clip)
    assert old == frozen
    assert refined['name'] != old['name']
    assert refined['sections'] == old['sections']
    assert refined['footage']['end_mode'] == 'hold'
    assert refined['effects']['slice_echo']['params']['slice_echo.envelope'] > 0
    first = render_sequence_frame(compile_composition(old), .2, (96,96))
    second = render_sequence_frame(compile_composition(refined), .2, (96,96))
    assert first.tobytes() != second.tobytes()
    path = tmp_path/'refined.json'; save_composition(path,refined)
    loaded = load_composition(path)
    assert render_sequence_frame(compile_composition(loaded), .2, (96,96)).tobytes() == second.tobytes()
    refined['effects']['slice_echo']['params']['slice_echo.angle'] = 40.
    assert portrait_composition(clip) == frozen
    assert exposure_composition(clip)['effects']['slice_echo']['params']['slice_echo.angle'] != 40.


def test_refined_treatment_keeps_input_framing_and_old_preset(clip):
    p = video_composition(clip)
    p['footage'].update(x=17.,y=-12.,zoom=1.4)
    original = apply_treatment(p,5)
    refined = apply_treatment(p,6)
    for key in ('footage','sections','canvas'):
        assert refined[key] == p[key]
    assert original['effects']['slice_echo']['params']['slice_echo.angle'] == 0
    assert refined['effects']['slice_echo']['params']['slice_echo.angle'] != 0
    assert refined['effects']['slice_echo']['params']['slice_echo.highlight_protect'] > 0


def test_refined_exposure_controls_are_editable_with_undo(window):
    panel = window.composer
    panel.apply_video_treatment(6)
    effects = panel.effects_panel
    effects.inspect_effect('slice_echo')
    for key,value in [('angle',12.),('highlight_protect',.7),('luma_mask',.8),('envelope',.3)]:
        control = effects.controls[f'slice_echo.{key}'].input
        before = control.value()
        control.setValue(value)
        assert window.composition['effects']['slice_echo']['params'][f'slice_echo.{key}'] == value
        window.undo_composition()
        assert effects.controls[f'slice_echo.{key}'].input.value() == before
