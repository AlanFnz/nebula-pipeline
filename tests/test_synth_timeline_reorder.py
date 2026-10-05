"""Body dragging reorders shared clips without colliding with edge resizing."""
import copy

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QScrollArea

from synth_composer_ui import SectionTimeline
from synth_composition import section_placements
from test_synth_timeline_resize import app, document, edge_point, timeline


def observe(widget):
    calls = []
    widget.reorderRequested.connect(lambda ids, before: calls.append((ids, before)))
    return calls


def press_body(widget, occurrence):
    point = widget.rectangles()[occurrence].center().toPoint()
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=point)
    return point


@pytest.mark.parametrize('source,x,expected', [(0, 599, (('alpha',), None)),
    (2, 1, (('gamma',), 'alpha')), (0, 500, (('alpha',), 'gamma'))])
def test_body_drag_previews_one_move_and_commits_only_on_release(timeline, source, x, expected):
    calls = observe(timeline)
    original = copy.deepcopy(timeline.document)
    start = press_body(timeline, source)
    for target in (start + QPoint(20, 0), QPoint(x, 40)):
        QTest.mouseMove(timeline, target)
    assert timeline._reorder['active']
    assert timeline.cursor().shape() == Qt.CursorShape.ClosedHandCursor
    assert timeline.document == original and calls == []
    assert timeline._preview_document is None  # No renders or timeline mutation while dragging.
    assert timeline._reorder['before'] == expected[1]
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=QPoint(x, 40))
    assert calls == [expected]
    assert timeline.document == original
    assert timeline._reorder is None and not timeline._reorder_scroll_timer.isActive()


def test_click_and_small_pointer_motion_do_not_reorder(timeline):
    calls = observe(timeline)
    point = timeline.rectangles()[1].center().toPoint()
    QTest.mouseMove(timeline, point)
    assert timeline.cursor().shape() == Qt.CursorShape.OpenHandCursor
    QTest.mousePress(timeline, Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(timeline, point + QPoint(2, 0))
    assert not timeline._reorder['active']
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=point + QPoint(2, 0))
    assert timeline.index == 1 and timeline.selected_ids == {'beta'} and not calls


def test_releasing_at_same_order_or_outside_timeline_does_nothing(timeline):
    calls = observe(timeline)
    point = press_body(timeline, 0)
    QTest.mouseMove(timeline, point + QPoint(20, 0))
    assert timeline._reorder['active'] and not timeline._reorder['changed']
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=point + QPoint(20, 0))
    assert not calls
    press_body(timeline, 0)
    QTest.mouseMove(timeline, QPoint(550, 140))
    assert not timeline._reorder['valid']
    assert timeline.cursor().shape() == Qt.CursorShape.ForbiddenCursor
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=QPoint(550, 140))
    assert not calls


@pytest.mark.parametrize('cancel', ['escape', 'hide', 'document'])
def test_cancel_clears_pending_drag_without_an_edit(timeline, cancel):
    calls = observe(timeline)
    original = copy.deepcopy(timeline.document)
    press_body(timeline, 0)
    QTest.mouseMove(timeline, QPoint(599, 40))
    assert timeline._reorder['changed']
    if cancel == 'escape': QTest.keyClick(timeline, Qt.Key.Key_Escape)
    elif cancel == 'hide': timeline.hide()
    else: timeline.set_document(copy.deepcopy(original), 0)
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=QPoint(599, 40))
    assert calls == [] and timeline._reorder is None
    assert not timeline._reorder_scroll_timer.isActive()
    assert timeline.document == original


def test_shift_and_command_selection_can_drag_together_in_original_order(timeline):
    calls = observe(timeline)
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=timeline.rectangles()[0].center().toPoint())
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier,
                     timeline.rectangles()[1].center().toPoint())
    assert timeline.selected_ids == {'alpha', 'beta'}
    press_body(timeline, 0)
    assert timeline._reorder['identifiers'] == ('alpha', 'beta')
    QTest.mouseMove(timeline, QPoint(599, 40))
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=QPoint(599, 40))
    assert calls == [(('alpha', 'beta'), None)]
    assert timeline.selected_ids == {'alpha', 'beta'}
    # A click without dragging still selects just that section.
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=timeline.rectangles()[0].center().toPoint())
    assert timeline.selected_ids == {'alpha'}
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.MetaModifier,
                     timeline.rectangles()[2].center().toPoint())
    press_body(timeline, 2)
    assert timeline._reorder['identifiers'] == ('alpha', 'gamma')
    QTest.mouseMove(timeline, QPoint(200, 40))
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=QPoint(200, 40))
    assert calls[-1] == (('alpha', 'gamma'), 'beta')


def test_shared_repeat_drags_its_original_and_marker_uses_legal_boundary(timeline):
    doc = document()
    doc['timeline_loops'] = [{'sections': ['alpha', 'beta'], 'loops': 2}]
    timeline.set_document(doc)
    calls = observe(timeline)
    assert [item[0] for item in section_placements(doc)] == [0, 1, 0, 1, 2]
    press_body(timeline, 2)  # Repeated alpha.
    target = timeline.rectangles()[3].center().toPoint()
    QTest.mouseMove(timeline, target)
    assert timeline._reorder['before'] == 'gamma'
    assert timeline._reorder['marker'] == pytest.approx(10 * timeline.pixels_per_second())
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=target)
    assert calls == [(('alpha',), 'gamma')]
    assert timeline.document == doc


def test_right_edge_still_stretches_and_never_starts_a_reorder(timeline):
    calls = observe(timeline)
    resized = []
    timeline.durationRequested.connect(lambda key, duration: resized.append((key, duration)))
    point = edge_point(timeline, 0)
    QTest.mousePress(timeline, Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(timeline, point + QPoint(30, 0))
    assert timeline._reorder is None and timeline._resize is not None
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=point + QPoint(30, 0))
    assert resized == [('alpha', 2.32)] and calls == []


def test_reorder_autoscroll_tracks_pointer_without_changing_document(app, monkeypatch):
    doc = document()
    doc['sections'] *= 4
    doc['sections'] = [dict(section, id=f'section-{i}') for i, section in enumerate(doc['sections'])]
    widget = SectionTimeline(); widget.set_document(doc)
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(widget)
    scroll.resize(320, 115); scroll.show(); app.processEvents()
    try:
        calls = observe(widget)
        point = press_body(widget, 0)
        QTest.mouseMove(widget, point + QPoint(30, 0))
        pointer = scroll.viewport().mapToGlobal(QPoint(scroll.viewport().width() + 20, 40))
        monkeypatch.setattr('synth_composer_ui.QCursor.pos', lambda: pointer)
        before = scroll.horizontalScrollBar().value()
        widget._auto_scroll_reorder()
        assert scroll.horizontalScrollBar().value() > before
        assert widget.document == doc and calls == []
        QTest.keyClick(widget, Qt.Key.Key_Escape)
        assert not widget._reorder_scroll_timer.isActive()
    finally:
        scroll.close(); app.processEvents()


@pytest.mark.parametrize('short_index', [0, 1])
def test_short_section_body_is_not_swallowed_by_its_or_neighboring_resize_handle(timeline, short_index):
    doc = document()
    doc['sections'][short_index]['duration'] = .04
    timeline.set_document(doc)
    calls = observe(timeline)
    point = press_body(timeline, short_index)
    assert timeline._resize is None and timeline._reorder is not None
    QTest.mouseMove(timeline, QPoint(timeline.width() - 1, 40))
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=QPoint(timeline.width() - 1, 40))
    assert calls == [((doc['sections'][short_index]['id'],), None)]
