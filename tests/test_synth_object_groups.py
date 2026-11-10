"""Navigation must not become an edit, erase wording, or change rendered studies."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication
from synth_effects import EFFECT_BY_ID, describe_effects
from synth_object_groups import TEXT_GROUPS, PLEATED_GROUPS, paths
from synth_starters import starter_composition
from synth_subject import scope_states
from synth_subject_ui import SubjectPanel
from synth_sequence import render_sequence_frame
from synth_composition import compile_composition
from test_synth_effects_editor_integration import make_window


def settle():
    for _ in range(4): QApplication.processEvents()


@pytest.fixture
def panel():
    app = QApplication.instance() or QApplication([])
    widget = SubjectPanel(); widget.resize(510, 670); widget.show()
    yield widget
    widget.close(); widget.deleteLater(); app.processEvents()


def load(panel, identifier, entries=None, parents=None, local=False):
    document = starter_composition(identifier)
    panel.refresh(describe_effects(scope_states(document)), entries or document['effects'], parents or {}, local,
                  context_key=('clip' if local else 'project', identifier), scope_label='Clip 1' if local else 'Entire project')
    settle()
    return document


@pytest.mark.parametrize('prefix,definitions,primary', [
    ('text', TEXT_GROUPS, ('text.font', 'text.weight', 'text.content')),
    ('pleated_field', PLEATED_GROUPS, ()),
])
def test_every_registered_control_has_exactly_one_home(prefix, definitions, primary):
    assigned = list(primary) + [p for _, _, _, names in definitions for p in paths(prefix, names)]
    assert len(assigned) == len(set(assigned))
    assert set(assigned) == set(EFFECT_BY_ID[prefix].paths)


def test_search_across_pages_focuses_result_and_restores_fold_and_scroll(panel):
    load(panel, 'text-contact-film')
    panel.text_tabs.setCurrentIndex(1)
    panel.reveal_object_group('Letterpress'); settle()
    scroll = panel.overview_scroll.verticalScrollBar(); before = scroll.value()
    expansion = dict(panel.object_expansion)
    changed = QSignalSpy(panel.parameter_changed)
    panel.object_filter.setFocus(); panel.object_filter.setText('Saturation'); settle()
    assert panel.controls['text.saturation'].isVisible()
    assert not panel.position_host.isVisible()
    assert panel.object_filter.hasFocus()
    QTest.keyClick(panel.object_filter, Qt.Key.Key_Return); settle()
    assert panel.controls['text.saturation'].input.hasFocus()
    panel.object_filter.clear(); settle()
    assert panel.text_tabs.currentIndex() == 1
    assert scroll.value() == before
    assert panel.object_expansion == expansion
    assert not panel.object_groups['Color & light'].body.isVisible()
    assert panel.object_groups['Letterpress'].body.isVisible()
    assert changed.count() == 0


def test_show_all_is_reversible_and_search_does_not_require_tab_guessing(panel):
    load(panel, 'text-contact-film')
    panel.text_tabs.setCurrentIndex(2)
    panel.object_filter.setText('Text size'); settle()
    assert panel.controls['text.size'].isVisible()
    panel.object_filter.clear(); settle()
    assert panel.text_tabs.currentIndex() == 2
    panel.text_tabs.setCurrentIndex(1)
    assert not panel.object_groups['Geometry'].body.isVisible()
    panel.show_all_controls.click()
    assert panel.object_groups['Geometry'].body.isVisible()
    panel.show_all_controls.click()
    assert not panel.object_groups['Geometry'].body.isVisible()
    panel.object_filter.setText('zzzzzz'); settle()
    assert panel.no_object_matches.isVisible()
    panel.object_filter.clear(); settle()
    assert not panel.no_object_matches.isVisible()


def test_group_counts_distinguish_inherited_fixed_and_event_animation(panel):
    entries = {'pleated_field': {'mode': 'recipe', 'params': {'pleated_field.saturation': .8}}}
    parents = {'pleated_field': {'mode': 'recipe', 'params': {'pleated_field.light': .9}}}
    load(panel, 'pleated-signal', entries, parents, True)
    panel.set_automation_counts({'pleated_field.saturation': 2})
    assert panel.object_groups['Palette'].summary.text() == '1 local value · 1 animated'
    assert panel.object_groups['Profile & scale'].summary.text() == '2 animated'
    panel.reveal_object_group('Palette'); settle()
    assert panel.controls['pleated_field.light'].origin.text() == 'Base · fixed · Entire project'
    assert panel.controls['pleated_field.saturation'].reset_button.isEnabled()
    assert not panel.controls['pleated_field.light'].reset_button.isEnabled()


def test_pleated_navigation_and_family_switch_keep_cached_controls_and_no_stale_groups(panel):
    load(panel, 'pleated-signal')
    control = panel.controls['pleated_field.depth']
    panel.reveal_object_group('Camera'); settle()
    assert panel.controls['pleated_field.projection'].isVisible()
    panel.object_filter.setText('Surface loop'); settle()
    assert panel.controls['pleated_field.loop_seconds'].isVisible()
    groups = list(panel.object_groups.values())
    load(panel, 'text-contact-film')
    assert not panel.object_filter.text()
    # Deferred deletion can happen during settle; any survivors must be hidden.
    import shiboken6
    assert all(not g.isVisible() for g in groups if shiboken6.isValid(g))
    load(panel, 'chromatic-lattice')
    assert panel.object_navigation.isVisible()
    load(panel, 'pleated-signal')
    assert panel.controls['pleated_field.depth'] is control


@pytest.mark.parametrize('size', [(1280, 800), (1440, 900), (1024, 768)])
def test_pinned_context_keyboard_navigation_and_narrow_inspector(make_window, size):
    w = make_window(composition=starter_composition('pleated-signal'))
    w.resize(*size); w.splitter.setSizes([size[0] - 430, 420])
    obj = w.composer.object_panel; w.composer.look_tabs.setCurrentWidget(obj); settle()
    original = copy.deepcopy(w.composition)
    title_y = obj.selector.mapTo(w, QPoint()).y()
    obj.object_jump.setFocus()
    index = obj.object_jump.findData('Camera')
    obj.object_jump.setCurrentIndex(index); obj.object_jump.activated.emit(index); settle()
    camera = obj.controls['pleated_field.projection']
    assert camera.isVisible()
    assert obj.overview_scroll.horizontalScrollBar().maximum() == 0
    assert obj.selector.mapTo(w, QPoint()).y() == title_y
    assert w.width() == size[0]
    assert obj.overview_scroll.viewport().height() >= 120
    assert w.composition == original and not w.has_unsaved_changes()


def test_text_draft_edit_undo_and_navigation_preserve_study_render(make_window):
    w = make_window(composition=starter_composition('text-contact-film'))
    obj = w.composer.object_panel; w.composer.look_tabs.setCurrentWidget(obj); settle()
    original = copy.deepcopy(w.composition)
    before = render_sequence_frame(compile_composition(original), 2., (96, 72)).tobytes()
    editor = obj.controls['text.content'].input
    editor.editor.setPlainText('PENDING WORDS')
    obj.text_tabs.setCurrentIndex(1); obj.object_filter.setText('Saturation'); settle()
    obj.object_filter.clear(); obj.text_tabs.setCurrentIndex(0); settle()
    assert editor.editor.toPlainText() == 'PENDING WORDS'
    assert w.composition == original
    assert render_sequence_frame(w.sequence, 2., (96, 72)).tobytes() == before
    editor.editor.setPlainText(editor.value())
    obj.reveal_control('text.size'); settle()
    obj.controls['text.size'].input.setValue(.6)
    assert w.composition != original
    assert obj.object_groups['Size & spacing'].body.isVisible()
    w.undo_composition(); settle()
    assert w.composition == original
    assert render_sequence_frame(w.sequence, 2., (96, 72)).tobytes() == before


def test_reading_explains_disabled_frame_without_enabling_it(panel):
    load(panel, 'text-reading-print')
    assert panel.text_motion_link.isVisible()
    panel.reveal_object_group('Frame & subtitle layout'); settle()
    assert panel.controls['text.badge_shape'].isVisible()
    assert not panel.controls['text.badge_shape'].isEnabled()
    panel.text_motion_link.click(); settle()
    assert panel.text_tabs.currentIndex() == 2
    assert panel.controls['text.reveal'].isVisible()


def test_pleated_activation_and_presets_remain_accessible(make_window):
    w = make_window(composition=starter_composition('pleated-signal'))
    c = w.composer; obj = c.object_panel; c.look_tabs.setCurrentWidget(obj)
    original = copy.deepcopy(w.composition)
    obj.details.click(); settle()
    assert obj.pages.currentWidget() is c.object_editor
    assert c.object_editor.activation_host.isVisible()
    assert c.object_editor.mode.isVisible() and c.object_editor.look.isVisible()
    assert not obj.object_navigation.isVisible()
    c.object_editor.back_button.click(); settle()
    assert obj.object_navigation.isVisible()
    assert obj.pages.currentWidget() is obj.overview_scroll
    assert w.composition == original and not w.has_unsaved_changes()
