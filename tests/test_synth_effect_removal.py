"""Visible Remove actions clear scoped treatments without resurrecting recipes."""
import copy

import pytest
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition, load_composition, save_composition
from synth_effect_discovery import effect_candidate
from synth_effects import effect_preset, state_values
from synth_sequence import render_sequence_frame
from test_synth_effects_editor_integration import make_window


def test_whole_clip_remove_clears_section_overrides_is_one_undo_and_round_trips(make_window, tmp_path):
    window = make_window()
    document = copy.deepcopy(window.composition)
    from synth_creative import CREATIVE_CONTROLS
    key = CREATIVE_CONTROLS['ghosts'][0].key
    document['effects']['ghosts'] = dict(effect_preset('ghosts'), bypassed=True,
                                       creative={'version': 1, 'values': {key: CREATIVE_CONTROLS['ghosts'][0].neutral}})
    document['sections'][1]['effects']['ghosts'] = dict(mode='on', params={'smear.ghosts': 8}, bypassed=False)
    document['effects']['tape'] = effect_preset('tape')
    window.set_composition(document)
    original = copy.deepcopy(window.composition)
    before_pixels = render_sequence_frame(window.sequence, 6.2, (64, 48)).tobytes()
    panel = window.composer.effects_panel
    panel.inspect_effect('ghosts')
    assert not panel.remove_button.isHidden() and panel.remove_button.isEnabled()
    panel.remove_button.click()
    assert window.composition['effects']['ghosts'] == {'mode': 'off', 'params': {}, 'bypassed': False}
    assert all('ghosts' not in section['effects'] for section in window.composition['sections'])
    assert 'ghosts' not in panel.applied_ids and 'ghosts' not in panel.browser_applied_ids()
    assert panel.pages.currentWidget() is panel.overview
    assert len(window.undo_compositions) == 1
    expected = copy.deepcopy(original)
    expected['effects']['ghosts'] = {'mode': 'off', 'params': {}, 'bypassed': False}
    for section in expected['sections']: section['effects'].pop('ghosts', None)
    assert window.composition == expected
    assert render_sequence_frame(window.sequence, 6.2, (64, 48)).tobytes() != before_pixels
    window.undo_composition()
    assert window.composition == original
    assert render_sequence_frame(window.sequence, 6.2, (64, 48)).tobytes() == before_pixels
    window.redo_composition()
    assert window.composition == expected
    path = tmp_path / 'removed.json'
    save_composition(path, window.composition)
    window.set_composition(load_composition(path))
    panel = window.composer.effects_panel
    assert 'ghosts' not in panel.applied_ids
    candidate = effect_candidate(window.composition, None, 'ghosts', 'add')
    panel.add_effect('ghosts', 0)
    assert window.composition == candidate
    assert 'ghosts' in panel.applied_ids
    assert window.composition['effects']['ghosts']['params'] == effect_preset('ghosts')['params']


def test_section_remove_shadows_inherited_bypass_and_can_be_added_again(make_window):
    window = make_window()
    document = copy.deepcopy(window.composition)
    document['effects']['tape'] = dict(effect_preset('tape'), bypassed=True)
    window.set_composition(document)
    original = copy.deepcopy(window.composition)
    window.composer.select_section(1)
    panel = window.composer.effects_panel
    panel.show_overview()
    panel.effect_choices['tape'].remove.click()
    assert window.composition['effects'] == original['effects']
    assert window.composition['sections'][0] == original['sections'][0]
    assert window.composition['sections'][2:] == original['sections'][2:]
    assert window.composition['sections'][1]['effects']['tape'] == {'mode': 'off', 'params': {}, 'bypassed': False}
    assert 'tape' not in panel.applied_ids and 'tape' not in panel.browser_applied_ids()
    sid = window.composition['sections'][1]['id']
    candidate = effect_candidate(window.composition, sid, 'tape', 'add')
    panel.add_effect('tape', 0)
    assert window.composition == candidate
    assert 'tape' in panel.applied_ids and not panel.is_bypassed('tape')
    window.undo_composition()
    assert 'tape' not in panel.applied_ids
    window.undo_composition()
    assert window.composition == original


def test_remove_embedded_study_effect_stays_absent_and_sources_have_no_remove(make_window):
    window = make_window()
    panel = window.composer.effects_panel
    original = copy.deepcopy(window.composition)
    assert 'ghosts' in panel.applied_ids
    assert 'ghosts' not in original['effects']
    panel.inspect_effect('ghosts'); panel.remove_button.click()
    assert 'ghosts' not in panel.applied_ids
    for state in window.sequence['states'].values():
        values, enabled = state_values(state)
        assert 'smear' not in enabled and values['slab.ghost_opacity'] == 0
    panel.inspect_effect('rays')
    assert panel.remove_button.isHidden()
    assert panel.effect_choices['rays'].remove.isHidden()
    edited = copy.deepcopy(window.composition)
    panel.remove_effect('rays')
    assert window.composition == edited
    window.undo_composition()
    assert window.composition == original


@pytest.mark.parametrize('width', [380, 490])
def test_remove_header_remains_visible_in_narrow_inspector(make_window, width):
    window = make_window()
    window.splitter.setSizes([1280 - width, width])
    panel = window.composer.effects_panel
    panel.inspect_effect('signal_background')
    QApplication.processEvents()
    assert panel.remove_button.isVisible()
    assert panel.remove_button.rect().right() + panel.remove_button.x() <= panel.editor.width()
    panel.parameter_scroll.verticalScrollBar().setValue(panel.parameter_scroll.verticalScrollBar().maximum())
    assert panel.remove_button.isVisible()


def test_long_effect_names_leave_room_for_removal_in_narrow_applied_list():
    from studio_theme import apply_theme
    from synth_effects import EFFECTS
    from synth_effects_ui import EffectChoice, SOURCE_EFFECTS
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    for effect in EFFECTS:
        if effect.id in SOURCE_EFFECTS: continue
        row = EffectChoice(effect)
        row.refresh(effect, {'active': True, 'intermittent': True}, False, False)
        row.resize(325, row.sizeHint().height()); row.show(); app.processEvents()
        try:
            assert row.width() == 325
            assert row.remove.isVisible()
            assert row.remove.geometry().right() < row.width()
            assert row.button.geometry().right() < row.badge.geometry().left()
            assert effect.label in row.button.accessibleName()
        finally:
            row.close()
