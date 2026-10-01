"""Focused inspector navigation and persisted bypass behavior."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from synth_composition import blank_composition, compile_composition, load_composition, reference_composition, save_composition
from synth_composer_ui import CompositionPanel
from synth_effects import effect_preset, merge_effects, normalize_effects, state_values
from synth_sequence import render_sequence_frame
from synth_subject import restore_subject


def pixels(document, time=.4):
    return render_sequence_frame(compile_composition(document), time, (96, 72)).tobytes()


@pytest.fixture
def panel():
    app = QApplication.instance() or QApplication([])
    from studio_theme import apply_theme
    apply_theme(app)
    widget = CompositionPanel(reference_composition(True))
    widget.resize(380, 750); widget.show(); app.processEvents()
    yield widget
    widget.close(); app.processEvents()


@pytest.mark.parametrize('invalid', [0, 1, None, 'false', [], {}])
def test_bypass_requires_boolean(invalid):
    with pytest.raises(ValueError, match='bypassed must be a boolean'):
        normalize_effects({'tape': {'bypassed': invalid}})


def test_bypass_normalization_is_optional_and_explicit_false_overrides_parent():
    assert normalize_effects({'tape': {}}) == {'tape': {'mode': 'recipe', 'params': {}}}
    parent = {'tape': dict(mode='recipe', params={'tape.mix': .4}, bypassed=True)}
    local = {'tape': dict(mode='recipe', params={}, bypassed=False)}
    result = merge_effects(parent, local)
    assert result['tape'] == dict(mode='recipe', params={'tape.mix': .4}, bypassed=False)
    assert parent['tape']['bypassed'] is True
    assert merge_effects(parent, {'tape': dict(mode='recipe', params={})})['tape']['bypassed'] is True


def test_intermittent_bypass_resumes_exact_saved_pixels(tmp_path):
    document = reference_composition(True)
    original = compile_composition(document)
    baseline = [pixels(document, time) for time in (.4, 4.1, 6.2)]
    document['effects']['ghosts'] = dict(mode='recipe', params={}, bypassed=True)
    assert pixels(document, 6.2) != baseline[2]
    path = tmp_path / 'bypass.json'; save_composition(path, document)
    loaded = load_composition(path)
    assert loaded['effects']['ghosts']['bypassed'] is True
    loaded['effects']['ghosts']['bypassed'] = False
    resumed = compile_composition(loaded)
    assert {name: state_values(state) for name, state in resumed['states'].items()} == {name: state_values(state) for name, state in original['states'].items()}
    assert [pixels(loaded, time) for time in (.4, 4.1, 6.2)] == baseline


def test_local_resume_inherits_params_and_parent_edits():
    document = reference_composition(True)
    document['effects']['ghosts'] = dict(mode='recipe', params={'smear.ghosts': 8}, bypassed=True)
    document['sections'][1]['effects']['ghosts'] = dict(mode='recipe', params={}, bypassed=False)
    state = compile_composition(document)['states']['section-2:slab']
    values, enabled = state_values(state)
    assert 'smear' in enabled and values['smear.ghosts'] == 8
    document['effects']['ghosts']['params']['smear.ghosts'] = 6
    values, enabled = state_values(compile_composition(document)['states']['section-2:slab'])
    assert 'smear' in enabled and values['smear.ghosts'] == 6
    document['sections'][1]['effects'].clear()
    values, enabled = state_values(compile_composition(document)['states']['section-2:slab'])
    assert 'smear' not in enabled and values['slab.ghost_opacity'] == 0


def test_source_restore_clears_bypass_retaining_authored_parameters():
    document = reference_composition(True)
    document['effects']['rays'] = dict(mode='off', params={'blinds.rows': 17}, bypassed=True)
    restored = restore_subject(document)
    assert restored['effects']['rays'] == dict(mode='recipe', params={'blinds.rows': 17})


def test_bypass_keeps_editor_ranges_and_edits_are_retained(panel):
    effect = panel.effects_panel; effect.inspect_effect('ghosts')
    before = copy.deepcopy(effect.authored_summary['ghosts']['ranges'])
    effect.bypass_button.click()
    assert effect.effect_id == 'ghosts' and 'ghosts' in effect.applied_ids
    assert effect.effect_choices['ghosts'].badge.text() == 'Bypassed'
    assert effect.authored_summary['ghosts']['ranges'] == before
    assert not effect.summary['ghosts']['active']
    effect.change_parameter('smear.ghosts', 7)
    assert panel.document['effects']['ghosts']['bypassed']
    assert panel.document['effects']['ghosts']['params']['smear.ghosts'] == 7
    effect.bypass_button.click()
    assert panel.document['effects']['ghosts']['mode'] == 'recipe'
    assert panel.document['effects']['ghosts']['bypassed'] is False


@pytest.mark.parametrize('width,height', [(380, 720), (490, 750), (490, 900)])
def test_focused_header_is_pinned_and_first_control_visible(panel, width, height):
    panel.resize(width, height); effect = panel.effects_panel; effect.inspect_effect('broadcast')
    QApplication.processEvents()
    control = next(control for control in effect.controls.values() if control.isVisible())
    position = control.mapTo(panel, QPoint(0, 0))
    assert position.y() < height - 100
    assert control.width() <= effect.parameter_scroll.viewport().width()
    title_y = effect.inspector_title.mapTo(panel, QPoint(0, 0)).y()
    scope_y = panel.scope_combo.mapTo(panel, QPoint(0, 0)).y()
    scroll = effect.parameter_scroll.verticalScrollBar(); scroll.setValue(scroll.maximum())
    QApplication.processEvents()
    assert effect.inspector_title.mapTo(panel, QPoint(0, 0)).y() == title_y
    assert panel.scope_combo.mapTo(panel, QPoint(0, 0)).y() == scope_y
    effect.inspect_effect('photocopy')
    assert scroll.value() == 0


def test_navigation_search_browser_and_grouping_never_author(panel):
    original = copy.deepcopy(panel.document); edits = []
    panel.changed.connect(lambda *args: edits.append(args))
    effect = panel.effects_panel
    effect.inspect_effect('broadcast'); effect.parameter_tabs.setCurrentIndex(2)
    effect.filter.setText('static'); effect.group.setCurrentIndex(min(1, effect.group.count()-1))
    effect.show_overview(); effect.open_browser()
    effect.browser.search.setText('tape'); effect.browser.reject()
    panel.look_tabs.setCurrentWidget(panel.object_panel)
    assert panel.document == original and not edits
    assert panel.scope == 0


def test_reset_isolated_by_focused_effect_object_finishing_master(panel):
    document = copy.deepcopy(panel.document)
    document['effects']['tape'] = effect_preset('tape')
    document['effects']['ghosts'] = effect_preset('ghosts')
    document['macros']['texture'] = 1.5
    document['geometry']['position_x'] = 25.
    document['master']['brightness'] = .1
    panel.document = document; panel.refresh()
    panel.effects_panel.inspect_effect('tape'); panel.reset_controls()
    assert 'tape' not in panel.document['effects']
    assert panel.document['effects']['ghosts'] == document['effects']['ghosts']
    assert panel.document['macros'] == document['macros'] and panel.document['master'] == document['master']
    panel.effects_panel.show_overview(); before = copy.deepcopy(panel.document); panel.reset_controls()
    assert panel.reset_label() == '' and panel.document == before
    panel.look_tabs.setCurrentIndex(2); panel.reset_controls()
    assert panel.document['macros']['texture'] == 1.
    assert panel.document['geometry']['position_x'] == 25.
    assert panel.document['effects']['ghosts'] == document['effects']['ghosts']
    panel.look_tabs.setCurrentWidget(panel.object_panel); panel.reset_controls()
    assert panel.document['geometry']['position_x'] == 0.
    assert panel.document['effects']['ghosts'] == document['effects']['ghosts']
    assert panel.document['master'] == document['master']


def text_panel(panel):
    document = blank_composition(); document['effects']['text'] = effect_preset('text')
    panel.document = document; panel.refresh(); panel.effects_panel.inspect_effect('text')
    return panel.effects_panel.controls['text.content']


def test_hidden_effect_text_draft_saves_without_changing_selected_effect(panel):
    text = text_panel(panel); text.input.editor.setPlainText('Pending hidden wording')
    panel.effects_panel.inspect_effect('tape')
    assert panel.pending_text_edits()
    panel.prepare_text_save()
    assert panel.document['effects']['text']['params']['text.content'] == 'Pending hidden wording'
    assert panel.effects_panel.effect_id == 'tape' and not panel.pending_text_edits()


def test_distinct_section_drafts_save_in_original_scopes(panel):
    text_panel(panel)
    second = copy.deepcopy(panel.document['sections'][0]); second['id'] = 'section-2'
    panel.document['sections'].append(second); panel.refresh()
    panel.change_scope(1); text = panel.effects_panel.controls['text.content']
    text.input.editor.setPlainText('First section wording')
    panel.select_section(1); text.input.editor.setPlainText('Second section wording')
    panel.prepare_text_save()
    assert panel.document['sections'][0]['effects']['text']['params']['text.content'] == 'First section wording'
    assert panel.document['sections'][1]['effects']['text']['params']['text.content'] == 'Second section wording'
    assert not panel.pending_text_edits()


def test_conflicting_same_scope_drafts_do_not_commit(panel):
    text = text_panel(panel); original = copy.deepcopy(panel.document)
    text.input.editor.setPlainText('Effects draft')
    panel.object_panel.controls['text.content'].input.editor.setPlainText('Object draft')
    with pytest.raises(ValueError, match='different unapplied wording'):
        panel.prepare_text_save()
    assert panel.document == original


def test_hidden_text_draft_after_source_switch_stays_off(panel):
    text = text_panel(panel); text.input.editor.setPlainText('Keep wording for later')
    panel.change_object('particles')
    assert panel.document['effects']['text']['mode'] == 'off'
    panel.prepare_text_save()
    assert panel.document['effects']['text']['params']['text.content'] == 'Keep wording for later'
    assert panel.document['effects']['text']['mode'] == 'off'


def test_bypass_undo_redo_and_reopen_resume_preserve_pixels(panel, tmp_path):
    from synth_studio import SynthStudio
    from PySide6.QtCore import QThreadPool
    window = SynthStudio(); window.auto_prepare.setChecked(False)
    try:
        window.set_composition(reference_composition(True))
        before = [pixels(window.composition, time) for time in (.4, 4.1, 6.2)]
        effects = window.composer.effects_panel; effects.inspect_effect('ghosts'); effects.bypass_button.click()
        assert window.composition['effects']['ghosts']['bypassed'] is True
        muted = copy.deepcopy(window.composition)
        window.undo_composition()
        assert [pixels(window.composition, time) for time in (.4, 4.1, 6.2)] == before
        window.redo_composition(); assert window.composition == muted
        path = tmp_path / 'undo-bypass.json'; save_composition(path, window.composition)
        window.set_composition(load_composition(path))
        effects = window.composer.effects_panel; effects.inspect_effect('ghosts'); effects.bypass_button.click()
        assert [pixels(window.composition, time) for time in (.4, 4.1, 6.2)] == before
    finally:
        window.close(); QThreadPool.globalInstance().waitForDone(10000); QApplication.processEvents()


def test_ordinary_edit_preserves_scroll_position(panel):
    effects = panel.effects_panel; effects.inspect_effect('broadcast'); QApplication.processEvents()
    bar = effects.parameter_scroll.verticalScrollBar(); bar.setValue(bar.maximum() // 2)
    before = bar.value(); assert before > 0
    effects.change_parameter('broadcast.static', .4); QApplication.processEvents()
    assert bar.value() == before


def test_source_overview_routes_to_object_and_disabled_duplicates_inspect(panel):
    effect = panel.effects_panel; effect.show_overview()
    effect.effect_choices['rays'].button.click()
    assert panel.look_tabs.currentWidget() is panel.object_panel
    panel.document['effects']['tape'] = dict(mode='off', params={'tape.mix': .3})
    panel.refresh(); original = copy.deepcopy(panel.document)
    effect.add_effect('tape', 0)
    assert panel.document == original and effect.effect_id == 'tape'


def test_removed_section_draft_is_inactive_until_undo_restores_its_scope(panel):
    text_panel(panel)
    second = copy.deepcopy(panel.document['sections'][0]); second['id'] = 'section-2'
    panel.document['sections'].append(second); panel.refresh(); panel.change_scope(1)
    original = copy.deepcopy(panel.document)
    text = panel.effects_panel.controls['text.content']; text.input.editor.setPlainText('Deleted section draft')
    panel.remove_section()
    assert not panel.pending_text_edits() and panel.prepare_text_save()
    assert panel.document['sections'][0]['id'] == 'section-2'
    panel.document = original; panel.index = 0; panel.refresh()
    assert panel.pending_text_edits() == [(text.input, 'Deleted section draft')]
    panel.prepare_text_save()
    assert panel.document['sections'][0]['effects']['text']['params']['text.content'] == 'Deleted section draft'


@pytest.mark.parametrize('height', [720, 800])
def test_arrange_has_bounded_real_window_page_and_returns_same_scope(panel, height):
    from synth_studio import SynthStudio
    from PySide6.QtCore import QThreadPool
    window = SynthStudio(); window.auto_prepare.setChecked(False)
    window.resize(1280, height); window.show(); QApplication.processEvents()
    try:
        composer = window.composer; composer.change_scope(1)
        composer.effects_panel.inspect_effect('broadcast')
        original = copy.deepcopy(window.composition); effect = composer.effects_panel.effect_id
        composer.arrangement_button.click(); QApplication.processEvents()
        assert window.height() == height
        assert composer.content_stack.currentWidget() is composer.arrangement_scroll
        assert not composer.parameters_group.isVisible() and composer.reset_label() == ''
        assert composer.fps.isVisible() and not composer.arrangement_scroll.isAncestorOf(composer.fps)
        for control in (composer.duration, composer.section_combo, composer.section_duration, composer.section_loops):
            composer.arrangement_scroll.ensureWidgetVisible(control); QApplication.processEvents()
            viewport = composer.arrangement_scroll.viewport()
            assert viewport.rect().contains(control.mapTo(viewport, control.rect().center()))
            point = control.mapTo(viewport, QPoint(0,0))
            assert point.x() >= 0 and point.x() + control.width() <= viewport.width()
        composer.arrangement_button.click(); QApplication.processEvents()
        assert composer.content_stack.currentWidget() is composer.parameters_group
        assert composer.effects_panel.effect_id == effect and composer.scope == 1
        assert window.composition == original and window.height() == height
    finally:
        window.close(); QThreadPool.globalInstance().waitForDone(10000); QApplication.processEvents()


def test_timeline_fps_stays_visible_and_global_while_editing_a_section(panel, tmp_path):
    panel.change_scope(1)
    panel.effects_panel.inspect_effect('broadcast')
    original = copy.deepcopy(panel.document)
    for page in (panel.effects_panel, panel.object_panel, panel.master_panel):
        panel.look_tabs.setCurrentWidget(page); QApplication.processEvents()
        assert panel.fps.isVisible()
        assert panel.rect().contains(panel.fps.mapTo(panel, panel.fps.rect().topLeft()))
        assert panel.rect().contains(panel.arrangement_button.mapTo(panel, panel.arrangement_button.rect().bottomRight()))
    assert panel.document == original
    panel.fps.setValue(12)
    assert panel.scope == 1 and panel.document['fps'] == 12
    assert compile_composition(panel.document)['fps'] == 12
    for before, after in zip(original['sections'], panel.document['sections']):
        assert after['duration'] == max(1, round(before['duration'] * 12)) / 12
        assert after['effects'] == before['effects']
    path = tmp_path / 'global-fps.json'
    save_composition(path, panel.document)
    assert load_composition(path)['fps'] == 12
    panel.arrangement_button.click(); QApplication.processEvents()
    assert panel.fps.isVisible()
