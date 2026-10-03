"""Compact rack chrome preserves source discovery and labelled effect actions."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

from studio_theme import apply_theme
from synth_composition import compile_composition, reference_composition
from synth_effects import EFFECTS, EFFECT_BY_ID, effect_preset
from synth_effects_ui import EffectsPanel


@pytest.fixture
def make_panel():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    panels = []

    def make(width=380, sources=('forms', 'rays'), treatments=('tape', 'broadcast'), allowed=None):
        document = reference_composition(True)
        document['effects'] = {effect.id: {'mode': 'off', 'params': {}} for effect in EFFECTS}
        for key in (*sources, *treatments):
            document['effects'][key] = effect_preset(key)
        states = list(compile_composition(document)['states'].values())
        widget = EffectsPanel()
        widget.set_context(document['effects'], {}, states, 'Whole clip', False, ('whole',), allowed_effects=allowed)
        widget.show_overview(); widget.resize(width, 600); widget.show(); app.processEvents()
        panels.append(widget)
        return widget, document, states

    yield make
    for widget in panels:
        widget.close(); widget.deleteLater()
    app.processEvents()


def assert_inside(widget, host):
    position = widget.mapTo(host, QPoint())
    assert position.x() >= 0 and position.x() + widget.width() <= host.width()
    assert widget.width() >= widget.minimumSizeHint().width()


@pytest.mark.parametrize('width', [380, 490])
def test_themed_headers_share_rows_and_rack_actions_fit(make_panel, width):
    panel, _, _ = make_panel(width)
    assert panel.width() == width
    assert panel.applied_title.text() == 'IMAGE EFFECTS · 2'
    assert panel.source_title.text() == 'OBJECT · 2 sources'
    assert panel.applied_title.mapTo(panel.overview, QPoint()).y() == panel.available_button.mapTo(panel.overview, QPoint()).y()
    assert panel.object_button.parentWidget() is panel.source_header
    assert panel.source_title.geometry().center().y() == panel.object_button.geometry().center().y()
    assert_inside(panel.available_button, panel.overview)
    assert_inside(panel.object_button, panel.source_header)
    scroll = panel.overview.findChild(QScrollArea)
    assert scroll.horizontalScrollBar().maximum() == 0
    for key in ('tape', 'broadcast'):
        row = panel.effect_choices[key]
        assert row.isVisible()
        assert row.button.width() >= 56
        assert row.button.accessibleName().startswith('Inspect ' + EFFECT_BY_ID[key].label)
        for action in (row.bypass, row.remove):
            assert action.isVisible() and action.text() in ('Bypass', 'Remove')
            assert action.focusPolicy() != Qt.FocusPolicy.NoFocus
            assert action.property('compact') is True
            assert_inside(action, row)
        assert row.remove.property('secondaryAction') is True
    object_actions = [button for button in panel.overview.findChildren(QPushButton)
                      if 'object' in button.text().casefold()]
    assert object_actions == [panel.object_button]


def test_each_composite_source_retains_object_route_and_discovery_expands(make_panel):
    panel, document, _ = make_panel()
    original = copy.deepcopy(document)
    requests = []
    panel.object_requested.connect(lambda: requests.append('object'))
    for key in ('forms', 'rays'):
        choice = panel.effect_choices[key]
        assert choice.isVisible()
        assert not choice.bypass.isVisible() and not choice.remove.isVisible()
        choice.button.setFocus(); QTest.keyClick(choice.button, Qt.Key.Key_Space)
    panel.object_button.setFocus(); QTest.keyClick(panel.object_button, Qt.Key.Key_Space)
    assert requests == ['object'] * 3
    assert not panel.breakdown_host.isVisible()
    panel.breakdown_button.setFocus(); QTest.keyClick(panel.breakdown_button, Qt.Key.Key_Space)
    QApplication.processEvents()
    assert panel.breakdown_host.isVisible()
    assert {'forms', 'rays', 'tape', 'broadcast'} <= panel.breakdown_rows.keys()
    assert any(button.text() == 'Open Finishing' for button in panel.breakdown_host.findChildren(QPushButton))
    assert any(button.text() == 'Open Master' for button in panel.breakdown_host.findChildren(QPushButton))
    panel.breakdown_button.click()
    assert not panel.breakdown_host.isVisible()
    assert document == original


@pytest.mark.parametrize('width', [380, 490])
def test_empty_source_keeps_one_object_entry_and_video_hides_it(make_panel, width):
    panel, _, _ = make_panel(width, sources=(), treatments=())
    assert panel.source_title.text() == 'OBJECT · no source'
    assert panel.source_header.isVisible() and panel.object_button.isVisible()
    assert not panel.source_host.isVisible()
    assert panel.empty_applied.isVisible() and panel.available_button.isVisible()
    video, _, _ = make_panel(width, sources=(), treatments=('tape',), allowed=('tape', 'broadcast'))
    assert not video.source_header.isVisible() and not video.object_button.isVisible()
    assert video.breakdown_button.isVisible()
    assert_inside(video.available_button, video.overview)


def test_keyboard_bypass_resume_and_remove_keep_authored_payloads(make_panel):
    panel, document, states = make_panel()
    entry = copy.deepcopy(document['effects']['tape'])
    edits = []
    panel.edited.connect(lambda key, value, reason: edits.append((key, value, reason)))
    row = panel.effect_choices['tape']
    row.bypass.setFocus(); QTest.keyClick(row.bypass, Qt.Key.Key_Space)
    assert edits[-1] == ('tape', dict(entry, bypassed=True), 'effect-bypass')
    entries = copy.deepcopy(document['effects']); entries['tape']['bypassed'] = True
    panel.set_context(entries, {}, states, 'Whole clip', False, ('whole',))
    assert row.bypass.text() == 'Resume' and row.badge.text() == 'Bypassed'
    row.bypass.setFocus(); QTest.keyClick(row.bypass, Qt.Key.Key_Space)
    assert edits[-1] == ('tape', dict(entry, bypassed=False), 'effect-bypass')
    row.remove.setFocus(); QTest.keyClick(row.remove, Qt.Key.Key_Space)
    assert edits[-1] == ('tape', {'mode': 'off', 'params': {}, 'bypassed': False}, 'effect-remove')
    assert panel.pages.currentWidget() is panel.overview
    assert document['effects']['tape'] == entry


def test_compact_add_action_retains_discovery_request(make_panel):
    panel, _, _ = make_panel()
    panel.discovery_enabled = True
    requests = []
    panel.discovery_requested.connect(lambda *request: requests.append(request))
    panel.available_button.setFocus(); QTest.keyClick(panel.available_button, Qt.Key.Key_Space)
    assert requests == [('', 0, 'add')]


@pytest.mark.parametrize('width', [380, 490])
def test_long_name_and_intermittent_state_keep_labelled_actions_visible(make_panel, width):
    panel, _, _ = make_panel(width, sources=('rays',), treatments=('interference',))
    assert panel.source_title.text() == 'OBJECT · 1 source'
    choice = panel.effect_choices['interference']
    info = dict(panel.authored_summary['interference'], intermittent=True)
    choice.refresh(EFFECT_BY_ID['interference'], info, False, False)
    QApplication.processEvents()
    assert choice.badge.text() == 'Intermittent'
    assert choice.button.width() >= 56 and choice.button.text()
    assert choice.button.accessibleName() == 'Inspect Signal interference · Intermittent'
    for action in (choice.bypass, choice.remove):
        assert_inside(action, choice)
        assert action.isVisible() and action.text() in ('Bypass', 'Remove')
    assert panel.overview.findChild(QScrollArea).horizontalScrollBar().maximum() == 0
