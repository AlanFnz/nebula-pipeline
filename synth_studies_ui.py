"""Dated, sortable study library with reversible removal."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHeaderView,
    QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from synth_studies import set_studies_removed, study_records


class StudiesDialog(QDialog):
    libraryChanged = Signal()

    def __init__(self, parent=None, directory=None):
        super().__init__(parent)
        self.directory = directory
        self.setWindowTitle('Manage studies')
        self.resize(880, 540)
        layout = QVBoxLayout(self)
        hint = QLabel('Sort by date to find older studies. Removal hides entries from the picker; '
                      'saved files stay available for recovery and for open compositions.')
        hint.setWordWrap(True); layout.addWidget(hint)
        self.show_removed = QCheckBox('Removed studies')
        self.show_removed.toggled.connect(self.refresh); layout.addWidget(self.show_removed)
        self.table = QTableWidget(0, 3)
        self.table.setAccessibleName('Study library')
        self.table.setHorizontalHeaderLabels(['Study', 'Date', 'Type'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.update_action)
        layout.addWidget(self.table, 1)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout()
        self.action = QPushButton('Remove selected')
        self.action.clicked.connect(self.change_selection); row.addWidget(self.action)
        row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close); row.addWidget(buttons)
        layout.addLayout(row)
        self.refresh()

    def selected_identifiers(self):
        return [item.data(Qt.ItemDataRole.UserRole)
                for index in self.table.selectionModel().selectedRows()
                if (item := self.table.item(index.row(), 0)) is not None]

    def update_action(self):
        self.action.setEnabled(bool(self.selected_identifiers()))

    def refresh(self):
        removed = self.show_removed.isChecked()
        records = [entry for entry in study_records(self.directory, include_removed=True)
                   if entry.removed == removed]
        header = self.table.horizontalHeader()
        column, order = header.sortIndicatorSection(), header.sortIndicatorOrder()
        if not self.table.isSortingEnabled(): column, order = 1, Qt.SortOrder.DescendingOrder
        self.table.setSortingEnabled(False)
        self.table.clearContents(); self.table.setRowCount(len(records))
        for row, entry in enumerate(records):
            name = QTableWidgetItem(entry.name)
            name.setData(Qt.ItemDataRole.UserRole, entry.identifier)
            date = QTableWidgetItem(entry.date); date.setToolTip(entry.date_hint)
            self.table.setItem(row, 0, name); self.table.setItem(row, 1, date)
            self.table.setItem(row, 2, QTableWidgetItem('Saved' if entry.personal else 'Built-in'))
        self.table.setSortingEnabled(True); self.table.sortItems(column, order)
        self.action.setText('Restore selected' if removed else 'Remove selected')
        self.action.setToolTip('Return selected entries to the Studies picker.' if removed else
                               'Remove selected entries from Studies. You can restore them in Removed studies.')
        self.status.setText(f'{len(records)} {"removed" if removed else "available"} studies. '
                            'Use Command-click or Shift-click to select several.')
        self.update_action()

    def change_selection(self):
        identifiers = self.selected_identifiers()
        if not identifiers: return
        restore = self.show_removed.isChecked()
        try:
            set_studies_removed(identifiers, removed=not restore, directory=self.directory)
        except (OSError, ValueError) as error:
            self.status.setText(f'Could not update Studies: {error}'); return
        self.refresh()
        self.status.setText(f'{"Restored" if restore else "Removed"} {len(identifiers)} '
                            f'stud{"y" if len(identifiers) == 1 else "ies"}.' +
                            ('' if restore else ' You can restore them in Removed studies.'))
        self.libraryChanged.emit()
