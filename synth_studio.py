#!/usr/bin/env python3
"""Native source-free Nebula Synth editor."""
from __future__ import annotations

import copy
import json
import random
import os
import tempfile
import sys
import time
from collections import deque
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QEvent, QObject, QRunnable, QSettings, QSignalBlocker, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QGroupBox,
    QHBoxLayout, QGridLayout, QLabel, QMainWindow, QPushButton, QScrollArea,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QMessageBox, QSizePolicy, QFrame, QInputDialog,
    QProgressBar, QMenu, QToolButton, QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox, QAbstractSlider, QAbstractButton, QStackedWidget, QComboBox as NativeComboBox,
)
from studio_widgets import ComboBox as QComboBox, DoubleSpinBox as QDoubleSpinBox, SpinBox as QSpinBox, Slider as QSlider
from studio_widgets import configure_parameter_spin, PlaybackButton
from synth_workspace_widgets import FlowLayout, ElidingLabel, WorkspaceSplitter, inline

from media import Cancellation
from studio_theme import COLORS, apply_theme, terminal_font, ui_font
from synth import MODULE_BY_ID, curated_presets, default_synth_preset, load_synth, normalize_synth, render_synth_frame, save_synth
from synth_media import export_synth_video
from synth_sequence import load_sequence, normalize_sequence, reference_sequence, render_sequence_frame, save_sequence
from synth_composition import FORMAT, compile_composition, composition_from_sequence, load_composition, normalize_composition, reference_composition, save_composition, section_ranges
from synth_composer_ui import CompositionPanel, SectionTimeline, CachedRangeStrip
from synth_canvas import CANVAS_FORMATS, format_canvas, normalize_canvas, preview_size, resize_canvas
from synth_studies import study_records, study_composition, save_study
from synth_studies_ui import StudiesDialog
from synth_new_piece_ui import NewPieceDialog
from synth_add_section_ui import AddVideoSectionDialog
from synth_starting_points import new_piece
from synth_artwork_ui import ArtworkControl
from synth_text_ui import TextControl
from synth_text import validate_text
from synth_master import normalize_master
from synth_master_ui import MasterPanel
from synth_viewer import SynthViewer
from synth_video import VideoFrameProvider, inspect_video, prepare_proxy, video_composition, relink_footage, check_source
from synth_preview import PreviewScheduler, resolve_scope, RenderValidity, preview_context, retained_frame_predicate
from synth_comparison_preview import ComparisonFrames
from synth_exploration_studio import ExplorationStudio


class SynthControl(QWidget):
    changed = Signal()

    def __init__(self, spec, value):
        super().__init__()
        self.spec = spec
        self.lock = QCheckBox("lock")
        self.lock.setToolTip("Keep this parameter fixed when Generate variation is pressed.")
        if spec.kind in ('artwork', 'text'):
            self.spin = ArtworkControl() if spec.kind == 'artwork' else TextControl(); self.spin.setValue(value)
            self.spin.changed.connect(lambda _value: self.changed.emit())
            layout = QVBoxLayout(self); layout.addWidget(QLabel(spec.label)); layout.addWidget(self.spin)
            self.lock.setChecked(True); self.lock.hide()
            return
        if spec.choices:
            self.spin = QComboBox(); self.spin.addItems(spec.choices); self.spin.setCurrentIndex(int(value))
            self.spin.currentIndexChanged.connect(lambda _value: self.changed.emit())
            layout = QVBoxLayout(self); layout.setContentsMargins(0, 3, 0, 4)
            label = QLabel(spec.label); label.setToolTip(spec.hint); layout.addWidget(label)
            row = QHBoxLayout(); row.addWidget(self.spin, 1); row.addWidget(self.lock); layout.addLayout(row)
            return
        self.spin = QSpinBox() if spec.kind == "int" else QDoubleSpinBox()
        configure_parameter_spin(self.spin, spec)
        if spec.key in {'unfold_seconds', 'unfolded_seconds', 'fold_seconds', 'folded_seconds'}:
            self.spin.setSpecialValueText('Recipe')
        self.spin.setSingleStep(spec.step)
        self.spin.setKeyboardTracking(False)
        self.spin.setValue(value)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setTracking(False)
        scale = 1 if spec.kind == "int" else 1 / spec.step
        self.slider.setRange(round(spec.minimum * scale), round(spec.maximum * scale))
        self.slider.setValue(round(float(value) * scale))
        self.slider.valueChanged.connect(lambda v: self.spin.setValue(v / scale))
        def sync_value(value):
            with QSignalBlocker(self.slider): self.slider.setValue(round(float(value) * scale))
            self.changed.emit()
        self.spin.valueChanged.connect(sync_value)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 4)
        label = QLabel(spec.label)
        label.setToolTip(spec.hint)
        layout.addWidget(label)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.slider, 1)
        self.spin.setFixedWidth(105)
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
    frame = Signal(object)


class ImportVideoJob(QRunnable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.cancel = Cancellation()
        self.signals = JobSignals()

    def run(self):
        try:
            self.cancel.check()
            footage = inspect_video(self.path)
            prepare_proxy(footage, self.cancel)
            self.cancel.check()
            self.signals.done.emit(footage)
        except Exception as exc:
            self.signals.failed.emit(str(exc) or 'Import cancelled')


class SaveStudyJob(QRunnable):
    def __init__(self, project, name):
        super().__init__()
        self.project, self.name = copy.deepcopy(project), name
        self.cancel = Cancellation()
        self.signals = JobSignals()

    def run(self):
        try:
            self.signals.done.emit(save_study(self.project, self.name, cancel=self.cancel))
        except Exception as exc:
            self.signals.failed.emit(str(exc) or 'Saving study cancelled')


class RenderJob(QRunnable):
    def __init__(self, preset, time_seconds, size, settings_generation, request_serial, sequence=None, frame_provider=None, bypass=False):
        super().__init__()
        self.preset, self.time_seconds, self.size = copy.deepcopy(preset), time_seconds, size
        self.settings_generation, self.request_serial = settings_generation, request_serial
        self.sequence = copy.deepcopy(sequence)
        self.signals = JobSignals()
        self.frame_provider, self.bypass = frame_provider, bypass

    def run(self):
        try:
            began = time.monotonic()
            if self.sequence is not None:
                image = render_sequence_frame(self.sequence, self.time_seconds, self.size, self.frame_provider, self.bypass)
            else:
                treatment_frame = round(self.time_seconds * self.preset["treatment_fps"])
                image = render_synth_frame(self.preset, treatment_frame, self.time_seconds, self.size)
            self.signals.done.emit((self.settings_generation, self.request_serial, self.time_seconds, image.size, image.tobytes(), time.monotonic()-began))
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            if self.frame_provider and self.frame_provider.cancel.event.is_set():
                self.frame_provider.close()


class PreparePreviewJob(QRunnable):
    def __init__(self, preset, sequence, size, frames, fps, generation, bypass):
        super().__init__()
        self.preset, self.sequence = copy.deepcopy(preset), copy.deepcopy(sequence)
        self.size, self.frames, self.fps = size, frames, fps
        self.generation, self.bypass = generation, bypass
        self.cancel = Cancellation(); self.signals = JobSignals()

    def run(self):
        try:
            packets = []
            with VideoFrameProvider(preview=True, cancel=self.cancel) as provider:
                for done, frame in enumerate(self.frames, 1):
                    self.cancel.check(); seconds = frame / self.fps
                    if self.sequence is not None:
                        image = render_sequence_frame(self.sequence, seconds, self.size, provider, self.bypass)
                    else:
                        image = render_synth_frame(self.preset, round(seconds*self.preset['treatment_fps']), seconds, self.size)
                    self.cancel.check()
                    packets.append((frame, (image.size, image.tobytes())))
            self.cancel.check()
            self.signals.done.emit((self.generation, packets))
        except Exception as exc:
            self.signals.failed.emit(str(exc) or 'Preview preparation cancelled')


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


class SynthStudio(ExplorationStudio, QMainWindow):
    def __init__(self, preset=None, sequence=None, composition=None, settings=None):
        super().__init__()
        self.workspace_settings = settings
        self.export_settings = settings
        self.last_export_directory = ''
        self.comparison = None
        self.discovery_session = None
        self.setWindowTitle("Nebula Synth")
        self.setFont(ui_font())
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
        self.document_identity = object()
        self.document_path = None
        self.detailed_copy = False
        self.clean_revision = 0
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
        self.preview_frames = ComparisonFrames()
        self.preview_validity = None
        self.prepare_job = None
        self.warming_job = None
        self.preview_scheduler = PreviewScheduler()
        self.preparation_target = ()
        self.preparation_explicit = False
        self.preparation_limited = False
        self.warm_debounce = QTimer(self); self.warm_debounce.setSingleShot(True)
        self.warm_debounce.timeout.connect(self._automatic_preparation)
        self.preview_debounce = QTimer(self); self.preview_debounce.setSingleShot(True)
        self.preview_debounce.timeout.connect(self.request_frame)
        self.display_times = deque(maxlen=60)
        self.play_origin = 0.; self.play_started = 0.; self.advancing = False
        self.last_render_seconds = 0.
        self.export_job = None
        self.import_job = None
        self.study_job = None
        self.studies_dialog = None
        self.study_browser_priority_timer = QTimer(self)
        self.study_browser_priority_timer.setInterval(100)
        self.study_browser_priority_timer.timeout.connect(self.update_study_browser_priority)
        self.video_frames = VideoFrameProvider(preview=True)
        self.controls = {}
        self.module_groups = []
        self.play_timer = QTimer(self)
        self.play_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.play_timer.timeout.connect(self.advance)
        self.build_ui()
        self.build_actions()
        QApplication.instance().installEventFilter(self)
        self.rebuild_modules()
        self.update_timeline_max()
        self.mark_document_clean()
        self.request_frame()

    def build_actions(self):
        file_menu = self.menuBar().addMenu('File')
        edit_menu = self.menuBar().addMenu('Edit')
        transport_menu = self.menuBar().addMenu('Preview')
        def action(menu, label, shortcut, callback):
            item = QAction(label, self)
            item.setShortcut(shortcut)
            item.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            item.triggered.connect(callback)
            menu.addAction(item)
            item.setToolTip(f'{label} ({item.shortcut().toString(QKeySequence.SequenceFormat.NativeText)})')
            return item
        self.new_piece_action = action(file_menu, 'New piece…', QKeySequence.StandardKey.New, self.new_piece_dialog)
        self.save_action = action(file_menu, 'Save', QKeySequence.StandardKey.Save, self.save_sequence_dialog)
        self.save_as_action = action(file_menu, 'Save As…', QKeySequence.StandardKey.SaveAs, self.save_as_dialog)
        self.open_action = action(file_menu, 'Open…', QKeySequence.StandardKey.Open, self.load_sequence_dialog)
        self.undo_action = action(edit_menu, 'Undo composition', QKeySequence.StandardKey.Undo, self.undo_composition)
        self.redo_action = action(edit_menu, 'Redo composition', QKeySequence.StandardKey.Redo, self.redo_composition)
        action(transport_menu, 'Play / pause', QKeySequence('Space'), lambda: self.play.setChecked(not self.play.isChecked()))
        for label, key, delta in (('Previous frame', 'Left', -1), ('Next frame', 'Right', 1),
                                  ('Back ten frames', 'Shift+Left', -10), ('Forward ten frames', 'Shift+Right', 10)):
            action(transport_menu, label, QKeySequence(key), lambda _checked=False, d=delta: self.step_frame(d))
        self.composition_undo_button.setToolTip(self.undo_action.toolTip())
        self.composition_redo_button.setToolTip(self.redo_action.toolTip())
        self.viewer.setToolTip(self.viewer.toolTip() + ' Space: play/pause. Arrows: step frames; Shift: ten frames.')
        self.timeline.setToolTip('Scrub preview. Space: play/pause. Arrows: one frame; Shift + arrows: ten frames.')

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ShortcutOverride and isinstance(watched, QWidget) and watched.window() is self:
            focus = self.focusWidget()
            transport = event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Left, Qt.Key.Key_Right)
            undo = event.matches(QKeySequence.StandardKey.Undo) or event.matches(QKeySequence.StandardKey.Redo)
            local_editor = False
            widget = focus
            while widget and widget is not self:
                if isinstance(widget, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox, NativeComboBox, QAbstractSlider)):
                    if widget is not self.timeline: local_editor = True
                if transport and isinstance(widget, QAbstractButton): local_editor = True
                widget = widget.parentWidget()
            if (transport or undo) and (local_editor or QApplication.activePopupWidget() or QApplication.activeModalWidget()):
                event.accept(); return True
        return super().eventFilter(watched, event)

    def step_frame(self, delta):
        self.play.setChecked(False)
        scope = self.active_preview_scope()
        self.timeline.setValue(scope.step(self.timeline.value(), delta))

    def document_state(self):
        if self.composition is not None:
            return 'composition', self.composition
        if self.sequence is not None:
            return 'sequence', self.sequence
        return 'preset', self.collect()

    def mark_document_clean(self):
        self.clean_document = copy.deepcopy(self.document_state())
        self.clean_revision += 1
        self.update_document_title()

    def update_document_title(self):
        if not hasattr(self, "clean_document"): return
        name = self.document_state()[1].get("name", "Untitled")
        title = f"{name}{' *' if self.has_unsaved_changes() else ''}"
        if self.detailed_copy: title += " · detailed copy"
        self.setWindowTitle(f"Nebula · {title}")
        self.document_title.setText(('* ' if self.has_unsaved_changes() else '') + self.document_title.fontMetrics().elidedText(name + (' · detailed copy' if self.detailed_copy else ''), Qt.TextElideMode.ElideRight, 200))
        self.document_title.setToolTip(title)
        self.document_title.setAccessibleDescription(title)

    def pending_text_edits(self):
        if self.composer is not None:
            return self.composer.pending_text_edits()
        controls = [control.spin for control in (self.sequence_state_controls if self.sequence is not None else self.controls).values()]
        return [(control, control.editor.toPlainText()) for control in controls
                if isinstance(control, TextControl) and control.editor.toPlainText() != control.value()]

    def has_unsaved_changes(self):
        return self.audition_pending() or bool(self.pending_text_edits()) or self.document_state() != self.clean_document

    def finish_focused_edit(self):
        focus = self.focusWidget()
        if focus is not None:
            focus.clearFocus()

    def prepare_document_save(self):
        if self.discovery_session: self.dismiss_effect_discovery()
        try:
            if self.composer is not None:
                return self.composer.prepare_text_save()
            drafts = self.pending_text_edits()
            for _control, value in drafts:
                validate_text(value)
            for control, value in drafts:
                control.editor.setPlainText(value)
                control.commit()
        except ValueError as exc:
            QMessageBox.critical(self, 'Could not save text', str(exc))
            return False
        return True

    def confirm_replacement(self, purpose="replacing this document"):
        return self.confirm_close(purpose)

    def confirm_close(self, purpose="closing"):
        if self.discovery_session: self.dismiss_effect_discovery()
        if self.audition_pending():
            choice = QMessageBox.question(self, 'Temporary variation', f'Keep this audition before {purpose}?',
                QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Cancel: return False
            if choice == QMessageBox.StandardButton.Apply: self.keep_audition()
            else: self.end_comparison()
        self.finish_focused_edit()
        if not self.has_unsaved_changes():
            return True
        choice = QMessageBox.warning(self, 'Unsaved changes',
            f'Save your changes before {purpose}?\nIf you discard them, your changes will be lost.',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Discard:
            return True
        if choice == QMessageBox.StandardButton.Save:
            return self.save_sequence_dialog()
        return False

    def show_workspace(self):
        settings = self.workspace_settings
        if settings is None:
            self.show(); return
        if settings.contains('window/geometry'):
            self.restoreGeometry(settings.value('window/geometry'))
        mode = settings.value('window/mode', 'fullscreen')
        if mode == 'fullscreen': self.showFullScreen()
        elif mode == 'maximized': self.showMaximized()
        else: self.showNormal()
        if settings.contains('window/splitter'):
            self.splitter.restoreState(settings.value('window/splitter'))
        if settings.contains('window/preview_splitter'):
            self.preview_splitter.restoreState(settings.value('window/preview_splitter'))
        self.viewer.set_zoom(float(settings.value('viewer/zoom', 0.)))

    def save_workspace(self):
        if self.workspace_settings is None: return
        settings = self.workspace_settings
        settings.setValue('window/geometry', self.saveGeometry())
        settings.setValue('window/mode', 'fullscreen' if self.isFullScreen() else 'maximized' if self.isMaximized() else 'normal')
        settings.setValue('window/splitter', self.splitter.saveState())
        settings.setValue('window/preview_splitter', self.preview_splitter.saveState())
        settings.setValue('viewer/zoom', self.viewer.zoom)
        settings.setValue('preview/auto_prepare', self.auto_prepare.isChecked())
        settings.setValue('preview/scope', self.preview_scope.currentIndex())
        settings.setValue('preview/quality', self.quality.currentIndex())
        settings.sync()

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, 'fullscreen_button'):
            label = 'Exit full screen' if self.isFullScreen() else 'Full screen'
            self.fullscreen_button.setAccessibleName(label); self.fullscreen_button.setToolTip(label)
        super().changeEvent(event)

    def build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 8, 12, 10); outer.setSpacing(7)
        self.header_host = QWidget(); self.header_host.setProperty('chrome', True)
        self.header_host.setObjectName('workspaceHeader')
        header_layout = QVBoxLayout(self.header_host); header_layout.setContentsMargins(0, 0, 0, 0); header_layout.setSpacing(5)
        header = FlowLayout(right_last=True); header_layout.addLayout(header)
        brand = QLabel("nebula_"); brand.setObjectName("brand")
        self.document_title = QLabel(); self.document_title.setAccessibleName("Document name and unsaved status")
        self.document_title.setMinimumWidth(100); self.document_title.setMaximumWidth(200)
        header.addWidget(inline(brand, self.document_title, spacing=12))
        self.composition_widgets = []; self.preset_widgets = []
        self.new_piece_button = QPushButton('New piece…'); self.new_piece_button.clicked.connect(self.new_piece_dialog)
        self.new_piece_button.setToolTip('Start with Text, Shape, Model, Video, or remix an existing study.')
        self.import_video_button = QPushButton('Import video…'); self.import_video_button.clicked.connect(self.import_video_dialog)
        self.cancel_import = QPushButton('Cancel import'); self.cancel_import.clicked.connect(self.cancel_video_import); self.cancel_import.hide()
        open_button = QPushButton('Open…'); open_button.clicked.connect(self.load_sequence_dialog)
        for button in (self.new_piece_button, self.import_video_button, open_button):
            button.setProperty('secondaryAction', True)
        self.save_button = QToolButton(); self.save_button.setText('Save'); self.save_button.setAccessibleName('Save composition')
        self.save_button.setMinimumWidth(68)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.save_button.clicked.connect(self.save_sequence_dialog)
        save_menu = QMenu(self.save_button)
        save_menu.addAction('Save As…', self.save_as_dialog)
        self.save_study_button = save_menu.addAction('Save as study…', self.save_study_dialog)
        self.save_study_button.setToolTip('Keep an independent copy in Studies, including a local copy of imported video.')
        self.save_button.setMenu(save_menu)
        header.addWidget(inline(self.new_piece_button, self.import_video_button, self.cancel_import, open_button, self.save_button))
        commands = QWidget(); command_row = QHBoxLayout(commands); command_row.setContentsMargins(0, 0, 0, 0); command_row.setSpacing(5)
        for text, callback in (("New variation", self.generate_variation), ("Undo", self.undo_composition), ("Redo", self.redo_composition)):
            button = QPushButton(text); button.clicked.connect(callback)
            button.setProperty('secondaryAction', True)
            if text == 'New variation': button.setToolTip('Generate another take of this composition using its unlocked controls.')
            if text == 'Undo': self.composition_undo_button = button
            if text == 'Redo': self.composition_redo_button = button
            command_row.addWidget(button); self.composition_widgets.append(button)
        self.export_button = QPushButton('Export MP4'); self.export_button.setObjectName('primary')
        self.export_button.clicked.connect(self.export_dialog); command_row.addWidget(self.export_button)
        header.addWidget(commands)
        # This action is attached to the current inspector when it is built.
        self.reset_controls_button = QPushButton('Restore effect', root)
        self.reset_controls_button.setProperty('compact', True); self.reset_controls_button.setProperty('secondaryAction', True)
        self.reset_controls_button.clicked.connect(lambda: self.composer and self.composer.reset_controls())
        self.reset_controls_button.hide()
        settings_row = FlowLayout(right_last=True); header_layout.addLayout(settings_row)
        self.starter_combo = QComboBox(); self.starter_combo.setAccessibleName('Studies')
        self.starter_combo.setPlaceholderText('Choose a study…')
        self.starter_combo.setToolTip('Choose a study, then Load to open an editable copy with its saved canvas.')
        self.starter_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.starter_combo.setMinimumContentsLength(20); self.starter_combo.setMinimumWidth(180); self.starter_combo.setMaximumWidth(250)
        self.load_starter_button = QPushButton('Load'); self.load_starter_button.setAccessibleName('Load study')
        self.load_starter_button.clicked.connect(self.load_starter); self.load_starter_button.setEnabled(False)
        self.starter_combo.currentIndexChanged.connect(lambda index: self.load_starter_button.setEnabled(index >= 0))
        self.manage_studies_button = QPushButton('Browse…'); self.manage_studies_button.setAccessibleName('Browse studies')
        self.manage_studies_button.setToolTip('Browse previews, search, favorite, remove or restore Studies.')
        self.manage_studies_button.clicked.connect(self.manage_studies)
        settings_row.addWidget(inline(QLabel('Studies'), self.starter_combo, self.load_starter_button, self.manage_studies_button))
        self.refresh_studies()
        self.canvas_combo = QComboBox(); self.canvas_combo.setAccessibleName('Canvas aspect ratio')
        for identifier, label, _width, _height in CANVAS_FORMATS: self.canvas_combo.addItem(label, identifier)
        self.canvas_combo.currentIndexChanged.connect(self.canvas_selected)
        self.canvas_combo.setToolTip('Canvas dimensions. Reframe without stretching the subject or rewriting its effects.')
        self.canvas_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.canvas_combo.setMinimumContentsLength(18); self.canvas_combo.setFixedWidth(238)
        self.fit_subject = QCheckBox('Fit subject'); self.fit_subject.setAccessibleName('Fit subject')
        self.fit_subject.setToolTip('Uniformly fit the artwork reference. Off keeps its pixel size and centers/crops it. Never stretches proportions.')
        self.fit_subject.toggled.connect(self.framing_changed)
        self.canvas_label = QLabel(); self.canvas_label.setObjectName('monitorMeta')
        settings_row.addWidget(inline(QLabel('Canvas'), self.canvas_combo, self.fit_subject, self.canvas_label))
        self.workspace_fps_host = QWidget(); self.workspace_fps_host.setProperty('chrome', True)
        self.workspace_fps_layout = QHBoxLayout(self.workspace_fps_host); self.workspace_fps_layout.setContentsMargins(0, 0, 0, 0); self.workspace_fps_layout.setSpacing(5)
        settings_row.addWidget(self.workspace_fps_host)
        legacy = QWidget(); legacy_row = FlowLayout(legacy)
        preset_label = QLabel('Preset'); legacy_row.addWidget(preset_label)
        self.preset_combo = QComboBox(); self.preset_combo.addItems([*curated_presets().keys(), 'Custom'])
        preset_name = self.preset.get('name', 'Custom')
        self.preset_combo.setCurrentText(preset_name if preset_name in curated_presets() else 'Custom')
        self.preset_combo.currentTextChanged.connect(self.select_curated); legacy_row.addWidget(self.preset_combo)
        for text, slot in (('Save preset', self.save_preset_dialog), ('Load preset', self.load_preset_dialog), ('Generate variation', self.generate_variation)):
            button = QPushButton(text); button.clicked.connect(slot); legacy_row.addWidget(button)
        self.preset_widgets.append(legacy); header_layout.addWidget(legacy)
        outer.addWidget(self.header_host)
        self.splitter = split = WorkspaceSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(9); split.setChildrenCollapsible(False)
        left = QWidget(); left_column = QVBoxLayout(left)
        left_column.setContentsMargins(0, 0, 5, 0); left_column.setSpacing(0)
        self.preview_splitter = WorkspaceSplitter(Qt.Orientation.Vertical)
        self.preview_splitter.setAccessibleName('Monitor and timeline layout')
        self.preview_splitter.setHandleWidth(9); self.preview_splitter.setChildrenCollapsible(False)
        left_column.addWidget(self.preview_splitter)
        monitor_pane = QWidget(); left_layout = QVBoxLayout(monitor_pane)
        left_layout.setContentsMargins(0, 0, 0, 0); left_layout.setSpacing(4)
        self.preview_splitter.addWidget(monitor_pane)
        self.preview_controls_scroll = QScrollArea()
        self.preview_controls_scroll.setAccessibleName('Timeline and preview controls')
        self.preview_controls_scroll.setWidgetResizable(True)
        self.preview_controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.preview_controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_controls_scroll.setMinimumHeight(112)
        controls_pane = QWidget(); controls_layout = QVBoxLayout(controls_pane)
        controls_layout.setContentsMargins(0, 5, 4, 0); controls_layout.setSpacing(4)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview_controls_scroll.setWidget(controls_pane)
        self.preview_splitter.addWidget(self.preview_controls_scroll)
        monitor = QFrame(); monitor.setObjectName("monitorFrame")
        monitor_layout = QVBoxLayout(monitor); monitor_layout.setContentsMargins(1, 1, 1, 1); monitor_layout.setSpacing(0)
        monitor_header = QWidget(); monitor_header.setObjectName('monitorHeader'); monitor_header.setProperty('chrome', True)
        monitor_flow = FlowLayout(monitor_header, spacing=4)
        title_group = QWidget(); monitor_row = QHBoxLayout(title_group); monitor_row.setContentsMargins(6, 2, 3, 2); monitor_row.setSpacing(5)
        monitor_title = QLabel('MONITOR'); monitor_title.setObjectName('sectionTitle'); monitor_row.addWidget(monitor_title)
        monitor_flow.addWidget(title_group)
        self.monitor_meta = QLabel(root); self.monitor_meta.hide()
        self.monitor_state = QLabel(root); self.monitor_state.hide()
        minus = QPushButton('−'); minus.setAccessibleName('Zoom out'); minus.setFixedWidth(24); minus.clicked.connect(lambda: self.viewer.zoom_by(.8))
        self.view_zoom = QDoubleSpinBox(); self.view_zoom.setRange(0, 800); self.view_zoom.setDecimals(1); self.view_zoom.setSpecialValueText('Fit'); self.view_zoom.setSuffix(' %'); self.view_zoom.setKeyboardTracking(False); self.view_zoom.setFixedWidth(78)
        self.view_zoom.setAccessibleName('Viewer zoom'); self.view_zoom.setToolTip('Viewer zoom only. Fit follows the available monitor size; numeric zoom stays fixed.')
        self.view_zoom.valueChanged.connect(lambda value: self.viewer.set_zoom(value / 100))
        plus = QPushButton('+'); plus.setAccessibleName('Zoom in'); plus.setFixedWidth(24); plus.clicked.connect(lambda: self.viewer.zoom_by(1.25))
        self.fit_view_button = fit = QPushButton('Fit'); fit.setCheckable(True); fit.setAccessibleName('Fit canvas in viewer'); fit.clicked.connect(lambda: self.viewer.set_zoom(0))
        actual = QPushButton('100%'); actual.setAccessibleName('View at 100 percent'); actual.clicked.connect(lambda: self.viewer.set_zoom(1))
        for button in (minus, plus, fit, actual): button.setProperty('secondaryAction', True)
        monitor_flow.addWidget(inline(minus, self.view_zoom, plus, fit, actual, spacing=2))
        self.source_preview = QCheckBox('Before / source'); self.source_preview.setAccessibleName('Before / source')
        self.source_preview.setToolTip('Compare this footage frame before treatments. Export includes treatments.')
        self.source_preview.toggled.connect(lambda _checked: self.invalidate()); monitor_flow.addWidget(self.source_preview)
        self.build_exploration_controls(monitor_flow, monitor_row)
        fullscreen = QPushButton('⛶'); fullscreen.setFixedWidth(28); fullscreen.setAccessibleName('Full screen'); fullscreen.setToolTip('Full screen')
        fullscreen.setProperty('secondaryAction', True)
        fullscreen.clicked.connect(self.toggle_fullscreen); monitor_flow.addWidget(fullscreen); self.fullscreen_button = fullscreen
        monitor_layout.addWidget(monitor_header)
        self.viewer = SynthViewer(); monitor_layout.addWidget(self.viewer, 1)
        left_layout.addWidget(monitor, 1)
        self.viewer.zoomChanged.connect(self.refresh_view_zoom)
        self.fit_view_button.setChecked(self.viewer.zoom == 0)
        self.section_timeline = SectionTimeline()
        self.section_timeline.selected.connect(lambda index: self.composer and self.composer.select_section(index, preserve_scope=True))
        self.section_timeline.editRequested.connect(lambda index: self.composer and self.composer.select_section(index))
        self.section_timeline.selectionChanged.connect(self.preview_scope_changed)
        self.section_timeline.durationRequested.connect(lambda identifier, duration: self.composer and self.composer.stretch_section(identifier, duration))
        self.section_timeline.stretchRequested.connect(lambda identifiers, factor: self.composer and self.composer.stretch_sections(identifiers, factor))
        self.section_timeline.reorderRequested.connect(lambda identifiers, before: self.composer and self.composer.reorder_sections(identifiers, before))
        self.section_timeline.duplicateRequested.connect(self.duplicate_timeline_sections)
        self.section_timeline.loopRequested.connect(lambda identifiers, count: self.composer and self.composer.loop_sections(identifiers, count))
        self.section_timeline.automationRequested.connect(self.timeline_automation)
        self.section_timeline.automationMoveRequested.connect(lambda sid, eid, start: self.composer and self.composer.timeline_automation(sid, eid, "move", start))
        self.section_timeline.seekRequested.connect(lambda time: self.composition and self.timeline.setValue(round(time * self.composition['fps'])))
        self.section_scroll = QScrollArea()
        self.section_scroll.setWidgetResizable(True); self.section_scroll.setWidget(self.section_timeline)
        self.section_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.section_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.section_scroll.setFixedHeight(78)
        self.section_timeline.automationVisibilityChanged.connect(lambda visible: self.section_scroll.setFixedHeight(108 if visible else 78))
        controls_layout.addWidget(self.section_scroll)
        self.section_tools = QWidget()
        tools_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        tools_policy.setHeightForWidth(True); self.section_tools.setSizePolicy(tools_policy)
        section_tools = FlowLayout(self.section_tools, spacing=5)
        self.section_hint = QPushButton('Timeline help'); self.section_hint.setProperty('compact', True); self.section_hint.setProperty('secondaryAction', True)
        gesture_help = 'Click to select a clip while keeping the editing scope. Double-click to edit that clip. Drag a clip to reorder. Drag its right edge to resize. Shift-click to select several; drag the last selected edge to scale them together. Select clips or an automation curve, then press Command-D to duplicate. Right-click for duplication and loops. Escape cancels a drag.'
        self.section_hint.setToolTip(gesture_help); self.section_hint.clicked.connect(lambda: QMessageBox.information(self, 'Timeline gestures', gesture_help))
        section_tools.addWidget(self.section_hint)
        self.add_footage_section = QPushButton('+ Add clip…')
        self.add_footage_section.setProperty('compact', True)
        self.add_footage_section.setAccessibleName('Add footage clip')
        self.add_footage_section.setToolTip('Choose new footage and optionally copy another clip’s look. Adds an independent clip after the active clip; Undo removes it.')
        self.add_footage_section.clicked.connect(self.add_footage_section_dialog)
        section_tools.addWidget(self.add_footage_section)
        self.section_resize_mode = QComboBox()
        self.section_resize_mode.addItem('Resize: Keep footage speed', 'effects')
        self.section_resize_mode.addItem('Resize: Stretch footage', 'video')
        self.section_resize_mode.setAccessibleName('Clip resize mode')
        self.section_resize_mode.setToolTip('Keep footage speed reveals more or less of the source, up to Source → Out. At Out, footage holds or loops according to its source settings. Stretch footage changes video speed and retimes its audio to keep the same source interval. Both modes stretch effects and automation. Applies to the next resize; switching modes does not undo earlier speed changes.')
        self.section_resize_mode.setItemData(0, 'Keep video speed while changing clip length. Source → Out limits the available footage; effects and automation stretch to fit.', Qt.ItemDataRole.ToolTipRole)
        self.section_resize_mode.setItemData(1, 'Keep the same source interval by changing video speed. Footage, audio, effects and automation stretch together.', Qt.ItemDataRole.ToolTipRole)
        self.section_resize_mode.currentIndexChanged.connect(lambda _index: self.composer and setattr(self.composer, 'resize_mode', self.section_resize_mode.currentData()))
        section_tools.addWidget(self.section_resize_mode)
        self.timeline_navigation = QWidget()
        self.timeline_navigation_layout = QHBoxLayout(self.timeline_navigation)
        self.timeline_navigation_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_navigation_layout.setSpacing(4)
        section_tools.addWidget(self.timeline_navigation)
        controls_layout.insertWidget(0, self.section_tools)
        self.section_tools.setProperty('chrome', True)
        self.status = ElidingLabel(auto_hide=True); self.status.setObjectName('muted'); self.status.setAccessibleName('Operation status')
        self.transport = transport = QWidget(); transport.setProperty('chrome', True)
        timeline = QHBoxLayout(transport); timeline.setContentsMargins(0, 0, 0, 0); timeline.setSpacing(6)
        self.play = PlaybackButton(); self.play.setFixedSize(30, 28); self.play.toggled.connect(self.toggle_play); timeline.addWidget(self.play)
        track = QWidget(); track.setFixedHeight(22); track_layout = QVBoxLayout(track); track_layout.setContentsMargins(0, 0, 0, 0); track_layout.setSpacing(0)
        self.timeline = QSlider(Qt.Orientation.Horizontal); self.timeline.setObjectName('transportScrubber'); self.timeline.setFixedHeight(19)
        self.timeline.valueChanged.connect(self.scrub); track_layout.addWidget(self.timeline)
        self.cached_ranges = CachedRangeStrip(self.timeline); track_layout.addWidget(self.cached_ranges)
        timeline.addWidget(track, 1)
        self.time_label = QLabel('00:00.00'); self.time_label.setObjectName('timecode'); self.time_label.setFont(terminal_font()); timeline.addWidget(self.time_label)
        self.total_time_label = QLabel(); self.total_time_label.setObjectName('monitorMeta'); self.total_time_label.setAccessibleName('Total duration')
        self.total_time_label.setToolTip('Duration of all clips and loops. Updates automatically when timing changes.')
        timeline.addWidget(self.total_time_label); left_layout.addWidget(transport)
        preview_line = QHBoxLayout(); preview_line.setContentsMargins(0, 0, 0, 3); preview_line.setSpacing(8)
        self.preview_status = ElidingLabel('Preview paused'); self.preview_status.setObjectName('muted'); self.preview_status.setAccessibleName('Preview performance')
        preview_line.addWidget(self.preview_status, 1)
        self.cache_status = QLabel('Preview ready: 0 frames'); self.cache_status.setObjectName('monitorMeta'); self.cache_status.setAccessibleName('Prepared preview frames')
        self.cached_ranges.rangesChanged.connect(self.refresh_cache_status)
        self.cache_status.setToolTip('Highlighted parts of the playback track have prepared frames at this quality. Unprepared frames may play more slowly.')
        preview_line.addWidget(self.cache_status); left_layout.addLayout(preview_line)
        preparation_host = QWidget(); preparation_host.setProperty('chrome', True)
        preparation_row = FlowLayout(preparation_host, spacing=5)
        self.preview_scope = QComboBox(); self.preview_scope.addItems(['Entire timeline', 'Selected clips']); self.preview_scope.setAccessibleName('Playback scope')
        self.preview_scope.setToolTip('Playback selection is separate from editing scope. Repeats play in timeline order.')
        self.preview_scope.currentIndexChanged.connect(self.preview_scope_changed)
        preparation_row.addWidget(inline(QLabel('Playback'), self.preview_scope))
        self.scope_summary = QLabel(); self.scope_summary.setObjectName('monitorMeta'); preparation_row.addWidget(self.scope_summary)
        self.quality = QComboBox(); self.quality.setAccessibleName('Preview quality'); self.quality.addItems(['360 px', '720 px', 'Full canvas'])
        self.quality.setToolTip('Monitor detail only. Export uses full canvas dimensions. Low-res finish can apply the preview texture to exported artwork.')
        self.quality.setMaximumWidth(112)
        self.quality.currentIndexChanged.connect(lambda _index: self.invalidate())
        timeline.addWidget(self.quality)
        self.auto_prepare = QCheckBox('Auto prepare'); self.auto_prepare.setChecked(True)
        self.auto_prepare.setToolTip('Prepare frames near the playhead after editing or scrubbing settles.')
        self.auto_prepare.toggled.connect(self.auto_prepare_changed)
        self.prepare_preview = QPushButton('Prepare'); self.prepare_preview.setAccessibleName('Prepare preview'); self.prepare_preview.setToolTip('Prepare playback of the active scope. Long clips prepare a bounded window. Does not start playback.')
        self.prepare_preview.clicked.connect(self.prepare_playback)
        preparation_row.addWidget(inline(self.auto_prepare, self.prepare_preview))
        if self.workspace_settings:
            self.auto_prepare.setChecked(self.workspace_settings.value('preview/auto_prepare', True, type=bool))
            self.preview_scope.setCurrentIndex(int(self.workspace_settings.value('preview/scope', 0)))
            self.quality.setCurrentIndex(int(self.workspace_settings.value('preview/quality', 0)))
        controls_layout.addWidget(preparation_host)
        controls_layout.addWidget(self.status)
        self.export_progress = QProgressBar(); self.export_progress.setRange(0, 100); self.export_progress.setValue(0)
        self.export_progress.setTextVisible(True); self.export_progress.setFormat('Ready to export')
        self.export_progress.setAccessibleName('Export progress'); self.export_progress.setToolTip('Frames rendered for MP4 export.'); self.export_progress.hide()
        self.cancel_export = QPushButton('Cancel export'); self.cancel_export.setEnabled(False); self.cancel_export.hide(); self.cancel_export.clicked.connect(self.cancel_export_job)
        export_feedback = QHBoxLayout(); export_feedback.addWidget(self.export_progress, 1); export_feedback.addWidget(self.cancel_export)
        controls_layout.addLayout(export_feedback)
        controls_layout.addStretch(1)
        self.preview_controls_scroll.setMinimumWidth(
            controls_pane.minimumSizeHint().width() + self.preview_controls_scroll.verticalScrollBar().sizeHint().width())
        # Keep transport and performance feedback beside the monitor while the
        # expanded timeline/preparation/export controls can scroll independently.
        self.preview_splitter.setStretchFactor(0, 1)
        self.preview_splitter.setStretchFactor(1, 0)
        self.preview_splitter.setSizes([600, 164])
        self.preview_splitter.handle(1).setToolTip('Drag up or down to resize the monitor and timeline controls.')
        split.addWidget(left)
        self.inspector_host = QStackedWidget(); self.inspector_host.setMinimumWidth(380)
        self.inspector_host.setObjectName('inspectorSurface')
        self.inspector_scroll = scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QWidget(); panel.setMinimumWidth(0)
        self.panel_layout = QVBoxLayout(panel); self.panel_layout.setContentsMargins(8, 0, 0, 0)
        self.panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop); scroll.setWidget(panel)
        self.inspector_host.addWidget(scroll)
        self.composer_host = QWidget(); self.composer_host.setMinimumWidth(0)
        self.composer_host.setObjectName('inspectorSurface')
        self.composer_layout = QVBoxLayout(self.composer_host)
        self.composer_layout.setContentsMargins(8, 0, 0, 0)
        self.inspector_host.addWidget(self.composer_host)
        split.addWidget(self.inspector_host); split.setSizes([820, 420]); outer.addWidget(split, 1)
        split.handle(1).setToolTip('Drag to resize the monitor and controls column.')
        self.setCentralWidget(root)

    def update_contextual_reset(self, label):
        self.reset_controls_button.setText(label or 'Restore effect')
        self.reset_controls_button.setAccessibleName(label or 'Restore effect')
        self.reset_controls_button.setEnabled(bool(label) and self.composer is not None)
        self.reset_controls_button.setToolTip(
            'Restore the current panel in the shown editing scope. Other panels keep their settings.'
            if label else 'Select an effect to restore its settings.')
        show_reset = bool(label) and self.composer is not None and self.composer.look_tabs.currentWidget() is not self.composer.effects_panel
        self.reset_controls_button.setVisible(show_reset)
        if self.composer: self.composer.workspace_actions.setVisible(show_reset)
        self.sync_timeline_editing_scope()

    def sync_timeline_editing_scope(self):
        panel = self.composer
        section = None
        if panel and panel.scope and not panel.scope_combo.isHidden():
            section = panel.document['sections'][panel.index]['id']
        self.section_timeline.set_editing_section(section)

    def refresh_view_zoom(self, percent):
        with QSignalBlocker(self.view_zoom): self.view_zoom.setValue(percent)
        with QSignalBlocker(self.fit_view_button): self.fit_view_button.setChecked(self.viewer.zoom == 0)

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
        headers = ["Time", "State", "Transition", "Hold / blend", "Intensity", "Direction"]
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(190)
        table.setMaximumHeight(280)
        for column, (label, minimum) in enumerate(zip(headers, (62, 100, 82, 82, 62, 62))):
            table.setColumnWidth(column, max(minimum, table.fontMetrics().horizontalAdvance(label) + 22))
            table.horizontalHeaderItem(column).setToolTip(label)
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
        for column, (key, label, minimum, maximum, step, integer) in enumerate((("duration", "seconds", min(self.sequence["duration"], 1 / self.sequence["fps"]), 3600, 1 / self.sequence["fps"], False), ("fps", "FPS", 1, 120, 1, True), ("seed", "seed", 0, 2**31 - 1, 1, True))):
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
        self._rebuild_modules()
        self.update_composition_history()
        self.bind_pending_text_titles()

    def bind_pending_text_titles(self, *_args):
        for control in self.findChildren(TextControl):
            if not getattr(control, "_title_connected", False):
                control.editor.textChanged.connect(self.update_document_title)
                control._title_connected = True
        self.update_document_title()

    def _rebuild_modules(self):
        self.refresh_canvas_controls()
        self.save_study_button.setEnabled(self.composition is not None and self.study_job is None)
        # These controls live outside the panel they belong to. Detach the
        # persistent reset action and retire the previous FPS controls first.
        self.reset_controls_button.setParent(self.centralWidget()); self.reset_controls_button.hide()
        while self.workspace_fps_layout.count():
            item = self.workspace_fps_layout.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        while self.timeline_navigation_layout.count():
            item = self.timeline_navigation_layout.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        self.workspace_fps_host.setVisible(self.composition is not None)
        if self.composer is not None:
            self.composition_index = self.composer.index
            self.composition_scope = self.composer.scope
            self.composer_layout.removeWidget(self.composer)
            self.composer.hide(); self.composer.deleteLater()
        self.composer = None
        self.inspector_host.setCurrentWidget(self.inspector_scroll)
        while self.panel_layout.count():
            item = self.panel_layout.takeAt(0); widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        self.controls.clear(); self.module_groups.clear()
        self.sequence_table = None
        self.sequence_state_controls = {}; self.sequence_enabled_controls = {}; self.sequence_field_controls = {}
        for widget in self.preset_widgets:
            widget.setVisible(self.composition is None)
        for widget in self.composition_widgets:
            widget.setVisible(self.composition is not None)
        self.section_timeline.setVisible(self.composition is not None)
        self.section_scroll.setVisible(self.composition is not None)
        self.section_tools.setVisible(self.composition is not None)
        self.section_resize_mode.setVisible(self.composition is not None and 'footage' in self.composition)
        self.add_footage_section.setVisible(self.composition is not None and 'footage' in self.composition)
        self.section_tools.layout().right_last = self.composition is not None and 'footage' in self.composition
        if self.composition is not None:
            self.composer = CompositionPanel(self.composition, self.composition_index, self.composition_scope)
            self.composer.resize_mode = self.section_resize_mode.currentData()
            self.composer.changed.connect(self.composition_changed)
            self.composer.changed.connect(self.bind_pending_text_titles)
            self.composer.playhead_seconds = lambda: self.timeline.value()/self.composition["fps"]
            self.composer.effects_panel.navigation_changed.connect(self.bind_pending_text_titles)
            self.composer.failed.connect(lambda message: self.status.setText(f"Composition edit ignored: {message}"))
            self.composer.sectionSelected.connect(self.composition_section_selected)
            self.composer.detailsRequested.connect(self.open_detailed_copy)
            self.composer.effects_panel.variation_requested.connect(self.open_effect_variation)
            self.composer.effects_panel.discovery_enabled = True
            self.composer.effects_panel.refresh_breakdown()
            self.composer.effects_panel.discovery_requested.connect(self.open_effect_discovery)
            self.composer.effects_panel.navigation_changed.connect(self.refresh_effect_explanations)
            self.composer.effects_panel.finishing_requested.connect(lambda: self.composer.look_tabs.setCurrentIndex(2))
            self.composer.effects_panel.master_requested.connect(lambda: self.composer.look_tabs.setCurrentWidget(self.composer.master_panel))
            self.composer.effects_panel.source_requested.connect(lambda: self.composer.look_tabs.setCurrentWidget(self.composer.video_panel))
            self.composer.relinkRequested.connect(lambda: self.import_video_dialog(relink=True))
            self.composer_layout.addWidget(self.composer)
            self.composer.embed_workspace_controls(self.workspace_fps_layout, self.reset_controls_button, self.timeline_navigation_layout)
            self.inspector_host.setCurrentWidget(self.composer_host)
            self.composer.reset_context_changed.connect(self.update_contextual_reset)
            self.update_contextual_reset(self.composer.reset_label())
            self.section_timeline.set_document(self.composition, self.composer.index)
            self.sync_timeline_editing_scope()
            self.update_composition_history()
            self.status.setText('')
            return
        if self.sequence is not None:
            compose = QPushButton("Use this sequence in composer")
            compose.clicked.connect(lambda: self.set_composition(composition_from_sequence(self.sequence), clean=False))
            self.panel_layout.addWidget(compose)
            self.panel_layout.addWidget(self.sequence_group())
            self.panel_layout.addWidget(self.sequence_settings_group())
            self.sequence_master_panel = MasterPanel()
            self.sequence_master_panel.set_values(self.sequence.get('master'))
            self.sequence_master_panel.edited.connect(self.change_sequence_master)
            self.sequence_master_panel.resetRequested.connect(self.reset_sequence_master)
            self.panel_layout.addWidget(self.sequence_master_panel)
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
        self.load_starter_id("approved")

    def load_refined_sequence(self):
        self.load_starter_id("refined")

    def new_composition(self):
        from synth_composition import blank_composition
        project = blank_composition(); project["canvas"] = self.current_canvas()
        self.set_composition(project)

    def new_piece_dialog(self):
        dialog = NewPieceDialog(self.current_canvas(), self.preview_fps(), study_records(),
                                self.starter_combo.currentData(), self)
        request = dialog.request() if dialog.exec() == dialog.DialogCode.Accepted else None
        dialog.deleteLater()
        if request is not None: self.create_piece(**request)

    def create_piece(self, kind, *, text=None, shape='rectangle', model='silhouette', study=None):
        if kind == 'video':
            self.import_video_dialog(); return
        if kind == 'remix':
            return self.load_starter_id(study) if study is not None else False
        options = dict(shape=shape, model=model)
        if text is not None: options['text'] = text
        try:
            project = new_piece(kind, self.current_canvas(), self.preview_fps(), **options)
        except ValueError as exc:
            self.status.setText(f'Could not create piece: {exc}'); return False
        if not self.set_composition(project, clean=False): return False
        self.timeline.setValue(0)
        self.composer.look_tabs.setCurrentWidget(self.composer.object_panel)
        self.status.setText('Edit your object, then open Effects → Add effect… to build its treatment. Save to keep this piece.')
        return True

    def load_particle_composition(self, refined=True):
        self.load_starter_id("particle-head" if refined else "original-particles")

    def load_particle_orbit(self):
        self.load_starter_id("particle-orbit")

    def load_starter(self):
        if self.starter_combo.currentData() is not None:
            try:
                self.load_starter_id(self.starter_combo.currentData())
            except (OSError, ValueError) as exc:
                self.status.setText(f'Could not load study: {exc}')

    def load_starter_id(self, identifier):
        try: project = study_composition(identifier)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Could not load study: {exc}"); return False
        if not self.set_composition(project): return False
        with QSignalBlocker(self.starter_combo):
            self.starter_combo.setCurrentIndex(self.starter_combo.findData(identifier))
        self.load_starter_button.setEnabled(True)
        if identifier in ("particle-head", "particle-orbit", "original-particles"):
            self.composer.effects_panel.inspect_effect("particles")
        elif identifier == "ink-bloom":
            self.composer.effects_panel.inspect_effect("ink_bloom")
        elif identifier == "mixed-media":
            self.composer.effects_panel.inspect_effect("frame_jitter")

    def refresh_studies(self):
        selected = self.starter_combo.currentData()
        with QSignalBlocker(self.starter_combo):
            self.starter_combo.clear()
            for entry in study_records():
                self.starter_combo.addItem(entry.label, entry.identifier)
                self.starter_combo.setItemData(self.starter_combo.count() - 1,
                                              entry.date_hint, Qt.ItemDataRole.ToolTipRole)
            self.starter_combo.setCurrentIndex(self.starter_combo.findData(selected) if selected else -1)
        self.load_starter_button.setEnabled(self.starter_combo.currentData() is not None)

    def manage_studies(self):
        if self.studies_dialog is None:
            self.studies_dialog = StudiesDialog(self)
            self.studies_dialog.libraryChanged.connect(self.refresh_studies)
            self.studies_dialog.studyRequested.connect(self.load_starter_id)
            self.studies_dialog.finished.connect(self.study_browser_priority_timer.stop)
        else:
            self.studies_dialog.refresh()
        self.update_study_browser_priority()
        self.studies_dialog.show(); self.studies_dialog.raise_(); self.studies_dialog.activateWindow()
        self.study_browser_priority_timer.start()

    def update_study_browser_priority(self):
        if self.studies_dialog is None: return
        busy = bool(self.discovery_session or self.closing or self.export_job or self.render_running or self.render_queued
                    or self.preparation_explicit or self.play.isChecked() or self.preview_debounce.isActive())
        if busy != self.studies_dialog._rendering_paused:
            self.studies_dialog.set_rendering_paused(busy)

    def save_study_dialog(self):
        if self.discovery_session: self.dismiss_effect_discovery()
        if self.audition_pending():
            self.status.setText('Keep or discard the temporary variation before saving a study.'); return
        if self.composition is None or self.study_job is not None: return
        self.finish_focused_edit()
        name, accepted = QInputDialog.getText(self, 'Save as study', 'Study name:', text=self.composition['name'])
        if not accepted: return
        if not name.strip() or len(name.strip()) > 80:
            self.status.setText('Use a study name between 1 and 80 characters.'); return
        if not self.prepare_document_save(): return
        job = SaveStudyJob(self.composition, name.strip())
        job.document_identity = self.document_identity
        job.clean_revision = self.clean_revision
        self.study_job = job; self.pending_jobs.append(job)
        self.save_study_button.setEnabled(False)
        self.status.setText('Saving study and its source video…' if 'footage' in self.composition else 'Saving study…')
        job.signals.done.connect(lambda identifier, j=job: self.study_saved(j, identifier))
        job.signals.failed.connect(lambda error, j=job: self.study_save_failed(j, error))
        self.jobs.start(job)

    def _finish_study_save(self, job):
        if job in self.pending_jobs: self.pending_jobs.remove(job)
        if self.study_job is job: self.study_job = None
        if not self.closing: self.save_study_button.setEnabled(self.composition is not None)

    def study_saved(self, job, identifier):
        self._finish_study_save(job)
        if self.closing: return
        if (getattr(job, 'document_identity', None) is self.document_identity
                and getattr(job, 'clean_revision', None) == self.clean_revision):
            self.clean_document = ('composition', copy.deepcopy(job.project))
            self.clean_revision += 1
        self.update_document_title()
        self.refresh_studies()
        if self.studies_dialog is not None: self.studies_dialog.refresh()
        self.status.setText(f'Saved study: {job.name}. Choose it in Studies to load a fresh copy.')

    def study_save_failed(self, job, error):
        self._finish_study_save(job)
        if not self.closing: self.status.setText(f'Could not save study: {error}')

    def current_canvas(self):
        if self.composition is not None:
            return normalize_canvas(self.composition.get("canvas"))
        if self.sequence is not None and "canvas" in self.sequence:
            return normalize_canvas(self.sequence["canvas"])
        return normalize_canvas(self.preset)

    def refresh_canvas_controls(self):
        canvas = self.current_canvas()
        is_video = self.sequence is not None and 'footage' in self.sequence
        self.fit_subject.setVisible(not is_video)
        self.source_preview.setVisible(is_video)
        if not is_video:
            with QSignalBlocker(self.source_preview): self.source_preview.setChecked(False)
        with QSignalBlocker(self.canvas_combo), QSignalBlocker(self.fit_subject):
            while self.canvas_combo.count() > len(CANVAS_FORMATS):
                self.canvas_combo.removeItem(self.canvas_combo.count() - 1)
            index = next((i for i, (_key, _label, w, h) in enumerate(CANVAS_FORMATS) if (w, h) == (canvas["width"], canvas["height"])), -1)
            if index < 0:
                self.canvas_combo.addItem(f"Custom · {canvas['width']}×{canvas['height']}", "custom")
                index = self.canvas_combo.count() - 1
            self.canvas_combo.setCurrentIndex(index)
            self.fit_subject.setChecked(canvas["framing"] in ('adaptive', 'fit'))
        self.canvas_label.setText(f"Export / {canvas['width']} × {canvas['height']}")
        self.viewer.set_canvas_size((canvas['width'], canvas['height']))
        with QSignalBlocker(self.quality):
            self.quality.setItemText(2, 'Full canvas')

    def canvas_selected(self, index):
        identifier = self.canvas_combo.itemData(index)
        if identifier and identifier != "custom":
            self.apply_canvas(resize_canvas(self.current_canvas(), format_canvas(identifier)))

    def framing_changed(self, checked):
        canvas = self.current_canvas()
        self.apply_canvas(resize_canvas(canvas, canvas, fit=checked))

    def apply_canvas(self, canvas):
        canvas = normalize_canvas(canvas)
        if canvas == self.current_canvas(): return
        if self.composition is not None:
            document = copy.deepcopy(self.composition); document["canvas"] = canvas
            self.composer.document = copy.deepcopy(document)
            self.composition_changed(document, "canvas")
        elif self.sequence is not None:
            self.sequence = normalize_sequence(dict(self.sequence, canvas=canvas))
            self.refresh_canvas_controls(); self.invalidate()
        else:
            self.preset.update(canvas); self.mark_custom()
            self.refresh_canvas_controls(); self.invalidate()

    def set_composition(self, project, *, clean=True, path=None, guard=True):
        project = normalize_composition(project)
        sequence = compile_composition(project)
        if guard and not self.confirm_replacement(): return False
        self.end_comparison()
        self.cancel_video_import()
        self.play.setChecked(False)
        self.document_path = self.associated_document_path(path)
        self.composition = project
        self.sequence = sequence
        self.document_identity = object()
        self.starter_combo.setCurrentIndex(-1)
        self.composition_index = 0; self.composition_scope = 0
        self.section_timeline.set_document(project, 0, reset_selection=True)
        if self.composer:
            self.composer.index = 0; self.composer.scope = 0
        self.undo_compositions.clear(); self.redo_compositions.clear(); self.edit_key = None
        self.preset = normalize_synth(curated_presets()["Reference blinds"])
        with QSignalBlocker(self.preset_combo):
            self.preset_combo.setCurrentText("Reference blinds")
        self.rebuild_modules(); self.update_timeline_max(); self.invalidate()
        if clean: self.mark_document_clean()
        self.update_document_title()
        return True

    def import_video_dialog(self, checked=False, relink=False):
        section_id = self.composer.document['sections'][self.composer.index]['id'] if relink and self.composer and self.composer.scope else None
        title = 'Choose video for selected clip' if section_id else 'Replace shared video' if relink else 'Import video as a new composition'
        path, _ = QFileDialog.getOpenFileName(self, title, '',
            'Video (*.mp4 *.mov *.m4v *.mkv *.avi *.webm);;All files (*)')
        if path: self.start_video_import(path, relink, section_id=section_id)

    def add_footage_section_dialog(self):
        if not self.composer or not self.composition or 'footage' not in self.composition: return
        if len(self.composition['sections']) >= 64:
            self.status.setText('Use at most 64 clips. Remove a clip before adding footage.'); return
        index = self.composer.index
        anchor = self.composition['sections'][index]['id']
        dialog = AddVideoSectionDialog(self.composition, index, self)
        if not dialog.exec(): return
        path, _ = QFileDialog.getOpenFileName(self, 'Choose footage for new clip', '',
            'Video (*.mp4 *.mov *.m4v *.mkv *.avi *.webm);;All files (*)')
        if path:
            self.start_video_import(path, add_section={'after_id': anchor, 'copy_from_id': dialog.look.currentData()})

    def start_video_import(self, path, relink=False, *, section_id=None, add_section=None):
        self.cancel_video_import()
        self.play.setChecked(False)
        job = ImportVideoJob(path)
        job.document_identity = self.document_identity
        job.section_id = section_id
        job.add_section = add_section
        self.import_job = job; self.pending_jobs.append(job)
        self.import_video_button.setEnabled(False); self.cancel_import.show()
        self.status.setText('Preparing video preview… You can keep editing. Original footage is used for export.')
        job.signals.done.connect(lambda footage, j=job: self.video_imported(j, footage, relink))
        job.signals.failed.connect(lambda error, j=job: self.video_import_failed(j, error))
        self.jobs.start(job)

    def cancel_video_import(self):
        if self.import_job:
            self.import_job.cancel.cancel()
            self.import_job = None
        if hasattr(self, 'cancel_import'):
            self.cancel_import.hide(); self.import_video_button.setEnabled(True)

    def _release_import(self, job):
        if job in self.pending_jobs: self.pending_jobs.remove(job)
        current = job is self.import_job
        if current:
            self.import_job = None; self.cancel_import.hide(); self.import_video_button.setEnabled(True)
        return current and not self.closing

    def video_import_failed(self, job, error):
        if self._release_import(job): self.status.setText(f'Video import: {error}')

    def video_imported(self, job, footage, relink):
        if not self._release_import(job): return
        if getattr(job, "document_identity", None) is not self.document_identity: return
        addition = getattr(job, 'add_section', None)
        if addition is not None:
            if not self.composer or not self.composition or 'footage' not in self.composition: return
            identifier = self.composer.add_video_section(footage, **addition)
            if not identifier: return
            self.status.setText('Clip added with independent footage. Undo removes it; other clips kept their settings.')
        elif relink and self.composition and 'footage' in self.composition:
            document = copy.deepcopy(self.composition)
            section_id = getattr(job, 'section_id', None)
            target = document if section_id is None else next((s for s in document['sections'] if s['id'] == section_id), None)
            if target is None:
                self.status.setText('The target clip was removed while loading. No footage was replaced.'); return
            target['footage'] = relink_footage(target.get('footage', document['footage']), footage)
            self.composer.commit(document, 'video-relink')
            self.status.setText('Clip footage replaced. Effects and other clips kept their settings.' if section_id else 'Shared footage replaced. Independent clips kept their videos.')
        else:
            if getattr(job, 'document_identity', None) is not self.document_identity: return
            project = video_composition(footage)
            if not self.set_composition(project, clean=False): return
            self.timeline.setValue(0)
            self.status.setText('Video ready. Save to keep this new composition.')
        self.composer.look_tabs.setCurrentWidget(self.composer.video_panel)

    def composition_changed(self, document, action):
        compiled = self.composer.compiled if self.composer and document is self.composer.document else compile_composition(document)
        if self.edit_key != action or not action.startswith(("macro:", "geometry:", "effect-param:", 'effect-creative:', 'master:', 'video:')):
            self.undo_compositions.append(copy.deepcopy(self.composition))
            self.undo_compositions = self.undo_compositions[-30:]
        self.edit_key = action; self.edit_timer.start(400)
        self.redo_compositions.clear()
        self.composition = copy.deepcopy(document); self.sequence = compiled
        self.composition_index = self.composer.index; self.composition_scope = self.composer.scope
        self.refresh_composition()

    def refresh_composition(self):
        self.refresh_canvas_controls()
        self.reconcile_comparison()
        old_time = self.current_time
        self.update_timeline_max()
        with QSignalBlocker(self.timeline):
            self.timeline.setValue(round(old_time * self.composition["fps"]))
        self.section_timeline.set_document(self.composition, self.composer.index)
        self.sync_timeline_editing_scope()
        self.status.setText('')
        self.update_composition_history(); self.invalidate()
        if self.play.isChecked():
            self.play_timer.start(max(15, round(1000 / self.composition["fps"])))

    def composition_section_selected(self, index):
        self.composition_index = index
        self.section_timeline.set_document(self.composition, index)
        self.sync_timeline_editing_scope()
        if not self.preview_scope.currentIndex():
            self.timeline.setValue(round(section_ranges(self.composition)[index][0] * self.composition["fps"]))

    def duplicate_timeline_sections(self, identifiers):
        if not self.composer: return
        copies = self.composer.duplicate_sections(identifiers)
        if copies:
            self.section_timeline.selected_ids = set(copies)
            self.section_timeline.selection_anchor = copies[0]
            self.section_timeline.update(); self.section_timeline.selectionChanged.emit()

    def timeline_automation(self, section_id, event_id, operation):
        if not self.composer: return
        duplicate = self.composer.timeline_automation(section_id, event_id, operation)
        if duplicate:
            lane = self.section_timeline.automation_lane
            lane.selected = (section_id, duplicate); lane.update()

    def update_composition_history(self):
        if hasattr(self, "undo_action"):
            self.undo_action.setEnabled(self.composition is not None and bool(self.undo_compositions))
            self.redo_action.setEnabled(self.composition is not None and bool(self.redo_compositions))
        if self.composer:
            self.composition_undo_button.setEnabled(bool(self.undo_compositions))
            self.composition_redo_button.setEnabled(bool(self.redo_compositions))

    def _restore_composition_history(self, source, destination):
        if not source: return
        selected_id = self.composer.document['sections'][self.composer.index]['id']
        destination.append(copy.deepcopy(self.composition))
        self.composition = source.pop(); self.sequence = compile_composition(self.composition)
        self.composer.document = copy.deepcopy(self.composition)
        self.composer.index = next((i for i, section in enumerate(self.composition['sections']) if section['id'] == selected_id),
                                   min(self.composer.index, len(self.composition['sections']) - 1))
        self.composer.refresh(); self.edit_key = None; self.refresh_composition()

    def undo_composition(self):
        self._restore_composition_history(self.undo_compositions, self.redo_compositions)

    def redo_composition(self):
        self._restore_composition_history(self.redo_compositions, self.undo_compositions)

    def open_detailed_copy(self):
        window = SynthStudio(preset=self.preset, sequence=copy.deepcopy(self.sequence))
        window.export_settings = self.export_settings
        window.last_export_directory = self.last_export_directory
        window.detailed_copy = True; window.update_document_title()
        self.detail_windows.append(window)
        window.show()

    def change_sequence_master(self, key, value):
        master = normalize_master(self.sequence.get('master')); master[key] = value
        self.sequence['master'] = normalize_master(master)
        self.sequence_master_panel.set_values(master); self.invalidate()

    def reset_sequence_master(self):
        self.sequence['master'] = normalize_master()
        self.sequence_master_panel.set_values(self.sequence['master']); self.invalidate()

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
        if path == 'ink_bloom.artwork' and state['overrides'][path]:
            control = self.sequence_state_controls['ink_bloom.shape']
            with QSignalBlocker(control): control.set_value(5)
            state['overrides']['ink_bloom.shape'] = 5
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
        if key == 'fps': edited['duration'] = max(edited['duration'], 1 / edited['fps'])
        if key in {'fps', 'duration'} and edited.get('time_map'):
            from synth_retime import resize_time_map
            edited['time_map'] = resize_time_map(edited['time_map'], edited['duration'])
        if key in {'fps', 'duration'} and edited.get('video_segments'):
            from synth_retime import resize_time_map
            edited['video_segments'] = resize_time_map(edited['video_segments'], edited['duration'])
        try:
            self.sequence = normalize_sequence(edited)
        except ValueError as exc:
            with QSignalBlocker(self.sequence_field_controls[key]):
                self.sequence_field_controls[key].setValue(self.sequence[key])
            self.status.setText(f"Sequence edit ignored: {exc}")
            return
        if key == 'fps':
            control = self.sequence_field_controls['duration']
            with QSignalBlocker(control):
                control.setMinimum(1 / self.sequence['fps'])
                control.setSingleStep(1 / self.sequence['fps'])
                control.setValue(self.sequence['duration'])
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

    def suggested_output_path(self, suffix):
        document = self.composition or self.sequence or self.preset
        name = "".join(character if character.isalnum() or character in "-_" else "-" for character in document.get("name", "nebula").lower()).strip("-") or "nebula"
        folder = Path.home() / ("Movies" if suffix == ".mp4" else "Documents")
        if suffix == '.mp4':
            remembered = self.export_settings.value('export/directory', '') if self.export_settings is not None else self.last_export_directory
            if remembered and Path(remembered).expanduser().is_dir(): folder = Path(remembered).expanduser()
        return str((folder if folder.is_dir() else Path.home()) / (name[:80] + suffix))

    def protected_document_destination(self, path):
        """Documents may never replace recipe resources, footage or preview proxies."""
        from synth_video import proxy_directory
        from synth_studies import studies_directory
        resolved = Path(path).expanduser().resolve()
        root = Path(__file__).resolve().parent
        directories = (root / 'presets', root / 'assets', proxy_directory(), studies_directory())
        if self.video_frames.directory: directories += (Path(self.video_frames.directory),)
        if any(resolved.is_relative_to(directory.resolve()) for directory in directories): return True
        documents = (self.composition, self.sequence, self.preset, *(item['document'] for item in (self.composition or {}).get('snapshots', [])))
        for document in documents:
            if not document: continue
            from synth_section_sources import footage_references
            for footage in footage_references(document):
                source = Path(footage['path']).expanduser()
                if resolved == source.resolve(): return True
                try:
                    if resolved.exists() and source.exists() and os.path.samefile(resolved, source): return True
                except OSError: pass
        return False

    def associated_document_path(self, path):
        return Path(path) if path and not self.protected_document_destination(path) else None

    def save_sequence_dialog(self, checked=False, *, save_as=False):
        if self.discovery_session: self.dismiss_effect_discovery()
        if self.audition_pending():
            self.status.setText('Keep or discard the temporary variation before saving.'); return False
        self.finish_focused_edit()
        path = str(self.document_path) if self.document_path and not save_as else None
        if path is None:
            kind = self.document_state()[0]
            path, _ = QFileDialog.getSaveFileName(self, f"Save {kind}", self.suggested_output_path('.json'), "Nebula document (*.json)")
        if not path: return False
        if self.protected_document_destination(path):
            QMessageBox.critical(self, 'Save error', 'Choose a document file outside bundled resources, the Study library and source/proxy media.')
            return False
        if not self.prepare_document_save(): return False
        temporary = None
        try:
            target = Path(path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.json', dir=target.parent)
            os.close(fd)
            kind, document = self.document_state()
            writer = {'composition': save_composition, 'sequence': save_sequence, 'preset': save_synth}[kind]
            writer(temporary, document)
            os.replace(temporary, target)
        except Exception as exc:
            QMessageBox.critical(self, 'Save error', str(exc)); return False
        finally:
            if temporary:
                try: Path(temporary).unlink(missing_ok=True)
                except OSError: pass
        self.document_path = target
        self.mark_document_clean()
        return True

    def save_as_dialog(self, checked=False):
        return self.save_sequence_dialog(save_as=True)

    def install_sequence(self, loaded, *, path=None):
        self.end_comparison()
        self.cancel_video_import(); self.play.setChecked(False)
        self.composition = None; self.sequence = loaded
        self.document_identity = object(); self.document_path = self.associated_document_path(path)
        self.undo_compositions.clear(); self.redo_compositions.clear(); self.edit_key = None
        base_name = next(iter(loaded['states'].values()))['preset']
        self.preset = normalize_synth(curated_presets()[base_name])
        with QSignalBlocker(self.preset_combo): self.preset_combo.setCurrentText(base_name)
        self.rebuild_modules(); self.update_timeline_max(); self.invalidate(); self.mark_document_clean()

    def load_sequence_dialog(self, checked=False):
        path, _ = QFileDialog.getOpenFileName(self, "Open composition, sequence or preset", "", "Nebula document (*.json)")
        if not path: return False
        try:
            with open(path) as document: raw = json.load(document)
            if raw.get('format') == FORMAT:
                return self.set_composition(load_composition(path), path=path)
            if 'states' in raw:
                loaded = load_sequence(path)
                if not self.confirm_replacement(): return False
                self.install_sequence(loaded, path=path)
            else:
                loaded = load_synth(path)
                if not self.confirm_replacement(): return False
                self.install_preset(loaded, path=path)
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Document error", str(exc)); return False

    def control_changed(self):
        for (index, key), control in self.controls.items():
            if key == 'artwork' and control is self.sender() and control.value():
                shape = self.controls[(index, 'shape')]
                with QSignalBlocker(shape): shape.set_value(5)
        self.preset = self.collect(); self.mark_custom(); self.invalidate()
    def module_toggled(self, index, checked): self.preset["modules"][index]["enabled"] = checked; self.mark_custom(); self.invalidate()

    def move_module(self, index, delta):
        new = index + delta
        if 0 <= new < len(self.preset["modules"]):
            self.preset = self.collect(); self.preset["modules"][index], self.preset["modules"][new] = self.preset["modules"][new], self.preset["modules"][index]; self.mark_custom(); self.rebuild_modules(); self.invalidate()

    def current_preview_context(self):
        return (*preview_context(self.preview_sequence(), self.preview_size(), self.preview_bypass(), self.video_frames.directory), self.comparison_context())

    def capture_preview_validity(self):
        from synth_exploration import content
        document = self.preview_document()
        return RenderValidity.capture(self.document_identity, content(document) if document else None, self.preview_sequence(),
                                      self.collect() if self.sequence is None else self.preset, self.current_preview_context())

    def ensure_preview_context(self):
        context = self.current_preview_context()
        if self.preview_validity is None:
            self.preview_validity = self.capture_preview_validity()
            self.preview_frames.switch(context)
        elif self.preview_validity.context != context:
            self.invalidate(force_clear=True)
            return False
        return True

    def invalidate(self, *, force_clear=False, comparison_switch=False):
        self.update_document_title()
        current = self.capture_preview_validity()
        retain = None if force_clear else retained_frame_predicate(self.preview_validity, current)
        self.settings_generation += 1  # Worker rejection changes even when pixels can be retained.
        if not comparison_switch:
            if retain is None: self.preview_frames.clear()
            else: self.preview_frames.retain(retain)
        self.preview_frames.switch(current.context)
        self.preview_validity = current
        self.display_times.clear()
        if self.play.isChecked():
            self.play_origin = self.active_preview_scope().position(self.timeline.value()); self.play_started = time.monotonic()
        self.cancel_preparation()
        self.cached_ranges.set_ranges(self.preview_frames.ranges())
        self.prepare_preview.setText('Prepare')
        self.schedule_auto_preparation()
        self.preview_status.setText('Updating preview…')
        self.render_queued = True
        self.preview_debounce.start(100)

    def preview_fps(self):
        return self.sequence['fps'] if self.sequence is not None else self.preset['export_fps']

    def preview_size(self):
        return preview_size(self.current_canvas(), 360 if self.discovery_session else (360, 720, None)[self.quality.currentIndex()])

    def active_preview_scope(self):
        return resolve_scope(self.composition, self.section_timeline.selected_ids, self.timeline.maximum(), bool(self.preview_scope.currentIndex()))

    def refresh_preview_scope(self):
        if not hasattr(self, 'scope_summary'): return
        scope = self.active_preview_scope()
        self.preview_scope.setEnabled(self.composition is not None)
        self.scope_summary.setText(f'{scope.occurrences} occurrences · {scope.count/self.preview_fps():.2f}s' if self.preview_scope.currentIndex() and self.composition else '')
        self.refresh_cache_status()

    def refresh_cache_status(self):
        if not hasattr(self, 'cache_status') or not hasattr(self, 'preview_scope'): return
        scope = self.active_preview_scope()
        count = sum(scope.contains(frame) for frame in self.preview_frames.items)
        self.cache_status.setText(f'Preview ready: {count}/{scope.count}')
        self.cache_status.setToolTip(f'{count} of {scope.count} frames in the playback scope are prepared at this preview quality. The thin green line below the scrubber shows their positions. Gaps may skip during playback; export renders every frame.')

    def preview_scope_changed(self, *_args):
        if not hasattr(self, 'preview_scope') or not hasattr(self, 'quality'): return
        self.play.setChecked(False)
        self.cancel_preparation()
        self.refresh_preview_scope()
        scope = self.active_preview_scope()
        if not scope.contains(self.timeline.value()): self.timeline.setValue(scope.frame_at(0))
        self.schedule_auto_preparation()

    def auto_prepare_changed(self, checked):
        if not checked:
            self.warm_debounce.stop()
            if not self.preparation_explicit: self.cancel_preparation()
        else: self.schedule_auto_preparation()

    def schedule_auto_preparation(self):
        if self.discovery_session or self.closing or not hasattr(self, 'auto_prepare') or not self.auto_prepare.isChecked() or self.export_job: return
        self.warm_debounce.start(400)

    def _automatic_preparation(self):
        if self.closing or self.export_job: return
        if self.preparation_explicit:
            self._start_warm_batch(); return
        if not self.auto_prepare.isChecked(): return
        self.preparation_target, self.preparation_limited = self.preview_scheduler.plan(
            self.active_preview_scope(), self.timeline.value(), self.preview_fps(), self.preview_size(), self.preparation_budget())
        self._start_warm_batch()

    def _obsolete_preparation(self):
        if self.prepare_job:
            self.prepare_job.cancel.cancel(); self.prepare_job = None

    def cancel_preparation(self):
        self._obsolete_preparation()
        self.warm_debounce.stop()
        self.preparation_target = (); self.preparation_explicit = False
        self.prepare_preview.setText('Prepare')

    def prepare_playback(self, checked=False):
        if self.preparation_explicit:
            self.cancel_preparation(); self.preview_status.setText('Ready · preparation cancelled; completed frames remain cached.'); return
        self._obsolete_preparation(); self.warm_debounce.stop()
        self.preparation_explicit = True
        self.preparation_target, self.preparation_limited = self.preview_scheduler.plan(
            self.active_preview_scope(), self.timeline.value(), self.preview_fps(), self.preview_size(), self.preparation_budget(), explicit=True)
        self._start_warm_batch()

    def _preparation_ready(self):
        self.prepare_preview.setText('Prepare')
        self.preparation_explicit = False
        scope = self.active_preview_scope()
        if self.preparation_limited:
            megabytes = self.preparation_budget() / 1024**2
            self.preview_status.setText('Preview partially prepared · lower quality caches more frames')
            self.preview_status.setToolTip(f'Limited by rendering · {len(self.preparation_target)} / {scope.count} frames in the bounded {megabytes:g} MB window. Choose 360 px for more cached frames; export is unaffected.')
        else:
            self.preview_status.setText('Preview prepared · press Play')

    def _start_warm_batch(self):
        if self.closing or self.export_job: return
        if not self.ensure_preview_context(): return
        if not self.preparation_target:
            self._preparation_ready(); return
        if self.warming_job: return
        if self.render_running or self.render_queued or self.preview_debounce.isActive():
            if not self.warm_debounce.isActive(): self.warm_debounce.start(100)
            return
        frames = self.preview_scheduler.batch(self.preparation_target, self.preview_frames)
        if not frames:
            self._preparation_ready(); return
        size = self.preview_size()
        job = PreparePreviewJob(self.preset, self.preview_sequence(), size, frames, self.preview_fps(), self.settings_generation, self.preview_bypass())
        job.reserved_bytes = len(frames)*size[0]*size[1]*3
        self.preview_frames.reserve(job.reserved_bytes, self.preparation_target)
        self.cached_ranges.set_ranges(self.preview_frames.ranges())
        self.prepare_job = self.warming_job = job; self.pending_jobs.append(job)
        self.prepare_preview.setText('Cancel preparation' if self.preparation_explicit else 'Prepare')
        self.preview_status.setText(f'Preparing · {sum(i in self.preview_frames.items for i in self.preparation_target)} / {len(self.preparation_target)} frames')
        job.signals.done.connect(lambda result, j=job: self.preparation_finished(j, result=result))
        job.signals.failed.connect(lambda error, j=job: self.preparation_finished(j, error))
        self.jobs.start(job)

    def prepared_frame(self, job, result):
        generation, frame, packet = result
        if self.closing or job is not self.prepare_job or generation != self.settings_generation: return
        if not self.ensure_preview_context(): return
        self.preview_frames.put(frame, packet)
        self.cached_ranges.set_ranges(self.preview_frames.ranges())
        if frame == self.timeline.value(): self.display_frame(frame/self.preview_fps(), packet, cached=True)

    def preparation_progress(self, job, done, total):
        if job is self.prepare_job and not self.closing:
            self.preview_status.setText(f'Preparing · {done} / {total} frames')

    def preparation_finished(self, job, error=None, *, result=None):
        if job in self.pending_jobs: self.pending_jobs.remove(job)
        self.preview_frames.release(getattr(job, 'reserved_bytes', 0)); job.reserved_bytes = 0
        if self.warming_job is job: self.warming_job = None
        valid = not self.closing and job is self.prepare_job and job.generation == self.settings_generation
        if valid and result is not None:
            generation, packets = result
            for frame, packet in packets: self.prepared_frame(job, (generation, frame, packet))
        if job is self.prepare_job: self.prepare_job = None
        if self.closing: return
        if valid and error:
            if self.discovery_session: self.discovery_session.fail(error)
            self.preparation_explicit = False; self.preparation_target = ()
            self.prepare_preview.setText('Prepare'); self.preview_status.setText(f'Limited by rendering · {error}'); return
        if self.render_queued and not self.render_running and not self.preview_debounce.isActive(): QTimer.singleShot(0, self.request_frame)
        if self.preparation_target: QTimer.singleShot(0, self._start_warm_batch)
        else: self.schedule_auto_preparation()

    def update_timeline_max(self):
        if hasattr(self, "timeline"):
            duration = self.sequence["duration"] if self.sequence is not None else self.preset["loop_seconds"]
            fps = self.sequence["fps"] if self.sequence is not None else self.preset["export_fps"]
            self.timeline.setMaximum(max(1, round(duration * fps)) - 1)
            centiseconds = round(duration * 100)
            self.total_time_label.setText(f'Total {centiseconds // 6000:02d}:{(centiseconds % 6000) / 100:05.2f}')
            self.total_time_label.setAccessibleDescription(f'{duration:.2f} seconds · {round(duration * fps)} frames at {fps} fps')
            self.refresh_preview_scope()
    def request_frame(self):
        if self.closing: return
        if not self.ensure_preview_context(): return
        sequence = self.preview_sequence()
        if sequence and 'footage' in sequence:
            from synth_section_sources import video_source_at
            source, _time = video_source_at(sequence, self.timeline.value()/self.preview_fps())
            try: check_source(source)
            except (ValueError, OSError) as exc:
                self.settings_generation += 1
                self.preview_frames.clear(); self.cached_ranges.set_ranges([]); self.cancel_preparation(); self.render_queued = False
                self.preview_status.setText(f'Preview unavailable: {exc}')
                if self.discovery_session: self.discovery_session.fail(exc)
                return
        self.request_serial += 1
        fps = self.sequence["fps"] if self.sequence is not None else self.preset["export_fps"]
        self.current_time = self.timeline.value() / max(1, fps)
        if self.composition is not None:
            self.section_timeline.set_time(self.current_time)
        if self.preview_debounce.isActive():
            self.render_queued = True; return
        self.preview_frames.anchor(self.timeline.value())
        packet = self.preview_frames.get(self.timeline.value())
        if packet is not None:
            self.render_queued = False
            self.display_frame(self.current_time, packet, cached=True)
            return
        self._obsolete_preparation()
        if self.render_running or (self.discovery_session and self.warming_job):
            self.render_queued = True
            return
        self.render_queued = False
        size = self.preview_size()
        if self.warming_job and self.preview_frames.reserved + size[0]*size[1]*3 > self.preview_frames.budget:
            self.render_queued = True; return
        self.render_running = True
        job = RenderJob(self.preset, self.current_time, size, self.settings_generation, self.request_serial, sequence, self.video_frames, self.preview_bypass())
        job.reserved_bytes = size[0]*size[1]*3 if size[0]*size[1]*3 <= self.preview_frames.budget else 0
        self.preview_frames.reserve(job.reserved_bytes, (self.timeline.value(),))
        self.cached_ranges.set_ranges(self.preview_frames.ranges())
        self.pending_jobs.append(job)
        job.signals.done.connect(lambda result, j=job: self._receive_foreground_frame(j, result))
        job.signals.done.connect(lambda _result, j=job: self._release_job(j))
        job.signals.failed.connect(lambda error, j=job: self.render_failed(error) if j.settings_generation == self.settings_generation and not self.closing else None)
        job.signals.failed.connect(lambda _error, j=job: self._release_job(j))
        self.jobs.start(job)

    def _receive_foreground_frame(self, job, result):
        self.preview_frames.release(getattr(job, 'reserved_bytes', 0)); job.reserved_bytes = 0
        self.frame_ready(result)

    def _release_job(self, job):
        self.preview_frames.release(getattr(job, 'reserved_bytes', 0)); job.reserved_bytes = 0
        if job in self.pending_jobs:
            self.pending_jobs.remove(job)
        self.render_running = False
        if self.render_queued and not self.closing and not self.preview_debounce.isActive():
            self.render_queued = False
            QTimer.singleShot(0, self.request_frame)
        if self.preparation_target: QTimer.singleShot(0, self._start_warm_batch)
        elif not self.warm_debounce.isActive(): self.schedule_auto_preparation()

    def frame_ready(self, result):
        if self.closing or not self.ensure_preview_context(): return
        settings_generation, request_serial, time_seconds, size, raw, elapsed = result
        if settings_generation != self.settings_generation or request_serial < self.last_displayed_request: return
        if self.closing: return
        self.last_displayed_request = request_serial
        self.last_render_seconds = elapsed
        self.preview_frames.put(round(time_seconds*self.preview_fps()), (size, raw))
        self.cached_ranges.set_ranges(self.preview_frames.ranges())
        # A prepared/cached newer frame must not jump backwards to an older job.
        if not self.play.isChecked() and abs(time_seconds-self.current_time) > .5/self.preview_fps(): return
        self.display_frame(time_seconds, (size, raw))

    def display_frame(self, time_seconds, packet, cached=False):
        self.refresh_effect_explanations(time_seconds)
        if self.discovery_session: self.discovery_session.accept_packet()
        if self.comparison:
            self.comparison['pending'] = False; self.refresh_comparison_controls()
        if cached: self.last_displayed_request = max(self.last_displayed_request, self.request_serial)
        size, raw = packet
        self.viewer.set_packet((size, raw)); self.time_label.setText(f"{int(time_seconds) // 60:02d}:{time_seconds % 60:05.2f}")
        self.monitor_meta.setText(f"{size[0]}×{size[1]} / RGB")
        fps = self.preview_fps()
        if self.play.isChecked():
            now = time.monotonic(); self.display_times.append(now)
            while len(self.display_times) > 2 and now-self.display_times[0] > 2.: self.display_times.popleft()
            actual = (len(self.display_times)-1)/max(.001, now-self.display_times[0]) if len(self.display_times)>1 else 0.
            speed = f'{actual:.1f}' if actual else 'measuring'
            note = ' · skipping preview frames' if actual and actual < fps*.9 else ''
            self.preview_status.setText(f'Preview: {speed} / {fps} fps{note}' + (' · cached' if cached else ''))
        elif not self.prepare_job:
            self.preview_status.setText(f'Preview paused · {"cached frame" if cached else f"rendered in {self.last_render_seconds*1000:.0f} ms"}')
        if self.play.isChecked() and not self.warm_debounce.isActive() and not self.preparation_explicit:
            self.schedule_auto_preparation()
    def render_failed(self, message):
        if self.discovery_session: self.discovery_session.fail(message)
        self.status.setText(f"Render error: {message}")
        self.preview_status.setText('Preview unavailable · see the operation status for details.')
    def scrub(self, value):
        if not self.advancing:
            self.cancel_preparation(); self.schedule_auto_preparation()
        if self.play.isChecked() and not self.advancing:
            self.play_origin = self.active_preview_scope().position(value); self.play_started = time.monotonic(); self.display_times.clear()
        self.request_frame()

    def advance(self):
        frame = int(self.play_origin + (time.monotonic()-self.play_started)*self.preview_fps()+1e-8)
        self.advancing = True
        try:
            scope = self.active_preview_scope()
            self.timeline.setValue(scope.frame_at(frame % max(1, scope.count)))
        finally: self.advancing = False
    def toggle_play(self, checked):
        self.monitor_state.setText("[ PLAY ]" if checked else "[ HOLD ]")
        fps = self.sequence["fps"] if self.sequence is not None else self.preset["export_fps"]
        if checked:
            self.cancel_preparation()
            scope = self.active_preview_scope()
            if not scope.contains(self.timeline.value()): self.timeline.setValue(scope.frame_at(0))
            self.play_origin = scope.position(self.timeline.value()); self.play_started = time.monotonic(); self.display_times.clear()
            self.preview_status.setText(f'Preview: measuring / {fps} fps')
            self.play_timer.start(max(5, round(1000 / fps)))
        else:
            self.play_timer.stop(); self.preview_status.setText('Preview paused')
    def install_preset(self, preset, *, path=None):
        self.end_comparison()
        self.cancel_video_import(); self.play.setChecked(False)
        self.sequence = None; self.composition = None; self.preset = preset
        self.document_identity = object(); self.document_path = self.associated_document_path(path)
        self.undo_compositions.clear(); self.redo_compositions.clear(); self.edit_key = None
        self.rebuild_modules(); self.update_timeline_max(); self.invalidate(); self.mark_document_clean()

    def select_curated(self, name):
        if name not in curated_presets(): return
        if not self.confirm_replacement():
            with QSignalBlocker(self.preset_combo): self.preset_combo.setCurrentText(self.preset.get('name', 'Custom'))
            return
        self.install_preset(copy.deepcopy(curated_presets()[name]))
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
                    if control.lock.isChecked() or control.spec.kind in ('artwork', 'text'): continue
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
            if control.lock.isChecked() or control.spec.kind in ('artwork', 'text'): continue
            spec = control.spec
            if spec.kind == "float": control.set_value(round(rng.uniform(spec.minimum, spec.maximum) / spec.step) * spec.step)
            else: control.set_value(rng.randint(int(spec.minimum), int(spec.maximum)))
        self.preset = self.collect(); self.invalidate()
    def save_preset_dialog(self, checked=False):
        return self.save_sequence_dialog()

    def load_preset_dialog(self, checked=False):
        return self.load_sequence_dialog()

    def export_dialog(self):
        if self.discovery_session: self.dismiss_effect_discovery()
        if self.audition_pending():
            self.status.setText('Keep or discard the temporary variation before exporting.'); return
        if self.export_job: return
        default_name = self.suggested_output_path(".mp4")
        path, _ = QFileDialog.getSaveFileName(self, "Export synth sequence" if self.sequence is not None else "Export synth loop", default_name, "MP4 video (*.mp4)")
        if not path: return
        self.cancel_preparation()
        self.export_button.setEnabled(False)
        self.export_progress.setValue(0)
        self.export_progress.setFormat('Exporting… 0%')
        self.export_progress.show(); self.cancel_export.show()
        QTimer.singleShot(0, lambda: self.preview_controls_scroll.ensureWidgetVisible(self.export_progress))
        p = copy.deepcopy(self.preset) if self.sequence is not None else self.collect()
        canvas = self.current_canvas(); size = (canvas["width"], canvas["height"])
        job = ExportJob(p, path, size, self.sequence); self.export_job = job; self.cancel_export.setEnabled(True); self.pending_jobs.append(job)
        job.signals.progress.connect(lambda done, total, j=job: self.export_progressed(j, done, total))
        job.signals.done.connect(lambda result, j=job: self.export_finished(j, result))
        job.signals.done.connect(lambda _result, j=job: self._finish_export(j))
        job.signals.failed.connect(lambda error, j=job: self.export_failed(j, error))
        job.signals.failed.connect(lambda _error, j=job: self._finish_export(j))
        self.jobs.start(job)

    def export_progressed(self, job, done, total):
        if self.export_job is not job or self.closing:
            return
        total = max(1, int(total))
        done = max(0, min(total, int(done)))
        percent = round(done * 100 / total)
        self.export_progress.setValue(percent)
        self.export_progress.setFormat(f'Exporting… {percent}% · frame {done}/{total}')
        self.status.setText(f'Exporting frame {done}/{total} · {percent}%')

    def export_finished(self, job, path):
        if self.export_job is not job or self.closing:
            return
        self.last_export_directory = str(Path(path).expanduser().resolve().parent)
        if self.export_settings is not None:
            self.export_settings.setValue('export/directory', self.last_export_directory)
            self.export_settings.sync()
        self.export_progress.setValue(100)
        self.export_progress.setFormat('Export complete · 100%')
        self.status.setText(f'Exported {path}')

    def export_failed(self, job, error):
        if self.export_job is not job or self.closing:
            return
        cancelled = 'cancel' in str(error).lower()
        self.export_progress.setFormat('Export cancelled' if cancelled else 'Export stopped')
        self.status.setText(f'Export error: {error}')

    def _finish_export(self, job):
        if job in self.pending_jobs:
            self.pending_jobs.remove(job)
        if self.export_job is job:
            self.export_job = None
            self.cancel_export.setEnabled(False); self.cancel_export.hide(); self.export_progress.hide()
            self.export_button.setEnabled(True)
            self.schedule_auto_preparation()

    def cancel_export_job(self):
        if self.export_job:
            self.export_job.cancel.cancel()
            self.export_progress.setFormat('Cancelling export…')
            self.status.setText("Cancelling export…")

    def closeEvent(self, event):
        if not self.closing and not self.confirm_close():
            event.ignore()
            return
        self.save_workspace()
        self.closing = True
        self.study_browser_priority_timer.stop()
        if self.studies_dialog is not None: self.studies_dialog.close()
        QApplication.instance().removeEventFilter(self)
        self.play_timer.stop()
        self.preview_debounce.stop(); self.cancel_preparation()
        self.cancel_video_import()
        if self.study_job: self.study_job.cancel.cancel()
        self.video_frames.cancel.cancel()
        if not self.render_running: self.video_frames.close()
        if self.export_job:
            self.export_job.cancel.cancel()
        self.jobs.waitForDone(1500)
        super().closeEvent(event)


    def refresh_effect_explanations(self, seconds=None):
        if not self.composition or not self.composer or not self.sequence: return
        import time
        now = time.monotonic()
        if self.play.isChecked() and isinstance(seconds, (int, float)) and now-getattr(self, '_explanation_time', 0)<.2: return
        self._explanation_time = now
        from synth_effect_diagnostics import explain_effect
        panel = self.composer.effects_panel
        sid = self.composer.target()['id'] if self.composer.scope else None
        from synth_sequence import resolve_sequence_frame
        seconds = seconds if isinstance(seconds, (int, float)) else self.timeline.value()/self.preview_fps()
        resolved = resolve_sequence_frame(self.sequence, seconds)
        panel.set_explanations(explain_effect(self.composition, self.sequence, panel.effect_id, seconds, sid, resolved))
        if panel.breakdown_host.isVisible():
            panel.update_breakdown_status({key: explain_effect(self.composition, self.sequence, key, seconds, sid, resolved)
                                           for key in panel.breakdown_rows})


def run_synth_app(preset=None):
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    state_dir = os.environ.get('NEBULA_STATE_DIR')
    settings = QSettings(str(Path(state_dir) / 'settings.ini'), QSettings.Format.IniFormat) if state_dir else QSettings('AlanFnz', 'Nebula Studio')
    window = SynthStudio(preset, settings=settings); window.show_workspace()
    return app.exec()



if __name__ == "__main__":
    run_synth_app()
