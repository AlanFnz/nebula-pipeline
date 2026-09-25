"""Native inspector for reusable effects and their authored parameter ranges."""
from __future__ import annotations

import copy

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QDoubleSpinBox, QSpinBox, QStackedWidget,
)

from synth_effects import EFFECTS, EFFECT_BY_ID, describe_effects, effect_preset, parameter


def format_value(path, value):
    spec = parameter(path)
    if spec.choices:
        return spec.choices[int(value)]
    return f"{value:g}"


class EffectParameter(QWidget):
    changed = Signal(object)
    reset = Signal()

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.spec = spec = parameter(path)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 3); layout.setSpacing(1)
        row = QHBoxLayout()
        label = QLabel(spec.label); label.setToolTip(spec.hint); row.addWidget(label, 1)
        if spec.choices:
            self.input = QComboBox(); self.input.addItems(spec.choices)
            self.input.currentIndexChanged.connect(self.changed.emit)
        else:
            self.input = QSpinBox() if spec.kind == "int" else QDoubleSpinBox()
            self.input.setRange(spec.minimum, spec.maximum); self.input.setSingleStep(spec.step)
            if spec.kind != "int": self.input.setDecimals(3)
            self.input.setKeyboardTracking(False)
            self.input.valueChanged.connect(self.changed.emit)
        self.input.setMinimumWidth(110); self.input.setToolTip(spec.hint)
        self.input.setAccessibleName(spec.label)
        self.value_stack = QStackedWidget()
        self.value_stack.addWidget(self.input)
        self.animated_value = QPushButton()
        self.animated_value.setAccessibleName(f"Fix {spec.label}")
        self.animated_value.clicked.connect(lambda: self.changed.emit(self.fixed_start))
        self.value_stack.addWidget(self.animated_value)
        row.addWidget(self.value_stack)
        self.reset_button = QPushButton("↶"); self.reset_button.setFixedWidth(30)
        self.reset_button.setToolTip("Follow the recipe or whole-clip value again.")
        self.reset_button.setAccessibleName(f"Reset {spec.label}")
        self.reset_button.clicked.connect(self.reset.emit); row.addWidget(self.reset_button)
        layout.addLayout(row)
        self.origin = QLabel(); self.origin.setObjectName("muted"); layout.addWidget(self.origin)

    def refresh(self, bounds, fixed, inherited, available):
        low, high = bounds
        value = fixed if fixed is not None else low
        self.fixed_start = low
        animated = fixed is None and low != high and available
        self.value_stack.setCurrentIndex(1 if animated else 0)
        self.animated_value.setText("Varies" if self.spec.choices else f"{low:g} … {high:g}")
        self.animated_value.setToolTip(f"Animated range. Click to set a fixed value, starting at {format_value(self.path, low)}.")
        with QSignalBlocker(self.input):
            if self.spec.choices: self.input.setCurrentIndex(int(value))
            else: self.input.setValue(value)
        self.input.setEnabled(available)
        self.reset_button.setEnabled(fixed is not None)
        if fixed is not None:
            text = "Fixed in this scope"
        elif not available:
            text = "Enable this effect to edit"
        elif low != high:
            text = f"Animated / varying: {format_value(self.path, low)} … {format_value(self.path, high)}"
        else:
            text = "From whole clip" if inherited else "From recipe"
        self.origin.setText(text)
        self.setToolTip("Editing fixes this parameter across the scope; all other recipe changes keep playing.")


class EffectsPanel(QWidget):
    edited = Signal(str, object, str)

    def __init__(self):
        super().__init__()
        self.entries = {}; self.parent_entries = {}; self.summary = {}
        self.effect_id = "rays"; self.controls = {}; self.rows = {}
        self.updating = False
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8)
        self.scope_label = QLabel(); self.scope_label.setObjectName("sectionTitle"); self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)
        self.selector = QComboBox(); self.selector.currentIndexChanged.connect(self.select_effect)
        self.selector.setToolTip("Every effect can be used in any section. Select one to inspect its own parameters.")
        layout.addWidget(self.selector)
        self.description = QLabel(); self.description.setWordWrap(True); self.description.setObjectName("muted"); layout.addWidget(self.description)
        row = QHBoxLayout()
        self.mode = QComboBox()
        for label, value in (("Follow recipe", "recipe"), ("On throughout scope", "on"), ("Off throughout scope", "off")):
            self.mode.addItem(label, value)
        self.mode.currentIndexChanged.connect(self.change_mode); row.addWidget(self.mode, 1)
        self.restore = QPushButton("Restore"); self.restore.setToolTip("Remove this scope's overrides for this effect.")
        self.restore.clicked.connect(self.restore_effect); row.addWidget(self.restore)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.look = QComboBox(); row.addWidget(self.look, 1)
        self.apply_button = QPushButton("+ Apply effect"); self.apply_button.clicked.connect(self.apply_look); row.addWidget(self.apply_button)
        layout.addLayout(row)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setObjectName("muted"); layout.addWidget(self.status)
        self.parameter_host = QWidget(); self.parameter_layout = QVBoxLayout(self.parameter_host); self.parameter_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.parameter_host)
        self.more = QPushButton("More controls"); self.more.setCheckable(True); self.more.toggled.connect(self.show_more); layout.addWidget(self.more)
        self.note = QLabel("Click a range to set a fixed value. ↶ restores the recipe. Fixed effect values take priority over Geometry and Finishing.")
        self.note.setWordWrap(True); self.note.setObjectName("muted"); layout.addWidget(self.note)
        layout.addStretch(1)

    def set_context(self, entries, parent_entries, states, scope_label, local):
        self.updating = True
        self.entries = copy.deepcopy(entries); self.parent_entries = copy.deepcopy(parent_entries)
        self.summary = describe_effects(states)
        self.scope_label.setText(scope_label)
        with QSignalBlocker(self.selector), QSignalBlocker(self.mode):
            self.selector.clear()
            for effect in EFFECTS:
                info = self.summary[effect.id]
                status = "intermittent" if info["intermittent"] else "active" if info["active"] else "off"
                self.selector.addItem(f"{effect.label} · {status}", effect.id)
            self.selector.setCurrentIndex(self.selector.findData(self.effect_id))
            self.mode.setItemText(0, "Follow whole clip / recipe" if local else "Follow recipe")
        self.updating = False
        self.refresh_effect()

    def select_effect(self, index):
        if self.updating or index < 0: return
        self.effect_id = self.selector.itemData(index)
        with QSignalBlocker(self.more): self.more.setChecked(False)
        self.refresh_effect()

    def refresh_effect(self):
        if not self.summary: return
        self.updating = True
        effect = EFFECT_BY_ID[self.effect_id]
        entry = self.entries.get(effect.id, {"mode": "recipe", "params": {}})
        with QSignalBlocker(self.mode): self.mode.setCurrentIndex(self.mode.findData(entry["mode"]))
        self.description.setText(effect.description)
        self.restore.setEnabled(effect.id in self.entries)
        if tuple(self.controls) != effect.paths:
            while self.parameter_layout.count():
                widget = self.parameter_layout.takeAt(0).widget()
                if widget:
                    widget.hide()
                    widget.deleteLater()
            self.controls = {}; self.rows = {}
            for path in effect.paths:
                control = EffectParameter(path)
                control.changed.connect(lambda value, path=path: self.change_parameter(path, value))
                control.reset.connect(lambda path=path: self.reset_parameter(path))
                self.parameter_layout.addWidget(control); self.controls[path] = control
            self.look.clear()
            for label, _ in effect.looks or (("Default settings", {}),): self.look.addItem(label)
        info = self.summary[effect.id]
        parent = self.parent_entries.get(effect.id, {})
        available = info["active"] or entry["mode"] in {"on", "off"} or effect.id in self.entries
        for path, control in self.controls.items():
            control.refresh(info["ranges"][path], entry["params"].get(path), path in parent.get("params", {}), available)
        self.apply_button.setText("Replace settings" if info["active"] else "+ Apply effect")
        self.status.setText("Active during part of the recipe. On keeps it enabled throughout." if info["intermittent"] else
                            "Active. Unedited values keep following their recipe." if info["active"] else
                            "Off. Apply a preset to add this effect, or turn it on with recipe values.")
        self.show_more(self.more.isChecked())
        self.updating = False

    def show_more(self, checked):
        effect = EFFECT_BY_ID[self.effect_id]
        for index, control in enumerate(self.controls.values()): control.setVisible(checked or index < effect.primary)
        extra = len(effect.paths) - effect.primary
        self.more.setVisible(extra > 0)
        self.more.setText("Fewer controls" if checked else f"More controls ({max(0, extra)})")

    def change_mode(self, index):
        if self.updating or index < 0: return
        entry = copy.deepcopy(self.entries.get(self.effect_id, {"mode": "recipe", "params": {}}))
        entry["mode"] = self.mode.itemData(index)
        self.edited.emit(self.effect_id, entry, "effect-mode")

    def change_parameter(self, path, value):
        if self.updating: return
        entry = copy.deepcopy(self.entries.get(self.effect_id, {"mode": "recipe", "params": {}}))
        entry["params"][path] = value
        self.edited.emit(self.effect_id, entry, f"effect-param:{path}")

    def reset_parameter(self, path):
        entry = copy.deepcopy(self.entries[self.effect_id]); entry["params"].pop(path, None)
        self.edited.emit(self.effect_id, entry, "effect-reset-param")

    def restore_effect(self):
        self.edited.emit(self.effect_id, None, "effect-restore")

    def apply_look(self):
        self.edited.emit(self.effect_id, effect_preset(self.effect_id, self.look.currentIndex()), "effect-apply")
