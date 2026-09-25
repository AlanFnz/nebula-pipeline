"""Native composition controls: sections and a small set of musical macros."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QRectF, QSignalBlocker, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QDoubleSpinBox, QSpinBox, QComboBox, QPushButton, QSlider, QCheckBox, QTabWidget,
)

from synth import SHAPES
from studio_theme import COLORS
from synth_composition import MACROS, compile_composition, default_geometry, effective_geometry, neutral_macros, normalize_composition, section_ranges, vary_composition
from synth_effects_ui import EffectsPanel


class SectionTimeline(QWidget):
    selected = Signal(int)

    def __init__(self):
        super().__init__()
        self.document = None
        self.index = 0
        self.time = 0
        self.setFixedHeight(90)
        self.setMouseTracking(True)

    def set_document(self, document, index=0):
        self.document = document
        self.index = index
        self.update()

    def set_time(self, time):
        self.time = time
        self.update()

    def rectangles(self):
        if not self.document:
            return []
        ranges = section_ranges(self.document)
        total = ranges[-1][1]
        return [QRectF(start / total * self.width() + 2, 5, (end - start) / total * self.width() - 4, 68) for start, end in ranges]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, rect in enumerate(self.rectangles()):
            section = self.document["sections"][index]
            selected = index == self.index
            painter.setBrush(QColor(COLORS["selected"] if selected else COLORS["panel"]))
            painter.setPen(QPen(QColor(COLORS["accent"] if selected else COLORS["border"]), 1))
            painter.drawRect(rect)
            small_font = self.font(); small_font.setPixelSize(10); painter.setFont(small_font)
            painter.setPen(QColor(COLORS["accent"] if selected else COLORS["muted"]))
            painter.drawText(rect.adjusted(7, 3, -4, -47), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{index + 1:02d}")
            label = self.document["phrases"][section["phrase"]]["name"]
            label_font = self.font(); label_font.setPixelSize(11); painter.setFont(label_font)
            painter.setPen(QColor(COLORS["text"]))
            label = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, max(0, int(rect.width() - 10)))
            painter.drawText(rect.adjusted(5, 20, -5, -21), Qt.AlignmentFlag.AlignCenter, label)
            painter.setFont(small_font); painter.setPen(QColor(COLORS["muted"]))
            painter.drawText(rect.adjusted(4, 43, -4, -3), Qt.AlignmentFlag.AlignCenter, f"{section['duration']:.2f}s")
        if self.document:
            total = section_ranges(self.document)[-1][1]
            x = max(1, min(self.width() - 1, self.time / total * self.width()))
            painter.setPen(QPen(QColor(COLORS["cursor"]), 1))
            painter.drawLine(int(x), 2, int(x), 77)
            painter.fillRect(QRectF(x - 3, 0, 6, 3), QColor(COLORS["cursor"]))

    def mousePressEvent(self, event):
        if not self.document:
            return
        ranges = section_ranges(self.document)
        time = event.position().x() / max(1, self.width()) * ranges[-1][1]
        index = next((i for i, (_start, end) in enumerate(ranges) if time < end), len(ranges) - 1)
        self.selected.emit(index)

    def mouseMoveEvent(self, event):
        for index, rect in enumerate(self.rectangles()):
            if rect.contains(event.position()):
                section = self.document["sections"][index]
                self.setToolTip(f"{index + 1}. {self.document['phrases'][section['phrase']]['name']} · click to edit this section")
                return


class MacroControl(QWidget):
    changed = Signal(float)
    locked = Signal(bool)

    def __init__(self, label, low, high, hint):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        row = QHBoxLayout()
        name = QLabel(label); name.setFixedWidth(88)
        row.addWidget(name)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(round(low * 100), round(high * 100))
        row.addWidget(self.slider, 1)
        self.lock = QCheckBox("Keep")
        self.lock.setToolTip("Keep this control when generating a new take.")
        self.spin = QDoubleSpinBox()
        self.spin.setRange(low, high); self.spin.setSingleStep(.05); self.spin.setDecimals(2)
        self.spin.setSuffix(" ×"); self.spin.setFixedWidth(76); self.spin.setKeyboardTracking(False)
        row.addWidget(self.spin)
        row.addWidget(self.lock)
        layout.addLayout(row)
        self.setToolTip(hint)
        self.spin.valueChanged.connect(self._spin_changed)
        self.slider.valueChanged.connect(lambda value: self.spin.setValue(value / 100))
        self.lock.toggled.connect(self.locked.emit)

    def _spin_changed(self, value):
        with QSignalBlocker(self.slider):
            self.slider.setValue(round(value * 100))
        self.changed.emit(value)

    def set_value(self, value, locked):
        with QSignalBlocker(self.spin), QSignalBlocker(self.slider), QSignalBlocker(self.lock):
            self.spin.setValue(value); self.slider.setValue(round(value * 100)); self.lock.setChecked(locked)


class CompositionPanel(QWidget):
    changed = Signal(object, str)
    failed = Signal(str)
    sectionSelected = Signal(int)
    detailsRequested = Signal()

    def __init__(self, document, index=0, scope=0):
        super().__init__()
        self.document = normalize_composition(document)
        self.index = min(index, len(document["sections"]) - 1)
        self.scope = scope
        self.updating = False
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("02 / COMPOSER"); title.setObjectName("sectionTitle")
        layout.addWidget(title)
        hint = QLabel("Combine effects. Arrange their changes in sections.")
        hint.setWordWrap(True); hint.setObjectName("muted"); layout.addWidget(hint)

        self.arrangement_button = QPushButton(); self.arrangement_button.setCheckable(True)
        self.arrangement_button.setToolTip("Show section arrangement, duration and frame-rate controls.")
        layout.addWidget(self.arrangement_button)

        clip = QGroupBox("CLIP / TIMING")
        grid = QGridLayout(clip)
        self.duration = QDoubleSpinBox(); self.duration.setRange(.24, 300); self.duration.setDecimals(2); self.duration.setSuffix(" s"); self.duration.setKeyboardTracking(False)
        self.fps = QSpinBox(); self.fps.setRange(1, 120); self.fps.setSuffix(" fps"); self.fps.setKeyboardTracking(False)
        grid.addWidget(QLabel("Duration"), 0, 0); grid.addWidget(QLabel("Frame rate"), 0, 1)
        grid.addWidget(self.duration, 1, 0); grid.addWidget(self.fps, 1, 1)
        self.duration.valueChanged.connect(self.resize_clip)
        self.fps.valueChanged.connect(self.change_fps)
        layout.addWidget(clip)

        section_box = QGroupBox("SEQUENCE / ARRANGEMENT")
        section_layout = QVBoxLayout(section_box)
        self.section_combo = QComboBox(); self.section_combo.currentIndexChanged.connect(self.select_section)
        section_layout.addWidget(self.section_combo)
        row = QHBoxLayout()
        self.phrase = QComboBox()
        for key, phrase in self.document["phrases"].items():
            self.phrase.addItem(phrase["name"], key)
        self.phrase.currentIndexChanged.connect(self.change_phrase); row.addWidget(self.phrase, 1)
        self.section_duration = QDoubleSpinBox(); self.section_duration.setRange(1 / self.document["fps"], 300); self.section_duration.setDecimals(2); self.section_duration.setSuffix(" s"); self.section_duration.setFixedWidth(95); self.section_duration.setKeyboardTracking(False)
        self.section_duration.valueChanged.connect(self.resize_section); row.addWidget(self.section_duration)
        section_layout.addLayout(row)
        row = QHBoxLayout()
        for label, callback in (("+ Add", self.add_section), ("Duplicate", self.duplicate_section), ("Remove", self.remove_section), ("←", lambda: self.move_section(-1)), ("→", lambda: self.move_section(1))):
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        section_layout.addLayout(row)
        layout.addWidget(section_box)
        clip.hide(); section_box.hide()
        self.arrangement_button.toggled.connect(clip.setVisible)
        self.arrangement_button.toggled.connect(section_box.setVisible)

        shape = QGroupBox("PARAMETERS / SCOPE")
        shape_layout = QVBoxLayout(shape)
        self.scope_combo = QComboBox(); self.scope_combo.addItems(["Whole clip", "Selected section"])
        self.scope_combo.currentIndexChanged.connect(self.change_scope); shape_layout.addWidget(self.scope_combo)
        self.look_tabs = QTabWidget()
        self.effects_panel = EffectsPanel()
        self.effects_panel.edited.connect(self.change_effect)
        self.look_tabs.addTab(self.effects_panel, "Effects")
        geometry_page = QWidget(); geometry_layout = QVBoxLayout(geometry_page)
        treatment_page = QWidget(); treatment_layout = QVBoxLayout(treatment_page)
        self.look_tabs.addTab(geometry_page, "Geometry"); self.look_tabs.addTab(treatment_page, "Finishing")
        treatment_hint = QLabel("Relative adjustments to the recipe. 1× keeps its original treatment; different recipes can look different at 1×.")
        treatment_hint.setWordWrap(True); treatment_hint.setObjectName("muted"); treatment_layout.addWidget(treatment_hint)
        shape_layout.addWidget(self.look_tabs)
        self.geometry_shape = QComboBox()
        self.geometry_shape.currentIndexChanged.connect(self.change_shape)
        geometry_layout.addWidget(self.geometry_shape)
        self.macro_controls = {}
        for key, (label, low, high, tip) in MACROS.items():
            control = MacroControl(label, low, high, tip)
            control.changed.connect(lambda value, key=key: self.change_macro(key, value))
            control.locked.connect(lambda value, key=key: self.lock_macro(key, value))
            (geometry_layout if key == "width" else treatment_layout).addWidget(control)
            self.macro_controls[key] = control
        self.geometry_controls = {}; self.geometry_rows = {}
        for key, label, low, high, step, suffix in (("height", "Height", .25, 2., .05, " ×"), ("diameter", "Diameter", 5., 150., 1., " %"), ("sides", "Sides", 3, 32, 1, ""), ("rotation", "Rotation", -180., 180., 1., "°")):
            row_widget = QWidget(); row = QHBoxLayout(row_widget); row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(label)); row.addStretch(1)
            control = QSpinBox() if key == "sides" else QDoubleSpinBox()
            control.setRange(low, high); control.setSingleStep(step); control.setSuffix(suffix); control.setKeyboardTracking(False)
            control.setFixedWidth(110)
            if key != "sides": control.setDecimals(2 if key == "height" else 1)
            control.valueChanged.connect(lambda value, key=key: self.change_geometry(key, value / 100 if key == "diameter" else value))
            row.addWidget(control); geometry_layout.addWidget(row_widget)
            self.geometry_controls[key] = control; self.geometry_rows[key] = row_widget
        self.geometry_hint = QLabel(); self.geometry_hint.setWordWrap(True); self.geometry_hint.setObjectName("muted")
        geometry_layout.addWidget(self.geometry_hint); geometry_layout.addStretch(1)
        treatment_layout.addStretch(1)
        self.take_label = QLabel(); self.take_label.setObjectName("muted"); shape_layout.addWidget(self.take_label)
        layout.addWidget(shape)
        details = QPushButton("Open detailed copy…"); details.clicked.connect(self.detailsRequested.emit); layout.addWidget(details)
        self.refresh()

    def target(self, document=None):
        document = self.document if document is None else document
        return document if self.scope == 0 else document["sections"][self.index]

    def refresh(self):
        self.updating = True
        try:
            self.duration.setMinimum(len(self.document["sections"]) / self.document["fps"])
            self.duration.setValue(section_ranges(self.document)[-1][1])
            self.fps.setValue(self.document["fps"])
            count = len(self.document["sections"])
            self.arrangement_button.setText(f"Arrange / {count} {'section' if count == 1 else 'sections'} · {self.duration.value():.2f}s · {self.document['fps']} fps")
            self.section_combo.clear()
            for index, section in enumerate(self.document["sections"]):
                self.section_combo.addItem(f"{index + 1} · {self.document['phrases'][section['phrase']]['name']}")
            self.section_combo.setCurrentIndex(self.index)
            section = self.document["sections"][self.index]
            self.phrase.setCurrentIndex(self.phrase.findData(section["phrase"]))
            self.section_duration.setMinimum(1 / self.document["fps"])
            self.section_duration.setValue(section["duration"])
            self.scope_combo.setCurrentIndex(self.scope)
            target = self.target()
            compiled = compile_composition(self.document)
            prefix = section["id"] + ":"
            states = [state for name, state in compiled["states"].items() if not self.scope or name.startswith(prefix)]
            label = f"SECTION {self.index + 1:02d} / {self.document['phrases'][section['phrase']]['name']}" if self.scope else "WHOLE CLIP / section overrides take priority"
            self.effects_panel.set_context(target["effects"], self.document["effects"] if self.scope else {}, states, label, bool(self.scope))
            for key, control in self.macro_controls.items():
                control.set_value(target["macros"][key], key in target["locks"])
            geometry = target["geometry"]
            self.geometry_shape.clear()
            if self.scope: self.geometry_shape.addItem("From whole clip", "inherit")
            self.geometry_shape.addItem("Original geometry", "original")
            for label in SHAPES: self.geometry_shape.addItem(label, label.lower())
            self.geometry_shape.setCurrentIndex(self.geometry_shape.findData(geometry["shape"]))
            inherited = geometry["shape"] == "inherit"
            resolved = effective_geometry(self.document, section) if self.scope else geometry
            radial = resolved["shape"] in {"circle", "polygon"}
            self.macro_controls["width"].setVisible(not radial)
            for key, control in self.geometry_controls.items():
                value = geometry[key] if key == "height" else resolved[key]
                control.setValue(value * 100 if key == "diameter" else value)
                control.setEnabled(key == "height" or (not inherited and geometry["shape"] != "original"))
                self.geometry_rows[key].setVisible({"height": not radial, "diameter": radial, "sides": resolved["shape"] == "polygon", "rotation": resolved["shape"] not in {"original", "circle"}}[key])
            self.geometry_hint.setText("Diameter is a percentage of image height. The source and ray aperture share the same shape." if radial else "Width and height scale the source and ray aperture. 1× preserves their authored proportions.")
            pristine = not target["effects"] and not target["variation"] and all(value == 1 for value in target["macros"].values()) and geometry == default_geometry(section=bool(self.scope))
            self.take_label.setText("Default controls in this scope" if pristine else (f"Take {target['variation']}" if target["variation"] else "Custom adjustments"))
        finally:
            self.updating = False

    def commit(self, document, action):
        try:
            normalized = normalize_composition(document)
        except ValueError as exc:
            self.index = min(self.index, len(self.document["sections"]) - 1)
            self.refresh(); self.failed.emit(str(exc))
            return
        self.document = normalized
        self.index = min(self.index, len(self.document["sections"]) - 1)
        self.refresh()
        self.changed.emit(self.document, action)

    def select_section(self, index):
        if self.updating or index < 0: return
        self.index = index
        self.scope = 1
        self.refresh()
        self.sectionSelected.emit(index)

    def change_scope(self, index):
        if self.updating: return
        self.scope = index; self.refresh()

    def change_macro(self, key, value):
        if self.updating: return
        document = copy.deepcopy(self.document)
        self.target(document)["macros"][key] = value
        self.commit(document, f"macro:{self.scope}:{self.index}:{key}")

    def change_effect(self, effect_id, entry, action):
        if self.updating: return
        document = copy.deepcopy(self.document)
        effects = self.target(document)["effects"]
        if entry is None:
            effects.pop(effect_id, None)
        else:
            effects[effect_id] = entry
        self.commit(document, f"{action}:{self.scope}:{self.index}:{effect_id}")

    def change_shape(self, index):
        if self.updating or index < 0: return
        document = copy.deepcopy(self.document)
        geometry = self.target(document)["geometry"]
        if geometry["shape"] == "inherit":
            for key in ("diameter", "sides", "rotation"):
                geometry[key] = document["geometry"][key]
        geometry["shape"] = self.geometry_shape.itemData(index)
        self.commit(document, "shape")

    def change_geometry(self, key, value):
        if self.updating: return
        document = copy.deepcopy(self.document)
        self.target(document)["geometry"][key] = value
        self.commit(document, f"geometry:{self.scope}:{self.index}:{key}")

    def lock_macro(self, key, locked):
        if self.updating: return
        document = copy.deepcopy(self.document)
        target = self.target(document)
        target["locks"] = [item for item in target["locks"] if item != key] + ([key] if locked else [])
        self.commit(document, "lock")

    def resize_clip(self, duration):
        if self.updating: return
        document = copy.deepcopy(self.document); fps = document["fps"]
        frames = max(len(document["sections"]), round(duration * fps))
        # Proportional boundaries retain an exact total on the output frame grid.
        original = section_ranges(document); total = original[-1][1]; cursor = 0
        for index, section in enumerate(document["sections"]):
            remaining = len(document["sections"]) - index - 1
            boundary = min(frames - remaining, max(cursor + 1, round(original[index][1] / total * frames)))
            section["duration"] = (boundary - cursor) / fps; cursor = boundary
        self.commit(document, "duration")

    def change_fps(self, fps):
        if self.updating: return
        document = copy.deepcopy(self.document); document["fps"] = fps
        for section in document["sections"]:
            section["duration"] = max(1, round(section["duration"] * fps)) / fps
        self.commit(document, "fps")

    def resize_section(self, duration):
        if self.updating: return
        document = copy.deepcopy(self.document); document["sections"][self.index]["duration"] = duration
        self.commit(document, "section-duration")

    def change_phrase(self, index):
        if self.updating or index < 0: return
        document = copy.deepcopy(self.document); document["sections"][self.index]["phrase"] = self.phrase.itemData(index)
        self.commit(document, "phrase")

    def _new_id(self, document):
        ids = {section["id"] for section in document["sections"]}
        index = 1
        while f"section-{index}" in ids: index += 1
        return f"section-{index}"

    def duplicate_section(self):
        if len(self.document["sections"]) >= 64: return
        document = copy.deepcopy(self.document)
        section = copy.deepcopy(document["sections"][self.index]); section["id"] = self._new_id(document)
        document["sections"].insert(self.index + 1, section); self.index += 1
        self.commit(document, "duplicate"); self.sectionSelected.emit(self.index)

    def add_section(self):
        if len(self.document["sections"]) >= 64: return
        document = copy.deepcopy(self.document)
        phrase_key = self.phrase.currentData(); phrase = document["phrases"][phrase_key]
        section = {"id": self._new_id(document), "phrase": phrase_key, "duration": phrase["end"] - phrase["start"], "macros": neutral_macros(), "variation": 0, "locks": []}
        document["sections"].insert(self.index + 1, section); self.index += 1
        self.commit(document, "add"); self.sectionSelected.emit(self.index)

    def remove_section(self):
        if len(self.document["sections"]) <= 1: return
        document = copy.deepcopy(self.document); del document["sections"][self.index]
        self.commit(document, "remove"); self.sectionSelected.emit(self.index)

    def move_section(self, delta):
        target = self.index + delta
        if not 0 <= target < len(self.document["sections"]): return
        document = copy.deepcopy(self.document)
        document["sections"][self.index], document["sections"][target] = document["sections"][target], document["sections"][self.index]
        self.index = target; self.commit(document, "move"); self.sectionSelected.emit(self.index)

    def new_take(self):
        self.commit(vary_composition(self.document, None if self.scope == 0 else self.index), "take")

    def reset_controls(self):
        document = copy.deepcopy(self.document)
        target = self.target(document); target["macros"] = neutral_macros(); target["variation"] = 0
        target["geometry"] = default_geometry(section=bool(self.scope))
        target["effects"] = {}
        self.commit(document, "reset")
