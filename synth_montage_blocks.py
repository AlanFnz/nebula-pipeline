"""Read-only block identification and navigation for the montage workspace."""
from PySide6.QtCore import Qt, Signal, QSignalBlocker, QSize, QRect, QTimer, QItemSelectionModel
from PySide6.QtGui import QFontMetrics, QPalette
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QAbstractItemView, QStyledItemDelegate, QStyle, QStyleOptionViewItem)

from synth_montage import placements


def time_label(frame, fps):
    milliseconds = round(frame / fps * 1000)
    minutes, remainder = divmod(milliseconds, 60000)
    return f'{minutes:02d}:{remainder // 1000:02d}.{remainder % 1000:03d}'


def block_rows(document):
    for index, (clip, start, end) in enumerate(placements(document), 1):
        asset = document['assets'][clip['asset']]; fps = document['fps']
        title = f"Block {index:02d} · {clip['name']}"
        timing = (f"{asset['kind'].title()} · Start {time_label(start, fps)} · "
                  f"Duration {clip['frames']} frames / {clip['frames']/fps:.3f}s")
        yield clip['id'], title + '\n' + timing + f"\nMaterial: {asset['name']}"


def block_details(document, key):
    return next((text for identity, text in block_rows(document) if identity == key), '')


def clip_label(index, name, width, metrics):
    """Never draw a partially clipped block number or pretend a short cut is wider."""
    number = f'{index:02d}'
    if width < metrics.horizontalAdvance(number): return ''
    if width < metrics.horizontalAdvance(number + ' · …'): return number
    return metrics.elidedText(number + ' · ' + name, Qt.TextElideMode.ElideRight, int(width))


class WrappedBlockDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        option = QStyleOptionViewItem(option); self.initStyleOption(option, index)
        width = max(40, self.parent().viewport().width() - 2 * self.parent().spacing())
        text = index.data(Qt.ItemDataRole.DisplayRole) or ''
        rect = QFontMetrics(option.font).boundingRect(QRect(0, 0, width - 16, 10000), Qt.TextFlag.TextWordWrap, text)
        return QSize(width, rect.height() + 16)

    def paint(self, painter, option, index):
        option = QStyleOptionViewItem(option); self.initStyleOption(option, index)
        text = option.text; option.text = ''
        self.parent().style().drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, self.parent())
        role = QPalette.ColorRole.HighlightedText if option.state & QStyle.StateFlag.State_Selected else QPalette.ColorRole.Text
        painter.save(); painter.setClipRect(option.rect); painter.setFont(option.font)
        painter.setPen(option.palette.color(role))
        painter.drawText(option.rect.adjusted(8, 8, -8, -8), Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop, text)
        painter.restore()


class BlockList(QListWidget):
    editRequested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAccessibleName('Montage block list')
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setWordWrap(True); self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(WrappedBlockDelegate(self)); self.setSpacing(3)
        self.itemDoubleClicked.connect(lambda item: self.editRequested.emit(item.data(Qt.ItemDataRole.UserRole)))

    def resizeEvent(self, event):
        super().resizeEvent(event); self.doItemsLayout()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if len(self.selectedItems()) == 1:
                self.editRequested.emit(self.selectedItems()[0].data(Qt.ItemDataRole.UserRole))
            event.accept(); return
        super().keyPressEvent(event)


class BlockBrowser(QWidget):
    selectionRequested = Signal(object, str)
    editRequested = Signal(str)

    def __init__(self):
        super().__init__(); layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit(); self.search.setPlaceholderText('Find block or material…')
        self.search.setAccessibleName('Find montage block'); self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        self.list = BlockList(); layout.addWidget(self.list, 1)
        self.hint = QLabel(); self.hint.setWordWrap(True); layout.addWidget(self.hint)
        self.search.textChanged.connect(self.filter)
        self.list.itemSelectionChanged.connect(self.request_selection)
        self.list.editRequested.connect(self.editRequested)
        self.signature = None

    def request_selection(self):
        keys = {i.data(Qt.ItemDataRole.UserRole) for i in self.list.selectedItems()}
        current = self.list.currentItem()
        key = current.data(Qt.ItemDataRole.UserRole) if current else ''
        self.selectionRequested.emit(keys, key)

    def set_document(self, document, selected):
        rows = list(block_rows(document))
        if rows != self.signature:
            current = self.list.currentItem()
            current_key = current.data(Qt.ItemDataRole.UserRole) if current else None
            scroll = self.list.verticalScrollBar().value()
            with QSignalBlocker(self.list):
                self.list.clear()
                for key, text in rows:
                    item = QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole, key)
                    item.setToolTip(text); item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, text)
                    self.list.addItem(item)
                    if key == current_key: self.list.setCurrentItem(item)
            self.signature = rows
            self.filter(); self.list.verticalScrollBar().setValue(scroll)
        self.sync_selection(selected)

    def sync_selection(self, selected):
        with QSignalBlocker(self.list):
            for row in range(self.list.count()):
                item = self.list.item(row); chosen = item.data(Qt.ItemDataRole.UserRole) in selected
                if chosen and len(selected) == 1:
                    self.list.setCurrentItem(item, QItemSelectionModel.SelectionFlag.NoUpdate)
                item.setSelected(chosen)
        self.update_hint()

    def filter(self, *_):
        terms = self.search.text().casefold().split()
        with QSignalBlocker(self.list):
            for row in range(self.list.count()):
                item = self.list.item(row)
                item.setHidden(not all(term in item.text().casefold() for term in terms))
        self.update_hint()

    def update_hint(self):
        count = self.list.count(); visible = sum(not self.list.item(r).isHidden() for r in range(count))
        self.hint.setText(f'{visible} of {count} blocks · Select to locate; Enter to edit.' if visible
                          else 'No matching blocks. Clear the search to see all blocks.')


class MontageBlockNavigation:
    def refresh_block_navigation(self):
        self.block_browser.set_document(self.document, self.selected)
        self.update_block_identification()

    def update_block_identification(self):
        self.block_browser.sync_selection(self.selected)
        clip = self.active_clip()
        text = block_details(self.document, clip['id']) if clip else (f'{len(self.selected)} blocks selected'
               if self.selected else 'Select a block to see its full name, position and duration.')
        self.block_summary.setText(text); self.block_summary.setToolTip(text)
        self.timeline.setAccessibleDescription(text); self.show_block_button.setEnabled(clip is not None)

    def select_from_block_list(self, keys, current):
        if self.select_blocks(keys):
            if current in keys: self.reveal_block(current)
        else: self.block_browser.sync_selection(self.selected)

    def edit_from_block_list(self, key):
        # A cancelled timing prompt must not open a different block.
        if self.selected == {key}: self.edit_clip(key)

    def reveal_block(self, key, *, center=False):
        entry = next((r for c, a, b, r in self.timeline.rectangles() if c['id'] == key), None)
        if entry is None: return
        bar = self.scroll.horizontalScrollBar(); left = bar.value(); width = self.scroll.viewport().width()
        if center: bar.setValue(round(entry.center().x() - width / 2))
        elif entry.width() > width - 40 or entry.left() < left + 20: bar.setValue(round(entry.left() - 20))
        elif entry.right() > left + width - 20: bar.setValue(round(entry.right() - width + 20))

    def show_selected_block(self):
        clip = self.active_clip()
        if not clip: return
        if self.previous_timeline_view is None:
            self.previous_timeline_view = (self.timeline.scale, self.scroll.horizontalScrollBar().value())
        self.previous_view_button.setEnabled(True)
        seconds = clip['frames'] / self.document['fps']
        scale = max(25, min(220, round(self.scroll.viewport().width() * .55 / seconds)))
        self.zoom(scale)
        key = clip['id']; self.view_request += 1; request = self.view_request
        QTimer.singleShot(0, lambda: self.reveal_block(key, center=True)
                          if request == self.view_request and self.selected == {key} and not self.closed else None)

    def restore_timeline_view(self):
        if self.previous_timeline_view is None: return
        scale, position = self.previous_timeline_view; self.previous_timeline_view = None
        self.previous_view_button.setEnabled(False); self.zoom(scale)
        self.view_request += 1; request = self.view_request
        QTimer.singleShot(0, lambda: self.scroll.horizontalScrollBar().setValue(position)
                          if request == self.view_request and not self.closed else None)

    def update_marker_context(self, *_):
        item = self.marker_list.currentItem()
        text = item.text() if item else 'Select a marker to see its full name. Double-click to seek.'
        self.marker_context.setText(text); self.marker_context.setToolTip(text)
