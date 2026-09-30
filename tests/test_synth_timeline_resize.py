"""Timeline edge gestures request one frame-snapped, loop-aware edit."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea

from synth_composer_ui import SectionTimeline
from synth_composition import section_placements


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def document():
    return {'fps':25,'phrases':{'one':{'name':'One'},'two':{'name':'Two'}},
            'sections':[{'id':'alpha','phrase':'one','duration':2.,'loops':1},
                        {'id':'beta','phrase':'two','duration':3.,'loops':1},
                        {'id':'gamma','phrase':'one','duration':1.,'loops':1}]}


@pytest.fixture
def timeline(app):
    widget = SectionTimeline()
    widget.resize(600,90)
    widget.set_document(document())
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    app.processEvents()


def edge_point(widget,occurrence):
    end = section_placements(widget.document)[occurrence][2]
    return QPoint(min(widget.width()-1,round(end*widget.pixels_per_second())),40)


def observe(widget):
    calls = []
    widget.durationRequested.connect(lambda identifier,duration: calls.append((identifier,duration)))
    return calls


def test_shared_edge_hover_selects_left_and_previews_ripple_without_editing_document(timeline):
    calls = observe(timeline)
    original = copy.deepcopy(timeline.document)
    point = edge_point(timeline,0)
    before = timeline.rectangles()
    scale = timeline.pixels_per_second()
    QTest.mouseMove(timeline,point)
    assert timeline.cursor().shape() == Qt.CursorShape.SizeHorCursor
    assert timeline.edge_at(QPointF(point)) == 0
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    QTest.mouseMove(timeline,point+QPoint(37,0))
    assert timeline.index == 0
    assert timeline.document == original
    assert calls == []
    assert timeline.pixels_per_second() == scale
    assert timeline.display_document()['sections'][0]['duration'] == 2.36
    after = timeline.rectangles()
    assert after[0].width()-before[0].width() == pytest.approx(.36*scale)
    assert after[1].left()-before[1].left() == pytest.approx(.36*scale)
    assert after[2].left()-before[2].left() == pytest.approx(.36*scale)
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=point+QPoint(37,0))
    assert calls == [('alpha',2.36)]
    assert timeline.document == original
    assert timeline._preview_document is None


def test_release_emits_only_final_value_and_parent_can_replace_document_synchronously(timeline):
    calls = observe(timeline)
    original = copy.deepcopy(timeline.document)
    # Real selection refreshes the timeline, and release refreshes it again.
    timeline.selected.connect(lambda index: timeline.set_document(timeline.document,index))
    def commit(identifier,duration):
        updated = copy.deepcopy(timeline.document)
        next(s for s in updated['sections'] if s['id']==identifier)['duration'] = duration
        timeline.set_document(updated,timeline.index)
    timeline.durationRequested.connect(commit)
    point = edge_point(timeline,1)
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    for delta in (10,25,35): QTest.mouseMove(timeline,point+QPoint(delta,0))
    assert calls == []
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=point+QPoint(40,0))
    assert calls == [('beta',3.4)]
    assert timeline.document['sections'][1]['duration'] == 3.4
    assert original['sections'][1]['duration'] == 3.


def test_escape_noop_and_external_changes_cancel_cleanly(timeline):
    calls = observe(timeline)
    original = copy.deepcopy(timeline.document)
    minimum = timeline.minimumWidth()
    point = edge_point(timeline,0)
    QTest.mouseClick(timeline,Qt.MouseButton.LeftButton,pos=point)
    assert calls == []
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    QTest.mouseMove(timeline,point+QPoint(75,0))
    QTest.keyClick(timeline,Qt.Key.Key_Escape)
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=point+QPoint(75,0))
    assert calls == []
    assert timeline.document == original
    assert timeline.minimumWidth() == minimum
    assert not timeline._resize_scroll_timer.isActive()
    point = edge_point(timeline,0)
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    QTest.mouseMove(timeline,point+QPoint(25,0))
    timeline.set_document(copy.deepcopy(original),1)
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=point+QPoint(25,0))
    assert calls == [] and timeline._resize is None


def test_dragging_back_to_original_snapped_frame_does_not_emit(timeline):
    calls = observe(timeline)
    point = edge_point(timeline,0)
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    QTest.mouseMove(timeline,point+QPoint(30,0))
    QTest.mouseRelease(timeline,Qt.MouseButton.LeftButton,pos=point+QPoint(1,0))
    assert calls == []


def test_repeated_view_tracks_pointer_and_edits_same_section_once(timeline):
    doc = document()
    doc['sections'][0]['loops'] = 2
    doc['timeline_loops'] = [{'sections':['alpha','beta'],'loops':3}]
    timeline.set_document(doc)
    calls = observe(timeline)
    point = edge_point(timeline,2)  # Second group pass of alpha.
    scale = timeline.pixels_per_second()
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    drag = timeline._resize
    assert drag['edge_factor'] == 4  # Two plays in each of two prior occurrences.
    timeline._update_resize(point.x()+scale*4)
    assert timeline.display_document()['sections'][0]['duration'] == 3.
    old = section_placements(doc)
    new = section_placements(timeline.display_document())
    assert new[2][2]-old[2][2] == 4.
    assert all(end-start == 6. for index,start,end,_ in new if index == 0)
    assert calls == []
    timeline._finish_resize(True)
    assert calls == [('alpha',3.)]
    assert doc['sections'][0]['duration'] == 2.


def test_frame_minimum_section_maximum_and_arrangement_cap_include_every_loop(timeline):
    calls = observe(timeline)
    point = edge_point(timeline,0)
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    timeline._update_resize(point.x()-1e7)
    assert timeline.display_document()['sections'][0]['duration'] == 1/25
    timeline._update_resize(point.x()+1e7)
    assert timeline.display_document()['sections'][0]['duration'] == 300.
    timeline._finish_resize(False)
    doc = document()
    doc['sections'] = doc['sections'][:2]
    doc['sections'][0].update(duration=10.,loops=2)
    doc['sections'][1]['duration'] = 100.
    doc['timeline_loops'] = [{'sections':['alpha','beta'],'loops':20}]
    timeline.set_document(doc)
    point = edge_point(timeline,2)
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    timeline._update_resize(point.x()+1e7)
    assert timeline.display_document()['sections'][0]['duration'] == 40.
    assert section_placements(timeline.display_document())[-1][2] == 3600.
    timeline._finish_resize(True)
    assert calls == [('alpha',40.)]


def test_modified_clicks_and_right_click_keep_selection_and_loop_gestures(timeline):
    calls = observe(timeline)
    QTest.mouseClick(timeline,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ShiftModifier,edge_point(timeline,1))
    assert timeline.selected_indices() == [0,1]
    QTest.mouseClick(timeline,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.MetaModifier,edge_point(timeline,2))
    assert timeline.selected_indices() == [0,1,2]
    QTest.mouseClick(timeline,Qt.MouseButton.RightButton,pos=timeline.rectangles()[1].center().toPoint())
    assert timeline.selected_indices() == [0,1,2]
    assert timeline._resize is None and calls == []
    loops = []
    timeline.loopRequested.connect(lambda ids,count: loops.append((ids,count)))
    menu = timeline.make_context_menu()
    menu.actions()[0].trigger()
    assert loops == [(('alpha','beta','gamma'),0)]
    menu.close()


def test_last_edge_gutter_and_autoscroll_preserve_the_frozen_scale(app,monkeypatch):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.resize(420,115)
    timeline = SectionTimeline()
    timeline.set_document(document())
    scroll.setWidget(timeline)
    scroll.show()
    app.processEvents()
    point = edge_point(timeline,2)
    scale = timeline.pixels_per_second()
    QTest.mousePress(timeline,Qt.MouseButton.LeftButton,pos=point)
    app.processEvents()
    assert scroll.horizontalScrollBar().maximum() > 0
    QTest.mouseMove(timeline,point+QPoint(5,0))
    pointer = scroll.viewport().mapToGlobal(QPoint(scroll.viewport().width()+10,40))
    monkeypatch.setattr('synth_composer_ui.QCursor.pos',lambda: pointer)
    before = scroll.horizontalScrollBar().value()
    timeline._auto_scroll_resize()
    assert scroll.horizontalScrollBar().value() > before
    assert timeline.pixels_per_second() == scale
    assert timeline.display_document()['sections'][-1]['duration'] > 1.
    QTest.keyClick(timeline,Qt.Key.Key_Escape)
    assert timeline.document['sections'][-1]['duration'] == 1.
    assert not timeline._resize_scroll_timer.isActive()
    scroll.close()
    app.processEvents()
