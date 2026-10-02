"""Searchable effect discovery with explicit, mutation-free action signals."""
from PySide6.QtCore import Qt, QSignalBlocker, Signal, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QScrollArea, QFrame, QListWidget, QListWidgetItem,
)

from studio_widgets import ComboBox
from synth_effect_catalog import CATEGORIES, SOURCE_EFFECT_IDS, effect_catalog


class CompactEffectList(QListWidget):
    """A native accessible list; compact discovery does not need a table grid."""
    def rowCount(self): return self.count()
    def clearContents(self): self.clear()
    def setRowCount(self, _count): pass
    def selectRow(self, row): self.setCurrentRow(row)
    def item(self, row, column=0): return super().item(row)



class EffectBrowserDialog(QDialog):
    effectRequested = Signal(str, int)
    effectInspected = Signal(str)
    objectRequested = Signal()

    def __init__(self, allowed_effects=None, applied_ids=(), parent=None, *, compact=False):
        super().__init__(parent)
        self.setWindowTitle('Add effect')
        self.setAccessibleName('Add image effect')
        self.resize(720, 600)
        self.setMinimumWidth(480)
        self.allowed_effects = None
        self.applied_ids = frozenset()
        self._entries = {}
        self._preset_choices = {}
        self.compact = compact
        outer = QVBoxLayout(self)
        body = QWidget(); layout = QVBoxLayout(body); layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout = layout
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(body)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame); outer.addWidget(scroll, 1)
        heading = QLabel('IMAGE EFFECTS'); heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        hint = QLabel('Browse treatments for your image. Choose a preset, then Add effect.')
        self.browser_hint = hint
        hint.setWordWrap(True); layout.addWidget(hint)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search effects and presets')
        self.search.setAccessibleName('Search effects and presets')
        self.search.setClearButtonEnabled(True)
        filters.addWidget(self.search, 1)
        self.category = ComboBox()
        self.category.setAccessibleName('Effect category')
        filters.addWidget(self.category)
        layout.addLayout(filters)

        self.results = QStackedWidget()
        self.table = CompactEffectList() if compact else QTableWidget(0, 3)
        self.table.setAccessibleName('Image effects')
        self.table.setAccessibleDescription('Select an effect to read its description. Use Add effect or Inspect effect to continue.')
        if not compact: self.table.setHorizontalHeaderLabels(('Effect', 'Category', 'Status'))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        if not compact:
            self.table.verticalHeader().hide()
            self.table.verticalHeader().setDefaultSectionSize(30)
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            if not compact: header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(140)
        self.results.addWidget(self.table)
        self.empty = QLabel()
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setAccessibleName('No matching effects')
        self.results.addWidget(self.empty)
        layout.addWidget(self.results, 1)
        self.status = QLabel(); self.status.setObjectName('muted')
        self.status.setWordWrap(True); layout.addWidget(self.status)

        self.title = QLabel('Select an effect')
        self.title.setObjectName('sectionTitle')
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.title)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextFormat(Qt.TextFormat.PlainText)
        self.description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.description.setAccessibleName('Effect description')
        layout.addWidget(self.description)
        self.preset_row = QWidget()
        presets = QHBoxLayout(self.preset_row); presets.setContentsMargins(0, 0, 0, 0)
        preset_label = QLabel('Starting preset')
        self.preset = ComboBox()
        self.preset.setAccessibleName('Starting effect preset')
        preset_label.setBuddy(self.preset)
        presets.addWidget(preset_label); presets.addWidget(self.preset, 1)
        layout.addWidget(self.preset_row)
        self.selection_note = QLabel(); self.selection_note.setWordWrap(True)
        self.selection_note.setObjectName('muted'); layout.addWidget(self.selection_note)

        source_title = QLabel('OBJECT SOURCES'); self.object_heading = source_title; source_title.setObjectName('controlGroup')
        layout.addWidget(source_title)
        sources = QHBoxLayout()
        self.object_note = QLabel('Text, shapes and particles have their own Object controls.')
        self.object_note.setWordWrap(True)
        sources.addWidget(self.object_note, 1)
        self.object_button = QPushButton('Choose object…')
        self.object_button.setAccessibleName('Choose object source')
        self.object_button.setAutoDefault(False)
        self.object_button.clicked.connect(self.request_object)
        sources.addWidget(self.object_button); layout.addLayout(sources)

        actions = QHBoxLayout(); actions.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_button.setAutoDefault(False)
        self.buttons.rejected.connect(self.reject)
        actions.addWidget(self.buttons)
        self.action = QPushButton('Add effect')
        self.action.setObjectName('primary')
        self.action.setAutoDefault(False)
        self.action.clicked.connect(self.request_effect)
        actions.addWidget(self.action); outer.addLayout(actions)

        self.search.textChanged.connect(self.apply_filters)
        self.category.currentIndexChanged.connect(self.apply_filters)
        self.table.itemSelectionChanged.connect(self.update_selection)
        self.preset.currentIndexChanged.connect(self.remember_preset)
        self.set_context(allowed_effects, applied_ids)
        self.search.setFocus()
        self.setTabOrder(self.search, self.category)
        self.setTabOrder(self.category, self.table)
        self.setTabOrder(self.table, self.preset)
        self.setTabOrder(self.preset, self.action)
        self.setTabOrder(self.action, self.object_button)
        self.setTabOrder(self.object_button, self.cancel_button)

    def set_context(self, allowed_effects=None, applied_ids=()):
        self.allowed_effects = None if allowed_effects is None else frozenset(allowed_effects)
        self.applied_ids = frozenset(applied_ids)
        previous_category = self.category.currentData()
        compatible = effect_catalog(self.allowed_effects)
        self._entries = {effect.id: effect for effect in compatible}
        categories = {effect.category for effect in compatible}
        with QSignalBlocker(self.category):
            self.category.clear(); self.category.addItem('All categories', '')
            for category in CATEGORIES:
                if category in categories: self.category.addItem(category, category)
            self.category.setCurrentIndex(max(0, self.category.findData(previous_category)))
        objects_allowed = self.allowed_effects is None or bool(SOURCE_EFFECT_IDS & self.allowed_effects)
        self.object_button.setEnabled(objects_allowed)
        self.object_button.setToolTip('Open Object controls without applying an effect.' if objects_allowed else
                                      'Object choices are unavailable for this source.')
        self.object_note.setText('Text, shapes and particles have their own Object controls.' if objects_allowed else
                                 'This source uses image treatments. Object choices are unavailable here.')
        self.apply_filters()

    def selected_effect_id(self):
        rows = self.table.selectionModel().selectedRows()
        item = self.table.item(rows[0].row(), 0) if rows else None
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def apply_filters(self, *_args):
        selected = self.selected_effect_id()
        entries = effect_catalog(self.allowed_effects, query=self.search.text(),
                                 category=self.category.currentData() or '')
        with QSignalBlocker(self.table):
            self.table.clearContents(); self.table.setRowCount(len(entries))
            selected_row = 0
            for row, effect in enumerate(entries):
                applied = effect.id in self.applied_ids
                status = 'Applied' if applied else 'Available'
                values = (effect.label + ' · ' + status,) if self.compact else (effect.label, effect.category, status)
                for column, value in enumerate(values):
                    item = QListWidgetItem(value) if self.compact else QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, effect.id)
                    item.setToolTip(effect.description)
                    if column == 0:
                        item.setData(Qt.ItemDataRole.AccessibleTextRole,
                                     f'{effect.label}, {effect.category}, {"already applied" if applied else "available"}')
                    if self.compact: self.table.addItem(item)
                    else: self.table.setItem(row, column, item)
                if effect.id == selected: selected_row = row
            if entries: self.table.selectRow(selected_row)
        self.results.setCurrentWidget(self.table if entries else self.empty)
        if not self._entries:
            self.empty.setText('No image effects are available for this source.')
        else:
            self.empty.setText('No effects match these filters.\nClear search or choose All categories.')
        self.status.setText(f'{len(entries)} effect' + ('' if len(entries) == 1 else 's') +
                            (f' of {len(self._entries)}' if len(entries) != len(self._entries) else ''))
        self.update_selection()

    def update_selection(self):
        identifier = self.selected_effect_id()
        effect = self._entries.get(identifier)
        self.action.setEnabled(effect is not None)
        with QSignalBlocker(self.preset):
            self.preset.clear()
            if effect is not None:
                for index, label in enumerate(effect.presets): self.preset.addItem(label, index)
                self.preset.setCurrentIndex(self._preset_choices.get(identifier, 0))
        applied = identifier in self.applied_ids
        self.action.setText('Inspect effect' if applied else 'Add effect')
        self.action.setAccessibleName('Inspect selected effect' if applied else 'Add selected effect')
        self.preset_row.setVisible(effect is not None and not applied)
        self.preset.setEnabled(effect is not None and not applied)
        if effect is None:
            self.title.setText('Select an effect'); self.description.clear(); self.selection_note.clear()
            return
        self.title.setText(effect.label)
        self.description.setText(effect.description)
        self.selection_note.setText('Already applied in this scope. Inspect keeps its current settings.' if applied else
                                   'Add uses this starting preset in the current editing scope.')
        # Long descriptions can shrink the results viewport. Keep the chosen
        # row visible after the details layout has taken its new space.
        self.layout().activate()
        row = self.table.selectionModel().selectedRows()[0].row()
        self.table.scrollToItem(self.table.item(row, 0))
        QTimer.singleShot(0, self, self.ensure_selection_visible)

    def ensure_selection_visible(self):
        rows = self.table.selectionModel().selectedRows()
        if rows: self.table.scrollToItem(self.table.item(rows[0].row(), 0), QAbstractItemView.ScrollHint.PositionAtCenter)

    def remember_preset(self, index):
        identifier = self.selected_effect_id()
        if identifier is not None and index >= 0:
            self._preset_choices[identifier] = index

    def request_effect(self):
        identifier = self.selected_effect_id()
        if identifier not in self._entries: return
        if identifier in self.applied_ids:
            self.effectInspected.emit(identifier)
        else:
            self.effectRequested.emit(identifier, self.preset.currentData())
        self.accept()

    def request_object(self):
        if not self.object_button.isEnabled(): return
        self.objectRequested.emit()
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Enter while browsing never silently applies the first candidate.
            # A focused action button still supports the native keyboard action.
            focus = self.focusWidget()
            if isinstance(focus, QPushButton) and focus.isEnabled(): focus.click()
            elif focus is self.search and self.table.rowCount(): self.table.setFocus()
            event.accept()
            return
        super().keyPressEvent(event)
