"""Task-oriented object inspector navigation; never writes document values."""
from PySide6.QtCore import Qt, QSignalBlocker, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from synth_object_catalog import family_groups, PARAMETER_OWNER


def paths(prefix, names):
    return tuple(prefix + '.' + name for name in names.split())


# (page, title, initially open, parameter names). Typography and main wording
# keep their existing editor above these groups on the Text page.
TEXT_GROUPS = (
    (0, 'Subtitle', False, 'badge badge_show_subtitle badge_subtitle'),
    (1, 'Size & spacing', True, 'size fit block_width fit_width align tracking leading wrap_columns'),
    (1, 'Color & light', False, 'hue saturation brightness opacity back_hue back_saturation back_brightness'),
    (1, 'Letterpress', False, 'press_height press_width press_angle press_baseline press_seed press_rate'),
    (1, 'Geometry', False, 'stretch_x stretch_y rotation morph_balance morph_roundness'),
    (1, 'Repetitions', False, 'copies copy_gap copy_floor'),
    (1, 'Frame & subtitle layout', False, 'badge_shape badge_border badge_padding_x badge_padding_y badge_type_fit badge_subtitle_scale badge_subtitle_width badge_gap badge_radius'),
    (2, 'Reading', True, 'reveal reading_duration reading_final word_seconds morph_hold morph_seconds'),
    (2, 'Interruptions & ending', False, 'reading_transition reading_weight reading_breakup reading_fragments reading_loop morph_loop'),
    (2, 'Morph character', False, 'morph_ease morph_snap morph_settle morph_flow morph_living'),
    (2, 'Size motion', False, 'motion zoom_start zoom_end period ease phase cadence'),
)
PLEATED_GROUPS = (
    (0, 'Profile & scale', True, 'profile density size'),
    (0, 'Surface & relief', False, 'depth curl stagger irregularity seams highlight light_angle'),
    (0, 'Camera', False, 'projection yaw pitch distance angle perspective shear tilt_x tilt_y pan_x pan_y'),
    (0, 'Palette', False, 'palette hue_shift saturation light background_motion'),
    (0, 'Outline & mirrors', False, 'aperture taper boundary edge symmetry mirror_x mirror_y'),
    (0, 'Motion & timing', False, 'phase flow cadence loop_seconds'),
    (0, 'Optical finish', False, 'softness mix'),
)


class ControlGroup(QWidget):
    def __init__(self, title, callback):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 4); layout.setSpacing(2)
        self.button = QPushButton(); self.button.setCheckable(True)
        self.button.setObjectName('controlGroup'); self.button.setProperty('compact', True)
        self.button.setAccessibleName(title + ' controls')
        self.button.toggled.connect(callback); layout.addWidget(self.button)
        self.summary = QLabel(); self.summary.setObjectName('muted'); self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.body = QWidget(); self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 2, 0, 0); self.body_layout.setSpacing(6)
        layout.addWidget(self.body)


class ObjectGroupsMixin:
    """Kept separate from source editing and effect/rendering contracts."""
    def setup_object_groups(self):
        self.object_groups = {}
        self.object_expansion = {}
        self.object_counts = {}
        self.search_snapshot = None
        self.search_generation = 0

    def clear_object_groups(self):
        # Cached parameter widgets (including unapplied text) outlive groups.
        for control in self.controls.values():
            control.setParent(self.control_host); control.hide()
        self.motion_frame.setParent(self.overview); self.motion_frame.hide()
        self.signal_host.setParent(self.overview); self.signal_host.hide()
        self.position_host.setParent(self.overview); self.position_host.hide()
        for group in self.object_groups.values():
            self.control_layout.removeWidget(group); group.hide(); group.deleteLater()
        self.object_groups = {}

    def build_object_groups(self):
        prefix = 'text' if self.kind == 'text' else 'pleated_field'
        if self.kind in ('text', 'pleated'):
            definitions = TEXT_GROUPS if self.kind == 'text' else PLEATED_GROUPS
            self.object_definitions = tuple((page, title, opened, paths(prefix, names))
                                            for page, title, opened, names in definitions)
        else:
            self.object_definitions = family_groups(self.kind)
        if self.kind == 'signal':
            self.object_definitions = ((0, 'Shared geometry', True, ()), *self.object_definitions)
        if self.kind != 'text':
            self.object_definitions = (self.object_definitions[0], (0, 'Canvas position', False, ()),
                                       *self.object_definitions[1:])
        else:
            layout = self.overview.layout()
            layout.insertWidget(layout.indexOf(self.control_host), self.position_host)
        for page, title, opened, members in self.object_definitions:
            group = ControlGroup(title, lambda state, t=title: self.toggle_object_group(t, state))
            self.object_groups[title] = group
            self.control_layout.addWidget(group)
            for path in members: group.body_layout.addWidget(self.controls[path])
            if self.kind == 'memory' and title == 'Path & travel':
                group.body_layout.addWidget(self.motion_frame); self.motion_frame.show()
            if self.kind == 'signal' and title == 'Shared geometry':
                group.body_layout.addWidget(self.signal_host); self.signal_host.show()
            if title == 'Canvas position':
                group.body_layout.addWidget(self.position_host); self.position_host.show()
        if self.kind == 'text':
            for path in ('text.font', 'text.weight', 'text.content'):
                self.wording_layout.addWidget(self.controls[path])

    def toggle_object_group(self, title, expanded):
        self.object_expansion[(self.kind, title)] = expanded
        self.show_object_groups()

    def set_automation_counts(self, counts):
        self.object_counts = counts
        for path, control in self.controls.items(): control.set_automation_count(counts.get(path, 0))
        if self.object_groups: self.show_object_groups()

    def group_summary(self, members):
        local = animated = 0
        for path in members:
            effect = PARAMETER_OWNER[path]
            fixed = self.object_entries.get(effect, {}).get('params', {}).get(path)
            inherited = self.object_parents.get(effect, {}).get('params', {}).get(path)
            low, high = self.object_ranges[effect]['ranges'][path]
            local += fixed is not None
            animated += bool(self.object_counts.get(path)) or (fixed is None and inherited is None and low != high)
        parts = []
        if local: parts.append(f'{local} local value' + ('s' if local != 1 else ''))
        if animated: parts.append(f'{animated} animated')
        return ' · '.join(parts) or 'No local overrides'

    def show_object_groups(self):
        if not self.object_groups: return
        query = self.object_filter.text().strip().casefold()
        page = self.text_tabs.currentIndex() if self.kind == 'text' else 0
        eligible = self.text_eligible if self.kind == 'text' else self.object_eligible
        self.search_results = []
        text_primary = ('text.font', 'text.weight', 'text.content') if self.kind == 'text' else ()
        for path in text_primary:
            control = self.controls[path]
            shown = path in eligible and (bool(query) or page == 0)
            shown = shown and (not query or query in (control.spec.label + ' ' + control.label.text() + ' ' + path + ' text typeface').casefold())
            control.setVisible(shown)
            if shown: self.search_results.append(path)
        self.wording_host.setVisible(any(p in self.search_results for p in text_primary))
        for group_page, title, opened, members in self.object_definitions:
            group = self.object_groups[title]
            matching = [p for p in members if p in eligible and
                        (not query or query in (self.controls[p].spec.label + ' ' + self.controls[p].label.text() + ' ' + p + ' ' + title + (' center path' if self.kind == 'memory' and title == 'Path & travel' else '')).casefold())]
            shared_geometry = self.kind == 'signal' and title == 'Shared geometry'
            geometry_match = shared_geometry and (not query or any(query in term for term in ('shared geometry', 'shape', 'width', 'height', 'diameter', 'sides', 'rotation')))
            position_group = title == 'Canvas position'
            position_match = position_group and (not query or any(query in term for term in ('position', 'position x', 'position y', 'canvas pixels')))
            visible = (bool(matching) or geometry_match or position_match) and (bool(query) or group_page == page)
            group.setVisible(visible)
            # Active framed labels expose their existing subtitle on first use.
            default_open = opened or (title == 'Subtitle' and self.text_ranges['text.badge'] != (0, 0))
            expanded = bool(query) or self.show_all_controls.isChecked() or self.object_expansion.get((self.kind, title), default_open)
            with QSignalBlocker(group.button): group.button.setChecked(expanded)
            label = (('Text', 'Layout', 'Motion')[group_page] + ' / ' if query and self.kind == 'text' else '') + title
            group.button.setText(label.replace('&', '&&') + (' ▾' if expanded else ' ▸'))
            group.button.setEnabled(not query and not self.show_all_controls.isChecked())
            summary = self.group_summary(members)
            if shared_geometry: summary = 'Geometry shared by the form and rays. Base groups below keep their individual study controls.'
            if position_group: summary = ''
            if self.kind == 'text' and title in ('Subtitle', 'Frame & subtitle layout'):
                if self.text_ranges['text.reveal'] in ((3, 3), (4, 4)):
                    summary += '\nMain text only in this reading mode. Choose Show in Motion to use a subtitle and frame.'
                elif self.text_ranges['text.badge'] == (0, 0):
                    summary += '\nEnable Framed label in Text / Subtitle to use these controls.'
            if self.kind == 'text' and title == 'Reading':
                summary += '\nReading timing does not change the clip or project duration.'
            group.summary.setText(summary); group.summary.setVisible(bool(summary) and summary != 'No local overrides')
            group.button.setAccessibleDescription(summary + '. Expand or collapse. Changes no values.')
            group.body.setVisible(expanded)
            for path in members: self.controls[path].setVisible(path in matching)
            if visible: self.search_results.extend(matching)
        position_match = bool(query) and any(query in term for term in ('position', 'position x', 'position y', 'canvas pixels'))
        self.position_host.setVisible(position_match if query else self.kind != 'text' or page == 1)
        self.control_host.show()
        if query:
            self.text_layout_note.hide(); self.text_motion_link.hide()
        self.no_object_matches.setVisible(bool(query) and not self.search_results and not position_match and not any(not g.isHidden() for g in self.object_groups.values()))
        if self.kind == 'memory':
            self.motion_frame.setVisible(not query or any(query in term for term in ('center path', 'path & travel', 'amplitude', 'travel')))
        self.object_filter.setToolTip('Search all object pages and groups. Press Enter to edit the first matching control. Clear to return to your previous view.')

    def filter_object_controls(self, query):
        active = bool(query.strip())
        if active and self.search_snapshot is None:
            self.search_snapshot = (self.text_tabs.currentIndex(), self.overview_scroll.verticalScrollBar().value())
        self.search_generation += 1
        generation = self.search_generation
        self.show_object_groups()
        if not active and self.search_snapshot is not None:
            page, scroll = self.search_snapshot; self.search_snapshot = None
            with QSignalBlocker(self.text_tabs): self.text_tabs.setCurrentIndex(page)
            self.show_text_controls() if self.kind == 'text' else self.show_object_groups()
            QTimer.singleShot(0, lambda: self.overview_scroll.verticalScrollBar().setValue(scroll)
                              if generation == self.search_generation else None)
        elif active:
            self.overview_scroll.verticalScrollBar().setValue(0)

    def focus_object_result(self):
        if self.kind == 'memory' and self.object_filter.text().strip().casefold() == 'center path' and self.center_path.isVisible():
            self.center_path.setFocus(); self.overview_scroll.ensureWidgetVisible(self.center_path)
        elif self.search_results: self.focus_object_control(self.search_results[0])
        elif self.position_host.isVisible():
            self.position_controls['x'].setFocus()
            self.overview_scroll.ensureWidgetVisible(self.position_controls['x'])

    def focus_object_control(self, path):
        control = self.controls[path]
        def focus():
            if path not in self.controls or self.controls[path] is not control or not control.isVisible(): return
            target = control.use_fixed if control.value_stack.currentIndex() == 1 else control.input
            if hasattr(target, 'editor'): target = target.editor
            elif control.spec.kind == 'font': target = target.choose
            target.setFocus(Qt.FocusReason.OtherFocusReason)
            self.overview_scroll.ensureWidgetVisible(target, 0, 12)
        QTimer.singleShot(0, focus)

    def reveal_object_group(self, title):
        self.object_filter.clear()
        for page, name, opened, members in self.object_definitions:
            if name != title: continue
            if self.kind == 'text': self.text_tabs.setCurrentIndex(page)
            self.object_expansion[(self.kind, title)] = True
            self.show_object_groups()
            first = next((p for p in members if not self.controls[p].isHidden()), None)
            if first: self.focus_object_control(first)
            elif title == 'Canvas position':
                self.position_controls['x'].setFocus()
                self.overview_scroll.ensureWidgetVisible(self.position_controls['x'])
            else: self.overview_scroll.ensureWidgetVisible(self.object_groups[title])
            return
