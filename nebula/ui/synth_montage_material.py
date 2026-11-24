"""Compact source rows and drag data for the montage Material tab."""
from collections import Counter

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QSize, Qt, QSignalBlocker, QTimer, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QTextLayout, QTextOption
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate

from nebula.ui.studio_graphite import GRAPHITE


ASSET_MIME = 'application/x-nebula-asset'
THUMB_SIZE = QSize(52, 38)


class MaterialRow(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(128, max(THUMB_SIZE.height(), 3 * option.fontMetrics.lineSpacing()) + 8)

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        painter.setClipRect(rect)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        surface = 'selection' if selected else 'raised' if hover else 'panel'
        painter.fillRect(rect, QColor(GRAPHITE[surface]))
        if selected:
            painter.fillRect(QRect(rect.x(), rect.y(), 3, rect.height()), QColor(GRAPHITE['accent']))
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QColor(GRAPHITE['focus']))
            painter.drawRect(rect.adjusted(1, 1, -2, -2))

        thumb = QRect(rect.left() + 7, rect.center().y() - THUMB_SIZE.height() // 2,
                      THUMB_SIZE.width(), THUMB_SIZE.height())
        painter.fillRect(thumb, QColor(GRAPHITE['canvas']))
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon and not icon.isNull():
            icon.paint(painter, thumb)
        else:
            painter.setPen(QColor(GRAPHITE['control']))
            painter.drawText(thumb, Qt.AlignmentFlag.AlignCenter, '—')

        title, _, metadata = index.data(Qt.ItemDataRole.DisplayRole).rpartition('\n')
        left = thumb.right() + 8
        width = max(0, rect.right() - left - 5)
        line_height = option.fontMetrics.lineSpacing()
        layout = QTextLayout(title, option.font)
        wrap = QTextOption()
        wrap.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(wrap)
        layout.beginLayout()
        first = layout.createLine()
        if first.isValid():
            first.setLineWidth(width)
        layout.endLayout()
        painter.setFont(option.font)
        painter.setPen(QColor(GRAPHITE['text']))
        top = rect.top() + 3
        if first.isValid():
            # QTextLine counts UTF-16 units, including surrogate pairs.
            rest = title.encode('utf-16-le')[first.textLength() * 2:].decode('utf-16-le').strip()
            if not rest:
                top += line_height // 2
            first.draw(painter, QPointF(left, top))
            top += line_height
            if rest:
                second = option.fontMetrics.elidedText(rest, Qt.TextElideMode.ElideMiddle, width)
                painter.drawText(left, top + option.fontMetrics.ascent(), second)
                top += line_height
        painter.setPen(QColor(GRAPHITE['secondary']))
        painter.drawText(left, top + option.fontMetrics.ascent(),
                         option.fontMetrics.elidedText(metadata, Qt.TextElideMode.ElideRight, width))
        painter.restore()


class LibraryList(QListWidget):
    thumbnailRequested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName('montageMaterial')
        self.setAccessibleName('Montage media library')
        self.setIconSize(THUMB_SIZE)
        self.setItemDelegate(MaterialRow(self))
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragEnabled(True)
        self.setMouseTracking(True)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(0)
        self.preview_timer.timeout.connect(self.request_visible_thumbnails)
        self.verticalScrollBar().valueChanged.connect(lambda _: self.preview_timer.start())

    def showEvent(self, event):
        super().showEvent(event)
        self.preview_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.preview_timer.start()

    def request_visible_thumbnails(self):
        if not self.isVisible():
            return
        first = self.indexAt(QPoint(1, 0))
        if not first.isValid():
            return
        for row in range(first.row(), self.count()):
            item = self.item(row)
            if self.visualItemRect(item).top() >= self.viewport().height():
                break
            if item.icon().isNull():
                self.thumbnailRequested.emit(item.data(Qt.ItemDataRole.UserRole))

    def set_material(self, assets, clips, thumbnails):
        current = self.currentItem()
        key = current.data(Qt.ItemDataRole.UserRole) if current else None
        scroll = self.verticalScrollBar().value()
        uses = Counter(clip['asset'] for clip in clips)
        with QSignalBlocker(self):
            self.clear()
            for asset_id, asset in assets.items():
                count = uses[asset_id]
                text = f"{asset['name']}\n{asset['kind'].title()} · {count} use{'s' if count != 1 else ''}"
                item = QListWidgetItem(text)
                item.setToolTip(text)
                item.setData(Qt.ItemDataRole.UserRole, asset_id)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, text.replace('\n', ' · '))
                if thumbnails.get(asset_id):
                    item.setIcon(QIcon(thumbnails[asset_id]))
                self.addItem(item)
                if key == asset_id:
                    self.setCurrentItem(item)
        if key in assets or key is None:
            self.doItemsLayout()
            self.verticalScrollBar().setValue(scroll)
        self.preview_timer.start()

    def startDrag(self, actions):
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        mime.setData(ASSET_MIME, item.data(Qt.ItemDataRole.UserRole).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
