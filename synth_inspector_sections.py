"""Foldable navigation for native inspector rows; never edits their values."""
from PySide6.QtCore import Qt, QSignalBlocker, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QScrollArea, QFrame, QLabel
from studio_widgets import ComboBox
from synth_object_groups import ControlGroup


class InspectorSections(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = {}; self.expansion = {}; self.snapshot = None; self.generation = 0
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText('Find a source control…')
        self.search.setAccessibleName('Find video source control'); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_changed); self.search.returnPressed.connect(self.focus_result)
        row.addWidget(self.search, 1)
        self.show_all = QCheckBox('Show all'); self.show_all.setAccessibleName('Show all video source controls')
        self.show_all.toggled.connect(self.refresh); row.addWidget(self.show_all); root.addLayout(row)
        self.jump = ComboBox(); self.jump.addItem('Jump to a group…', None)
        self.jump.setAccessibleName('Jump to video source group'); self.jump.activated.connect(self.reveal_group)
        root.addWidget(self.jump)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(100)
        self.body = QWidget(); self.body_layout = QVBoxLayout(self.body); self.body_layout.setContentsMargins(0, 0, 2, 0)
        self.scroll.setWidget(self.body); root.addWidget(self.scroll, 1)
        self.no_matches = QLabel('No matching source controls.'); self.no_matches.setObjectName('muted')
        self.body_layout.addWidget(self.no_matches); self.no_matches.hide(); self.body_layout.addStretch(1)

    def add_group(self, title, opened=False, container_layout=None):
        group = ControlGroup(title, lambda value: self.toggle(title, value)); group.summary.hide()
        self.groups[title] = group; self.expansion[title] = opened
        target = container_layout or self.body_layout
        if target is self.body_layout: target.insertWidget(target.count() - 2, group)
        else: target.addWidget(group)
        self.jump.addItem(title, title)
        return group.body_layout

    def toggle(self, title, value):
        self.expansion[title] = value; self.refresh()

    def available(self, group):
        parent = group.parentWidget()
        return parent is self.body or not parent.isHidden()

    def refresh(self):
        query = self.search.text().strip().casefold(); count = 0
        for title, group in self.groups.items():
            labels = [w.text() for w in group.body.findChildren(QLabel)]
            names = [w.accessibleName() for w in group.body.findChildren(QWidget)]
            matching = not query or query in ' '.join([title, *labels, *names]).casefold()
            visible = self.available(group) and matching
            group.setVisible(visible); count += visible
            expanded = bool(query) or self.show_all.isChecked() or self.expansion[title]
            with QSignalBlocker(group.button): group.button.setChecked(expanded)
            group.button.setText(title.replace('&', '&&') + (' ▾' if expanded else ' ▸'))
            group.button.setEnabled(not query and not self.show_all.isChecked())
            group.body.setVisible(expanded)
            self.jump.model().item(self.jump.findData(title)).setEnabled(self.available(group))
        self.no_matches.setVisible(bool(query) and not count)

    def filter_changed(self, text):
        if text.strip() and self.snapshot is None: self.snapshot = self.scroll.verticalScrollBar().value()
        self.generation += 1; generation = self.generation
        self.refresh()
        if not text.strip() and self.snapshot is not None:
            scroll = self.snapshot; self.snapshot = None
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(scroll) if generation == self.generation else None)
        elif text.strip(): self.scroll.verticalScrollBar().setValue(0)

    def focus_result(self):
        query = self.search.text().strip().casefold()
        for group in self.groups.values():
            if group.isHidden() or not self.available(group): continue
            for widget in group.body.findChildren(QWidget):
                if widget.isVisible() and widget.isEnabled() and widget.focusPolicy() != Qt.FocusPolicy.NoFocus and query in widget.accessibleName().casefold():
                    widget.setFocus(); self.scroll.ensureWidgetVisible(widget); return
            group.button.setFocus(); self.scroll.ensureWidgetVisible(group); return

    def reveal_group(self, index):
        title = self.jump.itemData(index)
        if title:
            self.search.clear(); self.expansion[title] = True; self.refresh()
            self.scroll.ensureWidgetVisible(self.groups[title])
        with QSignalBlocker(self.jump): self.jump.setCurrentIndex(0)
