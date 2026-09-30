"""Visual, sortable Study browser with independent, lazy still previews."""
from collections import OrderedDict
from PySide6.QtCore import QEvent, QItemSelectionModel, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QDialogButtonBox, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from studio_widgets import ComboBox
from synth_studies import CATEGORIES, set_studies_favorite, set_studies_removed, study_records
from synth_study_thumbnails import StudyThumbnailService

ROW_BOUNDS = (144, 84)
PREVIEW_BOUNDS = (384, 288)


class _StudyNameItem(QTableWidgetItem):
    def __lt__(self, other):
        return (self.text().casefold(), self.data(Qt.ItemDataRole.UserRole) or '') < (
            other.text().casefold(), other.data(Qt.ItemDataRole.UserRole) or '')


class _FavoriteItem(QTableWidgetItem):
    def __init__(self, entry):
        super().__init__('')
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        self.setCheckState(Qt.CheckState.Checked if entry.favorite else Qt.CheckState.Unchecked)
        self.setData(Qt.ItemDataRole.UserRole, entry.identifier)
        self.setData(Qt.ItemDataRole.AccessibleTextRole, f'Favorite {entry.name}')
        self.setData(Qt.ItemDataRole.AccessibleDescriptionRole, 'Press Space to toggle favorite.')
        self.setToolTip('Remove from favorites' if entry.favorite else 'Add to favorites')

    def __lt__(self, other):
        return self.checkState().value < other.checkState().value


class _FavoriteDelegate(QStyledItemDelegate):
    """Native checkable table cells without per-row QWidget/deferred-delete churn."""
    def paint(self, painter, option, index):
        appearance = QStyleOptionViewItem(option)
        self.initStyleOption(appearance, index)
        appearance.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        appearance.text = ''
        widget = appearance.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, appearance, painter, widget)
        painter.save()
        font = painter.font(); font.setPixelSize(20); painter.setFont(font)
        role = QPalette.ColorRole.HighlightedText if option.state & QStyle.StateFlag.State_Selected else QPalette.ColorRole.Text
        painter.setPen(option.palette.color(role))
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked.value
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, '★' if checked else '☆')
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if not index.flags() & Qt.ItemFlag.ItemIsEnabled: return False
        mouse = event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton
        keyboard = event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Select)
        if event.type() == QEvent.Type.MouseButtonDblClick: return True
        if not mouse and not keyboard: return False
        if mouse and not option.rect.contains(event.position().toPoint()): return False
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked.value
        model.setData(index, Qt.CheckState.Unchecked.value if checked else Qt.CheckState.Checked.value,
                      Qt.ItemDataRole.CheckStateRole)
        return True


class StudiesDialog(QDialog):
    libraryChanged = Signal()
    studyRequested = Signal(str)

    def __init__(self, parent=None, directory=None, thumbnail_service=None):
        super().__init__(parent)
        self.directory = directory
        self.setWindowTitle('Browse studies'); self.resize(1120, 640)
        self._records = {}; self._images = OrderedDict(); self._completed = set(); self._errors = {}
        self._rendering_paused = False
        self.thumbnails = thumbnail_service or StudyThumbnailService(directory, self)
        self.thumbnails.ready.connect(self._thumbnail_ready)
        self._schedule_timer = QTimer(self); self._schedule_timer.setSingleShot(True)
        self._schedule_timer.setInterval(35); self._schedule_timer.timeout.connect(self._request_visible)
        layout = QVBoxLayout(self)
        hint = QLabel('Select a Study to inspect it. Load opens a fresh editable copy. '
                      'Removed studies retain their saved files and can be restored.')
        hint.setWordWrap(True); layout.addWidget(hint)
        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText('Search study names')
        self.search.setAccessibleName('Search study names'); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filters); filters.addWidget(self.search, 1)
        self.category = ComboBox(); self.category.addItem('All categories', '')
        for category in CATEGORIES: self.category.addItem(category, category)
        self.category.setAccessibleName('Study category'); self.category.currentIndexChanged.connect(self.apply_filters)
        filters.addWidget(self.category)
        self.favorites_only = QCheckBox('Favorites only'); self.favorites_only.toggled.connect(self.apply_filters)
        filters.addWidget(self.favorites_only)
        self.show_removed = QCheckBox('Removed studies'); self.show_removed.toggled.connect(self.apply_filters)
        filters.addWidget(self.show_removed); layout.addLayout(filters)
        content = QHBoxLayout()
        self.table = QTableWidget(0, 5); self.table.setAccessibleName('Study library')
        self.table.setHorizontalHeaderLabels(['Study', 'Date', 'Category', 'Origin', 'Favorite'])
        self.favorite_delegate = _FavoriteDelegate(self.table)
        self.table.setItemDelegateForColumn(4, self.favorite_delegate)
        self.table.setIconSize(QSize(*ROW_BOUNDS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide(); self.table.verticalHeader().setDefaultSectionSize(96)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4): header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._favorite_item_changed)
        self.table.itemSelectionChanged.connect(self.update_action)
        self.table.itemDoubleClicked.connect(self._double_click)
        self.table.verticalScrollBar().valueChanged.connect(self._schedule_visible)
        header.sortIndicatorChanged.connect(self._schedule_visible)
        self.table.viewport().installEventFilter(self)
        content.addWidget(self.table, 1)
        detail = QVBoxLayout()
        self.preview = QLabel('Select a Study to preview'); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(*PREVIEW_BOUNDS); self.preview.setWordWrap(True)
        self.preview.setAccessibleName('Selected Study still preview')
        detail.addWidget(self.preview)
        self.details = QLabel(''); self.details.setWordWrap(True); self.details.setTextFormat(Qt.TextFormat.PlainText)
        detail.addWidget(self.details)
        self.load = QPushButton('Load study'); self.load.setAccessibleName('Load selected Study')
        self.load.clicked.connect(self.request_load); detail.addWidget(self.load); detail.addStretch(1)
        content.addLayout(detail); layout.addLayout(content, 1)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout()
        self.action = QPushButton('Remove selected'); self.action.clicked.connect(self.change_selection)
        row.addWidget(self.action); row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close); row.addWidget(buttons); layout.addLayout(row)
        self.finished.connect(self.thumbnails.close)
        self.refresh()

    def selected_identifiers(self):
        return [item.data(Qt.ItemDataRole.UserRole) for index in self.table.selectionModel().selectedRows()
                if (item := self.table.item(index.row(), 0)) is not None]

    def update_action(self):
        identifiers = self.selected_identifiers()
        self.action.setEnabled(bool(identifiers))
        self.load.setEnabled(len(identifiers) == 1 and not self._records[identifiers[0]].removed)
        self.preview.clear()
        if len(identifiers) == 1:
            entry = self._records[identifiers[0]]
            self.details.setText(f'{entry.name}\n{"Saved" if entry.personal else "Built-in"} · {entry.category}\n{entry.date}' +
                                 (' · Removed' if entry.removed else ''))
            key = (entry.identifier, PREVIEW_BOUNDS)
            if key in self._images: self._show_preview(self._images[key])
            elif key in self._completed: self.preview.setText('Preview unavailable. See the Study row for details.')
            else: self.preview.setText('Preparing still preview…')
        else:
            self.details.clear()
            self.preview.setText('Select one Study to preview' if identifiers else 'Select a Study to preview')
        self._schedule_visible()

    def refresh(self):
        self._records = {entry.identifier: entry for entry in study_records(self.directory, include_removed=True)}
        self._images.clear(); self._completed.clear(); self._errors.clear()
        self.apply_filters()

    def apply_filters(self, *_args):
        selected = set(self.selected_identifiers())
        current_column = self.table.currentColumn()
        current_item = self.table.item(self.table.currentRow(), 0)
        current_identifier = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        self.thumbnails.reset()
        removed = self.show_removed.isChecked(); query = self.search.text().strip().casefold()
        category = self.category.currentData()
        records = [entry for entry in self._records.values() if entry.removed == removed
                   and query in entry.name.casefold() and (not category or entry.category == category)
                   and (not self.favorites_only.isChecked() or entry.favorite)]
        header = self.table.horizontalHeader()
        column, order = header.sortIndicatorSection(), header.sortIndicatorOrder()
        if not self.table.isSortingEnabled(): column, order = 1, Qt.SortOrder.DescendingOrder
        self.table.blockSignals(True); self.table.setSortingEnabled(False)
        self.table.clearContents(); self.table.setRowCount(len(records))
        for row, entry in enumerate(records):
            name = _StudyNameItem(entry.name); name.setData(Qt.ItemDataRole.UserRole, entry.identifier)
            key = (entry.identifier, ROW_BOUNDS)
            name.setIcon(QIcon(self._images[key]) if key in self._images else self._placeholder(
                'Preview unavailable' if key in self._errors else 'Still preview'))
            name.setToolTip(self._errors.get(key, entry.date_hint))
            date = QTableWidgetItem(entry.date); date.setToolTip(entry.date_hint)
            for column_index, item in enumerate((name, date, QTableWidgetItem(entry.category),
                                                QTableWidgetItem('Saved' if entry.personal else 'Built-in'),
                                                _FavoriteItem(entry))):
                self.table.setItem(row, column_index, item)
        self.table.setSortingEnabled(True); self.table.sortItems(column, order)
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) in selected:
                for column_index in range(self.table.columnCount()): self.table.item(row, column_index).setSelected(True)
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == current_identifier:
                self.table.setCurrentCell(row, max(0, current_column), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.table.blockSignals(False)
        self.action.setText('Restore selected' if removed else 'Remove selected')
        self.action.setToolTip('Return selected entries to the Studies picker.' if removed else
                               'Remove selected entries from Studies. Restore them in Removed studies.')
        self.status.setText(f'{len(records)} {"removed" if removed else "available"} studies. '
                            'Use Command-click or Shift-click to select several.' if records else
                            'No studies match these filters. Clear search or change the filters.')
        self.update_action()

    def _favorite_item_changed(self, item):
        if item.column() != 4: return
        identifier = item.data(Qt.ItemDataRole.UserRole)
        favorite = item.checkState() == Qt.CheckState.Checked
        if identifier not in self._records or favorite == self._records[identifier].favorite: return
        # Finish native selection/check-state dispatch before filters replace the model items.
        QTimer.singleShot(0, lambda key=identifier, checked=favorite: self.change_favorite(key, checked))

    def change_favorite(self, identifier, favorite):
        try: set_studies_favorite([identifier], favorite, self.directory)
        except (OSError, ValueError) as error:
            self.apply_filters(); self.status.setText(f'Could not update favorites: {error}'); return
        # Preferences do not invalidate artistic thumbnail content.
        from dataclasses import replace
        self._records[identifier] = replace(self._records[identifier], favorite=favorite)
        self.apply_filters(); self.libraryChanged.emit()

    def change_selection(self):
        identifiers = self.selected_identifiers()
        if not identifiers: return
        restore = self.show_removed.isChecked()
        try: set_studies_removed(identifiers, removed=not restore, directory=self.directory)
        except (OSError, ValueError) as error:
            self.status.setText(f'Could not update Studies: {error}'); return
        self.refresh()
        self.status.setText(f'{"Restored" if restore else "Removed"} {len(identifiers)} '
                            f'stud{"y" if len(identifiers) == 1 else "ies"}.' +
                            ('' if restore else ' You can restore them in Removed studies.') +
                            (' No studies match these filters.' if not self.table.rowCount() else ''))
        self.libraryChanged.emit()

    def request_load(self):
        identifiers = self.selected_identifiers()
        if len(identifiers) != 1: return
        identifier = identifiers[0]
        available = {entry.identifier for entry in study_records(self.directory)}
        if identifier not in available:
            self.refresh(); self.status.setText('This Study is no longer available. Restore it before loading.'); return
        self.studyRequested.emit(identifier)

    def _double_click(self, item):
        if item.column() != 4: self.request_load()

    def eventFilter(self, watched, event):
        if watched is self.table.viewport() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show): self._schedule_visible()
        return super().eventFilter(watched, event)

    def _schedule_visible(self, *_args):
        self._schedule_timer.start()

    def _request_visible(self):
        if not self.isVisible() or self._rendering_paused: return
        jobs = []
        selected = self.selected_identifiers()
        if len(selected) == 1 and (selected[0], PREVIEW_BOUNDS) not in self._completed:
            jobs.append((selected[0], PREVIEW_BOUNDS))
        viewport = self.table.viewport().rect()
        first = max(0, self.table.rowAt(0))
        last = self.table.rowAt(viewport.bottom())
        if last < 0: last = self.table.rowCount() - 1
        for row in range(first, last + 1):
            item = self.table.item(row, 0)
            if item is None: continue
            key = (item.data(Qt.ItemDataRole.UserRole), ROW_BOUNDS)
            if key not in self._completed: jobs.append(key)
        self.thumbnails.request(jobs)

    def _thumbnail_ready(self, generation, identifier, bounds, data, error):
        bounds = tuple(bounds)
        if generation != self.thumbnails.generation or identifier not in self._records or not self.isVisible() or self._rendering_paused: return
        key = (identifier, bounds); self._completed.add(key)
        if error: self._errors[key] = error
        if data:
            pixmap = QPixmap(); pixmap.loadFromData(data)
            if not pixmap.isNull():
                self._images[key] = pixmap; self._images.move_to_end(key)
                while len(self._images) > 48:
                    old_key, _old = self._images.popitem(last=False); self._completed.discard(old_key)
                    if old_key[1] == ROW_BOUNDS:
                        for row in range(self.table.rowCount()):
                            item = self.table.item(row, 0)
                            if item.data(Qt.ItemDataRole.UserRole) == old_key[0]: item.setIcon(self._placeholder('Still preview'))
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item.data(Qt.ItemDataRole.UserRole) == identifier:
                if bounds == ROW_BOUNDS and key in self._images: item.setIcon(QIcon(self._images[key]))
                if bounds == ROW_BOUNDS and error: item.setIcon(self._placeholder('Preview unavailable'))
                item.setToolTip(error or self._records[identifier].date_hint)
        if bounds == PREVIEW_BOUNDS and self.selected_identifiers() == [identifier]:
            if key in self._images: self._show_preview(self._images[key])
            else: self.preview.setText(error or 'Preview unavailable')
        self._schedule_visible()

    def _placeholder(self, text):
        pixmap = QPixmap(*ROW_BOUNDS); pixmap.fill(self.palette().base().color())
        painter = QPainter(pixmap); painter.setPen(self.palette().text().color())
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        painter.end()
        return QIcon(pixmap)

    def _show_preview(self, pixmap):
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))

    def set_rendering_paused(self, paused):
        """Suspend/cancel warming during export or active editing; resume visible work."""
        self._rendering_paused = bool(paused)
        if paused: self.thumbnails.reset(); self._schedule_timer.stop()
        else: self._schedule_visible()

    def hideEvent(self, event):
        self.thumbnails.reset(); self._schedule_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        if hasattr(self.thumbnails, 'start'): self.thumbnails.start()
        super().showEvent(event); self._schedule_visible()

    def closeEvent(self, event):
        self.thumbnails.close(); self._schedule_timer.stop()
        super().closeEvent(event)
