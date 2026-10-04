"""Independent integration checks for gesture edits and prepared preview frames."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from synth_composition import blank_composition
from synth_effects import effect_preset
from test_synth_effects_editor_integration import make_window


def test_automation_edits_discard_stale_frames_and_cancel_keeps_them(make_window):
    document = blank_composition()
    document['sections'][0]['duration'] = 10.
    document['effects']['tape'] = effect_preset('tape', 3)
    window = make_window(composition=document)
    window.auto_prepare.setChecked(False)
    panel = window.composer
    frame = round(4.2 * document['fps'])
    packet = ((1, 1), b'old')

    def prepare():
        window.preview_frames.put(frame, packet)
        assert window.preview_frames.get(frame) == packet
        return window.settings_generation

    before = copy.deepcopy(window.composition)
    generation = prepare()
    draft = panel.open_automation('tape.pull')
    draft.times['start'].setValue(4.)
    draft.amount.setValue(.35)
    draft.reject()
    assert window.composition == before
    assert window.preview_frames.get(frame) == packet
    assert window.settings_generation == generation

    event = dict(id='review-pull', path='tape.pull', amount=.35,
                 enabled=True, easing='smooth', start_fraction=.4,
                 attack_fraction=.015, hold_fraction=0., recovery_fraction=.085)
    panel.save_automation('section-1', event)
    assert window.preview_frames.get(frame) is None
    assert window.settings_generation > generation

    for operation in ('move', 'toggle', 'toggle', 'remove'):
        generation = prepare()
        panel.change_automation('section-1', 'review-pull', operation, .5)
        assert window.preview_frames.get(frame) is None, operation
        assert window.settings_generation > generation, operation

    generation = prepare()
    window.undo_composition()
    assert window.preview_frames.get(frame) is None
    assert window.settings_generation > generation
    assert window.composition['sections'][0]['automations'][0]['id'] == 'review-pull'
