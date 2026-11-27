"""The artist-facing layer list for a poster composition."""
import copy
from dataclasses import replace

from PySide6.QtCore import Qt, QSignalBlocker, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QMenu, QPushButton, QScrollArea, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from nebula.documents.synth_poster import PosterFrame
from nebula.documents.synth_composition import section_placements
from nebula.effects.synth_effects import parameter
from nebula.resources import RESOURCE_ROOT
from nebula.ui.synth_color_ui import COLORS, ColorPanel
from nebula.ui.synth_effect_parameter_ui import EffectParameter
from nebula.ui.synth_font_ui import FontControl
from nebula.ui.studio_widgets import ComboBox, DoubleSpinBox
from nebula.ui.studio_theme import COLORS as THEME
from nebula.sources.synth_blender_colors import color_spec


class LayerTree(QTreeWidget):
    reorder = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.press = self.pointer = None
        self.marker = QFrame(self.viewport())
        self.marker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.marker.setStyleSheet(f'background: {THEME["accent"]}')
        self.marker.hide()
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(70)
        self.scroll_timer.timeout.connect(self.scroll_drag)
        self.model().modelAboutToBeReset.connect(self.cancel_drag)

    def keyPressEvent(self, event):
        if self.press and event.key() == Qt.Key.Key_Escape:
            self.cancel_drag()
            event.accept()
            return
        if event.modifiers() == Qt.KeyboardModifier.AltModifier and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            item = self.currentItem()
            if item and item.flags() & Qt.ItemFlag.ItemIsDragEnabled:
                key = item.data(0, Qt.ItemDataRole.UserRole)
                self.reorder.emit(key, -1 if event.key() == Qt.Key.Key_Up else 1)
                event.accept()
                return
        super().keyPressEvent(event)

    def cancel_drag(self):
        self.press = self.pointer = None
        self.scroll_timer.stop()
        self.marker.hide()

    def mousePressEvent(self, event):
        self.cancel_drag()
        super().mousePressEvent(event)
        point = event.position().toPoint()
        item = self.itemAt(point)
        if (event.button() == Qt.MouseButton.LeftButton and item and item.flags() & Qt.ItemFlag.ItemIsDragEnabled
                and point.x() > self.visualItemRect(item).left() + 20):
            self.press = item.data(0, Qt.ItemDataRole.UserRole), point

    def destination(self, point):
        if not self.viewport().rect().contains(point):
            return None
        target = self.itemAt(point)
        if not target:
            return None, False, point.y()
        key = target.data(0, Qt.ItemDataRole.UserRole)
        if not target.flags() & Qt.ItemFlag.ItemIsDragEnabled and key not in ('footer', 'paper'):
            return None
        rect = self.visualItemRect(target)
        below = point.y() > rect.center().y() and key != 'paper'
        return key, below, rect.bottom() if below else rect.top()

    def update_marker(self):
        landing = self.destination(self.pointer)
        if landing is None:
            self.marker.hide()
        else:
            self.marker.setGeometry(0, max(0, landing[2]), self.viewport().width(), 2)
            self.marker.show()
            self.marker.raise_()

    def scroll_drag(self):
        if self.pointer is None:
            return
        bar = self.verticalScrollBar()
        step = 1 if self.pointer.y() >= self.viewport().height()-15 else -1 if self.pointer.y() <= 15 else 0
        if step:
            bar.setValue(bar.value()+step*bar.singleStep())
            self.update_marker()

    def mouseMoveEvent(self, event):
        point = event.position().toPoint()
        if self.press and (self.pointer is not None or (point-self.press[1]).manhattanLength() >= QApplication.startDragDistance()):
            self.pointer = point
            self.update_marker()
            if not self.scroll_timer.isActive():
                self.scroll_timer.start()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.pointer is not None:
            key = self.press[0]
            landing = self.destination(event.position().toPoint())
            self.cancel_drag()
            if landing:
                self.reorder.emit(key, landing[:2])
            event.accept()
            return
        self.cancel_drag()
        super().mouseReleaseEvent(event)

    def hideEvent(self, event):
        self.cancel_drag()
        super().hideEvent(event)


class LayerTexture(QGroupBox):
    def __init__(self, composer):
        super().__init__('Texture')
        self.composer = composer
        layout = QVBoxLayout(self)
        self.local_rows = QVBoxLayout()
        layout.addLayout(self.local_rows)
        self.toggle = QPushButton('Shared print texture')
        self.toggle.setObjectName('controlGroup')
        self.toggle.setCheckable(True)
        self.toggle.setAccessibleName('Shared print texture')
        self.toggle.setToolTip('These printing settings affect every layer processed by the same finish.')
        self.toggle.toggled.connect(self.show_shared)
        layout.addWidget(self.toggle)
        self.shared = QWidget()
        self.shared_rows = QVBoxLayout(self.shared)
        self.shared_rows.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shared)
        self.shared.hide()
        self.paths = ((), ())
        self.controls = {}
        self.group_titles = []
        self.scopes = {}
        self.context = None
        self.hide()

    def bind(self, paths, scopes):
        if paths != self.paths or scopes != self.scopes:
            self.paths, self.scopes = paths, scopes
            with QSignalBlocker(self.toggle):
                self.toggle.setChecked(False)
            self.show_shared(False)
        else:
            self.refresh_rows()

    def show_shared(self, expanded):
        self.shared.setVisible(expanded)
        self.toggle.setText('Shared print texture ' + ('▾' if expanded else '▸'))
        self.toggle.setVisible(bool(self.paths[1]))
        self.setVisible(any(self.paths))
        self.context = None
        self.refresh_rows()

    def refresh_rows(self):
        effects = self.composer.effects_panel
        if self.context is effects.authored_summary:
            return
        self.context = effects.authored_summary
        local, shared = self.paths
        visible = local + (shared if self.toggle.isChecked() else ())
        for title in self.group_titles:
            title.hide()
            title.deleteLater()
        self.group_titles.clear()
        last_scope = None
        for path in tuple(self.controls):
            if path not in visible:
                row = self.controls.pop(path)
                row.hide()
                row.setParent(None)
                row.deleteLater()
        for path in visible:
            owner = path.split('.')[0]
            if path not in self.controls:
                row = self.controls[path] = EffectParameter(path)
                row.changed.connect(lambda value, p=path, o=owner: effects.change_parameter(p, value, o))
                row.reset.connect(lambda p=path, o=owner: effects.reset_parameter(p, o))
                row.animate.connect(effects.automation_requested.emit)
            row = self.controls[path]
            layout = self.local_rows if path in local else self.shared_rows
            scope = self.scopes.get(path)
            if scope and scope != last_scope:
                title = QLabel(scope)
                title.setObjectName('sectionTitle')
                layout.addWidget(title)
                self.group_titles.append(title)
                last_scope = scope
            layout.addWidget(row)
            effects.refresh_base_control(row, owner)
            row.set_automation_count(effects.automation_counts.get(path, 0))


class PosterLayers(QWidget):
    selection_changed = Signal()
    frame_changed = Signal()
    animate_requested = Signal(str)

    def __init__(self, composer):
        super().__init__()
        self.composer = composer
        self.frame = self.sequence = None
        self.seconds = None
        self.at_playhead = True
        self.selected = None
        self.items = {}
        self.groups = {}
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        self.add_button = QPushButton('+ Layer')
        menu = QMenu(self.add_button)
        menu.addAction('Text', lambda: self.add_layer('text'))
        menu.addAction('Ink plate', lambda: self.add_layer('plate'))
        self.add_button.setMenu(menu)
        self.duplicate = QPushButton('Duplicate')
        self.duplicate.clicked.connect(self.duplicate_layer)
        for button in (self.add_button, self.duplicate):
            actions.addWidget(button)
            button.setToolTip('Changes the layer stack for the whole composition.')
        actions.addStretch()
        layout.addLayout(actions)
        self.tree = LayerTree()
        icons = RESOURCE_ROOT / 'assets'
        self.tree.setStyleSheet(
            'QTreeWidget::indicator { width: 17px; height: 17px; }'
            f'QTreeWidget::indicator:checked {{ image: url("{icons / "layer-visible.svg"}"); }}'
            f'QTreeWidget::indicator:unchecked {{ image: url("{icons / "layer-hidden.svg"}"); }}')
        self.tree.setAccessibleName('Poster layers')
        self.tree.setHeaderLabels(['Layer', 'Kind'])
        self.tree.setToolTip('Front layers are at the top. Click the eye to show or hide a layer. Drag or use Alt+Up/Down to reorder.')
        self.tree.reorder.connect(self.reorder_layer)
        self.tree.itemChanged.connect(self.visibility_changed)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setMinimumHeight(150)
        self.tree.currentItemChanged.connect(self._select_item)
        self.tree.itemDoubleClicked.connect(lambda item, _: self.edit() if item.data(0, Qt.ItemDataRole.UserRole) else None)
        layout.addWidget(self.tree, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        properties = QWidget()
        scroll.setWidget(properties)
        layout.addWidget(scroll, 2)
        layout = QVBoxLayout(properties)
        self.selection_title = QLabel()
        self.selection_title.setObjectName('sectionTitle')
        self.selection_title.setWordWrap(True)
        heading = QHBoxLayout()
        heading.addWidget(self.selection_title, 1)
        self.animate = QPushButton('Animate this layer…')
        self.animate.clicked.connect(self.animate_layer)
        heading.addWidget(self.animate)
        layout.addLayout(heading)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setObjectName('muted')
        layout.addWidget(self.detail)
        self.position = QWidget()
        positions = QHBoxLayout(self.position)
        positions.setContentsMargins(0, 0, 0, 0)
        self.axes = []
        for axis in ('X', 'Y'):
            field = DoubleSpinBox()
            field.setRange(-32768., 32768.)
            field.setDecimals(2)
            field.setSuffix(' px')
            field.setKeyboardTracking(False)
            field.setAccessibleName('Layer center ' + axis)
            field.editingFinished.connect(self._position_edited)
            form = QFormLayout()
            form.addRow(axis, field)
            positions.addLayout(form)
            self.axes.append(field)
        layout.addWidget(self.position)
        self.align = QPushButton('Align center…')
        self.align.setMenu(QMenu(self.align))
        self.align.menu().aboutToShow.connect(self.alignment_targets)
        layout.addWidget(self.align)
        self.properties = QWidget()
        self.form = QFormLayout(self.properties)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.wording = QPushButton()
        self.wording.setAccessibleName('Edit layer wording')
        self.wording.clicked.connect(self.edit_wording)
        self.form.addRow('Wording', self.wording)
        self.font_control = FontControl()
        self.font_control.changed.connect(lambda v: self.change('font', v))
        self.form.addRow('Typeface', self.font_control)
        self.text_fields = {}
        for label in ('Type size', 'Letter spacing'):
            field = DoubleSpinBox()
            field.setDecimals(3)
            field.setKeyboardTracking(False)
            field.setAccessibleName(label)
            field.valueChanged.connect(lambda v, f=field: self.change(f.property('parameter'), v))
            self.form.addRow(label, field)
            self.text_fields[label] = field
        self.dimensions = {}
        self.plate_shape = ComboBox()
        self.plate_shape.setAccessibleName('Plate shape')
        self.plate_shape.addItems(parameter('dye_transfer.mask_shape').choices[1:])
        self.plate_shape.activated.connect(lambda i: self.change('mask_shape', i+1))
        self.form.addRow('Shape', self.plate_shape)
        for key, label in (('mask_size', 'Plate height'), ('mask_aspect', 'Width / height'), ('mask_angle', 'Rotation')):
            spec = parameter('dye_transfer.' + key)
            field = DoubleSpinBox()
            field.setDecimals(3)
            field.setRange(spec.minimum, spec.maximum)
            field.setSingleStep(spec.step)
            if key == 'mask_size':
                field.display_scale = 100.
                field.setSuffix(' %')
            elif key == 'mask_angle':
                field.setSuffix('°')
            field.setKeyboardTracking(False)
            field.setAccessibleName(label)
            field.valueChanged.connect(lambda v, path=key: self.change(path, v))
            self.form.addRow(label, field)
            self.dimensions[key] = field
        layout.addWidget(self.properties)
        names = {'paper': 'Paper color', 'ink': 'Printed text color',
                 'mask_ink': 'Plate color on type', 'mask_paper': 'Plate color on paper'}
        self.colors = ColorPanel(tuple(replace(spec, label=names[spec.key]) for spec in COLORS))
        self.colors.context_provider = composer.color_context
        self.colors.changed.connect(composer.change_color)
        self.colors.restored.connect(composer.restore_color)
        layout.addWidget(self.colors)
        self.fill_host = QVBoxLayout()
        layout.addLayout(self.fill_host)
        self.fill_key = self.fill_panel = None
        self.texture = LayerTexture(composer)
        layout.addWidget(self.texture)
        self.editor = QPushButton()
        self.editor.clicked.connect(self.edit)
        layout.addWidget(self.editor)
        layout.addStretch()

    def add_layer(self, kind, duplicate=None):
        doc = copy.deepcopy(self.composer.document)
        try:
            key = self.frame.add_layer(doc, kind, duplicate=duplicate, above=self.selected)
        except ValueError as exc:
            self.composer.failed.emit(str(exc))
            return
        self.composer.commit(doc, 'poster-duplicate' if duplicate else 'poster-add')
        self.select(key)

    def duplicate_layer(self):
        if self.selected in self.frame.order:
            self.add_layer(self.frame.by_key[self.selected].kind, self.selected)

    def alignment_targets(self):
        menu = self.align.menu()
        menu.clear()
        menu.addAction('Center on sheet', lambda: self.align_center(None))
        for key in self.frame.order:
            if key != self.selected and key not in self.frame.hidden and self.frame.by_key[key].kind == 'plate':
                menu.addAction('Center on ' + self.frame.by_key[key].label, lambda checked=False, k=key: self.align_center(k))

    def align_center(self, target):
        x, y = self.frame.center(self.selected)
        cx, cy = self.frame.center(target) if target else (v/2 for v in self.frame.canvas)
        self.commit_move(self.frame, self.selected, cx-x, cy-y)

    def reorder_layer(self, key, destination):
        order = self.frame.order
        if key not in order:
            return
        if isinstance(destination, int):
            neighbor = order.index(key) + destination
            if not 0 <= neighbor < len(order):
                return
            destination = order[neighbor], destination > 0
        before, below = destination
        if key == before:
            return
        if before == 'footer' and self.frame.footer:
            before = self.frame.footer[-1 if below else 0]
        if before not in order and before not in ('paper', None):
            return
        updated = [k for k in order if k != key]
        index = updated.index(before) + int(below) if before in updated else len(updated)
        updated.insert(index, key)
        if updated != order:
            doc = copy.deepcopy(self.composer.document)
            # Preserve the slots of layers that are only present in other clips.
            from nebula.effects.synth_effect_order import replace_ordered_slots
            previous = list(dict.fromkeys([*doc['poster'].get('order', ()), *order]))
            doc['poster']['order'] = replace_ordered_slots(previous, updated)
            self.composer.commit(doc, 'poster-order')

    def visibility_changed(self, item, column):
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if column or not self.frame or key not in self.frame.order:
            return
        hidden = set(self.frame.hidden)
        if item.checkState(0) == Qt.CheckState.Checked:
            hidden.discard(key)
        else:
            hidden.add(key)
        if hidden != self.frame.hidden:
            doc = copy.deepcopy(self.composer.document)
            doc['poster']['hidden'] = sorted(hidden)
            self.composer.commit(doc, 'poster-visibility')

    def animate_layer(self):
        node = self.frame.by_key.get(self.selected)
        if node and node.key in self.frame.order:
            path = 'mask_angle' if node.kind == 'plate' else 'size' if node.key == 'text' else 'x'
            self.animate_requested.emit(f'{node.owner}.{path}')

    def refresh(self, seconds=None):
        sequence = self.composer.compiled
        if seconds is None:
            seconds = self.composer.playhead_seconds()
        self.at_playhead = True
        if self.composer.scope:
            spans = [(start, end) for i, start, end, _ in section_placements(self.composer.document)
                     if i == self.composer.index]
            self.at_playhead = any(start <= seconds < end for start, end in spans)
            if not self.at_playhead:
                seconds = spans[0][0]
        if sequence is self.sequence and seconds == self.seconds:
            return
        self.sequence, self.seconds = sequence, seconds
        current = self.frame
        self.frame = PosterFrame(sequence, seconds, self.composer.document['poster'])
        if current is None or self.frame.layers != current.layers or self.frame.hidden != current.hidden:
            expanded = {name for name, item in self.groups.items() if item.isExpanded()}
            with QSignalBlocker(self.tree):
                self.tree.clear()
                self.items.clear()
                self.groups.clear()
                for node in self.frame.layers:
                    if node.group and node.group not in self.groups:
                        group = QTreeWidgetItem(self.tree, [node.group])
                        group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                        if node.group == 'Footer':
                            group.setData(0, Qt.ItemDataRole.UserRole, 'footer')
                            group.setText(1, 'Group')
                            self.items['footer'] = group
                        else:
                            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                        group.setExpanded(node.group in expanded)
                        self.groups[node.group] = group
                    kind = {'text': 'Text', 'plate': 'Shape', 'paper': 'Background', 'finish': 'Effect'}[node.kind]
                    item = QTreeWidgetItem(self.groups.get(node.group, self.tree), [node.label, kind])
                    item.setData(0, Qt.ItemDataRole.UserRole, node.key)
                    if node.key in self.frame.order:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled)
                        item.setCheckState(0, Qt.CheckState.Unchecked if node.key in self.frame.hidden else Qt.CheckState.Checked)
                        item.setToolTip(0, 'Show or hide in the whole composition. Drag to reorder.')
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                    self.items[node.key] = item
        self.select(self.selected if self.selected in self.items else None)
        self.frame_changed.emit()

    def select(self, key):
        self.selected = key if key in self.items else None
        item = self.items.get(self.selected)
        with QSignalBlocker(self.tree):
            self.tree.setCurrentItem(item)
            if item and item.parent():
                item.parent().setExpanded(True)
        node = self.frame.by_key.get(self.selected)
        artwork = bool(node and node.key in self.frame.order)
        self.duplicate.setEnabled(artwork)
        if artwork:
            self.duplicate.setToolTip('Make an independent impression from the current source settings.'
                                      if node.key in ('plate', 'text') else
                                      'Duplicate the impression across the composition, including its clip edits and automation.')
        self.animate.setVisible(artwork)
        self.selection_title.setVisible(bool(node))
        if node:
            self.selection_title.setText(f"{node.kind.capitalize()} · {node.label}" if artwork else node.label)
            self.selection_title.setTextFormat(Qt.TextFormat.PlainText)
        movable = bool(node and node.kind in ('text', 'plate', 'group'))
        self.position.setVisible(movable)
        self.align.setVisible(movable)
        self.editor.setVisible(bool(node and node.owner))
        self.detail.setVisible(not node or node.kind in ('paper', 'group'))
        self.detail.setText('Select a layer here or click it in the monitor.' if not node else
                            'Drag to move the whole footer. Expand Footer and select an inscription to edit its texture.' if node.kind == 'group' else
                            'Paper is fixed to the canvas. Its color and texture are editable.' if node.kind == 'paper' else '')
        if node and node.kind != 'group':
            self.editor.setText({'text': 'More typography controls…', 'plate': 'More plate controls…', 'paper': 'More paper controls…',
                                 'finish': 'Edit effect…'}[node.kind])
        text = bool(node and node.kind == 'text')
        plate = bool(node and node.kind == 'plate')
        self.properties.setVisible(text or plate)
        self.form.setRowVisible(self.plate_shape, plate)
        if plate:
            self.plate_shape.setCurrentIndex(self.frame.modules[node.owner]['mask_shape']-1)
        self.form.setRowVisible(self.wording, text)
        self.form.setRowVisible(self.font_control, text)
        for field in self.text_fields.values():
            self.form.setRowVisible(field, text)
        if text:
            params = self.frame.modules[node.owner]
            self.wording.setText(node.label)
            with QSignalBlocker(self.font_control):
                self.font_control.setValue(params['font'])
            size_key = 'size' if node.key == 'text' or params.get('layout') == 1 else 'height'
            for label, name in (('Type size', size_key), ('Letter spacing', 'tracking')):
                field = self.text_fields[label]
                spec = parameter(f'{node.owner}.{name}')
                with QSignalBlocker(field):
                    field.setProperty('parameter', name)
                    field.setRange(spec.minimum, spec.maximum)
                    field.setSingleStep(spec.step)
                    field.display_scale = 100. if label == 'Type size' else 1.
                    field.setSuffix(' %' if label == 'Type size' else '')
                    field.setValue(params[name])
        for key, field in self.dimensions.items():
            self.form.setRowVisible(field, plate)
            if plate:
                with QSignalBlocker(field):
                    field.setValue(self.frame.modules[node.owner][key])
        colors = []
        direct_fill = None
        word_count = sum(self.frame.by_key[k].kind == 'text' for k in self.frame.before_print)
        count_label = f'{word_count} text ' + ('layer' if word_count == 1 else 'layers')
        if self.selected == 'plate':
            target = int(self.frame.dye['mask_target'])
            colors = {1: ['mask_ink'], 2: ['mask_paper'], 3: ['mask_ink', 'mask_paper']}.get(target, [])
        elif node and node.kind == 'paper' and self.frame.dye:
            colors = ['paper']
        elif self.selected in self.frame.before_print:
            colors = ['ink']
            self.detail.setText(f'Shared ink · {count_label}. This color applies to all of them.')
            self.detail.show()
        elif text or plate:
            direct_fill = 'layer_fill/' + node.owner
        self.colors.show_colors(colors)
        if direct_fill != self.fill_key:
            if self.fill_panel:
                self.fill_panel.hide()
                self.fill_panel.deleteLater()
            self.fill_key, self.fill_panel = direct_fill, None
            if direct_fill:
                self.fill_panel = ColorPanel((color_spec(direct_fill),))
                self.fill_panel.context_provider = self.composer.color_context
                self.fill_panel.changed.connect(self.composer.change_color)
                self.fill_panel.restored.connect(self.composer.restore_color)
                self.fill_host.addWidget(self.fill_panel)
        if self.fill_panel:
            self.fill_panel.show_colors([direct_fill])
        paths = self.frame.texture_paths(self.selected)
        scopes = {}
        for path in paths[1]:
            if path in ('dye_transfer.stock_relief', 'dye_transfer.fiber_size', 'dye_transfer.grain'):
                label = 'Whole sheet · paper and printed ink'
            elif path.startswith('photocopy.'):
                label = 'Shared screen · paper and screened lettering'
            else:
                label = 'Shared ink · ' + count_label
            scopes[path] = label
        self.texture.setTitle('Layer texture · ' + node.label if node and node.kind in ('text', 'plate') else 'Texture')
        self.texture.bind(paths, scopes)
        if movable:
            self.center = self.frame.center(self.selected)
            for field, v in zip(self.axes, self.center):
                with QSignalBlocker(field):
                    field.setValue(v)
        self.selection_changed.emit()

    def _select_item(self, item, previous):
        self.select(item.data(0, Qt.ItemDataRole.UserRole) if item else None)

    def change(self, name, value):
        node = self.frame.by_key[self.selected]
        if self.frame.modules[node.owner][name] == value:
            return
        self.composer.change_object_parameter(node.owner, f'{node.owner}.{name}', value)

    def edit_wording(self):
        node = self.frame.by_key[self.selected]
        wording, accepted = QInputDialog.getMultiLineText(
            self, 'Layer wording', 'Wording', self.frame.modules[node.owner]['content'])
        if accepted:
            self.change('content', wording)

    def gesture_document(self, frame, key, mode, delta):
        doc = copy.deepcopy(self.composer.document)
        if mode == 'move':
            frame.move(self.composer.target(doc), key, *delta)
        else:
            frame.transform_plate(self.composer.target(doc), key, *delta)
        return doc

    def commit_move(self, frame, key, dx, dy):
        self.commit_gesture(frame, key, 'move', (dx, dy))

    def commit_gesture(self, frame, key, mode, delta):
        doc = self.gesture_document(frame, key, mode, delta)
        if doc != self.composer.document:
            self.composer.commit(doc, 'poster-' + mode)

    def _position_edited(self):
        if self.selected is None or self.frame.by_key[self.selected].kind not in ('text', 'plate', 'group'):
            return
        # The display rounds to hundredths. Preserve untouched native precision.
        dx, dy = (field.value() - v if field.value() != round(v, 2) else 0.
                  for field, v in zip(self.axes, self.center))
        if dx or dy:
            self.commit_move(self.frame, self.selected, dx, dy)

    def edit(self):
        if self.selected is None or self.selected == 'footer':
            return
        node = self.frame.by_key[self.selected]
        c = self.composer
        if not node.owner:
            return
        if node.owner == 'text':
            c.open_object_details('text', False)
            return
        c.look_tabs.setCurrentWidget(c.effects_panel)
        c.effects_panel.inspect_effect(node.owner)
        control = {'plate': 'mask_shape', 'paper': 'paper_hue' if node.owner == 'dye_transfer' else 'light',
                   'text': 'content'}.get(node.kind)
        if control:
            c.effects_panel.reveal_control(f'{node.owner}.{control}')
