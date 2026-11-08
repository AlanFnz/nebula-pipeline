"""Short-block discovery changes navigation, never authored timing or rendering."""
import copy
import pytest

from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from synth_montage import normalize_montage, save_montage, load_montage
from synth_montage_blocks import block_details, clip_label
from test_synth_montage_selection import window
from test_synth_montage import project, montage
from test_synth_navigation import workspace


def dense_document(window):
    doc = copy.deepcopy(window.document)
    next(iter(doc['assets'].values()))['document']['sections'][0]['duration'] = 30
    base = doc['clips'][0]
    doc['clips'] = [dict(base, id='intro', name='Introduction', in_frame=0, frames=600)]
    for i in range(30):
        doc['clips'].append(dict(base, id=f'shot-{i}', name=f'Crowd {i} · a complete descriptive name',
                                 in_frame=0, frames=4+i%3))
    doc['clips'][5]['name'] = 'Canarias · banderas avanzando'
    doc['clips'][18]['name'] = 'Novi Sad · bengalas y celebración'
    doc['clips'][30]['name'] = 'Argentina · multitud frente al Congreso'
    doc['markers'] = [dict(frame=602, name='A complete marker name that will not fit over a four-frame shot')]
    window.document = normalize_montage(doc); window.clean = copy.deepcopy(window.document)
    window.refresh(); window.resize(1280, 800); window.material_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    return copy.deepcopy(window.document)


def visible_items(window):
    listing = window.block_browser.list
    return [listing.item(i) for i in range(listing.count()) if not listing.item(i).isHidden()]


def click_item(window, item):
    listing = window.block_browser.list; listing.scrollToItem(item); QApplication.processEvents()
    QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton,
                     pos=listing.visualItemRect(item).center())


def test_find_three_short_blocks_including_offscreen_without_changing_playback(window, tmp_path):
    original = dense_document(window); window.seek(7)
    window.library.setCurrentRow(0); source = window.library_key()
    for name, key in [('Canarias', 'shot-4'), ('Novi Sad', 'shot-17'), ('Argentina', 'shot-29')]:
        window.block_browser.search.setText(name)
        items = visible_items(window); assert len(items) == 1
        click_item(window, items[0])
        assert window.selected == {key}
        assert window.frame == 7 and not window.timer.isActive() and window.timeline.scale == 65
        assert window.library_key() == source and name in window.block_summary.text()
        rect = next(r for c,a,b,r in window.timeline.rectangles() if c['id'] == key)
        left = window.scroll.horizontalScrollBar().value()
        assert left <= rect.center().x() <= left + window.scroll.viewport().width()
        assert window.document == original and not window.undo_stack
    assert window.scroll.horizontalScrollBar().value() > 0
    save_montage(tmp_path/'unchanged.json', window.document)
    assert load_montage(tmp_path/'unchanged.json') == original


def test_timeline_keyboard_and_list_share_identity_and_complete_information(window, monkeypatch):
    dense_document(window); window.select_clip('shot-4'); window.timeline.setFocus()
    QTest.keyClick(window.timeline, Qt.Key.Key_Right)
    assert window.selected == {'shot-5'}
    item = window.block_browser.list.currentItem()
    assert item.data(Qt.ItemDataRole.UserRole) == 'shot-5' and item.isSelected()
    assert item.toolTip() == window.block_summary.text() == window.timeline.accessibleDescription()
    assert 'Duration 6 frames / 0.200s' in item.text()
    opened = []; monkeypatch.setattr(window, 'edit_clip', opened.append)
    QTest.keyClick(window.block_browser.list, Qt.Key.Key_Return)
    assert opened == ['shot-5']


def test_filter_does_not_change_target_or_pending_timing_and_clear_restores_rows(window):
    original = dense_document(window); window.select_clip('shot-4'); window.length.setValue(9)
    window.block_browser.search.setText('nothing matches')
    assert not visible_items(window) and 'No matching blocks' in window.block_browser.hint.text()
    assert window.selected == {'shot-4'} and window.has_timing_draft()
    window.block_browser.search.clear()
    assert len(visible_items(window)) == 31 and window.length.value() == 9
    assert window.block_browser.list.selectedItems()[0].data(Qt.ItemDataRole.UserRole) == 'shot-4'
    assert window.document == original


def test_block_list_respects_pending_draft_stay_then_discard(window, monkeypatch):
    original = dense_document(window); window.select_clip('shot-4'); window.length.setValue(9)
    window.block_browser.search.setText('Argentina'); item = visible_items(window)[0]
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'stay')
    click_item(window, item)
    assert window.selected == {'shot-4'} and window.length.value() == 9
    assert not item.isSelected()
    opened=[]; monkeypatch.setattr(window,'edit_clip',opened.append)
    window.edit_from_block_list('shot-29'); assert opened == []
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'discard')
    click_item(window, item)
    assert window.selected == {'shot-29'} and not window.has_timing_draft()
    assert window.document == original


def test_multiselection_and_reorder_undo_refresh_numbers_without_retargeting(window):
    original = dense_document(window); key = 'shot-4'; window.select_clip(key)
    window.move_clip(key, 1)
    assert window.document['clips'][1]['id'] == key
    assert window.block_summary.text().startswith('Block 02 · Canarias')
    assert window.block_browser.list.currentItem().text().startswith('Block 02 · Canarias')
    window.undo()
    assert window.document == original and window.selected == {key}
    assert window.block_summary.text().startswith('Block 06 · Canarias')
    window.redo(); assert window.block_summary.text().startswith('Block 02 · Canarias')
    window.undo(); window.select_all()
    assert len(window.block_browser.list.selectedItems()) == 31
    assert not window.show_block_button.isEnabled() and window.block_summary.text() == '31 blocks selected'
    window.block_browser.list.setCurrentRow(30, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    assert window.selected == {'shot-29'} and window.active_clip()['id'] == 'shot-29'


def test_show_and_previous_view_restore_zoom_scroll_keep_waveform_and_playhead(window):
    original = dense_document(window); window.select_clip('shot-29'); window.seek(9)
    window.wave.show(); QApplication.processEvents()
    window.scroll.horizontalScrollBar().setValue(123)
    view = (window.timeline.scale, window.scroll.horizontalScrollBar().value())
    window.show_selected_block(); QApplication.processEvents()
    assert window.timeline.scale > view[0] and window.previous_view_button.isEnabled()
    assert window.frame == 9 and not window.timer.isActive()
    assert window.wave.width() == round(sum(c['frames'] for c in original['clips']) / 30 * window.timeline.scale)
    assert window.wave.mapTo(window.tracks, window.wave.rect().topLeft()).x() == 12
    # A second focus retains the original overview, rather than losing it.
    window.select_clip('shot-17'); window.show_selected_block(); QApplication.processEvents()
    window.restore_timeline_view(); QApplication.processEvents()
    assert (window.timeline.scale, window.scroll.horizontalScrollBar().value()) == view
    assert window.zoom_control.value() == view[0] and not window.previous_view_button.isEnabled()
    assert window.document == original and not window.undo_stack


def test_marker_focus_shows_complete_name_without_seeking(window):
    original = dense_document(window); window.seek(3)
    window.marker_list.setCurrentRow(0); marker = window.marker_list.currentItem()
    assert original['markers'][0]['name'] in window.marker_context.text()
    assert marker.toolTip() == window.marker_context.text() and window.frame == 3
    window.refresh()
    assert window.marker_list.currentRow() == 0 and original['markers'][0]['name'] in window.marker_context.text()
    window.marker_list.itemDoubleClicked.emit(window.marker_list.currentItem())
    assert window.frame == 602 and window.document == original


def test_clicking_a_short_cut_near_viewport_edge_does_not_scroll_or_edit(window):
    original = dense_document(window); window.zoom(220); QApplication.processEvents()
    key = 'shot-4'
    rect = next(r for c,a,b,r in window.timeline.rectangles() if c['id'] == key)
    window.scroll.horizontalScrollBar().setValue(round(rect.left()) - 1)
    position = window.scroll.horizontalScrollBar().value()
    QTest.mouseClick(window.timeline, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
    assert window.selected == {key} and window.document == original and not window.undo_stack
    assert window.scroll.horizontalScrollBar().value() == position


def test_short_labels_preserve_proportional_width_and_no_partial_number(window):
    original = dense_document(window); metrics = window.timeline.fontMetrics()
    assert clip_label(8, 'Long shot name', metrics.horizontalAdvance('08'), metrics) == '08'
    assert clip_label(8, 'Long shot name', metrics.horizontalAdvance('08')-1, metrics) == ''
    assert clip_label(8, 'Name', 500, metrics) == '08 · Name'
    for clip,a,b,rect in window.timeline.rectangles():
        assert rect.width() == pytest.approx(max(2, (b-a)/30*window.timeline.scale-2))
    assert 'Start 00:24.800' in block_details(original, 'shot-29')
    assert window.document == original


def test_open_from_list_and_return_keep_document_selection_and_view(workspace):
    root, window, app = workspace
    original = dense_document(window)
    window.block_browser.search.setText('Argentina')
    click_item(window, visible_items(window)[0]); window.seek(9); window.zoom(150)
    app.processEvents(); window.scroll.horizontalScrollBar().setValue(120)
    view = (window.timeline.scale, window.scroll.horizontalScrollBar().value(), window.frame)
    QTest.keyClick(window.block_browser.list, Qt.Key.Key_Return); app.processEvents()
    assert root.workspace_navigation.editor is not None
    assert root.workspace_navigation.return_to_montage(); app.processEvents()
    assert window.selected == {'shot-29'} and window.document == original
    assert (window.timeline.scale, window.scroll.horizontalScrollBar().value(), window.frame) == view
    assert window.block_browser.search.text() == 'Argentina' and not window.undo_stack
