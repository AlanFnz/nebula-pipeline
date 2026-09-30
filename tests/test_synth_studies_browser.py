"""Focused Qt browser interaction and isolated thumbnail/cancellation coverage."""
import copy
from io import BytesIO
import os
from pathlib import Path
import threading
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import pytest

from media import Cancellation
from synth_composition import compile_composition
from synth_sequence import render_sequence_frame
from synth_starters import STARTERS, starter_composition
from synth_studies import save_study, set_studies_removed
from synth_studies_ui import PREVIEW_BOUNDS, ROW_BOUNDS, StudiesDialog
from synth_study_thumbnails import MAX_PENDING, StudyThumbnailService, ThumbnailCache, fitted_size, render_thumbnail, thumbnail_key
from synth_video import video_composition
from test_synth_video import clip


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def settle(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate(): return
        time.sleep(.01)
    assert predicate(), 'Qt worker did not settle before the timeout'


class FakeThumbnails(QObject):
    ready = Signal(int, str, object, object, str)
    def __init__(self):
        super().__init__(); self.generation = 0; self.requests = []; self.closed = False
    def reset(self): self.generation += 1; return self.generation
    def request(self, jobs): self.requests.append(jobs)
    def close(self, *_args): self.closed = True; self.reset()
    def start(self): self.closed = False


def select(dialog, identifier):
    row = next(row for row in range(dialog.table.rowCount())
               if dialog.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == identifier)
    dialog.table.selectRow(row)
    return row


def favorite_click(dialog, row):
    item = dialog.table.item(row, 4)
    dialog.table.scrollToItem(item)
    QApplication.processEvents()
    point = dialog.table.visualItemRect(item).center()
    QTest.mouseClick(dialog.table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QApplication.processEvents()


def test_browser_filters_favorites_selection_load_and_removed_multiselection(app, tmp_path):
    first = save_study(starter_composition('profile-doryphoros'), 'Duplicate PROFILE', tmp_path)
    second = save_study(starter_composition('profile-doryphoros'), 'Duplicate PROFILE', tmp_path)
    service = FakeThumbnails(); dialog = StudiesDialog(directory=tmp_path, thumbnail_service=service)
    requested = []; dialog.studyRequested.connect(requested.append)
    dialog.show(); QApplication.processEvents()
    assert requested == [] and not dialog.load.isEnabled()
    row = select(dialog, first)
    assert not requested and dialog.load.isEnabled() and 'Profiles' in dialog.details.text()
    assert dialog.table.item(row, 4).data(Qt.ItemDataRole.AccessibleTextRole).startswith('Favorite ')
    assert dialog.table.item(row, 4).flags() & Qt.ItemFlag.ItemIsUserCheckable
    favorite_click(dialog, row)
    dialog.search.setText('duplicate profile')
    dialog.category.setCurrentIndex(dialog.category.findData('Profiles'))
    assert dialog.table.rowCount() == 2
    dialog.favorites_only.setChecked(True)
    assert dialog.table.rowCount() == 1
    select(dialog, first); dialog.load.click()
    assert requested == [first] and dialog.isVisible()
    dialog._double_click(dialog.table.item(0, 0)); assert requested == [first, first]
    dialog.search.clear(); dialog.favorites_only.setChecked(False)
    dialog.category.setCurrentIndex(0)
    dialog.table.sortItems(0, Qt.SortOrder.AscendingOrder)
    names = [dialog.table.item(row, 0).text().casefold() for row in range(dialog.table.rowCount())]
    assert names == sorted(names)
    dialog.search.setText('Duplicate')
    dialog.table.selectAll(); dialog.action.click()
    assert dialog.table.rowCount() == 0 and 'No studies match' in dialog.status.text()
    dialog.show_removed.setChecked(True)
    assert dialog.table.rowCount() == 2
    select(dialog, first); assert not dialog.load.isEnabled()
    dialog.request_load(); assert requested == [first, first]
    dialog.table.selectAll(); dialog.action.click()
    assert dialog.table.rowCount() == 0
    dialog.show_removed.setChecked(False); dialog.favorites_only.setChecked(True)
    assert dialog.table.rowCount() == 1
    select(dialog, first)
    set_studies_removed([first], directory=tmp_path)
    dialog.request_load(); assert requested == [first, first]
    dialog.close()


def test_browser_laziness_stale_delivery_errors_pause_and_hide(app, tmp_path):
    service = FakeThumbnails(); dialog = StudiesDialog(directory=tmp_path, thumbnail_service=service)
    assert service.requests == []
    dialog.show(); dialog._request_visible()
    assert 0 < len(service.requests[-1]) < len(STARTERS)
    select(dialog, 'profile-doryphoros'); dialog._request_visible()
    assert service.requests[-1][0] == ('profile-doryphoros', PREVIEW_BOUNDS)
    old = service.generation
    dialog.search.setText('Doryphoros')
    png = BytesIO(); Image.new('RGB', (20, 10), 'green').save(png, format='PNG')
    dialog._thumbnail_ready(old, 'profile-doryphoros', PREVIEW_BOUNDS, png.getvalue(), '')
    assert dialog.preview.pixmap().isNull()
    dialog._thumbnail_ready(service.generation, 'profile-doryphoros', PREVIEW_BOUNDS, None, 'Preview unavailable: missing footage')
    assert 'missing footage' in dialog.preview.text()
    count = len(service.requests); generation = service.generation
    dialog.set_rendering_paused(True); dialog._request_visible()
    assert service.generation > generation and len(service.requests) == count
    dialog.set_rendering_paused(False); dialog._request_visible()
    assert len(service.requests) > count
    generation = service.generation; dialog.hide()
    assert service.generation > generation
    dialog.close()


def test_queue_bounds_cancellation_and_reopen_uncached_result(app, tmp_path):
    started = threading.Event(); released = threading.Event(); calls = []
    def renderer(project, bounds, cancel, provider):
        calls.append(project['name']); started.set()
        while not released.wait(.01): cancel.check()
        cancel.check()
        output = BytesIO(); Image.new('RGB', (24, 12), 'green').save(output, format='PNG')
        return output.getvalue()
    service = StudyThumbnailService(tmp_path, cache_directory=tmp_path / 'cache', renderer=renderer)
    results = []; service.ready.connect(lambda *args: results.append(args))
    service.request([('refined', ROW_BOUNDS)])
    assert started.wait(2)
    service.request([(key, ROW_BOUNDS) for key, _label, _factory in STARTERS])
    assert service.pending_count <= MAX_PENDING
    service.reset(); released.set()
    settle(lambda: service.state.active_job is None)
    assert results == []
    service.close(); service.start()
    service.request([('approved', PREVIEW_BOUNDS)])
    settle(lambda: bool(results))
    assert results[0][1] == 'approved'
    assert results[0][0] == service.generation
    before = len(calls)
    service.reset(); service.request([('approved', PREVIEW_BOUNDS)])
    settle(lambda: len(results) == 2)
    assert len(calls) == before  # A worker cache hit must skip compiling/rendering.
    assert service.state.results.maxsize == 1
    service.close()


def test_reusable_browser_reopens_worker_and_renders_uncached_selection(app, tmp_path):
    calls = []
    def renderer(project, bounds, cancel, provider):
        calls.append(project['name']); cancel.check()
        output = BytesIO(); Image.new('RGB', (32, 18), 'green').save(output, format='PNG')
        return output.getvalue()
    service = StudyThumbnailService(tmp_path, cache_directory=tmp_path / 'cache', renderer=renderer)
    dialog = StudiesDialog(directory=tmp_path, thumbnail_service=service)
    dialog.search.setText('Doryphoros'); dialog.show(); select(dialog, 'profile-doryphoros')
    settle(lambda: ('profile-doryphoros', PREVIEW_BOUNDS) in dialog._images)
    dialog.close(); assert service.state.stopped
    dialog.search.setText('opium'); dialog.show(); select(dialog, 'text-opium')
    settle(lambda: ('text-opium', PREVIEW_BOUNDS) in dialog._images)
    assert any('opium' in name.lower() for name in calls)
    dialog.close()


def test_real_thumbnail_aspect_sample_cache_invalidation_and_unwritable_cache(app, tmp_path):
    project = starter_composition('profile-doryphoros')
    before = copy.deepcopy(project)
    data = render_thumbnail(project, ROW_BOUNDS)
    image = Image.open(BytesIO(data))
    assert image.size == fitted_size(project['canvas'], ROW_BOUNDS)
    sequence = compile_composition(project)
    expected = render_sequence_frame(sequence, sequence['duration'] / 3, image.size)
    assert image.tobytes() == expected.tobytes() and project == before
    key = thumbnail_key(project, ROW_BOUNDS, tmp_path)
    changed = copy.deepcopy(project); changed['seed'] += 1
    assert thumbnail_key(changed, ROW_BOUNDS, tmp_path) != key
    source = tmp_path / 'image.dat'; source.write_bytes(b'one')
    changed['external'] = {'path': str(source)}
    first = thumbnail_key(changed, ROW_BOUNDS, tmp_path)
    source.write_bytes(b'changed-source')
    assert thumbnail_key(changed, ROW_BOUNDS, tmp_path) != first
    blocked = tmp_path / 'blocked'; blocked.write_text('not a directory')
    cache = ThumbnailCache(blocked, memory_entries=1)
    cache.put(key, data); assert cache.get(key) == data
    cache.put('other', data); assert len(cache.memory) == 1
    disk = ThumbnailCache(tmp_path / 'disk', disk_entries=1)
    disk.put(key, data); disk.put('other', data)
    assert len(list((tmp_path / 'disk').glob('*.png'))) == 1
    assert ThumbnailCache(tmp_path / 'disk').get('other') == data


def test_real_video_thumbnail_and_missing_source_placeholder(app, clip, tmp_path):
    project = video_composition(clip)
    data = render_thumbnail(project, ROW_BOUNDS)
    image = Image.open(BytesIO(data))
    sequence = compile_composition(project)
    assert image.tobytes() == render_sequence_frame(sequence, sequence['duration'] / 3, image.size).tobytes()
    key = save_study(project, 'Missing clip', tmp_path)
    loaded = __import__('synth_studies').study_composition(key, tmp_path)
    Path(loaded['footage']['path']).unlink()
    service = StudyThumbnailService(tmp_path, cache_directory=tmp_path / 'cache')
    dialog = StudiesDialog(directory=tmp_path, thumbnail_service=service)
    dialog.search.setText('Missing clip'); dialog.show(); select(dialog, key)
    settle(lambda: 'missing' in dialog.preview.text().lower(), timeout=6)
    assert dialog.load.isEnabled() and 'missing' in dialog.table.item(0, 0).toolTip().lower()
    favorite_click(dialog, 0); dialog.action.click()
    assert dialog.table.rowCount() == 0
    dialog.close()


def test_blank_thumbnail_uses_only_one_deterministic_fallback(tmp_path, monkeypatch):
    import synth_study_thumbnails
    project = starter_composition('profile-doryphoros'); samples = []
    sequence = compile_composition(project)
    def blank(sequence, time_seconds, size, provider):
        samples.append(time_seconds)
        return Image.new('RGB', size, 'black')
    monkeypatch.setattr(synth_study_thumbnails, 'render_sequence_frame', blank)
    render_thumbnail(project, ROW_BOUNDS)
    assert samples == [sequence['duration'] / 3, sequence['duration'] * 2 / 3]


def test_frozen_renderer_build_identity_invalidates_cache(tmp_path, monkeypatch):
    import synth_study_thumbnails
    executable = tmp_path / 'Nebula Studio'; executable.write_bytes(b'build-one')
    monkeypatch.setattr(synth_study_thumbnails.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(synth_study_thumbnails.sys, 'executable', str(executable))
    project = starter_composition('profile-doryphoros')
    first = thumbnail_key(project, ROW_BOUNDS, tmp_path)
    executable.write_bytes(b'build-two-with-updated-renderer')
    assert thumbnail_key(project, ROW_BOUNDS, tmp_path) != first


def test_favorite_cells_support_keyboard_sorting_and_deferred_cleanup(app, tmp_path):
    def exercise():
        dialog = StudiesDialog(directory=tmp_path, thumbnail_service=FakeThumbnails())
        dialog.show(); QApplication.processEvents()
        requested = []; dialog.studyRequested.connect(requested.append)
        row = select(dialog, 'profile-doryphoros')
        dialog.table.setCurrentCell(row, 4)
        QTest.keyClick(dialog.table, Qt.Key.Key_Space)
        QApplication.processEvents()
        assert dialog.table.currentColumn() == 4
        row = dialog.table.currentRow()
        assert dialog.table.item(row, 4).checkState() == Qt.CheckState.Checked
        assert dialog.table.cellWidget(row, 4) is None
        QTest.keyClick(dialog.table, Qt.Key.Key_Space); QApplication.processEvents()
        row = select(dialog, 'profile-doryphoros')
        assert dialog.table.item(row, 4).checkState() == Qt.CheckState.Unchecked
        favorite_click(dialog, row)
        assert dialog.table.item(row, 4).checkState() == Qt.CheckState.Checked
        dialog.table.sortItems(4, Qt.SortOrder.DescendingOrder)
        assert dialog.table.item(0, 4).checkState() == Qt.CheckState.Checked
        assert 'profile-doryphoros' in dialog.selected_identifiers()
        from synth_studies import study_records
        for turn in range(30):
            dialog.search.setText('profile')
            row = select(dialog, 'profile-doryphoros'); favorite_click(dialog, row)
            expected = turn % 2 == 1
            assert next(entry for entry in study_records(tmp_path)
                        if entry.identifier == 'profile-doryphoros').favorite == expected
            dialog.search.clear()
        row = select(dialog, 'profile-doryphoros')
        point = dialog.table.visualItemRect(dialog.table.item(row, 4)).center()
        QTest.mouseDClick(dialog.table.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert requested == []
        dialog.close(); dialog.show(); dialog.close()
    exercise()
    # The real popup event loop flushes deferred deletions after test locals leave scope.
    # Do this without retaining the old browser's QObject ownership graph.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QTest.qWait(1)
