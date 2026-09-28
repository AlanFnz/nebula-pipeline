"""Native inspector for reusable effects and their authored parameter ranges."""
from __future__ import annotations

import copy
import math

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QTabBar, QFrame,
)
from studio_widgets import ComboBox as QComboBox, DoubleSpinBox as QDoubleSpinBox, SpinBox as QSpinBox

from synth_effects import EFFECTS, EFFECT_BY_ID, describe_effects, effect_preset, parameter
from synth_artwork_ui import ArtworkControl
from synth_text_ui import TextControl
from synth_ink_timing import DURATION_KEYS, TIMING_KEYS

INK_DURATIONS = {f'ink_bloom.{key}' for key in DURATION_KEYS}
INK_TIMING = tuple(f'ink_bloom.{key}' for key in TIMING_KEYS)
SHARED_TIMING_CONTROLS = INK_TIMING[:8]
TEXT_TIMING = tuple('text.' + key for key in ('reveal', 'word_seconds', 'motion', 'zoom_start', 'zoom_end', 'period', 'ease', 'phase', 'cadence'))
POLARITY_CONTROLS = tuple('broadcast.' + key for key in ('reverse', 'reverse_period', 'reverse_phase', 'reverse_blend', 'field_spread', 'reverse_stage', 'reverse_hue', 'reverse_saturation'))
SIGNAL_CONTROLS = tuple('broadcast.' + key for key in ('static_style', 'static', 'outages', 'sync_tear', 'period', 'duration', 'phase', 'rate', 'static_chroma', 'band', 'roll'))
SCREEN_CONTROLS = tuple('broadcast.' + key for key in ('screen', 'screen_inset', 'screen_wear', 'halo', 'halo_radius', 'halo_hue', 'curve', 'vignette', 'halo_threshold'))
REGION_CONTROLS = tuple('edge_phosphor.' + key for key in (
    'fade_mode', 'neck_dissolve', 'fade_strength', 'fade_start', 'fade_width',
    'fade_angle', 'fade_softness', 'fade_anchor', 'fade_x', 'fade_y', 'fade_curve'))


def format_value(path, value):
    spec = parameter(path)
    if spec.kind == 'text': return value.replace('\n', ' / ')[:60] or 'Empty text'
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
        if spec.kind in ('artwork', 'text'):
            self.input = ArtworkControl() if spec.kind == 'artwork' else TextControl(); self.input.changed.connect(self.changed.emit)
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
        self.animated_value.setText("Varies" if self.spec.choices or self.spec.kind in ('artwork', 'text') else f"{low:g} … {high:g}")
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


class EffectChoice(QFrame):
    """A compact, non-scrolling navigation row with a separate state badge."""
    selected = Signal(str)

    def __init__(self, effect):
        super().__init__()
        self.setObjectName('effectChoice')
        row = QHBoxLayout(self); row.setContentsMargins(2, 0, 7, 0); row.setSpacing(4)
        self.button = QPushButton(effect.label); self.button.setObjectName('effectChoiceButton')
        self.button.clicked.connect(lambda: self.selected.emit(effect.id))
        row.addWidget(self.button, 1)
        self.badge = QLabel(); self.badge.setObjectName('effectState'); row.addWidget(self.badge)

    def refresh(self, effect, info, selected, bypassed):
        state = 'Intermittent' if info['intermittent'] else 'On' if info['active'] else 'Bypassed' if bypassed else 'Off'
        self.badge.setText(state)
        self.button.setAccessibleName(f'Inspect {effect.label} · {state}')
        self.setToolTip(effect.description + (' Active during part of this scope.' if info['intermittent'] else ''))
        self.setProperty('selected', selected)
        self.badge.setProperty('active', info['active'])
        for widget in (self, self.badge):
            widget.style().unpolish(widget); widget.style().polish(widget); widget.update()


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
        self.allowed_effects = None
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8)
        self.scope_label = QLabel(); self.scope_label.setObjectName("sectionTitle"); self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)
        self.applied_title = QLabel(); self.applied_title.setObjectName('sectionTitle')
        self.applied_title.setToolTip('Effects enabled anywhere in the selected scope. Intermittent means they are used during only part of it.')
        layout.addWidget(self.applied_title)
        self.applied_host = QWidget(); self.applied_layout = QVBoxLayout(self.applied_host)
        self.applied_layout.setContentsMargins(0, 0, 0, 0); self.applied_layout.setSpacing(2)
        layout.addWidget(self.applied_host)
        self.empty_applied = QLabel('No effects applied in this scope. Choose an available effect to add one.')
        self.empty_applied.setWordWrap(True); self.empty_applied.setObjectName('muted'); layout.addWidget(self.empty_applied)
        self.available_button = QPushButton(); self.available_button.setCheckable(True)
        self.available_button.setAccessibleName('Show available effects')
        self.available_button.toggled.connect(self.show_available); layout.addWidget(self.available_button)
        self.available_host = QWidget(); self.available_layout = QVBoxLayout(self.available_host)
        self.available_layout.setContentsMargins(0, 0, 0, 0); self.available_layout.setSpacing(2)
        layout.addWidget(self.available_host); self.available_host.hide()
        self.applied_ids = (); self.available_ids = ()
        self.effect_choices = {}
        for effect in EFFECTS:
            choice = EffectChoice(effect); choice.selected.connect(self.inspect_effect)
            self.available_layout.addWidget(choice); self.effect_choices[effect.id] = choice
        self.inspector_title = QLabel(); self.inspector_title.setObjectName('sectionTitle'); self.inspector_title.setWordWrap(True)
        layout.addWidget(self.inspector_title)
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
        self.parameter_tabs.addTab('Signal'); self.parameter_tabs.addTab('Screen')
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
        self.note = QLabel("Click a range to set a fixed value. ↶ restores the recipe. Fixed effect values take priority over geometric Object controls and Finishing.")
        self.note.setWordWrap(True); self.note.setObjectName("muted"); layout.addWidget(self.note)
        layout.addStretch(1)

    def set_context(self, entries, parent_entries, states, scope_label, local, context_key, shared_timing=None, shared_states=None, allowed_effects=None):
        self.updating = True
        self.entries = copy.deepcopy(entries); self.parent_entries = copy.deepcopy(parent_entries)
        self.summary = describe_effects(states)
        self.allowed_effects = allowed_effects
        visible_effects = [e for e in EFFECTS if allowed_effects is None or e.id in allowed_effects]
        self.shared_timing = copy.deepcopy(shared_timing or {})
        self.shared_summary = self.summary['ink_bloom'] if shared_states is None or shared_states is states else describe_effects(shared_states)['ink_bloom']
        self.context_scope_label = scope_label
        active = [effect for effect in visible_effects if self.summary[effect.id]["active"]]
        if allowed_effects is not None and self.effect_id not in allowed_effects:
            self.effect_id = (active or visible_effects)[0].id
        changed_context = context_key != self.context_key
        if changed_context and not self.summary[self.effect_id]["active"] and active:
            self.effect_id = active[0].id
            with QSignalBlocker(self.more): self.more.setChecked(False)
        self.context_key = context_key
        self.applied_ids = tuple(effect.id for effect in active)
        self.available_ids = tuple(effect.id for effect in visible_effects if effect.id not in self.applied_ids)
        self.applied_title.setText(f'APPLIED EFFECTS · {len(active)}')
        self.empty_applied.setVisible(not active)
        for effect in EFFECTS:
            target = self.applied_layout if effect.id in self.applied_ids else self.available_layout
            target.addWidget(self.effect_choices[effect.id])
            self.effect_choices[effect.id].setVisible(allowed_effects is None or effect.id in allowed_effects)
        if changed_context:
            self.available_button.setChecked(not active)
        self.available_button.setEnabled(bool(self.available_ids))
        self.show_available(self.available_button.isChecked())
        with QSignalBlocker(self.mode):
            self.mode.setItemText(0, "Follow whole clip / recipe" if local else "Follow recipe")
        self.updating = False
        self.refresh_effect()

    def inspect_effect(self, effect_id):
        if self.updating or effect_id not in EFFECT_BY_ID: return
        if self.allowed_effects is not None and effect_id not in self.allowed_effects: return
        self.effect_id = effect_id
        self.available_button.setChecked(False)
        with QSignalBlocker(self.more): self.more.setChecked(False)
        self.refresh_effect()

    def show_available(self, expanded):
        self.available_host.setVisible(expanded and bool(self.available_ids))
        self.available_button.setText(f'{"▾" if expanded else "▸"} Available effects · {len(self.available_ids)}')

    def refresh_effect(self):
        if not self.summary: return
        self.updating = True
        effect = EFFECT_BY_ID[self.effect_id]
        self.inspector_title.setText(f'EDIT / {effect.label}')
        for item in EFFECTS:
            local_mode = self.entries.get(item.id, {}).get('mode', 'recipe')
            bypassed = local_mode == 'off' or (local_mode == 'recipe' and self.parent_entries.get(item.id, {}).get('mode') == 'off')
            self.effect_choices[item.id].refresh(item, self.summary[item.id], item.id == effect.id, bypassed)
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
        with QSignalBlocker(self.parameter_tabs):
            if effect.id != 'broadcast' and self.parameter_tabs.currentIndex() > 1:
                self.parameter_tabs.setCurrentIndex(0)
            for index in (2, 3): self.parameter_tabs.setTabVisible(index, effect.id == 'broadcast')
        ink = effect.id == 'ink_bloom'
        text = effect.id == 'text'
        text_timing = text and self.parameter_tabs.currentIndex() == 1
        broadcast = effect.id == 'broadcast'
        polarity = broadcast and self.parameter_tabs.currentIndex() == 1
        phosphor = effect.id == 'edge_phosphor'
        region = phosphor and self.parameter_tabs.currentIndex() == 1
        timing = ink and self.parameter_tabs.currentIndex() == 1
        self.parameter_tabs.setTabText(1, 'Region' if phosphor else 'Polarity' if broadcast else 'Timing')
        self.parameter_tabs.setVisible(ink or phosphor or text or broadcast)
        self.timing_note.setVisible(timing)
        self.restore_timing.setVisible(timing)
        self.restore_timing.setEnabled(bool(self.shared_timing))
        for widget in (self.mode, self.restore, self.look, self.apply_button, self.status): widget.setVisible(not timing)
        self.scope_label.setText('GLOBAL TIMING / all sections' if timing else self.context_scope_label)
        self.timing_selected.emit(timing)
        visible_paths = SHARED_TIMING_CONTROLS if timing else tuple(path for path in effect.paths if not ink or path not in INK_TIMING)
        if text:
            visible_paths = TEXT_TIMING if text_timing else tuple(path for path in effect.paths if path not in TEXT_TIMING)
            ranges = self.summary['text']['ranges']
            if ranges['text.motion'][0] == ranges['text.motion'][1] and ranges['text.motion'][0] != 1:
                visible_paths = tuple(path for path in visible_paths if path != 'text.ease')
            if ranges['text.fit'][0] == ranges['text.fit'][1] and ranges['text.fit'][0] != 2:
                visible_paths = tuple(path for path in visible_paths if path != 'text.block_width')
            if ranges['text.fit'][0] == ranges['text.fit'][1] and ranges['text.fit'][0] != 1:
                visible_paths = tuple(path for path in visible_paths if path not in ('text.fit_width', 'text.copy_floor'))
        if broadcast:
            groups = (tuple(path for path in effect.paths if path not in POLARITY_CONTROLS + SIGNAL_CONTROLS + SCREEN_CONTROLS),
                      POLARITY_CONTROLS, SIGNAL_CONTROLS, SCREEN_CONTROLS)
            visible_paths = groups[self.parameter_tabs.currentIndex()]
        if self.allowed_effects is not None:
            visible_paths = tuple(path for path in visible_paths if not path.startswith('slab.'))
        if phosphor:
            if region:
                mode = self.summary['edge_phosphor']['ranges']['edge_phosphor.fade_mode']
                legacy = mode == (0, 0)
                visible_paths = REGION_CONTROLS if mode[0] != mode[1] else REGION_CONTROLS[:2] if legacy else tuple(p for p in REGION_CONTROLS if p != 'edge_phosphor.neck_dissolve')
                if mode == (2, 2):
                    visible_paths = tuple(p for p in visible_paths if p != 'edge_phosphor.fade_anchor')
                self.description.setText('Profile preset keeps the original neck blend. Choose Object to attach a reusable fade to a source, or Canvas to hold it in the viewport. The region affects contours, echoes, fill and surrounding light; it leaves the final background texture intact.')
                sources = ('silhouette', 'forms', 'ink_bloom', 'particles', 'rays', 'text')
                anchor = self.summary['edge_phosphor']['ranges']['edge_phosphor.fade_anchor']
                missing = mode == (1, 1) and (not any(self.summary[s]['active'] for s in sources) if anchor == (0, 0) else
                          anchor[0] == anchor[1] and not self.summary[sources[int(anchor[0]) - 1]]['active'])
                if missing:
                    self.status.setText('The selected object anchor is not present. Choose an active object anchor or Canvas for this region.')
                neck_control = self.controls['edge_phosphor.neck_dissolve']
                neck_control.setEnabled(self.summary['silhouette']['active'])
                if legacy and not self.summary['silhouette']['active']:
                    self.status.setText('Profile preset needs Model silhouette. Choose Object or Canvas to use the directional region with this source.')
            else:
                visible_paths = tuple(p for p in visible_paths if p not in REGION_CONTROLS)
                self.description.setText(effect.description)
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
        if path == 'edge_phosphor.fade_mode' and value and 'edge_phosphor.fade_strength' not in entry['params']:
            info = self.summary['edge_phosphor']['ranges']
            strength = info['edge_phosphor.neck_dissolve'][1]
            entry['params']['edge_phosphor.fade_strength'] = info['edge_phosphor.fade_strength'][1] or strength or 1.
            if value == 1 and strength and self.summary['silhouette']['active']:
                entry['params'].setdefault('edge_phosphor.fade_start', .9)
                entry['params'].setdefault('edge_phosphor.fade_width', .38)
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
