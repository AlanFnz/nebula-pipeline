"""Native inspector for reusable effects and their authored parameter ranges."""
from __future__ import annotations

import copy
import math

from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QTabBar, QFrame, QLineEdit, QScrollArea, QSizePolicy,
)
from studio_widgets import ComboBox as QComboBox, DoubleSpinBox as QDoubleSpinBox, SpinBox as QSpinBox
from studio_widgets import Slider, configure_parameter_spin, parameter_number
from synth_inspector import grouped_paths

from synth_effects import EFFECTS, EFFECT_BY_ID, describe_effects, effect_preset, parameter
from synth_artwork_ui import ArtworkControl
from synth_text_ui import TextControl
from synth_ink_timing import DURATION_KEYS, TIMING_KEYS
from synth_subject import SOURCE_EFFECTS
from synth_creative import CREATIVE_CONTROLS
from synth_creative_ui import CreativeControlsPanel

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


from synth_effect_parameter_ui import EffectParameter, format_value


class EffectChoice(QFrame):
    """A compact, non-scrolling navigation row with a separate state badge."""
    selected = Signal(str)
    bypassRequested = Signal(str)

    def __init__(self, effect):
        super().__init__()
        self.setObjectName('effectChoice')
        row = QHBoxLayout(self); row.setContentsMargins(2, 0, 7, 0); row.setSpacing(4)
        self.button = QPushButton(effect.label); self.button.setObjectName('effectChoiceButton')
        self.button.clicked.connect(lambda: self.selected.emit(effect.id))
        row.addWidget(self.button, 1)
        self.badge = QLabel(); self.badge.setObjectName('effectState'); row.addWidget(self.badge)
        self.bypass = QPushButton('Bypass'); self.bypass.setVisible(effect.id not in SOURCE_EFFECTS)
        self.bypass.clicked.connect(lambda: self.bypassRequested.emit(effect.id)); row.addWidget(self.bypass)

    def refresh(self, effect, info, selected, bypassed):
        state = 'Bypassed' if bypassed else 'Intermittent' if info['intermittent'] else 'On' if info['active'] else 'Off'
        self.badge.setText(state)
        self.bypass.setText("Resume" if bypassed else "Bypass")
        self.bypass.setAccessibleName(f'{self.bypass.text()} {effect.label}')
        self.button.setAccessibleName(f'Inspect {effect.label} · {state}')
        self.setToolTip(effect.description + (' Active during part of this scope.' if info['intermittent'] else ''))
        for widget, name, value in ((self, 'selected', selected), (self.badge, 'active', info['active'])):
            if widget.property(name) != value:
                widget.setProperty(name, value)
                widget.style().unpolish(widget); widget.style().polish(widget); widget.update()


class EffectsPanel(QWidget):
    edited = Signal(str, object, str)
    timing_edited = Signal(str, object)
    timing_reset = Signal()
    timing_selected = Signal(bool)
    navigation_changed = Signal()
    object_requested = Signal()
    variation_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.entries = {}; self.parent_entries = {}; self.summary = {}; self.authored_summary = {}
        self.effect_id = "rays"; self.controls = {}; self.rows = {}; self.control_cache = {}
        self.context_key = None; self.local = False; self.focused = True
        self.shared_timing = {}; self.shared_summary = {}; self.context_scope_label = ''
        self.updating = False; self.allowed_effects = None; self.browser = None
        self.applied_ids = (); self.available_ids = (); self.effect_choices = {}; self.group_labels = {}
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 4, 8, 4); layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scope_label = QLabel(); self.scope_label.setObjectName("sectionTitle"); self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)
        self.pages = QStackedWidget(); layout.addWidget(self.pages, 1)
        self.overview = QWidget(); overview_layout = QVBoxLayout(self.overview); overview_layout.setContentsMargins(0, 0, 0, 0)
        self.applied_title = QLabel(); self.applied_title.setObjectName('sectionTitle'); overview_layout.addWidget(self.applied_title)
        self.available_button = QPushButton('Add effect…'); self.available_button.clicked.connect(self.open_browser)
        overview_layout.addWidget(self.available_button)
        rack_scroll = QScrollArea(); rack_scroll.setWidgetResizable(True); rack_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rack = QWidget(); rack_layout = QVBoxLayout(rack); rack_layout.setContentsMargins(0, 0, 0, 0)
        self.applied_host = QWidget(); self.applied_layout = QVBoxLayout(self.applied_host)
        self.applied_layout.setContentsMargins(0, 0, 0, 0); self.applied_layout.setSpacing(3)
        rack_layout.addWidget(self.applied_host)
        self.empty_applied = QLabel('No image effects applied. Add an effect to treat the source.'); self.empty_applied.setWordWrap(True)
        self.empty_applied.setObjectName('muted'); rack_layout.addWidget(self.empty_applied)
        self.source_title = QLabel('OBJECT / sources'); self.source_title.setObjectName('sectionTitle'); rack_layout.addWidget(self.source_title)
        self.source_host = QWidget(); self.source_layout = QVBoxLayout(self.source_host); self.source_layout.setContentsMargins(0, 0, 0, 0)
        rack_layout.addWidget(self.source_host)
        self.object_button = QPushButton('Choose or edit object…'); self.object_button.clicked.connect(self.object_requested.emit)
        rack_layout.addWidget(self.object_button); rack_layout.addStretch(1)
        rack_scroll.setWidget(rack); overview_layout.addWidget(rack_scroll, 1); self.pages.addWidget(self.overview)
        # Retain the public row lookup for programmatic inspection. Discovery is in the dialog.
        self.available_host = QWidget(); self.available_host.hide(); self.available_layout = QVBoxLayout(self.available_host)
        for effect in EFFECTS:
            choice = EffectChoice(effect); choice.selected.connect(self.inspect_choice)
            choice.bypassRequested.connect(self.toggle_bypass)
            self.available_layout.addWidget(choice); self.effect_choices[effect.id] = choice
        self.editor = QWidget(); editor_layout = QVBoxLayout(self.editor); editor_layout.setContentsMargins(0, 0, 0, 0); editor_layout.setSpacing(4)
        row = QHBoxLayout()
        self.back_button = QPushButton('← Back to effects'); self.back_button.clicked.connect(self.show_overview); row.addWidget(self.back_button)
        self.add_button = QPushButton('Add effect…'); self.add_button.clicked.connect(self.open_browser); row.addWidget(self.add_button)
        editor_layout.addLayout(row)
        row = QHBoxLayout()
        self.inspector_title = QLabel(); self.inspector_title.setObjectName('sectionTitle'); self.inspector_title.setWordWrap(True); row.addWidget(self.inspector_title, 1)
        self.bypass_button = QPushButton('Bypass'); self.bypass_button.clicked.connect(lambda: self.toggle_bypass(self.effect_id)); row.addWidget(self.bypass_button)
        editor_layout.addLayout(row)
        self.description = QLabel(); self.description.hide()
        row = QHBoxLayout()
        self.mode = QComboBox()
        for label, value in (("Follow study", "recipe"), ("On throughout scope", "on"), ("Off throughout scope", "off")): self.mode.addItem(label, value)
        self.mode.currentIndexChanged.connect(self.change_mode); row.addWidget(self.mode, 1)
        self.restore = QPushButton("Restore this effect"); self.restore.clicked.connect(self.restore_effect); row.addWidget(self.restore)
        self.activation_row = row; editor_layout.addLayout(row)
        row = QHBoxLayout()
        self.look = QComboBox(); row.addWidget(self.look, 1)
        self.apply_button = QPushButton("Replace with preset"); self.apply_button.clicked.connect(self.apply_look); row.addWidget(self.apply_button)
        self.preset_row = row; editor_layout.addLayout(row)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setObjectName('muted'); editor_layout.addWidget(self.status)
        self.parameter_tabs = QTabBar()
        for title in ('Look', 'Timing', 'Signal', 'Screen'): self.parameter_tabs.addTab(title)
        self.parameter_tabs.currentChanged.connect(self.change_parameter_tab); editor_layout.addWidget(self.parameter_tabs)
        row = QHBoxLayout()
        self.group = QComboBox(); self.group.setAccessibleName('Effect control group'); self.group.currentIndexChanged.connect(lambda _index: self.show_controls()); row.addWidget(self.group, 1)
        self.filter = QLineEdit(); self.filter.setPlaceholderText('Find a control…'); self.filter.setClearButtonEnabled(True)
        self.filter.setAccessibleName('Find effect control'); self.filter.textChanged.connect(lambda _text: self.show_controls()); row.addWidget(self.filter, 1)
        editor_layout.addLayout(row)
        self.parameter_scroll = QScrollArea(); self.parameter_scroll.setWidgetResizable(True); self.parameter_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.parameter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.parameter_scroll.setMinimumHeight(100); editor_layout.addWidget(self.parameter_scroll, 1)
        body = QWidget(); body_layout = QVBoxLayout(body); body_layout.setContentsMargins(0, 0, 2, 0)
        self.activation_button = QPushButton('Activation && preset ▸'); self.activation_button.setCheckable(True)
        self.activation_button.setToolTip('Choose activation timing, restore this effect or replace its settings with a preset.')
        body_layout.addWidget(self.activation_button)
        self.activation_host = QWidget(); activation_layout = QVBoxLayout(self.activation_host)
        activation_layout.setContentsMargins(0, 0, 0, 6)
        editor_layout.removeItem(self.activation_row); editor_layout.removeItem(self.preset_row); editor_layout.removeWidget(self.status)
        activation_layout.addLayout(self.activation_row); activation_layout.addLayout(self.preset_row); activation_layout.addWidget(self.status)
        self.description.setParent(self.activation_host); self.description.setWordWrap(True); self.description.setObjectName('muted')
        activation_layout.addWidget(self.description); self.description.show()
        body_layout.addWidget(self.activation_host); self.activation_host.hide()
        self.activation_button.toggled.connect(self.show_activation)
        self.timing_note = QLabel(); self.timing_note.setWordWrap(True); self.timing_note.setObjectName('muted'); body_layout.addWidget(self.timing_note)
        self.restore_timing = QPushButton('Restore shared timing'); self.restore_timing.clicked.connect(self.timing_reset.emit); body_layout.addWidget(self.restore_timing)
        self.creative_panel = CreativeControlsPanel()
        self.creative_panel.changed.connect(self.change_creative)
        self.creative_panel.restored.connect(self.restore_creative)
        self.creative_panel.variation_requested.connect(self.variation_requested.emit)
        body_layout.addWidget(self.creative_panel)
        self.creative_notice = QLabel(); self.creative_notice.setWordWrap(True)
        self.creative_notice.setObjectName('muted'); body_layout.addWidget(self.creative_notice)
        self.parameter_host = QWidget(); self.parameter_layout = QVBoxLayout(self.parameter_host); self.parameter_layout.setContentsMargins(0, 0, 0, 0); body_layout.addWidget(self.parameter_host)
        self.no_matches = QLabel('No matching controls in this tab.'); self.no_matches.setObjectName('muted'); body_layout.addWidget(self.no_matches); self.no_matches.hide()
        self.note = QLabel('Use fixed value to override an animated control. Restore follows the whole clip or study again.')
        self.note.setWordWrap(True); self.note.setObjectName('muted'); body_layout.addWidget(self.note); body_layout.addStretch(1)
        self.parameter_scroll.setWidget(body); self.pages.addWidget(self.editor); self.pages.setCurrentWidget(self.editor)

    def show_activation(self, expanded):
        self.activation_host.setVisible(expanded)
        self.activation_button.setText('Activation && preset ' + ('▾' if expanded else '▸'))

    def is_bypassed(self, effect_id):
        return self.entries.get(effect_id, {}).get('bypassed', self.parent_entries.get(effect_id, {}).get('bypassed', False))

    def show_overview(self):
        self.focused = False; self.pages.setCurrentWidget(self.overview)
        self.scope_label.setText(self.context_scope_label); self.timing_selected.emit(False); self.navigation_changed.emit()

    def inspect_choice(self, effect_id):
        if effect_id in SOURCE_EFFECTS: self.object_requested.emit()
        else: self.inspect_effect(effect_id)

    def browser_applied_ids(self):
        # Authored disabled entries are still duplicates; Inspect preserves them.
        return tuple(dict.fromkeys((*self.applied_ids, *self.parent_entries, *self.entries)))

    def open_browser(self):
        from synth_effect_browser import EffectBrowserDialog
        if self.browser is None:
            self.browser = EffectBrowserDialog(self.allowed_effects, self.browser_applied_ids(), self)
            self.browser.effectRequested.connect(self.add_effect)
            self.browser.effectInspected.connect(self.inspect_effect)
            self.browser.objectRequested.connect(self.object_requested.emit)
        self.browser.set_context(self.allowed_effects, self.browser_applied_ids())
        self.browser.open()

    def add_effect(self, effect_id, preset_index):
        if effect_id in self.browser_applied_ids():
            self.inspect_effect(effect_id); return
        if effect_id not in EFFECT_BY_ID or effect_id in SOURCE_EFFECTS: return
        if self.allowed_effects is not None and effect_id not in self.allowed_effects: return
        self.inspect_effect(effect_id)
        self.edited.emit(effect_id, effect_preset(effect_id, preset_index), 'effect-add')

    def toggle_bypass(self, effect_id):
        if self.updating or effect_id in SOURCE_EFFECTS: return
        entry = copy.deepcopy(self.entries.get(effect_id, {'mode': 'recipe', 'params': {}}))
        entry['bypassed'] = not self.is_bypassed(effect_id)
        self.edited.emit(effect_id, entry, 'effect-bypass')

    def set_context(self, entries, parent_entries, states, scope_label, local, context_key, shared_timing=None, shared_states=None, allowed_effects=None, authored_states=None):
        self.updating = True
        self.entries = copy.deepcopy(entries); self.parent_entries = copy.deepcopy(parent_entries); self.local = local
        self.summary = describe_effects(states); self.authored_summary = describe_effects(authored_states) if authored_states is not None else self.summary
        self.allowed_effects = allowed_effects
        visible_effects = [e for e in EFFECTS if allowed_effects is None or e.id in allowed_effects]
        self.shared_timing = copy.deepcopy(shared_timing or {})
        self.shared_summary = describe_effects(shared_states)['ink_bloom'] if shared_states is not None else self.authored_summary['ink_bloom']
        self.context_scope_label = scope_label if scope_label.startswith('Editing:') else 'Editing: ' + scope_label
        active = [effect for effect in visible_effects if self.summary[effect.id]['active'] or self.is_bypassed(effect.id)]
        initial_context = self.context_key is None
        changed_context = context_key != self.context_key
        if visible_effects and (self.effect_id not in {e.id for e in visible_effects} or
                (changed_context and not self.summary[self.effect_id]['active'] and not self.is_bypassed(self.effect_id) and active)):
            self.effect_id = (active or visible_effects)[0].id
        self.context_key = context_key
        self.applied_ids = tuple(effect.id for effect in active)
        self.available_ids = tuple(effect.id for effect in visible_effects if effect.id not in self.applied_ids)
        treatments = [e for e in active if e.id not in SOURCE_EFFECTS]
        sources = [e for e in active if e.id in SOURCE_EFFECTS]
        self.applied_title.setText(f'IMAGE EFFECTS · {len(treatments)}'); self.empty_applied.setVisible(not treatments)
        self.source_title.setVisible(bool(sources)); self.source_host.setVisible(bool(sources))
        self.object_button.setVisible(allowed_effects is None or any(key in allowed_effects for key in SOURCE_EFFECTS))
        for effect in EFFECTS:
            target = self.source_layout if effect.id in SOURCE_EFFECTS else self.applied_layout
            target.addWidget(self.effect_choices[effect.id])
            self.effect_choices[effect.id].setVisible(effect.id in self.applied_ids)
        with QSignalBlocker(self.mode): self.mode.setItemText(0, 'Follow whole clip / study' if local else 'Follow study')
        self.updating = False
        self.refresh_effect()
        if changed_context: self.parameter_scroll.verticalScrollBar().setValue(0)
        if initial_context and not active: self.show_overview()

    def inspect_effect(self, effect_id):
        if self.updating or effect_id not in EFFECT_BY_ID: return
        if self.allowed_effects is not None and effect_id not in self.allowed_effects: return
        switched = self.effect_id != effect_id
        self.effect_id = effect_id; self.focused = True; self.pages.setCurrentWidget(self.editor)
        with QSignalBlocker(self.filter): self.filter.clear()
        with QSignalBlocker(self.group): self.group.setCurrentIndex(0)
        if switched:
            self.activation_button.setChecked(False)
            with QSignalBlocker(self.parameter_tabs): self.parameter_tabs.setCurrentIndex(0)
        self.refresh_effect(); self.parameter_scroll.verticalScrollBar().setValue(0); self.navigation_changed.emit()

    def show_available(self, expanded):
        if expanded: self.open_browser()

    def refresh_effect(self):
        if not self.summary: return
        self.updating = True
        effect = EFFECT_BY_ID[self.effect_id]
        self.inspector_title.setText(f'{"SOURCE" if effect.id in SOURCE_EFFECTS else "EDIT"} / {effect.label}')
        self.inspector_title.setToolTip(effect.description)
        for item in EFFECTS:
            self.effect_choices[item.id].refresh(item, self.authored_summary[item.id], item.id == effect.id, self.is_bypassed(item.id))
        entry = self.entries.get(effect.id, {"mode": "recipe", "params": {}})
        with QSignalBlocker(self.mode): self.mode.setCurrentIndex(self.mode.findData(entry["mode"]))
        self.description.setText(effect.description)
        self.restore.setEnabled(effect.id in self.entries)
        self.restore.setToolTip("Remove only this effect's overrides in the selected scope. Follow the whole clip or study again.")
        self.bypass_button.setVisible(effect.id not in SOURCE_EFFECTS)
        self.bypass_button.setText('Resume' if self.is_bypassed(effect.id) else 'Bypass')
        self.bypass_button.setToolTip('Temporarily disable this effect while retaining its activation timing and parameters.')
        if tuple(self.controls) != effect.paths:
            while self.parameter_layout.count():
                widget = self.parameter_layout.takeAt(0).widget()
                if widget: widget.hide()
            for label in self.group_labels.values(): label.deleteLater()
            self.group_labels = {}
            self.controls = self.control_cache.get(effect.id, {})
            if not self.controls:
                for path in effect.paths:
                    control = EffectParameter(path)
                    control.changed.connect(lambda value, path=path, effect_id=effect.id: self.change_parameter(path, value, effect_id))
                    control.reset.connect(lambda path=path, effect_id=effect.id: self.reset_parameter(path, effect_id))
                    self.controls[path] = control
                self.control_cache[effect.id] = self.controls
            for control in self.controls.values(): self.parameter_layout.addWidget(control)
            with QSignalBlocker(self.look):
                self.look.clear()
                for label, _ in effect.looks or (("Default settings", {}),): self.look.addItem(label)
            with QSignalBlocker(self.group): self.group.clear()
        info = self.authored_summary[effect.id]
        parent = self.parent_entries.get(effect.id, {})
        available = info["active"] or entry["mode"] in {"on", "off"} or effect.id in self.entries
        self.creative_panel.refresh(effect.id, entry, parent, info, available, self.local)
        for path, control in self.controls.items():
            if path in INK_TIMING:
                control.refresh(self.shared_summary['ranges'][path], self.shared_timing.get(path), False, True, scope_label='Whole clip', origin_label='Whole clip · shared timing', context_key=('shared-timing',))
                control.origin.setText('Shared across all sections' if self.shared_timing else 'Recipe timing · edits apply to all sections')
                control.setToolTip('One timing setup for the whole composition, regardless of the selected section.')
            else:
                control.refresh(info["ranges"][path], entry["params"].get(path), path in parent.get("params", {}), available, parent_value=parent.get("params", {}).get(path), scope_label=self.context_scope_label.removeprefix("Editing: "), context_key=self.context_key)
            control.base_origin = control.origin.text()
        self.apply_button.setText("Replace with preset" if effect.id in self.applied_ids else "Apply preset")
        self.status.setText("Active during part of the recipe. On keeps it enabled throughout." if info["intermittent"] else
                            "Active. Unedited values keep following their recipe." if info["active"] else
                            f"{effect.label} is off in this scope. Open Activation & preset to apply settings, or return to the effects overview.")
        if self.is_bypassed(effect.id): self.status.setText('Bypassed · edits are retained. Resume restores the original activation timing.')
        elif self.local: self.status.setText(self.status.text() + ' Unedited controls follow the whole clip or study.')
        else: self.status.setText(self.status.text() + ' Section overrides take priority.')
        if effect.id == 'ink_bloom' and self.controls['ink_bloom.shape'].input.currentIndex() == 5 and not self.controls['ink_bloom.artwork'].input.value():
            self.status.setText('Import artwork to supply the custom silhouette, or choose a built-in shape.')
        self.show_controls()
        self.updating = False
        self.navigation_changed.emit()

    def change_parameter_tab(self, _index):
        with QSignalBlocker(self.filter): self.filter.clear()
        with QSignalBlocker(self.group): self.group.clear()
        self.show_controls(); self.parameter_scroll.verticalScrollBar().setValue(0); self.navigation_changed.emit()

    def show_controls(self):
        if not self.summary: return
        effect = EFFECT_BY_ID[self.effect_id]
        pilot = effect.id in CREATIVE_CONTROLS
        with QSignalBlocker(self.parameter_tabs):
            if effect.id != 'broadcast' and self.parameter_tabs.currentIndex() > 1:
                self.parameter_tabs.setCurrentIndex(0)
            for index in (2, 3): self.parameter_tabs.setTabVisible(index, effect.id == 'broadcast')
        creative = pilot and self.parameter_tabs.currentIndex() == 0
        ink = effect.id == 'ink_bloom'
        text = effect.id == 'text'
        text_timing = text and self.parameter_tabs.currentIndex() == 1
        broadcast = effect.id == 'broadcast'
        polarity = broadcast and self.parameter_tabs.currentIndex() == 1
        phosphor = effect.id == 'edge_phosphor'
        region = phosphor and self.parameter_tabs.currentIndex() == 1
        timing = ink and self.parameter_tabs.currentIndex() == 1
        self.parameter_tabs.setTabText(0, 'Creative' if pilot else 'Look')
        self.parameter_tabs.setTabText(1, 'Parameters' if pilot else 'Region' if phosphor else 'Polarity' if broadcast else 'Timing')
        self.parameter_tabs.setVisible(pilot or ink or phosphor or text or broadcast)
        self.creative_panel.setVisible(creative)
        self.parameter_host.setVisible(not creative)
        self.filter.setVisible(not creative)
        self.note.setVisible(not creative)
        adjustments = dict(self.parent_entries.get(effect.id, {}).get('creative', {}).get('values', {}))
        adjustments.update(self.entries.get(effect.id, {}).get('creative', {}).get('values', {}))
        adjusted = [spec for spec in CREATIVE_CONTROLS.get(effect.id, ()) if adjustments.get(spec.key, spec.neutral) != spec.neutral]
        labels = ', '.join(f'{spec.label} {adjustments[spec.key]:+g} copies' if spec.operation == 'offset'
                           else f'{spec.label} {adjustments[spec.key] * 100:.0f}%' for spec in adjusted)
        self.creative_notice.setText('Creative adjustments still act after these base values: ' + labels + '. Open Creative to change or restore them.' if adjusted else '')
        self.creative_notice.setVisible(pilot and not creative and bool(adjusted))
        for path, control in self.controls.items():
            influences = [spec.label for spec in adjusted if path in spec.paths]
            origin = getattr(control, 'base_origin', control.origin.text())
            control.origin.setText(origin + (' · adjusted by ' + ', '.join(influences) if influences else ''))
        self.activation_button.setVisible(not timing)
        self.activation_host.setVisible(not timing and self.activation_button.isChecked())
        self.timing_note.setVisible(timing)
        self.restore_timing.setVisible(timing)
        self.restore_timing.setEnabled(bool(self.shared_timing))
        for widget in (self.mode, self.restore, self.look, self.apply_button, self.status): widget.setVisible(not timing)
        self.scope_label.setText('Editing: Whole clip · shared timing' if timing else self.context_scope_label)
        if not self.focused: self.scope_label.setText(self.context_scope_label)
        self.timing_selected.emit(timing and self.focused)
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
        groups = grouped_paths(visible_paths)
        titles = tuple(title for title, _paths in groups)
        if tuple(self.group.itemText(i) for i in range(1, self.group.count())) != titles:
            with QSignalBlocker(self.group):
                self.group.clear(); self.group.addItem('All groups', None)
                for title in titles: self.group.addItem(title, title)
        self.group.setVisible(not creative and len(titles) > 1)
        selected_group = self.group.currentData()
        if selected_group:
            visible_paths = next(paths for title, paths in groups if title == selected_group)
        query = self.filter.text().strip().casefold()
        shown = {p for p in visible_paths if not query or query in parameter(p).label.casefold() or query in p.casefold()}
        for path, control in self.controls.items(): control.setVisible(path in shown)
        for label in self.group_labels.values(): label.hide()
        index = 0
        for title, paths in grouped_paths(visible_paths):
            matching = [p for p in paths if p in shown]
            if not matching: continue
            if title not in self.group_labels:
                label = QLabel(title.upper()); label.setObjectName('controlGroup'); self.group_labels[title] = label
            label = self.group_labels[title]; label.show()
            for widget in (label, *(self.controls[p] for p in matching)):
                if self.parameter_layout.indexOf(widget) != index: self.parameter_layout.insertWidget(index, widget)
                index += 1
        self.no_matches.setVisible(not creative and not shown)
        if timing:
            loops = self.shared_summary['loop_seconds']
            if not loops: loop = 'Enable Ink bloom to preview its timing.'
            elif not math.isfinite(loops[1]): loop = 'Gesture speed is frozen in part or all of this scope.'
            elif loops[0] == loops[1]: loop = f'Loop: {loops[0]:.2f} s at the current speed.'
            else: loop = f'Loop varies: {loops[0]:.2f}–{loops[1]:.2f} s across this scope.'
            self.timing_note.setText('Changes apply to every section. ' + loop + ' Complete-cycle sections resize together to keep their boundaries aligned. Durations are at 1×; Stay folded is the total rest between gestures.')

    def change_mode(self, index):
        if self.updating or index < 0: return
        entry = copy.deepcopy(self.entries.get(self.effect_id, {"mode": "recipe", "params": {}}))
        entry["mode"] = self.mode.itemData(index)
        self.edited.emit(self.effect_id, entry, "effect-mode")

    def change_creative(self, key, value):
        if self.updating: return
        entry = copy.deepcopy(self.entries.get(self.effect_id, {'mode': 'recipe', 'params': {}}))
        creative = entry.setdefault('creative', {'version': 1, 'values': {}})
        creative.pop('variation', None)
        creative['values'][key] = value
        self.edited.emit(self.effect_id, entry, f'effect-creative:{self.context_key}:{self.effect_id}:{key}')

    def restore_creative(self, key):
        if self.updating: return
        entry = copy.deepcopy(self.entries.get(self.effect_id, {'mode': 'recipe', 'params': {}}))
        if key is None: entry.pop('creative', None)
        elif 'creative' in entry:
            entry['creative'].pop('variation', None)
            entry['creative']['values'].pop(key, None)
            if not entry['creative']['values']: entry.pop('creative')
        if entry['mode'] == 'recipe' and not entry['params'] and set(entry) == {'mode', 'params'}:
            entry = None
        self.edited.emit(self.effect_id, entry, 'effect-creative-restore')

    def change_parameter(self, path, value, effect_id=None):
        effect_id = effect_id or self.effect_id
        if self.updating: return
        if path in INK_TIMING:
            self.timing_edited.emit(path, value)
            return
        entry = copy.deepcopy(self.entries.get(effect_id, {"mode": "recipe", "params": {}}))
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
        self.edited.emit(effect_id, entry, f"effect-param:{path}")

    def reset_parameter(self, path, effect_id=None):
        effect_id = effect_id or self.effect_id
        if path in INK_TIMING:
            self.timing_edited.emit(path, None)
            return
        entry = copy.deepcopy(self.entries.get(effect_id, {"mode": "recipe", "params": {}})); entry["params"].pop(path, None)
        self.edited.emit(effect_id, entry, "effect-reset-param")

    def restore_effect(self):
        self.edited.emit(self.effect_id, None, "effect-restore")

    def apply_look(self):
        entry = effect_preset(self.effect_id, self.look.currentIndex())
        previous = self.entries.get(self.effect_id, {})
        if 'bypassed' in previous: entry['bypassed'] = previous['bypassed']
        if self.local and 'creative' in self.parent_entries.get(self.effect_id, {}):
            entry['creative'] = {'version': 1, 'values': {spec.key: spec.neutral for spec in CREATIVE_CONTROLS.get(self.effect_id, ())}}
        self.edited.emit(self.effect_id, entry, "effect-apply")
