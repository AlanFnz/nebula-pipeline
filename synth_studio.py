#!/usr/bin/env python3
"""Native source-free Nebula Synth editor."""
from __future__ import annotations

import copy
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QRunnable, QRect, QSignalBlocker, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGroupBox,
    QHBoxLayout, QGridLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QSlider,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QMessageBox, QSizePolicy,
)

from media import Cancellation
from studio import STYLE
from synth import MODULE_BY_ID, curated_presets, default_synth_preset, load_synth, normalize_synth, render_synth_frame, save_synth
from synth_media import export_synth_video
from synth_sequence import load_sequence, normalize_sequence, reference_sequence, render_sequence_frame, save_sequence
from synth_composition import FORMAT, compile_composition, composition_from_sequence, load_composition, normalize_composition, reference_composition, save_composition, section_ranges
from synth_composer_ui import CompositionPanel, SectionTimeline


class SynthViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.packet = None
        self.setMinimumSize(460, 320)

    def set_packet(self, packet):
        self.packet = packet
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101216"))
        if not self.packet:
            painter.setPen(QColor("#929ba9"))
            painter.setFont(QFont("Helvetica", 15))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Generate a synth frame\n\nLuminous slabs · irregular blinds")
            return
        (w, h), raw = self.packet
        ratio = min(self.width() / w, self.height() / h)
        target = (round((self.width() - w * ratio) / 2), round((self.height() - h * ratio) / 2), round(w * ratio), round(h * ratio))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(QRect(*target), QImage(raw, w, h, w * 3, QImage.Format.Format_RGB888))


class SynthControl(QWidget):
    changed = Signal()

    def __init__(self, spec, value):
        super().__init__()
        self.spec = spec
        self.lock = QCheckBox("lock")
        self.lock.setToolTip("Keep this parameter fixed when Generate variation is pressed.")
        if spec.choices:
            self.spin = QComboBox(); self.spin.addItems(spec.choices); self.spin.setCurrentIndex(int(value))
            self.spin.currentIndexChanged.connect(lambda _value: self.changed.emit())
            layout = QVBoxLayout(self); layout.setContentsMargins(0, 3, 0, 4)
            label = QLabel(spec.label); label.setToolTip(spec.hint); layout.addWidget(label)
            row = QHBoxLayout(); row.addWidget(self.spin, 1); row.addWidget(self.lock); layout.addLayout(row)
            return
        self.spin = QSpinBox() if spec.kind == "int" else QDoubleSpinBox()
        self.spin.setRange(spec.minimum, spec.maximum)
        if spec.kind == "float":
            self.spin.setDecimals(max(2, len(str(spec.step).split(".")[-1])))
        self.spin.setSingleStep(spec.step)
        self.spin.setKeyboardTracking(False)
        self.spin.setValue(value)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        scale = 1 if spec.kind == "int" else 1000
        self.slider.setRange(round(spec.minimum * scale), round(spec.maximum * scale))
        self.slider.setValue(round(float(value) * scale))
        self.slider.valueChanged.connect(lambda v: self.spin.setValue(v / scale))
        self.spin.valueChanged.connect(lambda v: (self.slider.setValue(round(float(v) * scale)), self.changed.emit()))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 4)
        label = QLabel(spec.label)
        label.setToolTip(spec.hint)
        layout.addWidget(label)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.slider, 1)
        self.spin.setFixedWidth(78)
        row.addWidget(self.spin)
        self.lock.setFixedWidth(48)
        row.addWidget(self.lock)
        layout.addLayout(row)
        layout.addWidget(self.lock)

    def value(self):
        return self.spin.currentIndex() if self.spec.choices else self.spin.value()

    def set_value(self, value):
        if self.spec.choices:
            self.spin.setCurrentIndex(int(value))
        else:
            self.spin.setValue(value)


class JobSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)


class RenderJob(QRunnable):
    def __init__(self, preset, time_seconds, size, settings_generation, request_serial, sequence=None):
        super().__init__()
        self.preset, self.time_seconds, self.size = copy.deepcopy(preset), time_seconds, size
        self.settings_generation, self.request_serial = settings_generation, request_serial
        self.sequence = copy.deepcopy(sequence)
        self.signals = JobSignals()

    def run(self):
        try:
            if self.sequence is not None:
                image = render_sequence_frame(self.sequence, self.time_seconds, self.size)
            else:
                treatment_frame = round(self.time_seconds * self.preset["treatment_fps"])
                image = render_synth_frame(self.preset, treatment_frame, self.time_seconds, self.size)
            self.signals.done.emit((self.settings_generation, self.request_serial, self.time_seconds, image.size, image.tobytes()))
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class ExportJob(QRunnable):
    def __init__(self, preset, path, size, sequence=None):
        super().__init__()
        self.preset, self.path, self.size = copy.deepcopy(preset), path, size
        self.sequence = copy.deepcopy(sequence)
        self.cancel = Cancellation()
        self.signals = JobSignals()

    def run(self):
        try:
            export_synth_video(self.preset, self.path, cancel=self.cancel, size=self.size, sequence=self.sequence, progress=lambda a, b: self.signals.progress.emit(a, b))
            self.signals.done.emit(self.path)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class SynthStudio(QMainWindow):
    def __init__(self, preset=None, sequence=None, composition=None):
        super().__init__()
        self.setWindowTitle("Nebula Synth")
        self.resize(1280, 800)
        if preset is None and sequence is None and composition is None:
            composition = reference_composition(refined=True)
        if preset is None:
            preset = curated_presets()["Reference blinds"]
        self.preset = normalize_synth(preset)
        self.composition = normalize_composition(composition) if composition is not None else None
        self.sequence = compile_composition(self.composition) if self.composition is not None else (normalize_sequence(sequence) if sequence is not None else None)
        self.composer = None
        self.composition_index = 0
        self.composition_scope = 0
        self.undo_compositions = []
        self.redo_compositions = []
        self.edit_key = None
        self.edit_timer = QTimer(self); self.edit_timer.setSingleShot(True); self.edit_timer.timeout.connect(lambda: setattr(self, "edit_key", None))
        self.detail_windows = []
        self.closing = False
        self.sequence_table = None
        self.sequence_updating = False
        self.sequence_state_updating = False
        self.sequence_state_name = None
        self.sequence_state_controls = {}
        self.sequence_enabled_controls = {}
        self.sequence_field_controls = {}
        self.settings_generation = 0
        self.request_serial = 0
        self.last_displayed_request = 0
        self.current_time = 0.0
        self.jobs = QThreadPool.globalInstance()
        self.pending_jobs = []
        self.render_running = False
        self.render_queued = False
        self.export_job = None
        self.controls = {}
        self.module_groups = []
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.advance)
        self.build_ui()
        self.rebuild_modules()
        self.update_timeline_max()
        self.request_frame()

    def build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        header = QHBoxLayout()
        brand = QLabel("NEBULA / SYNTHESIS")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch(1)
        self.composition_widgets = []
        for text, callback in (("New take", self.generate_variation), ("Reset controls", lambda: self.composer and self.composer.reset_controls()), ("Undo", self.undo_composition), ("Redo", self.redo_composition)):
            button = QPushButton(text); button.clicked.connect(callback)
            if text == "New take": button.setObjectName("primary")
            if text == "Undo": self.composition_undo_button = button
            if text == "Redo": self.composition_redo_button = button
            header.addWidget(button); self.composition_widgets.append(button)
        preset_label = QLabel("Preset")
        header.addWidget(preset_label)
        self.preset_widgets = [preset_label]
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([*curated_presets().keys(), "Custom"])
        preset_name = self.preset.get("name", "Custom")
        self.preset_combo.setCurrentText(preset_name if preset_name in curated_presets() else "Custom")
        self.preset_combo.currentTextChanged.connect(self.select_curated)
        header.addWidget(self.preset_combo)
        self.preset_widgets.append(self.preset_combo)
        for text, slot in (("Save preset", self.save_preset_dialog), ("Load preset", self.load_preset_dialog), ("Generate variation", self.generate_variation)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            header.addWidget(button)
            self.preset_widgets.append(button)
        outer.addLayout(header)
        sequence_actions = QHBoxLayout()
        for text, slot in (("New clip", self.new_composition), ("Refined 15s", self.load_refined_sequence), ("Approved 15s", self.load_reference_sequence), ("Save…", self.save_sequence_dialog), ("Open…", self.load_sequence_dialog)):
            button = QPushButton(text); button.clicked.connect(slot); sequence_actions.addWidget(button)
        sequence_actions.addStretch(1)
        outer.addLayout(sequence_actions)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); left_layout = QVBoxLayout(left)
        self.viewer = SynthViewer(); left_layout.addWidget(self.viewer, 1)
        self.section_timeline = SectionTimeline()
        self.section_timeline.selected.connect(lambda index: self.composer and self.composer.select_section(index))
        left_layout.addWidget(self.section_timeline)
        self.status = QLabel("Source-free deterministic synthesis")
        self.status.setObjectName("muted"); left_layout.addWidget(self.status)
        timeline = QHBoxLayout()
        self.play = QPushButton("Play"); self.play.setCheckable(True); self.play.toggled.connect(self.toggle_play)
        timeline.addWidget(self.play)
        self.timeline = QSlider(Qt.Orientation.Horizontal); self.timeline.valueChanged.connect(self.scrub); timeline.addWidget(self.timeline, 1)
        self.time_label = QLabel("0.00s"); timeline.addWidget(self.time_label)
        left_layout.addLayout(timeline)
        export_row = QHBoxLayout()
        self.quality = QComboBox(); self.quality.addItems(["Preview 360p", "Full 720×576"]); self.quality.currentIndexChanged.connect(lambda _index: self.invalidate()); export_row.addWidget(self.quality)
        export = QPushButton("Export MP4"); export.setObjectName("primary"); export.clicked.connect(self.export_dialog); export_row.addWidget(export)
        self.cancel_export = QPushButton("Cancel export"); self.cancel_export.setEnabled(False); self.cancel_export.clicked.connect(self.cancel_export_job); export_row.addWidget(self.cancel_export)
        left_layout.addLayout(export_row)
        split.addWidget(left)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); panel = QWidget(); panel.setMinimumWidth(0); self.panel_layout = QVBoxLayout(panel); self.panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop); scroll.setWidget(panel); split.addWidget(scroll); split.setSizes([760, 460]); outer.addWidget(split, 1)
        self.setCentralWidget(root)

    def global_group(self):
        group = QGroupBox("Global timing")
        layout = QVBoxLayout(group)
        specs = [("treatment_fps", "Treatment FPS", 1, 120, 1), ("export_fps", "Export FPS", 1, 120, 1), ("loop_seconds", "Loop seconds", .1, 3600, .1), ("speed", "Animation speed", 0, 8, .05), ("depth", "Animation depth", 0, 1, .01), ("seed", "Seed", 0, 2**31 - 1, 1)]
        self.global_controls = {}
        for key, label, lo, hi, step in specs:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); spin = QSpinBox() if key in {"treatment_fps", "export_fps", "seed"} else QDoubleSpinBox(); spin.setRange(lo, hi); spin.setSingleStep(step); spin.setValue(self.preset[key]); spin.setKeyboardTracking(False); row.addWidget(spin); layout.addLayout(row); self.global_controls[key] = spin; spin.valueChanged.connect(lambda _v, k=key: self.global_changed(k))
        row = QHBoxLayout(); row.addWidget(QLabel("Variation mode")); combo = QComboBox(); combo.addItems(["smooth", "stepped"]); combo.setCurrentText(self.preset["variation_mode"]); combo.currentTextChanged.connect(lambda value: self.global_changed("variation_mode", value)); row.addWidget(combo); layout.addLayout(row); self.global_controls["variation_mode"] = combo
        modulation = QGroupBox("Animation modulation")
        modulation_layout = QVBoxLayout(modulation)
        self.mod_controls = {}
        targets = self.preset.get("animation", {}).get("targets", {})
        for target in ("blinds.aperture", "blinds.aperture_position", "blinds.curvature", "slab.width", "slab.spacing"):
            values = targets.get(target, {"depth": 0.0, "rate": 0.0})
            module_id, param_key = target.split(".", 1)
            module = MODULE_BY_ID[module_id]
            spec = next(spec for spec in module.params if spec.key == param_key)
            block = QVBoxLayout(); title = QLabel(f"{module.label} · {spec.label}"); title.setToolTip(spec.hint); block.addWidget(title)
            row = QHBoxLayout()
            for key, label, lo, hi, step in (("depth", "depth", 0, 1, .01), ("rate", "rate", 0, 4, .01)):
                row.addWidget(QLabel(label)); spin = QDoubleSpinBox(); spin.setRange(lo, hi); spin.setSingleStep(step); spin.setValue(values.get(key, 0)); spin.valueChanged.connect(self.modulation_changed); row.addWidget(spin); self.mod_controls[(target, key)] = spin
            block.addLayout(row); modulation_layout.addLayout(block)
        layout.addWidget(modulation)
        return group

    def sequence_group(self):
        group = QGroupBox("Editable sequence cues")
        layout = QVBoxLayout(group)
        label = QLabel("15-second reference study · edit times, states and transition types")
        label.setWordWrap(True)
        layout.addWidget(label)
        table = QTableWidget(len(self.sequence["cues"]), 6)
        table.setHorizontalHeaderLabels(["Time", "State", "Transition", "Hold / blend", "Intensity", "Direction"])
        table.setAlternatingRowColors(True)
        table.setStyleSheet("QTableView { alternate-background-color: #22272e; selection-background-color: #43546b; }")
        table.setMinimumHeight(190)
        table.setMaximumHeight(280)
        table.setColumnWidth(0, 62); table.setColumnWidth(1, 90); table.setColumnWidth(2, 82); table.setColumnWidth(3, 82); table.setColumnWidth(4, 62); table.setColumnWidth(5, 62)
        for row, cue in enumerate(self.sequence["cues"]):
            values = (f"{cue['time']:.2f}", cue["state"], cue["transition"], f"{cue.get('duration', 0):.2f}", f"{cue.get('intensity', 1.0):.2f}", f"{cue.get('direction', 1.0):.2f}")
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.cellChanged.connect(self.sequence_cell_changed)
        table.itemSelectionChanged.connect(self.sequence_selection_changed)
        self.sequence_table = table
        layout.addWidget(table)
        buttons = QHBoxLayout()
        add = QPushButton("Add cue"); add.clicked.connect(self.add_sequence_cue)
        remove = QPushButton("Remove cue"); remove.clicked.connect(self.remove_sequence_cue)
        buttons.addWidget(add); buttons.addWidget(remove); buttons.addStretch(1)
        layout.addLayout(buttons)
        return group

    def sequence_settings_group(self):
        group = QGroupBox("Sequence timing and field")
        layout = QVBoxLayout(group)
        self.sequence_updating = True
        self.sequence_field_controls = {}
        timing = QGridLayout()
        for column, (key, label, minimum, maximum, step, integer) in enumerate((("duration", "seconds", .1, 3600, .1, False), ("fps", "FPS", 1, 120, 1, True), ("seed", "seed", 0, 2**31 - 1, 1, True))):
            timing.addWidget(QLabel(label), 0, column)
            spin = QSpinBox() if integer else QDoubleSpinBox()
            spin.setRange(minimum, maximum); spin.setSingleStep(step); spin.setValue(self.sequence[key]); spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda value, k=key: self.sequence_setting_changed(k, value))
            timing.addWidget(spin, 1, column); self.sequence_field_controls[key] = spin
        layout.addLayout(timing)
        field_widget = QWidget()
        field = QGridLayout(field_widget)
        field.setContentsMargins(0, 0, 0, 0)
        for index, (key, label, minimum, maximum, step) in enumerate((("valley_start", "valley in", 0, 3600, .01), ("valley_end", "valley out", 0, 3600, .01), ("valley_gain", "valley gain", 0, 2, .01), ("cloud_start", "cloud in", 0, 3600, .01), ("cloud_strength", "cloud", 0, 1, .01), ("cloud_late_start", "late cloud", 0, 3600, .01), ("cloud_late_rate", "late rate", 0, 1, .01))):
            row, column = divmod(index, 2)
            field.addWidget(QLabel(label), row, column * 2)
            spin = QDoubleSpinBox(); spin.setRange(minimum, maximum); spin.setSingleStep(step); spin.setDecimals(2); spin.setValue(self.sequence["field"].get(key, 0.0)); spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda value, k=key: self.sequence_field_changed(k, value))
            field.addWidget(spin, row, column * 2 + 1); self.sequence_field_controls[key] = spin
        field_widget.setVisible(False)
        field_toggle = QPushButton("Exposure and cloud track ▸")
        field_toggle.setCheckable(True)
        field_toggle.toggled.connect(field_widget.setVisible)
        field_toggle.toggled.connect(lambda opened: field_toggle.setText("Exposure and cloud track ▾" if opened else "Exposure and cloud track ▸"))
        layout.addWidget(field_toggle)
        layout.addWidget(field_widget)
        self.sequence_updating = False
        return group

    def sequence_state_group(self):
        group = QGroupBox("Selected state")
        layout = QVBoxLayout(group)
        row = QHBoxLayout(); row.addWidget(QLabel("State"))
        combo = QComboBox(); combo.addItems(list(self.sequence["states"]))
        combo.setMinimumWidth(0)
        combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if self.sequence_state_name in self.sequence["states"]:
            combo.setCurrentText(self.sequence_state_name)
        else:
            combo.setCurrentIndex(0)
        combo.currentTextChanged.connect(self.select_sequence_state); row.addWidget(combo, 1)
        duplicate = QPushButton("Duplicate state"); duplicate.clicked.connect(self.duplicate_sequence_state); row.addWidget(duplicate)
        layout.addLayout(row)
        self.sequence_state_combo = combo
        self.sequence_state_controls = {}
        self.sequence_enabled_controls = {}
        self.sequence_state_name = combo.currentText()
        state = self.sequence["states"][self.sequence_state_name]
        base = normalize_synth(curated_presets()[state["preset"]])
        overrides = state.get("overrides", {})
        enabled = set(state.get("enabled", [entry["id"] for entry in base["modules"] if entry.get("enabled", True)]))
        for entry in base["modules"]:
            module = MODULE_BY_ID.get(entry.get("id"))
            if module is None:
                continue
            module_box = QGroupBox(module.label); module_box.setCheckable(True); module_box.setChecked(entry["id"] in enabled)
            module_box.toggled.connect(lambda checked, module_id=entry["id"]: self.sequence_module_enabled_changed(module_id, checked))
            module_layout = QVBoxLayout(module_box)
            for spec in module.params:
                path = f"{module.id}.{spec.key}"
                value = overrides.get(path, entry.get("params", {}).get(spec.key, spec.default))
                control = SynthControl(spec, value); control.changed.connect(lambda path=path: self.sequence_state_control_changed(path)); module_layout.addWidget(control); self.sequence_state_controls[path] = control
            layout.addWidget(module_box); self.sequence_enabled_controls[module.id] = module_box
        return group

    def rebuild_modules(self):
        if self.composer is not None:
            self.composition_index = self.composer.index
            self.composition_scope = self.composer.scope
        self.composer = None
        while self.panel_layout.count():
            item = self.panel_layout.takeAt(0); widget = item.widget(); widget and widget.deleteLater()
        self.controls.clear(); self.module_groups.clear()
        self.sequence_table = None
        self.sequence_state_controls = {}; self.sequence_enabled_controls = {}; self.sequence_field_controls = {}
        for widget in self.preset_widgets:
            widget.setVisible(self.composition is None)
        for widget in self.composition_widgets:
            widget.setVisible(self.composition is not None)
        self.section_timeline.setVisible(self.composition is not None)
        if self.composition is not None:
            self.composer = CompositionPanel(self.composition, self.composition_index, self.composition_scope)
            self.composer.changed.connect(self.composition_changed)
            self.composer.failed.connect(lambda message: self.status.setText(f"Composition edit ignored: {message}"))
            self.composer.sectionSelected.connect(self.composition_section_selected)
            self.composer.detailsRequested.connect(self.open_detailed_copy)
            self.panel_layout.addWidget(self.composer)
            self.section_timeline.set_document(self.composition, self.composer.index)
            self.update_composition_history()
            self.status.setText(f"{self.composition['name']} · {len(self.composition['sections'])} sections")
            return
        if self.sequence is not None:
            compose = QPushButton("Use this sequence in composer")
            compose.clicked.connect(lambda: self.set_composition(composition_from_sequence(self.sequence)))
            self.panel_layout.addWidget(compose)
            self.panel_layout.addWidget(self.sequence_group())
            self.panel_layout.addWidget(self.sequence_settings_group())
            self.panel_layout.addWidget(self.sequence_state_group())
            note = QLabel("Sequence mode uses the selected-state inspector above. Standalone preset controls are hidden to keep edits reproducible."); note.setWordWrap(True); note.setObjectName("muted"); self.panel_layout.addWidget(note)
            return
        self.panel_layout.addWidget(self.global_group())
        for index, entry in enumerate(self.preset["modules"]):
            module = MODULE_BY_ID.get(entry.get("id"))
            if not module: continue
            group = QGroupBox(module.label); group.setCheckable(True); group.setChecked(entry.get("enabled", True)); group.toggled.connect(lambda checked, i=index: self.module_toggled(i, checked))
            layout = QVBoxLayout(group)
            description = QLabel(module.description); description.setWordWrap(True); layout.addWidget(description)
            order = QHBoxLayout(); order.addStretch(1)
            up = QPushButton("↑"); down = QPushButton("↓"); up.setFixedWidth(32); down.setFixedWidth(32); up.clicked.connect(lambda _=False, i=index: self.move_module(i, -1)); down.clicked.connect(lambda _=False, i=index: self.move_module(i, 1)); order.addWidget(up); order.addWidget(down); layout.addLayout(order)
            for spec in module.params:
                control = SynthControl(spec, entry.get("params", {}).get(spec.key, spec.default)); control.changed.connect(self.control_changed); layout.addWidget(control); self.controls[(index, spec.key)] = control
            self.panel_layout.addWidget(group); self.module_groups.append((index, group))

    def collect(self):
        p = copy.deepcopy(self.preset)
        for key, control in self.global_controls.items():
            p[key] = control.currentText() if isinstance(control, QComboBox) else control.value()
        for target in {target for target, _key in self.mod_controls}:
            p["animation"]["targets"][target] = {key: self.mod_controls[(target, key)].value() for key in ("depth", "rate")}
        for index, entry in enumerate(p["modules"]):
            module = MODULE_BY_ID.get(entry.get("id"))
            if not module:
                continue
            for spec in module.params:
                control = self.controls.get((index, spec.key)); control and entry["params"].update({spec.key: control.value()})
        for index, group in self.module_groups:
            if index < len(p["modules"]): p["modules"][index]["enabled"] = group.isChecked()
        return normalize_synth(p)

    def global_changed(self, key, value=None):
        self.preset = self.collect(); self.mark_custom(); self.update_timeline_max(); self.invalidate()
        if self.play.isChecked(): self.play_timer.start(max(15, round(1000 / self.preset["export_fps"])))
    def modulation_changed(self):
        self.preset = self.collect(); self.mark_custom(); self.invalidate()

    def mark_custom(self):
        self.preset["name"] = "Custom"
        if hasattr(self, "preset_combo"):
            with QSignalBlocker(self.preset_combo):
                self.preset_combo.setCurrentText("Custom")

    def load_reference_sequence(self):
        self.set_composition(reference_composition())

    def load_refined_sequence(self):
        self.set_composition(reference_composition(refined=True))

    def new_composition(self):
        project = reference_composition(refined=True)
        project["name"] = "New composition"
        project["sections"] = [project["sections"][1]]
        project["sections"][0]["duration"] = 15.
        self.set_composition(project)

    def set_composition(self, project):
        project = normalize_composition(project)
        sequence = compile_composition(project)
        self.composition = project
        self.sequence = sequence
        self.composition_index = 0; self.composition_scope = 0
        if self.composer:
            self.composer.index = 0; self.composer.scope = 0
        self.undo_compositions.clear(); self.redo_compositions.clear(); self.edit_key = None
        self.preset = normalize_synth(curated_presets()["Reference blinds"])
        with QSignalBlocker(self.preset_combo):
            self.preset_combo.setCurrentText("Reference blinds")
        self.rebuild_modules(); self.update_timeline_max(); self.invalidate()

    def composition_changed(self, document, action):
        compiled = compile_composition(document)
        if self.edit_key != action or not action.startswith(("macro:", "geometry:")):
            self.undo_compositions.append(copy.deepcopy(self.composition))
            self.undo_compositions = self.undo_compositions[-30:]
        self.edit_key = action; self.edit_timer.start(400)
        self.redo_compositions.clear()
        self.composition = copy.deepcopy(document); self.sequence = compiled
        self.composition_index = self.composer.index; self.composition_scope = self.composer.scope
        self.refresh_composition()

    def refresh_composition(self):
        old_time = self.current_time
        self.update_timeline_max()
        with QSignalBlocker(self.timeline):
            self.timeline.setValue(round(old_time * self.composition["fps"]))
        self.section_timeline.set_document(self.composition, self.composer.index)
        self.status.setText(f"{self.composition['name']} · {len(self.composition['sections'])} sections")
        self.update_composition_history(); self.invalidate()
        if self.play.isChecked():
            self.play_timer.start(max(15, round(1000 / self.composition["fps"])))

    def composition_section_selected(self, index):
        self.composition_index = index
        self.section_timeline.set_document(self.composition, index)
        self.timeline.setValue(round(section_ranges(self.composition)[index][0] * self.composition["fps"]))

    def update_composition_history(self):
        if self.composer:
            self.composition_undo_button.setEnabled(bool(self.undo_compositions))
            self.composition_redo_button.setEnabled(bool(self.redo_compositions))

    def _restore_composition_history(self, source, destination):
        if not source: return
        destination.append(copy.deepcopy(self.composition))
        self.composition = source.pop(); self.sequence = compile_composition(self.composition)
        self.composer.document = copy.deepcopy(self.composition)
        self.composer.index = min(self.composer.index, len(self.composition["sections"]) - 1)
        self.composer.refresh(); self.edit_key = None; self.refresh_composition()

    def undo_composition(self):
        self._restore_composition_history(self.undo_compositions, self.redo_compositions)

    def redo_composition(self):
        self._restore_composition_history(self.redo_compositions, self.undo_compositions)

    def open_detailed_copy(self):
        window = SynthStudio(preset=self.preset, sequence=copy.deepcopy(self.sequence))
        window.setWindowTitle("Nebula · detailed copy")
        self.detail_windows.append(window)
        window.show()

    def sequence_cell_changed(self, row, column):
        if self.sequence_updating or self.sequence is None or self.sequence_table is None:
            return
        try:
            edited = copy.deepcopy(self.sequence)
            cue = edited["cues"][row]
            value = self.sequence_table.item(row, column).text().strip()
            if column == 0:
                cue["time"] = float(value)
            elif column == 1:
                if value not in self.sequence["states"]: raise ValueError("Unknown state")
                cue["state"] = value
            elif column == 2:
                if value not in {"cut", "morph", "sweep", "flash"}: raise ValueError("Unknown transition")
                cue["transition"] = value
            elif column == 3:
                cue["duration"] = max(0.0, float(value))
            elif column == 4:
                cue["intensity"] = float(value)
            else:
                cue["direction"] = float(value)
            edited["cues"].sort(key=lambda item: item["time"])
            self.sequence = normalize_sequence(edited)
            self.rebuild_modules(); self.update_timeline_max(); self.invalidate()
        except Exception as exc:
            self.status.setText(f"Sequence edit ignored: {exc}")
            self.sequence_updating = True
            try:
                cue = self.sequence["cues"][row]
                for index, value in enumerate((cue["time"], cue["state"], cue["transition"], cue.get("duration", 0), cue.get("intensity", 1.0), cue.get("direction", 1.0))):
                    self.sequence_table.item(row, index).setText(f"{value:.2f}" if isinstance(value, float) else str(value))
            finally:
                self.sequence_updating = False

    def add_sequence_cue(self):
        if self.sequence is None: return
        time = self.timeline.value() / max(1, self.sequence["fps"])
        state = self.sequence_state_name or next(iter(self.sequence["states"]))
        self.sequence["cues"].append({"time": min(time, self.sequence["duration"]), "state": state, "transition": "cut", "duration": 0.0})
        self.sequence["cues"].sort(key=lambda cue: cue["time"])
        self.sequence = normalize_sequence(self.sequence); self.rebuild_modules(); self.invalidate()

    def sequence_selection_changed(self):
        if self.sequence_table is None or self.sequence_table.currentRow() < 0:
            return
        row = self.sequence_table.currentRow()
        cue = self.sequence["cues"][row]
        state = cue["state"]
        self.timeline.setValue(round(cue["time"] * self.sequence["fps"]))
        if state in self.sequence["states"] and hasattr(self, "sequence_state_combo"):
            self.sequence_state_combo.setCurrentText(state)
            with QSignalBlocker(self.sequence_table):
                self.sequence_table.selectRow(row)

    def select_sequence_state(self, name):
        if self.sequence is None or name not in self.sequence["states"]:
            return
        self.sequence_state_name = name
        active = [cue for cue in self.sequence["cues"] if cue["time"] <= self.current_time]
        if not active or active[-1]["state"] != name:
            first = next((cue for cue in self.sequence["cues"] if cue["state"] == name), None)
            if first is not None:
                self.timeline.setValue(round(first["time"] * self.sequence["fps"]))
        self.rebuild_modules(); self.invalidate()

    def sequence_state_control_changed(self, path):
        if self.sequence_state_updating or self.sequence is None or self.sequence_state_name not in self.sequence["states"]:
            return
        state = self.sequence["states"][self.sequence_state_name]
        state.setdefault("overrides", {})[path] = self.sequence_state_controls[path].value()
        self.sequence = normalize_sequence(self.sequence); self.invalidate()

    def sequence_module_enabled_changed(self, module_id, checked):
        if self.sequence_state_updating or self.sequence is None or self.sequence_state_name not in self.sequence["states"]:
            return
        state = self.sequence["states"][self.sequence_state_name]
        base = curated_presets()[state["preset"]]
        enabled = set(state.get("enabled", [entry["id"] for entry in base["modules"] if entry.get("enabled", True)]))
        if checked: enabled.add(module_id)
        else: enabled.discard(module_id)
        state["enabled"] = sorted(enabled)
        self.sequence = normalize_sequence(self.sequence); self.invalidate()

    def sequence_setting_changed(self, key, value):
        if self.sequence_updating or self.sequence is None or self.sequence_field_controls is None:
            return
        edited = copy.deepcopy(self.sequence)
        edited[key] = int(value) if key in {"fps", "seed"} else float(value)
        try:
            self.sequence = normalize_sequence(edited)
        except ValueError as exc:
            with QSignalBlocker(self.sequence_field_controls[key]):
                self.sequence_field_controls[key].setValue(self.sequence[key])
            self.status.setText(f"Sequence edit ignored: {exc}")
            return
        self.update_timeline_max(); self.invalidate()

    def sequence_field_changed(self, key, value):
        if self.sequence_updating or self.sequence is None:
            return
        self.sequence.setdefault("field", {})[key] = float(value)
        self.sequence = normalize_sequence(self.sequence); self.invalidate()

    def duplicate_sequence_state(self):
        if self.sequence is None or self.sequence_state_name not in self.sequence["states"]:
            return
        source = self.sequence["states"][self.sequence_state_name]
        base = f"{self.sequence_state_name}_copy"; name = base; index = 2
        while name in self.sequence["states"]:
            name = f"{base}{index}"; index += 1
        self.sequence["states"][name] = copy.deepcopy(source)
        row = self.sequence_table.currentRow() if self.sequence_table is not None else -1
        if row < 0:
            row = max((index for index, cue in enumerate(self.sequence["cues"]) if cue["time"] <= self.current_time), default=0)
        self.sequence["cues"][row]["state"] = name
        self.sequence_state_name = name
        self.sequence = normalize_sequence(self.sequence); self.rebuild_modules(); self.invalidate()

    def remove_sequence_cue(self):
        if self.sequence is None or self.sequence_table is None or self.sequence_table.currentRow() <= 0: return
        del self.sequence["cues"][self.sequence_table.currentRow()]
        self.sequence = normalize_sequence(self.sequence); self.rebuild_modules(); self.invalidate()

    def save_sequence_dialog(self):
        if self.composition is not None:
            path, _ = QFileDialog.getSaveFileName(self, "Save composition", "nebula-composition.json", "Nebula composition (*.json)")
            if path: save_composition(path, self.composition)
            return
        if self.sequence is None:
            self.load_reference_sequence()
        path, _ = QFileDialog.getSaveFileName(self, "Save synth sequence", "reference-study-15s.json", "Nebula sequence (*.json)")
        if path: save_sequence(path, self.sequence)

    def load_sequence_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open composition or sequence", "", "Nebula document (*.json)")
        if not path: return
        try:
            with open(path) as document:
                if json.load(document).get("format") == FORMAT:
                    self.set_composition(load_composition(path))
                    return
            loaded = load_sequence(path)
            self.composition = None
            self.sequence = loaded
            base_name = next(iter(self.sequence["states"].values()))["preset"]
            self.preset = normalize_synth(curated_presets()[base_name])
            with QSignalBlocker(self.preset_combo): self.preset_combo.setCurrentText("Reference blinds" if base_name == "Reference blinds" else base_name)
            self.rebuild_modules(); self.update_timeline_max(); self.invalidate()
        except Exception as exc:
            QMessageBox.critical(self, "Sequence error", str(exc))

    def control_changed(self): self.preset = self.collect(); self.mark_custom(); self.invalidate()
    def module_toggled(self, index, checked): self.preset["modules"][index]["enabled"] = checked; self.mark_custom(); self.invalidate()

    def move_module(self, index, delta):
        new = index + delta
        if 0 <= new < len(self.preset["modules"]):
            self.preset = self.collect(); self.preset["modules"][index], self.preset["modules"][new] = self.preset["modules"][new], self.preset["modules"][index]; self.mark_custom(); self.rebuild_modules(); self.invalidate()

    def invalidate(self):
        self.settings_generation += 1; self.request_frame()
    def update_timeline_max(self):
        if hasattr(self, "timeline"):
            duration = self.sequence["duration"] if self.sequence is not None else self.preset["loop_seconds"]
            fps = self.sequence["fps"] if self.sequence is not None else self.preset["export_fps"]
            self.timeline.setMaximum(max(1, round(duration * fps)) - 1)
    def request_frame(self):
        if self.closing: return
        self.request_serial += 1
        fps = self.sequence["fps"] if self.sequence is not None else self.preset["export_fps"]
        self.current_time = self.timeline.value() / max(1, fps)
        if self.composition is not None:
            self.section_timeline.set_time(self.current_time)
        if self.render_running:
            self.render_queued = True
            return
        edge = 360 if self.quality.currentIndex() == 0 else min(self.preset["width"], 720)
        scale = min(1, edge / max(self.preset["width"], self.preset["height"])); size = (max(1, round(self.preset["width"] * scale)), max(1, round(self.preset["height"] * scale)))
        self.render_running = True
        job = RenderJob(self.preset, self.current_time, size, self.settings_generation, self.request_serial, self.sequence); self.pending_jobs.append(job); job.signals.done.connect(self.frame_ready); job.signals.done.connect(lambda _result, j=job: self._release_job(j)); job.signals.failed.connect(self.render_failed); job.signals.failed.connect(lambda _error, j=job: self._release_job(j)); self.jobs.start(job)

    def _release_job(self, job):
        if job in self.pending_jobs:
            self.pending_jobs.remove(job)
        self.render_running = False
        if self.render_queued and not self.closing:
            self.render_queued = False
            QTimer.singleShot(0, self.request_frame)

    def frame_ready(self, result):
        settings_generation, request_serial, time_seconds, size, raw = result
        if settings_generation != self.settings_generation or request_serial < self.last_displayed_request: return
        self.last_displayed_request = request_serial
        self.viewer.set_packet((size, raw)); self.time_label.setText(f"{time_seconds:.2f}s")
    def render_failed(self, message): self.status.setText(f"Render error: {message}")
    def scrub(self, value): self.request_frame()
    def advance(self): self.timeline.setValue((self.timeline.value() + 1) % max(1, self.timeline.maximum() + 1))
    def toggle_play(self, checked):
        self.play.setText("Pause" if checked else "Play")
        fps = self.sequence["fps"] if self.sequence is not None else self.preset["export_fps"]
        if checked: self.play_timer.start(max(15, round(1000 / fps)))
        else: self.play_timer.stop()
    def select_curated(self, name):
        if name not in curated_presets(): return
        self.sequence = None
        self.composition = None
        self.preset = copy.deepcopy(curated_presets()[name]); self.rebuild_modules(); self.update_timeline_max(); self.invalidate()
    def generate_variation(self):
        if self.composition is not None:
            self.composer.new_take()
            return
        if self.sequence is not None:
            rng = random.Random(self.sequence["seed"] + 1)
            self.sequence["seed"] = rng.randrange(2**31 - 1)
            state = self.sequence["states"][self.sequence_state_name]
            self.sequence_state_updating = True
            try:
                for path, control in self.sequence_state_controls.items():
                    if control.lock.isChecked(): continue
                    spec = control.spec
                    delta = (spec.maximum - spec.minimum) * .12
                    value = max(spec.minimum, min(spec.maximum, control.value() + rng.uniform(-delta, delta)))
                    value = round(value) if spec.kind == "int" else round(value / spec.step) * spec.step
                    control.set_value(value)
                    state.setdefault("overrides", {})[path] = control.value()
            finally:
                self.sequence_state_updating = False
            self.sequence = normalize_sequence(self.sequence)
            with QSignalBlocker(self.sequence_field_controls["seed"]):
                self.sequence_field_controls["seed"].setValue(self.sequence["seed"])
            self.invalidate()
            return
        self.preset = self.collect(); rng = random.Random(self.preset["seed"] + 1); self.preset["seed"] = rng.randrange(2**31 - 1); self.mark_custom()
        with QSignalBlocker(self.global_controls["seed"]):
            self.global_controls["seed"].setValue(self.preset["seed"])
        for (index, key), control in self.controls.items():
            if control.lock.isChecked(): continue
            spec = control.spec
            if spec.kind == "float": control.set_value(round(rng.uniform(spec.minimum, spec.maximum) / spec.step) * spec.step)
            else: control.set_value(rng.randint(int(spec.minimum), int(spec.maximum)))
        self.preset = self.collect(); self.invalidate()
    def save_preset_dialog(self):
        if self.sequence is not None:
            self.save_sequence_dialog()
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save synth preset", "", "Nebula synth (*.json)"); path and save_synth(path, self.collect())
    def load_preset_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load synth preset", "", "Nebula synth (*.json)")
        if path:
            try: self.preset = load_synth(path); self.sequence = None; self.composition = None; self.rebuild_modules(); self.update_timeline_max(); self.invalidate()
            except Exception as exc: QMessageBox.critical(self, "Preset error", str(exc))
    def export_dialog(self):
        default_name = "reference-study-15s.mp4" if self.sequence is not None else "nebula-synth.mp4"
        path, _ = QFileDialog.getSaveFileName(self, "Export synth sequence" if self.sequence is not None else "Export synth loop", default_name, "MP4 video (*.mp4)")
        if not path: return
        p = copy.deepcopy(self.preset) if self.sequence is not None else self.collect()
        edge = 360 if self.quality.currentIndex() == 0 else None; size = None if edge is None else (round(p["width"] * edge / max(p["width"], p["height"])), round(p["height"] * edge / max(p["width"], p["height"])))
        job = ExportJob(p, path, size, self.sequence); self.export_job = job; self.cancel_export.setEnabled(True); self.pending_jobs.append(job); job.signals.progress.connect(lambda a, b: self.status.setText(f"Exporting {a}/{b}")); job.signals.done.connect(lambda _: self.status.setText(f"Exported {path}")); job.signals.done.connect(lambda _result, j=job: self._finish_export(j)); job.signals.failed.connect(lambda error: self.status.setText(f"Export error: {error}")); job.signals.failed.connect(lambda _error, j=job: self._finish_export(j)); self.jobs.start(job)

    def _finish_export(self, job):
        if job in self.pending_jobs:
            self.pending_jobs.remove(job)
        if self.export_job is job:
            self.export_job = None
            self.cancel_export.setEnabled(False)

    def cancel_export_job(self):
        if self.export_job:
            self.export_job.cancel.cancel()
            self.status.setText("Cancelling export…")

    def closeEvent(self, event):
        self.closing = True
        self.play_timer.stop()
        if self.export_job:
            self.export_job.cancel.cancel()
        self.jobs.waitForDone(1500)
        super().closeEvent(event)


def run_synth_app(preset=None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = SynthStudio(preset); window.show()
    return app.exec()


if __name__ == "__main__":
    run_synth_app()
