"""Effect discovery is separate from applying presets or choosing sources."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from studio_widgets import ComboBox
from synth_effect_browser import EffectBrowserDialog
from synth_effect_catalog import CATEGORIES, EFFECT_CATEGORIES, SOURCE_EFFECT_IDS, effect_catalog
from synth_effects import EFFECTS, EFFECT_BY_ID, effect_preset
from synth_subject import SOURCE_EFFECTS
from synth_video import VIDEO_EFFECTS


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def browser(app):
    dialogs = []

    def make(**kwargs):
        dialog = EffectBrowserDialog(**kwargs)
        dialogs.append(dialog)
        dialog.show(); app.processEvents()
        return dialog

    yield make
    for dialog in dialogs: dialog.close()
    app.processEvents()


def visible_ids(dialog):
    return [dialog.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(dialog.table.rowCount())]


def select(dialog, identifier):
    dialog.table.selectRow(visible_ids(dialog).index(identifier))


def observe(dialog):
    events = []
    dialog.effectRequested.connect(lambda identifier, preset: events.append(('add', identifier, preset)))
    dialog.effectInspected.connect(lambda identifier: events.append(('inspect', identifier)))
    dialog.objectRequested.connect(lambda: events.append(('object',)))
    return events


def test_catalog_covers_every_treatment_and_uses_existing_presets():
    assert SOURCE_EFFECT_IDS == set(SOURCE_EFFECTS)
    treatments = {effect.id for effect in EFFECTS} - SOURCE_EFFECT_IDS
    assert set(EFFECT_CATEGORIES) == treatments
    catalog = effect_catalog()
    assert {effect.id for effect in catalog} == treatments
    assert {effect.category for effect in catalog} == set(CATEGORIES) - {'Other'}
    for entry in catalog:
        effect = EFFECT_BY_ID[entry.id]
        assert entry.description == effect.description
        assert entry.presets == (tuple(label for label, _ in effect.looks) or ('Default settings',))


def test_catalog_search_combines_words_categories_descriptions_and_preset_names():
    assert [entry.id for entry in effect_catalog(query='  QUIET   paper ')] == ['print_surface']
    assert [entry.id for entry in effect_catalog(query='toner', category='Texture')] == ['photocopy']
    assert [entry.id for entry in effect_catalog(query='Crisp pixels')] == ['low_res']
    assert not effect_catalog(query='toner', category='Distortion')
    assert 'screen_mesh' in {entry.id for entry in effect_catalog(query='RGB')}
    assert not effect_catalog(())
    assert not effect_catalog(('unknown', 'text'))


def test_browsing_selection_filtering_and_presets_never_request_an_edit(browser):
    allowed = [effect.id for effect in EFFECTS if effect.id != 'subject_cutout']
    applied = ['bloom']
    before = copy.deepcopy((allowed, applied, EFFECTS))
    dialog = browser(allowed_effects=allowed, applied_ids=applied)
    events = observe(dialog)
    assert not SOURCE_EFFECT_IDS.intersection(visible_ids(dialog))
    assert 'subject_cutout' not in visible_ids(dialog)
    assert isinstance(dialog.category, ComboBox) and isinstance(dialog.preset, ComboBox)
    dialog.search.setText('quiet paper')
    assert visible_ids(dialog) == ['print_surface']
    assert dialog.description.text() == EFFECT_BY_ID['print_surface'].description
    dialog.preset.setCurrentIndex(2)
    dialog.search.clear()
    dialog.category.setCurrentIndex(dialog.category.findData('Light & color'))
    select(dialog, 'bloom')
    assert dialog.action.text() == 'Inspect effect'
    assert (allowed, applied, EFFECTS) == before and events == []


@pytest.mark.parametrize('identifier,index', [('print_surface', 2), ('low_res', 3), ('bloom', 0)])
def test_explicit_add_emits_the_selected_existing_preset(browser, identifier, index):
    dialog = browser()
    events = observe(dialog)
    original = copy.deepcopy(EFFECT_BY_ID[identifier])
    select(dialog, identifier)
    dialog.preset.setCurrentIndex(index)
    assert events == []
    dialog.action.click()
    assert events == [('add', identifier, index)]
    assert dialog.result() == QDialog.DialogCode.Accepted and not dialog.isVisible()
    assert EFFECT_BY_ID[identifier] == original
    # Every emitted index resolves through the existing renderer preset API.
    assert effect_preset(identifier, index)['mode'] == 'on'


def test_applied_entries_inspect_without_preset_replacement(browser):
    dialog = browser(applied_ids=('print_surface',))
    events = observe(dialog)
    select(dialog, 'print_surface')
    assert dialog.action.text() == 'Inspect effect'
    assert not dialog.preset_row.isVisible() and not dialog.preset.isEnabled()
    assert 'current settings' in dialog.selection_note.text()
    dialog.action.click()
    assert events == [('inspect', 'print_surface')]
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_context_changes_update_compatibility_selection_and_applied_actions(browser):
    dialog = browser()
    events = observe(dialog)
    select(dialog, 'print_surface'); dialog.preset.setCurrentIndex(2)
    dialog.set_context(VIDEO_EFFECTS, ('print_surface',))
    assert dialog.selected_effect_id() == 'print_surface'
    assert set(visible_ids(dialog)) == set(VIDEO_EFFECTS)
    assert not dialog.object_button.isEnabled()
    assert dialog.action.text() == 'Inspect effect'
    dialog.request_object(); assert events == []
    dialog.set_context(('print_surface', 'text'), ())
    assert visible_ids(dialog) == ['print_surface']
    assert dialog.action.text() == 'Add effect' and dialog.preset.currentIndex() == 2
    assert dialog.object_button.isEnabled()
    dialog.action.click()
    assert events == [('add', 'print_surface', 2)]


def test_restricting_context_removes_stale_selection_and_unavailable_categories(browser):
    dialog = browser()
    events = observe(dialog)
    dialog.category.setCurrentIndex(dialog.category.findData('Texture'))
    select(dialog, 'print_surface')
    dialog.set_context(('bloom',), ())
    assert dialog.category.currentData() == ''
    assert dialog.category.findData('Texture') == -1
    assert visible_ids(dialog) == ['bloom']
    assert dialog.selected_effect_id() == 'bloom' and events == []
    dialog.set_context((), ())
    dialog.request_effect()
    assert not dialog.action.isEnabled() and events == []


def test_empty_filter_and_empty_compatibility_have_recovery_messages(browser):
    dialog = browser(allowed_effects=('bloom', 'text'))
    events = observe(dialog)
    dialog.search.setText('no such treatment')
    assert visible_ids(dialog) == [] and not dialog.action.isEnabled()
    assert dialog.selected_effect_id() is None and not dialog.description.text()
    assert 'Clear search' in dialog.empty.text() and dialog.empty.isVisible()
    dialog.request_effect(); assert events == []
    dialog.search.clear()
    assert visible_ids(dialog) == ['bloom'] and dialog.action.isEnabled()
    dialog.set_context(('text',))
    assert 'No image effects are available' in dialog.empty.text()
    assert dialog.object_button.isEnabled() and not dialog.action.isEnabled()
    dialog.object_button.click()
    assert events == [('object',)] and dialog.result() == QDialog.DialogCode.Accepted


@pytest.mark.parametrize('action', ['button', 'escape'])
def test_cancel_does_not_add_inspect_or_change_object(browser, action):
    dialog = browser()
    events = observe(dialog)
    select(dialog, 'print_surface'); dialog.preset.setCurrentIndex(2)
    if action == 'button': dialog.cancel_button.click()
    else: QTest.keyClick(dialog.search, Qt.Key.Key_Escape)
    assert events == [] and dialog.result() == QDialog.DialogCode.Rejected
    assert not dialog.isVisible()


def test_keyboard_browsing_requires_an_explicit_focused_action(browser):
    dialog = browser()
    events = observe(dialog)
    dialog.search.setFocus(); dialog.search.setText('photocopy')
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    assert events == [] and dialog.table.hasFocus() and dialog.isVisible()
    QTest.keyClick(dialog.table, Qt.Key.Key_Return)
    assert events == [] and dialog.isVisible()
    dialog.preset.setCurrentIndex(1)
    dialog.action.setFocus()
    QTest.keyClick(dialog.action, Qt.Key.Key_Return)
    assert events == [('add', 'photocopy', 1)]


def test_long_description_keeps_selected_row_visible_in_a_narrow_dialog(browser):
    dialog = browser(allowed_effects=VIDEO_EFFECTS)
    dialog.resize(480, 600)
    QApplication.processEvents()
    select(dialog, 'subject_cutout')
    QApplication.processEvents()
    row = visible_ids(dialog).index('subject_cutout')
    assert dialog.table.viewport().rect().contains(dialog.table.visualItemRect(dialog.table.item(row, 0)))
    assert dialog.table.horizontalScrollBar().maximum() == 0
    assert dialog.description.height() >= dialog.description.heightForWidth(dialog.description.width())
