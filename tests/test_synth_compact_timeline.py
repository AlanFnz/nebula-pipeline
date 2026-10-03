"""Compact lane geometry and editing scope stay separate from arrangement gestures."""
import copy

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest

from studio_theme import COLORS
from test_synth_timeline_resize import app, document, timeline


def test_compact_blocks_share_paint_and_hit_bounds(timeline):
    assert timeline.height() == 62
    for occurrence, rect in enumerate(timeline.rectangles()):
        assert rect.height() == 46
        assert timeline.occurrence_at(rect.center()) == occurrence
        edge = QPointF(rect.right() + 2, rect.center().y())
        assert timeline.edge_at(edge) == occurrence
        for y in (rect.top() - 1, rect.bottom() + 1):
            assert timeline.edge_at(QPointF(edge.x(), y)) is None
            assert timeline.occurrence_at(QPointF(rect.center().x(), y)) is None


def test_edit_fill_is_independent_of_multi_selection_and_does_not_edit(timeline):
    original = copy.deepcopy(timeline.document)
    timeline.select_at(1, Qt.KeyboardModifier.ShiftModifier)
    selected = set(timeline.selected_ids)

    def fills():
        image = timeline.grab().toImage()
        return [image.pixelColor(round(rect.left() + 10), round(rect.bottom() - 3))
                for rect in timeline.rectangles()]

    assert fills() == [QColor(COLORS['panel'])] * 3
    timeline.set_editing_section('beta')
    assert fills() == [QColor(COLORS['panel']), QColor(COLORS['selected']), QColor(COLORS['panel'])]
    # Arrangement/playback selection can move without changing inspector scope.
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton,
                     pos=timeline.rectangles()[2].center().toPoint())
    assert timeline.selected_ids == {'gamma'}
    assert timeline.editing_section_id == 'beta'
    timeline.selected_ids = selected
    timeline.set_editing_section(None)
    assert fills() == [QColor(COLORS['panel'])] * 3
    image = timeline.grab().toImage()
    rect = timeline.rectangles()[1]
    assert image.pixelColor(round(rect.left()), round(rect.top() + 3)) != QColor(COLORS['panel'])
    assert timeline.selected_ids == selected and timeline.document == original
    assert 'Editing: Whole clip' in timeline.accessibleDescription()


def test_narrow_long_names_and_metadata_stay_bounded_and_discoverable(timeline):
    doc = document()
    name = 'A very long phrase identity that must remain discoverable'
    doc['phrases']['one']['name'] = name
    doc['sections'][0].update(duration=.04, loops=2)
    doc['timeline_loops'] = [{'sections': ['alpha', 'beta'], 'loops': 2}]
    timeline.set_document(doc)
    for rect in timeline.rectangles():
        title, metadata = timeline.text_rectangles(rect)
        assert title.width() >= 0 and metadata.width() >= 0
        assert title.left() >= rect.left() and title.right() <= rect.right()
        assert metadata.top() >= rect.top() and metadata.bottom() <= rect.bottom()
    # A repeated occurrence still identifies its authored owner and full metadata.
    QTest.mouseMove(timeline, timeline.rectangles()[2].center().toPoint())
    assert name in timeline.toolTip()
    assert '0.04s per play' in timeline.toolTip()
    assert '2× total plays' in timeline.toolTip()
    assert 'Sequence repetition 2' in timeline.toolTip()
    assert name in timeline.accessibleDescription() and '(alpha)' in timeline.accessibleDescription()
    timeline.grab()  # Exercise clipping/elision during real Qt painting.


def test_edit_scope_fills_every_occurrence_and_clears_deleted_owner(timeline):
    doc = document()
    doc['timeline_loops'] = [{'sections': ['alpha', 'beta'], 'loops': 2}]
    timeline.set_document(doc)
    timeline.set_editing_section('alpha')
    image = timeline.grab().toImage()
    for occurrence in (0, 2):
        rect = timeline.rectangles()[occurrence]
        assert image.pixelColor(round(rect.left() + 10), round(rect.bottom() - 3)) == QColor(COLORS['selected'])
    doc['sections'] = doc['sections'][1:]
    doc.pop('timeline_loops')
    timeline.set_document(doc)
    assert timeline.editing_section_id is None
    assert 'Editing: Whole clip' in timeline.accessibleDescription()
