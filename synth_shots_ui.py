"""A readable storyboard of ordinary composition clips, including very short cuts."""
from collections import deque
from io import BytesIO
from queue import Empty, Full, Queue
import tempfile
import threading

from PySide6.QtCore import Qt, QSize, QRect, QSignalBlocker, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QListView, QLabel, QPushButton, QStyledItemDelegate, QStyle

from media import Cancellation
from studio_theme import COLORS
from studio_widgets import DoubleSpinBox, SpinBox
from synth_workspace_widgets import FlowLayout, inline
from synth_composition import section_ranges
from synth_sequence import render_sequence_frame
from synth_study_thumbnails import fitted_size
from synth_video import VideoFrameProvider


class _ThumbnailWork:
    """One worker, visible-first queue, one pending delivery; no GUI objects."""
    def __init__(self):
        self.condition = threading.Condition()
        self.jobs = deque()
        self.results = Queue(maxsize=1)
        self.cancel = None
        self.active = None
        self.stopped = False

    def stop(self):
        with self.condition:
            self.stopped = True
            self.jobs.clear()
            if self.cancel: self.cancel.cancel()
            self.condition.notify()

    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.jobs or self.stopped)
                if self.stopped: return
                generation, index, seconds, sequence = self.jobs.popleft()
                self.active = (generation, index)
                cancel = self.cancel = Cancellation()
            data = None
            try:
                with tempfile.TemporaryDirectory(prefix='nebula-shot-') as scratch:
                    with VideoFrameProvider(preview=True, cancel=cancel, directory=scratch, budget=8 * 1024**2) as provider:
                        size = fitted_size(sequence['canvas'], (288, 162))
                        frame = render_sequence_frame(sequence, seconds, size, provider)
                        cancel.check()
                        output = BytesIO(); frame.save(output, format='PNG'); data = output.getvalue()
            except Exception:
                # An unavailable source must not interfere with document editing.
                pass
            while not cancel.event.is_set():
                try:
                    self.results.put((generation, index, data), timeout=.05)
                    break
                except Full: continue
            with self.condition:
                self.active = None; self.cancel = None


class _ShotCard(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect.adjusted(3, 2, -3, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.fillRect(rect, QColor(COLORS['selected'] if selected else COLORS['panel']))
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon:
            icon.paint(painter, QRect(rect.x() + 8, rect.y() + 4, rect.width() - 16, 81))
        lines = index.data(Qt.ItemDataRole.DisplayRole).split('\n')
        painter.setFont(option.font); painter.setPen(QColor(COLORS['text']))
        title = option.fontMetrics.elidedText(lines[0], Qt.TextElideMode.ElideRight, rect.width() - 12)
        painter.drawText(QRect(rect.x() + 6, rect.y() + 87, rect.width() - 12, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        painter.setPen(QColor(COLORS['muted']))
        painter.drawText(QRect(rect.x() + 6, rect.y() + 104, rect.width() - 12, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lines[-1])
        painter.restore()


class ClipStoryboard(QWidget):
    selected = Signal(int)
    editRequested = Signal(int)
    durationRequested = Signal(str, float)
    loopsRequested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = self.sequence = None
        self.selected_index = 0
        self.generation = 0
        self.completed = set()
        self.work = _ThumbnailWork()
        self.thread = None
        self.destroyed.connect(lambda *_args, state=self.work: state.stop())
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(4)
        self.cards = QListWidget()
        self.cards.setItemDelegate(_ShotCard(self.cards))
        self.cards.setAccessibleName('Shots')
        self.cards.setToolTip('Click to preview a shot. Double-click or use Edit text to edit just that clip. Switch to Timeline to arrange clips and automation.')
        self.cards.setViewMode(QListView.ViewMode.IconMode)
        self.cards.setFlow(QListView.Flow.LeftToRight); self.cards.setWrapping(False)
        self.cards.setMovement(QListView.Movement.Static)
        self.cards.setResizeMode(QListView.ResizeMode.Adjust)
        self.cards.setIconSize(QSize(144, 81)); self.cards.setGridSize(QSize(168, 128))
        self.cards.setWordWrap(False); self.cards.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.cards.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.cards.setFixedHeight(150)
        self.cards.currentRowChanged.connect(self._select)
        self.cards.itemDoubleClicked.connect(lambda _item: self.editRequested.emit(self.cards.currentRow()))
        self.cards.horizontalScrollBar().valueChanged.connect(self.request_visible)
        layout.addWidget(self.cards)
        # The studio places this same footer beneath either Timeline or Shots.
        self.footer = QWidget(); self.footer.setAccessibleName('Selected clip timing')
        row = FlowLayout(self.footer, spacing=8)
        self.caption = QLabel(); row.addWidget(self.caption)
        self.duration = DoubleSpinBox(); self.duration.setDecimals(3); self.duration.setSuffix(' s')
        self.duration.setKeyboardTracking(False); self.duration.setAccessibleName('Selected clip duration per play')
        self.duration.setToolTip('Duration of this clip per play, rounded to a whole frame. Its movement and effects stretch with it. Undo restores the previous timing.')
        self.duration.setFixedWidth(112); self.duration.valueChanged.connect(self._resize)
        duration_label = QLabel('Duration'); duration_label.setBuddy(self.duration)
        row.addWidget(inline(duration_label, self.duration))
        self.loops = SpinBox(); self.loops.setRange(1, 32); self.loops.setSuffix(' ×')
        self.loops.setKeyboardTracking(False); self.loops.setFixedWidth(72)
        self.loops.setAccessibleName('Selected clip repeat count')
        self.loops.setToolTip('Total plays of the selected clip: 1 = once, 2 = twice. Repeats the clip without stretching its timing. Procedural motion and footage keep running. Undo restores the previous count.')
        self.loops.valueChanged.connect(self._repeat)
        repeat_label = QLabel('Repeat'); repeat_label.setBuddy(self.loops)
        row.addWidget(inline(repeat_label, self.loops))
        self.timing_summary = QLabel(); self.timing_summary.setObjectName('monitorMeta')
        self.timing_summary.setAccessibleName('Selected clip repeated duration')
        self.timing_summary.setToolTip('Duration per play × total plays = duration of this clip. Any repeated sequence adds further plays. The monitor shows the total project duration.')
        control_height = max(self.duration.sizeHint().height(), self.loops.sizeHint().height())
        self.caption.setMinimumHeight(control_height)
        self.timing_summary.setMinimumHeight(control_height)
        row.addWidget(self.timing_summary)
        self.edit = QPushButton('Edit text'); self.edit.setAccessibleName('Edit selected shot')
        self.edit.clicked.connect(lambda: self.editRequested.emit(self.selected_index))
        row.addWidget(self.edit); layout.addWidget(self.footer)
        self.timer = QTimer(self); self.timer.setInterval(40); self.timer.timeout.connect(self._deliver)

    def set_document(self, project, sequence, index=0):
        # Selection changes do not restart renders. A compiled sequence is immutable
        # for this widget and replaced by the studio after any document edit/undo.
        changed = sequence is not self.sequence
        self.project, self.sequence = project, sequence
        if changed:
            self.generation += 1; self.completed.clear()
            with self.work.condition:
                self.work.jobs.clear()
                if self.work.cancel: self.work.cancel.cancel()
            blank = QPixmap(144, 81); blank.fill(Qt.GlobalColor.black)
            with QSignalBlocker(self.cards):
                self.cards.clear()
                for i, section in enumerate(project['sections']):
                    states = [value for key, value in sequence['states'].items() if key.startswith(section['id'] + ':')]
                    text = next((s.get('overrides', {}).get('text.content') for s in states if s.get('overrides', {}).get('text.content')), '')
                    empty_override = any('text.content' in target.get('effects', {}).get('text', {}).get('params', {})
                                         for target in (project, section))
                    label = ' '.join(text.split()) or ('No text' if empty_override else project['phrases'][section['phrase']]['name'])
                    repeats = f" ×{section['loops']}" if section['loops'] > 1 else ''
                    title = f"{i + 1:02}  {label}\n{section['duration']:.3f} s{repeats}"
                    item = QListWidgetItem(QIcon(blank), title)
                    item.setToolTip(title + '\nDouble-click to edit this clip.')
                    self.cards.addItem(item)
        with QSignalBlocker(self.cards): self.cards.setCurrentRow(index)
        self.set_timing_context(project, index)
        self.request_visible()

    def set_timing_context(self, project, index):
        # Timeline mode needs timing controls, not thumbnail/card construction.
        self.project = project
        self.selected_index = index
        self._selection_controls(index)

    def _selection_controls(self, index):
        if not self.project or not 0 <= index < len(self.project['sections']): return
        section = self.project['sections'][index]
        self.caption.setText(f"Clip {index + 1} / {len(self.project['sections'])}")
        self.caption.setToolTip(self.project['phrases'][section['phrase']]['name'])
        with QSignalBlocker(self.duration):
            self.duration.setRange(1 / self.project['fps'], 300)
            self.duration.setSingleStep(1 / self.project['fps'])
            self.duration.setValue(section['duration'])
        loops = int(section.get('loops', 1))
        with QSignalBlocker(self.loops): self.loops.setValue(loops)
        seconds = lambda value: f'{value:.3f}'.rstrip('0').rstrip('.')
        self.timing_summary.setText(f"{seconds(section['duration'])} s × {loops} = {seconds(section['duration'] * loops)} s")

    def _select(self, index):
        if not self.project or index < 0: return
        self.set_timing_context(self.project, index); self.selected.emit(index)

    def _resize(self, value):
        if self.project and 0 <= self.selected_index < len(self.project['sections']):
            self.durationRequested.emit(self.project['sections'][self.selected_index]['id'], value)
            self._selection_controls(self.selected_index)

    def _repeat(self, value):
        if self.project and 0 <= self.selected_index < len(self.project['sections']):
            self.loopsRequested.emit(self.project['sections'][self.selected_index]['id'], value)
            self._selection_controls(self.selected_index)

    def request_visible(self, *_args):
        if not self.sequence or not self.isVisible() or self.work.stopped: return
        if self.thread is None:
            self.thread = threading.Thread(target=self.work.run, name='Shot thumbnails', daemon=True)
            self.thread.start(); self.timer.start()
        viewport = self.cards.viewport().rect()
        visible = [i for i in range(self.cards.count()) if self.cards.visualItemRect(self.cards.item(i)).intersects(viewport)]
        selected = self.cards.currentRow()
        wanted = list(dict.fromkeys(([selected] if selected >= 0 else []) + visible))
        ranges = section_ranges(self.project)
        jobs = []
        for i in wanted:
            if i in self.completed: continue
            first = ranges[i][0]
            # First play's middle frame (never a neighbouring cut).
            count = round(self.project['sections'][i]['duration'] * self.project['fps'])
            seconds = first + (count // 2) / self.project['fps']
            jobs.append((self.generation, i, seconds, self.sequence))
        with self.work.condition:
            self.work.jobs = deque(job for job in jobs[:12] if job[:2] != self.work.active)
            self.work.condition.notify()

    def _deliver(self):
        try: generation, index, data = self.work.results.get_nowait()
        except Empty: return
        if generation == self.generation and index < self.cards.count():
            self.completed.add(index)
            if data:
                pixmap = QPixmap(); pixmap.loadFromData(data)
                self.cards.item(index).setIcon(QIcon(pixmap))
            else: self.cards.item(index).setToolTip(self.cards.item(index).toolTip() + '\nPreview unavailable.')
        self.request_visible()

    def showEvent(self, event):
        super().showEvent(event); QTimer.singleShot(0, self.request_visible)

    def resizeEvent(self, event):
        super().resizeEvent(event); QTimer.singleShot(0, self.request_visible)

    def hideEvent(self, event):
        with self.work.condition:
            self.work.jobs.clear()
            if self.work.cancel: self.work.cancel.cancel()
        super().hideEvent(event)

    def close(self):
        self.work.stop(); self.timer.stop()
        return super().close()
