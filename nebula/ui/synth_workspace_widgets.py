"""Compact workspace chrome; these widgets never modify artistic documents."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QSizePolicy, QSplitter, QSplitterHandle, QWidget

from nebula.ui.studio_theme import COLORS


def inline(*widgets, spacing=5, separated=False):
    host = QWidget()
    layout = QHBoxLayout(host); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(spacing)
    if separated:
        host.setProperty('actionGroup', True)
        layout.setContentsMargins(12, 0, 0, 0)
    for widget in widgets: layout.addWidget(widget)
    return host


class FlowLayout(QLayout):
    """Wrap whole control groups, keeping every action reachable at small widths."""
    def __init__(self, parent=None, spacing=6, right_last=False, center_vertical=False):
        super().__init__(parent)
        self.items = []; self.right_last = right_last
        self.center_vertical = center_vertical
        self.setContentsMargins(0, 0, 0, 0); self.setSpacing(spacing)

    def addItem(self, item): self.items.append(item)
    def count(self): return len(self.items)
    def itemAt(self, index): return self.items[index] if 0 <= index < len(self.items) else None
    def takeAt(self, index): return self.items.pop(index) if 0 <= index < len(self.items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self._arrange(QRect(0, 0, width, 0), False)
    def minimumSize(self):
        result = QSize(0, 0)
        for item in self.items:
            if not item.isEmpty(): result = result.expandedTo(item.minimumSize())
        return result
    def sizeHint(self):
        visible = [item for item in self.items if not item.isEmpty()]
        return QSize(sum(item.sizeHint().width() for item in visible) + max(0, len(visible)-1)*self.spacing(),
                     max((item.sizeHint().height() for item in visible), default=0))
    def setGeometry(self, rect):
        super().setGeometry(rect); self._arrange(rect, True)
    def _arrange(self, rect, apply):
        x, y, height = rect.x(), rect.y(), 0
        row = []
        def place_row():
            if apply:
                for item, left, size in row:
                    offset = (height - size.height()) // 2 if self.center_vertical else 0
                    item.setGeometry(QRect(QPoint(left, y + offset), size))
        visible = [item for item in self.items if not item.isEmpty()]
        for index, item in enumerate(visible):
            size = item.sizeHint().boundedTo(item.maximumSize())
            width = min(size.width(), max(item.minimumSize().width(), rect.width()))
            if x > rect.x() and x + width > rect.right()+1:
                place_row(); row = []
                x = rect.x(); y += height+self.spacing(); height = 0
            if self.right_last and index == len(visible)-1:
                x = max(x, rect.right()+1-width)
            row.append((item, x, QSize(width, size.height())))
            x += width+self.spacing(); height = max(height, size.height())
        place_row()
        return y+height-rect.y()


class PairedControlsLayout(FlowLayout):
    """Two related groups share the width, or stack without squeezing controls."""
    def __init__(self, parent, *, right_width=None):
        super().__init__(parent, spacing=6)
        self.right_width = right_width

    def _arrange(self, rect, apply):
        items = [item for item in self.items if not item.isEmpty()]
        if not items: return 0
        gap = 20
        paired = (len(items) == 2 and rect.width() >= items[0].sizeHint().width() + gap
                  + (self.right_width or items[1].sizeHint().width()))
        widths = ([items[0].sizeHint().width(), rect.width()-items[0].sizeHint().width()-gap]
                  if paired else [rect.width()] * len(items))
        heights = [max(item.minimumSize().height(), item.heightForWidth(width)
                       if item.hasHeightForWidth() else item.sizeHint().height())
                   for item, width in zip(items, widths)]
        height = max(heights) if paired else sum(heights) + (len(items)-1)*self.spacing()
        x, y = rect.x(), rect.y()
        for item, width, h in zip(items, widths, heights):
            if apply:
                item.setGeometry(QRect(x, y + ((height-h)//2 if paired else 0), width, h))
            if paired: x += width + gap
            else: y += h + self.spacing()
        return height


class ElidingLabel(QLabel):
    """A single visible line with the complete status retained for accessibility."""
    def __init__(self, text='', *, auto_hide=False):
        super().__init__(text)
        self.auto_hide = auto_hide
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(40)
        self.setText(text)
    def setText(self, text):
        super().setText(text); self.setToolTip(text); self.setAccessibleDescription(text)
        if getattr(self, 'auto_hide', False): self.setVisible(bool(text))
    def paintEvent(self, event):
        painter = QPainter(self); painter.setPen(self.palette().windowText().color())
        painter.drawText(self.contentsRect(), self.alignment(),
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width()))


class WorkspaceHandle(QSplitterHandle):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS['background']))
        painter.setPen(QPen(QColor(COLORS['accent'] if self.underMouse() else COLORS['border']), 1))
        center = self.rect().center()
        if self.orientation() == Qt.Orientation.Horizontal:
            painter.drawLine(center.x(), 6, center.x(), self.height()-7)
            painter.setPen(QPen(QColor(COLORS['muted']), 3))
            painter.drawLine(center.x(), center.y()-10, center.x(), center.y()+10)
        else:
            painter.drawLine(6, center.y(), self.width()-7, center.y())
            painter.setPen(QPen(QColor(COLORS['muted']), 3))
            painter.drawLine(center.x()-10, center.y(), center.x()+10, center.y())


class WorkspaceSplitter(QSplitter):
    def createHandle(self): return WorkspaceHandle(self.orientation(), self)
