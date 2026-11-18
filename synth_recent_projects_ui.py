"""Instant, disk-backed project gallery. This view never requests a render."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QPen
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QStyledItemDelegate, QStyle, QVBoxLayout)
from studio_theme import COLORS
from synth_recent_projects import signature

ENTRY = Qt.ItemDataRole.UserRole
COVER = int(ENTRY) + 1
STATE = int(ENTRY) + 2


class ProjectCard(QStyledItemDelegate):
    def sizeHint(self, option, index): return QSize(250, 250)

    def paint(self, painter, option, index):
        entry = index.data(ENTRY); pixmap = index.data(COVER); status = index.data(STATE)
        if not entry: return
        painter.save()
        rect = option.rect.adjusted(5, 5, -5, -5)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(QPen(QColor(COLORS['accent'] if selected else COLORS['border']), 1))
        painter.setBrush(QColor(COLORS['selected'] if selected else COLORS['panel']))
        painter.drawRoundedRect(rect, 7, 7)
        thumb = QRect(rect.x()+8, rect.y()+8, rect.width()-16, 142)
        painter.fillRect(thumb, QColor(COLORS['monitor']))
        if pixmap and not pixmap.isNull():
            fitted = pixmap.size().scaled(thumb.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(0, 0, fitted.width(), fitted.height()); target.moveCenter(thumb.center())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(target, pixmap)
        else:
            painter.setPen(QColor(COLORS['muted']))
            painter.drawText(thumb, Qt.AlignmentFlag.AlignCenter, 'Preview unavailable' if status == 'unavailable' else 'Preparing cover…')
        if status != 'ready':
            note = {'missing': 'File not found', 'changed': 'File changed · saved preview',
                    'updating': 'Updating saved preview…', 'unavailable': 'Preview unavailable'}[status]
            banner = QRect(thumb.x(), thumb.bottom()-24, thumb.width(), 25)
            painter.fillRect(banner, QColor(15, 18, 20, 230)); painter.setPen(QColor(COLORS['warning']))
            painter.drawText(banner.adjusted(6,0,-6,0), Qt.AlignmentFlag.AlignVCenter, note)
        font = painter.font(); font.setBold(True); painter.setFont(font)
        painter.setPen(QColor(COLORS['text']))
        def line(text, y):
            painter.drawText(QRect(rect.x()+11, y, rect.width()-22, 22), Qt.AlignmentFlag.AlignVCenter,
                             painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, rect.width()-22))
        line(entry['name'], thumb.bottom()+7)
        font.setBold(False); painter.setFont(font); painter.setPen(QColor(COLORS['muted']))
        line(Path(entry['path']).name, thumb.bottom()+29)
        stamp = datetime.fromtimestamp(entry['updated']).strftime('%d %b · %H:%M')
        line(entry['kind']+' · '+stamp, thumb.bottom()+53)
        painter.restore()


class RecentProjectsDialog(QDialog):
    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library; self.selected_path = None; self.relocated_from = None
        self.setWindowTitle('Open project'); self.resize(1100, 735)
        self.setMinimumSize(560, 420)
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 18, 20, 18); layout.setSpacing(12)
        top = QHBoxLayout()
        heading = QLabel('Recent projects'); heading.setStyleSheet('font-size: 22px; font-weight: 600;')
        top.addWidget(heading); top.addStretch()
        self.browse = QPushButton('Browse files'); self.browse.clicked.connect(self.browse_files); top.addWidget(self.browse)
        layout.addLayout(top)
        hint = QLabel('Continue from the last saved version. Previews are kept on this computer.'); hint.setObjectName('muted')
        hint.setWordWrap(True); layout.addWidget(hint)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search projects or filenames')
        self.search.setAccessibleName('Search recent projects'); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_items); layout.addWidget(self.search)
        self.grid = QListWidget(); self.grid.setAccessibleName('Recent projects')
        self.grid.setViewMode(QListWidget.ViewMode.IconMode); self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static); self.grid.setSpacing(0)
        self.grid.setGridSize(QSize(250,250)); self.grid.setUniformItemSizes(True)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid.setItemDelegate(ProjectCard(self.grid))
        self.grid.itemActivated.connect(self.open_selected); self.grid.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.grid, 1)
        self.empty = QLabel('No recent projects yet. Browse for a file or add a folder.'); self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        self.location = QLabel(); self.location.setObjectName('muted'); self.location.setTextFormat(Qt.TextFormat.PlainText)
        self.location.setWordWrap(True); layout.addWidget(self.location)
        bottom = QHBoxLayout()
        self.add_folder = QPushButton('Add folder'); self.add_folder.setToolTip('Add Nebula JSON files from a folder. Files stay in their original location.')
        self.add_folder.clicked.connect(self.import_folder); bottom.addWidget(self.add_folder)
        self.remove = QPushButton('Remove from recents'); self.remove.setToolTip('Only removes this card; the project file stays on disk.')
        self.remove.clicked.connect(self.remove_selected); bottom.addWidget(self.remove)
        bottom.addStretch()
        close = QPushButton('Cancel'); close.clicked.connect(self.reject); bottom.addWidget(close)
        self.open = QPushButton('Open project'); self.open.setObjectName('primary'); self.open.setDefault(True)
        self.open.clicked.connect(self.open_selected); bottom.addWidget(self.open); layout.addLayout(bottom)
        library.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        selected = self.selected_entry()
        selected_path = selected['path'] if selected else None
        scroll = self.grid.verticalScrollBar().value()
        self.grid.blockSignals(True); self.grid.clear()
        for entry in self.library.store.records():
            status = 'ready'
            try:
                if signature(entry['path']) != entry['signature']: status = 'changed'
                elif not self.library.store.current_cover(entry): status = 'unavailable' if entry.get('error') else 'updating'
            except OSError: status = 'missing'
            data = self.library.store.cover(entry)
            pixmap = QPixmap()
            if data: pixmap.loadFromData(data)
            if pixmap.isNull() and status == 'ready': status = 'unavailable'
            item = QListWidgetItem(entry['name']); item.setData(ENTRY, entry.copy()); item.setData(COVER,pixmap); item.setData(STATE,status)
            item.setSizeHint(QSize(250,250)); item.setToolTip(entry['path'] + ('\n'+entry['error'] if entry.get('error') else ''))
            item.setData(Qt.ItemDataRole.AccessibleTextRole, entry['name']+' · '+Path(entry['path']).name+' · '+status)
            self.grid.addItem(item)
            if entry['path'] == selected_path: self.grid.setCurrentItem(item)
        self.grid.blockSignals(False); self.filter_items(); self.grid.verticalScrollBar().setValue(scroll)

    def filter_items(self):
        query = self.search.text().casefold().strip(); visible = 0
        for i in range(self.grid.count()):
            item = self.grid.item(i); entry = item.data(ENTRY)
            hidden = query not in (entry['name']+' '+entry['path']).casefold()
            item.setHidden(hidden); visible += not hidden
        self.empty.setVisible(not visible)
        self.empty.setText('No matching projects.' if self.grid.count() else 'No recent projects yet. Browse for a file or add a folder.')
        self.selection_changed()

    def selected_entry(self):
        item = self.grid.currentItem()
        return item.data(ENTRY) if item and not item.isHidden() else None

    def selection_changed(self):
        entry = self.selected_entry()
        self.open.setEnabled(bool(entry)); self.remove.setEnabled(bool(entry))
        missing = bool(entry and not Path(entry['path']).is_file())
        self.open.setText('Locate file' if missing else 'Open project')
        self.location.setText(entry['path'] if entry else f'{self.grid.count()} projects · most recently used first')

    def browse_files(self):
        from synth_project_files import OPEN_FILTER
        path, _ = QFileDialog.getOpenFileName(self, 'Open Nebula project', '', OPEN_FILTER)
        if path: self.selected_path = path; self.accept()

    def open_selected(self, *_):
        entry = self.selected_entry()
        if not entry: return
        path = entry['path']
        if not Path(path).is_file():
            from synth_project_files import OPEN_FILTER
            path, _ = QFileDialog.getOpenFileName(self, 'Locate '+entry['name'], str(Path(path).parent), OPEN_FILTER)
            if not path: return
            self.relocated_from = entry['path']
        self.selected_path = path; self.accept()

    def remove_selected(self):
        entry = self.selected_entry()
        if entry: self.library.remove(entry['path'])

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Add a folder of Nebula projects')
        if folder: self.library.import_folder(folder)
