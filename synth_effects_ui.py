"""Native inspector for reusable effects and their authored parameter ranges."""
from __future__ import annotations

import copy
import math

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QTabBar,
)
from studio_widgets import ComboBox as QComboBox, DoubleSpinBox as QDoubleSpinBox, SpinBox as QSpinBox

from synth_effects import EFFECTS, EFFECT_BY_ID, describe_effects, effect_preset, parameter
from studio_theme import COLORS
from synth_artwork_ui import ArtworkControl
from synth_ink_timing import DURATION_KEYS, TIMING_KEYS

INK_DURATIONS = {f'ink_bloom.{key}' for key in DURATION_KEYS}
INK_TIMING = tuple(f'ink_bloom.{key}' for key in TIMING_KEYS)
SHARED_TIMING_CONTROLS = INK_TIMING[:8]


def format_value(path, value):
    spec = parameter(path)
    if spec.kind == 'artwork': return 'Embedded artwork' if value else 'No artwork'
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
        if spec.kind == 'artwork':
            self.input = ArtworkControl(); self.input.changed.connect(self.changed.emit)
        elif spec.choices:
            self.input = QComboBox(); self.input.addItems(spec.choices)
            self.input.currentIndexChanged.connect(self.changed.emit)
        else:
            self.input = QSpinBox() if spec.kind == "int" else QDoubleSpinBox()
            self.input.setRange(spec.minimum, spec.maximum); self.input.setSingleStep(spec.step)
            if path in INK_DURATIONS: self.input.setMinimum(0)
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
        if self.path in INK_DURATIONS and fixed is not None and fixed < 0:
            fixed = None; inherited = False
        value = fixed if fixed is not None else low
        self.fixed_start = low
        animated = fixed is None and low != high and available
        self.value_stack.setCurrentIndex(1 if animated else 0)
        self.animated_value.setText("Varies" if self.spec.choices or self.spec.kind == 'artwork' else f"{low:g} … {high:g}")
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
    timing_edited = Signal(str, object)
    timing_reset = Signal()
    timing_selected = Signal(bool)

    def __init__(self):
        super().__init__()
        self.entries = {}; self.parent_entries = {}; self.summary = {}
        self.effect_id = "rays"; self.controls = {}; self.rows = {}
        self.context_key = None
        self.shared_timing = {}; self.shared_summary = {}; self.context_scope_label = ''
        self.updating = False
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8)
        self.scope_label = QLabel(); self.scope_label.setObjectName("sectionTitle"); self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)
        self.used_effects = QLabel(); self.used_effects.setWordWrap(True)
        self.used_effects.setObjectName("muted")
        self.used_effects.setOpenExternalLinks(False)
        self.used_effects.linkActivated.connect(self.inspect_effect)
        layout.addWidget(self.used_effects)
        inspector_label = QLabel("INSPECT EFFECT"); inspector_label.setObjectName("sectionTitle")
        layout.addWidget(inspector_label)
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
        self.parameter_tabs = QTabBar(); self.parameter_tabs.addTab('Look'); self.parameter_tabs.addTab('Timing')
        self.parameter_tabs.currentChanged.connect(self.change_parameter_tab)
        layout.addWidget(self.parameter_tabs)
        self.timing_note = QLabel(); self.timing_note.setWordWrap(True); self.timing_note.setObjectName('muted')
        layout.addWidget(self.timing_note)
        self.restore_timing = QPushButton('Restore recipe timing')
        self.restore_timing.clicked.connect(self.timing_reset.emit)
        layout.addWidget(self.restore_timing)
        self.parameter_host = QWidget(); self.parameter_layout = QVBoxLayout(self.parameter_host); self.parameter_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.parameter_host)
        self.more = QPushButton("More controls"); self.more.setCheckable(True); self.more.toggled.connect(self.show_more); layout.addWidget(self.more)
        self.note = QLabel("Click a range to set a fixed value. ↶ restores the recipe. Fixed effect values take priority over Geometry and Finishing.")
        self.note.setWordWrap(True); self.note.setObjectName("muted"); layout.addWidget(self.note)
        layout.addStretch(1)

    def set_context(self, entries, parent_entries, states, scope_label, local, context_key, shared_timing=None, shared_states=None):
        self.updating = True
        self.entries = copy.deepcopy(entries); self.parent_entries = copy.deepcopy(parent_entries)
        self.summary = describe_effects(states)
        self.shared_timing = copy.deepcopy(shared_timing or {})
        self.shared_summary = self.summary['ink_bloom'] if shared_states is None or shared_states is states else describe_effects(shared_states)['ink_bloom']
        self.context_scope_label = scope_label
        active = [effect for effect in EFFECTS if self.summary[effect.id]["active"]]
        if context_key != self.context_key and not self.summary[self.effect_id]["active"] and active:
            self.effect_id = active[0].id
            with QSignalBlocker(self.more): self.more.setChecked(False)
        self.context_key = context_key
        links = []
        for effect in active:
            label = effect.label + (" (intermittent)" if self.summary[effect.id]["intermittent"] else "")
            links.append(f'<a href="{effect.id}" style="color: {COLORS["accent"]}">{label}</a>')
        prefix = "Used in this section: " if local else "Used across the clip: "
        self.used_effects.setText(prefix + (" · ".join(links) if links else "none. Choose an effect below to build this section."))
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

    def inspect_effect(self, effect_id):
        index = self.selector.findData(effect_id)
        if index >= 0: self.selector.setCurrentIndex(index)

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
            if path in INK_TIMING:
                control.refresh(self.shared_summary['ranges'][path], self.shared_timing.get(path), False, self.shared_summary['active'])
                control.origin.setText('Shared across all sections' if self.shared_timing else 'Recipe timing · edits apply to all sections')
                control.setToolTip('One timing setup for the whole composition, regardless of the selected section.')
            else:
                control.refresh(info["ranges"][path], entry["params"].get(path), path in parent.get("params", {}), available)
        self.apply_button.setText("Replace settings" if info["active"] else "+ Apply effect")
        self.status.setText("Active during part of the recipe. On keeps it enabled throughout." if info["intermittent"] else
                            "Active. Unedited values keep following their recipe." if info["active"] else
                            f"{effect.label} is off in this scope. Other effects are listed above. Apply a preset to add it.")
        if effect.id == 'ink_bloom' and self.controls['ink_bloom.shape'].input.currentIndex() == 5 and not self.controls['ink_bloom.artwork'].input.value():
            self.status.setText('Import artwork to supply the custom silhouette, or choose a built-in shape.')
        self.show_more(self.more.isChecked())
        self.updating = False

    def change_parameter_tab(self, _index):
        with QSignalBlocker(self.more): self.more.setChecked(False)
        self.show_more(False)

    def show_more(self, checked):
        effect = EFFECT_BY_ID[self.effect_id]
        ink = effect.id == 'ink_bloom'
        timing = ink and self.parameter_tabs.currentIndex() == 1
        self.parameter_tabs.setVisible(ink)
        self.timing_note.setVisible(timing)
        self.restore_timing.setVisible(timing)
        self.restore_timing.setEnabled(bool(self.shared_timing))
        for widget in (self.mode, self.restore, self.look, self.apply_button, self.status): widget.setVisible(not timing)
        self.scope_label.setText('GLOBAL TIMING / all sections' if timing else self.context_scope_label)
        self.timing_selected.emit(timing)
        visible_paths = SHARED_TIMING_CONTROLS if timing else tuple(path for path in effect.paths if not ink or path not in INK_TIMING)
        primary = 6 if timing else effect.primary
        shown = set(visible_paths if checked else visible_paths[:primary])
        for path, control in self.controls.items(): control.setVisible(path in shown)
        for index, path in enumerate(visible_paths):
            control = self.controls[path]
            if self.parameter_layout.indexOf(control) != index:
                self.parameter_layout.insertWidget(index, control)
        if timing:
            loops = self.shared_summary['loop_seconds']
            if not loops: loop = 'Enable Ink bloom to preview its timing.'
            elif not math.isfinite(loops[1]): loop = 'Gesture speed is frozen in part or all of this scope.'
            elif loops[0] == loops[1]: loop = f'Loop: {loops[0]:.2f} s at the current speed.'
            else: loop = f'Loop varies: {loops[0]:.2f}–{loops[1]:.2f} s across this scope.'
            self.timing_note.setText('Changes apply to every section. ' + loop + ' Complete-cycle sections resize together to keep their boundaries aligned. Durations are at 1×; Stay folded is the total rest between gestures.')
        extra = len(visible_paths) - primary
        self.more.setVisible(extra > 0)
        self.more.setText("Fewer controls" if checked else f"More controls ({max(0, extra)})")

    def change_mode(self, index):
        if self.updating or index < 0: return
        entry = copy.deepcopy(self.entries.get(self.effect_id, {"mode": "recipe", "params": {}}))
        entry["mode"] = self.mode.itemData(index)
        self.edited.emit(self.effect_id, entry, "effect-mode")

    def change_parameter(self, path, value):
        if self.updating: return
        if path in INK_TIMING:
            self.timing_edited.emit(path, value)
            return
        entry = copy.deepcopy(self.entries.get(self.effect_id, {"mode": "recipe", "params": {}}))
        entry["params"][path] = value
        if path == 'ink_bloom.artwork' and value:
            entry['params']['ink_bloom.shape'] = 5
        self.edited.emit(self.effect_id, entry, f"effect-param:{path}")

    def reset_parameter(self, path):
        if path in INK_TIMING:
            self.timing_edited.emit(path, None)
            return
        entry = copy.deepcopy(self.entries[self.effect_id]); entry["params"].pop(path, None)
        self.edited.emit(self.effect_id, entry, "effect-reset-param")

    def restore_effect(self):
        self.edited.emit(self.effect_id, None, "effect-restore")

    def apply_look(self):
        self.edited.emit(self.effect_id, effect_preset(self.effect_id, self.look.currentIndex()), "effect-apply")
