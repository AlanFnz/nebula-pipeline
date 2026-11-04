"""Project-owned visual gestures; no study-specific UI or extra windows."""
import copy
from PIL import Image
from PySide6.QtCore import QTimer
from synth_performance import (defaults, normalize_performance, available_controls,
                               base_document, source_time, apply_frame, values_at, CONTROLS, SURFACE_CONTROLS, MAX_POINTS)
from synth_performance_ui import PerformancePanel


class PerformanceStudio:
    def init_performance(self):
        self.performance_panel = None
        self.performance_active = False
        self.performance_recording = False
        self.performance_recorded = False
        self.performance_record_keys = set()
        self.performance_gesture = False
        self.performance_gesture_saved = False
        self.performance_last_time = 0.
        self.performance_base_cache = None
        self.performance_needs_render = False
        self.performance_timer = QTimer(self)
        self.performance_timer.setSingleShot(True)
        self.performance_timer.setInterval(33)
        self.performance_timer.timeout.connect(self.flush_performance)

    def performance_panels(self):
        dialog = getattr(self, 'visual_sound_dialog', None)
        return [p for p in (self.performance_panel, getattr(dialog, 'performance_panel', None)) if p is not None]

    def make_performance_panel(self):
        panel = PerformancePanel(tuple(CONTROLS.values()))
        panel.set_available(available_controls(self.sequence))
        panel.edited.connect(self.edit_performance)
        panel.enabledChanged.connect(lambda value: self.edit_performance('enabled', value))
        panel.recordChanged.connect(self.set_performance_recording)
        panel.resetRequested.connect(lambda: self.replace_performance(defaults()))
        panel.clearRequested.connect(self.clear_performance_tracks)
        panel.prepareRequested.connect(self.prepare_full_playback)
        panel.gestureStarted.connect(self.begin_performance_gesture)
        panel.gestureFinished.connect(self.end_performance_gesture)
        return panel

    def attach_performance_panel(self):
        self.performance_panel = self.make_performance_panel()
        self.composer.look_tabs.addTab(self.performance_panel, 'Perform')
        self.composer.look_tabs.currentChanged.connect(self.performance_tab_changed)
        self.refresh_performance_panels()

    def attach_sound_performance(self, dialog):
        if hasattr(dialog, 'performance_panel'): return
        dialog.performance_panel = self.make_performance_panel()
        page = dialog.page('Visuals'); page.addWidget(dialog.performance_panel)
        dialog.performance_tab = dialog.tabs.count() - 1
        dialog.visuals_active = lambda: dialog.tabs.currentIndex() == dialog.performance_tab
        def tab_changed(_):
            dialog.workspace_hint.setText('Visual controls edit the project immediately. Save the project to keep them; Undo reverses edits. Apply below saves only the sound.' if dialog.visuals_active() else dialog.sound_hint)
            self.update_composition_history()
        dialog.tabs.currentChanged.connect(tab_changed)
        self.refresh_performance_panels()

    def performance_tab_changed(self, *_):
        active = self.performing_visuals()
        if active == self.performance_active: return
        self.performance_active = active
        if hasattr(self, 'soundtrack_playback') and hasattr(self, 'visual_sound_button'):
            self.refresh_soundtrack()

    def performing_visuals(self):
        return bool(self.composition and self.composer and self.performance_panel and
                    self.composer.look_tabs.currentWidget() is self.performance_panel)

    def refresh_performance_panels(self, force=False):
        if not self.composition or not self.sequence: return
        config = self.composition.get('visual_performance')
        controls = available_controls(self.sequence)
        for panel in self.performance_panels():
            panel.set_available(controls)
            panel.set_config(config, self.current_time, self.sequence['duration'], self.performance_recording, self.sequence['fps'], force=force)

    def update_performance_playhead(self, seconds):
        if not self.sequence: return
        if self.performance_recording and seconds < self.performance_last_time - .01:
            self.stop_performance_recording()
        self.performance_last_time = seconds
        for panel in self.performance_panels():
            if panel.isVisible(): panel.set_playhead(seconds, self.sequence['duration'])

    def begin_performance_gesture(self):
        self.performance_gesture = True; self.performance_gesture_saved = False

    def end_performance_gesture(self):
        self.performance_gesture = False; self.performance_gesture_saved = False

    def set_performance_recording(self, enabled):
        self.performance_recording = enabled
        self.performance_recorded = False
        self.performance_record_keys = set()
        self.performance_last_time = self.current_time
        self.refresh_performance_panels()

    def stop_performance_recording(self, *_):
        if self.performance_recording: self.set_performance_recording(False)

    def remember_performance(self):
        if self.performance_recording and self.performance_recorded: return
        if self.performance_gesture and self.performance_gesture_saved: return
        self.undo_compositions.append(copy.deepcopy(self.composition))
        self.undo_compositions = self.undo_compositions[-30:]
        self.redo_compositions.clear(); self.edit_key = None
        self.performance_recorded = self.performance_recording
        self.performance_gesture_saved = self.performance_gesture

    def edit_performance(self, key, value):
        if not self.composition or self.comparison: return
        config = copy.deepcopy(self.composition.get('visual_performance') or defaults())
        clock = self.current_time
        if key in SURFACE_CONTROLS:
            clock = source_time(config, clock, self.sequence['duration'], self.sequence['fps'])
        old = values_at(config, clock, self.sequence['duration']).get(key)
        if key == 'enabled': config['enabled'] = value
        else:
            config['values'][key] = value
            if self.performance_recording and self.play.isChecked():
                fraction = min(1., max(0., clock / self.sequence['duration']))
                points = config['tracks'].get(key, [])
                if key in self.performance_record_keys and points and fraction < points[-1][0]:
                    self.stop_performance_recording()
                    self.status.setText('Visual source looped. Recording saved.'); return
                if key not in self.performance_record_keys:
                    points = [p for p in points if p[0] < fraction]
                    if not points and fraction > 0: points = [[0., old]]
                    hold = max(0., fraction - 1 / (self.sequence['fps'] * self.sequence['duration']))
                    if points and hold > points[-1][0]: points.append([hold, old])
                    self.performance_record_keys.add(key)
                points = [p for p in points if p[0] < fraction]
                points.append([fraction, value]); config['tracks'][key] = points
                if sum(map(len, config['tracks'].values())) > MAX_POINTS:
                    self.stop_performance_recording()
                    self.status.setText('Recording full. Start a new take or clear the recording.'); return
            else: config['tracks'].pop(key, None)
        if config == self.composition.get('visual_performance'): return
        self.remember_performance()
        self.store_performance(config)

    def replace_performance(self, config):
        self.stop_performance_recording(); self.end_performance_gesture()
        if not self.composition: return
        self.remember_performance(); self.store_performance(config)

    def clear_performance_tracks(self):
        config = copy.deepcopy(self.composition.get('visual_performance') or defaults())
        config['tracks'] = {}; self.replace_performance(config)

    def store_performance(self, config):
        config = normalize_performance(config)
        previous = self.composition.get('visual_performance') or defaults()
        def surface(config):
            if not config.get('enabled', True): config = defaults()
            return {k: (config['values'][k], config['tracks'].get(k)) for k in SURFACE_CONTROLS}
        changed_surface = surface(previous) != surface(config)
        prepared = self.performance_base_sequence()
        self.performance_needs_render |= changed_surface
        # Copy just metadata here. The source, effects and compiled cues are unchanged.
        self.composition = dict(self.composition, schema_version=7, visual_performance=config)
        self.sequence = dict(self.sequence, schema_version=7, visual_performance=copy.deepcopy(config))
        self.composer.document = dict(self.composer.document, schema_version=7, visual_performance=copy.deepcopy(config))
        self.composer.compiled = self.sequence
        if not changed_surface:
            self.performance_base_cache = (self.sequence, prepared, self.settings_generation)
        else:
            self.performance_base_cache = None
        self.update_composition_history(); self.update_document_title()
        if not self.performance_timer.isActive(): self.performance_timer.start()

    def flush_performance(self):
        if self.closing: return
        if self.performance_needs_render:
            self.performance_needs_render = False
            self.invalidate(preserve_transport=True)
            return
        # We own these edits: only performance metadata changed. Avoid copying
        # and hashing all source states on every live knob sample.
        self.preview_performance_config = copy.deepcopy(self.sequence.get('visual_performance'))
        self.refresh_performance_panels()
        if self.wants_live_sound():
            self.audition_visual_sound(self.live_draft)
        else:
            self.refresh_visual_sound()
        self.request_frame()

    def performance_base_sequence(self):
        sequence = self.preview_sequence()
        cache = self.performance_base_cache
        if cache is None or cache[0] is not sequence or cache[2] != self.settings_generation:
            cache = (sequence, base_document(sequence), self.settings_generation); self.performance_base_cache = cache
        return cache[1]

    def performance_source_time(self, seconds):
        sequence = self.preview_sequence()
        if not sequence or self.preview_bypass(): return seconds
        return source_time(sequence.get('visual_performance'), seconds, sequence['duration'], sequence['fps'])

    def perform_packet(self, packet, seconds):
        sequence = self.preview_sequence()
        config = (sequence or {}).get('visual_performance')
        if not config or self.preview_bypass(): return packet
        size, raw = packet
        image = Image.frombytes('RGB', size, raw)
        result = apply_frame(image, config, seconds, sequence['duration'], sequence.get('seed', 0))
        return packet if result is image else (result.size, result.tobytes())
