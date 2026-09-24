#!/usr/bin/env python3
"""Nebula Studio — a native desktop surface for the existing analog pipeline."""
import argparse
import copy
import math
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRect, QSignalBlocker
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox,
    QScrollArea, QGroupBox, QFileDialog, QMessageBox, QSplitter, QProgressBar,
)

from media import Cancellation, Cancelled, probe, frame_count, export_video
from parameters import DEFAULTS, LIMITS, RANGES, STAGES, PRESETS_DIR, normalize, load, save
from preview_jobs import Events, PreviewWorker
from _version import __version__

STYLE = """
QWidget { background: #181b20; color: #e4e5e8; font-size: 12px; }
QMainWindow { background: #181b20; }
QLabel#brand { color: #f1c37c; font-size: 23px; font-weight: 600; }
QLabel#muted { color: #929ba9; }
QPushButton { background: #2b3039; border: 1px solid #424a57; border-radius: 5px; padding: 7px 11px; }
QPushButton:hover { background: #39414c; }
QPushButton:checked { background: #665133; border-color: #f1c37c; }
QPushButton:disabled { color: #66707d; border-color: #303640; }
QPushButton#primary { background: #e1b476; color: #191b20; font-weight: 600; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #232830; border: 1px solid #414956; border-radius: 4px; padding: 5px; }
QGroupBox { border: 1px solid #343c48; border-radius: 6px; margin-top: 16px; padding: 12px 8px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; color: #c4cad3; }
QSlider::groove:horizontal { background: #353d48; height: 4px; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #c5a373; border-radius: 2px; }
QSlider::handle:horizontal { background: #f1c37c; width: 12px; margin: -5px 0; border-radius: 6px; }
QScrollArea { border: none; }
QSplitter::handle { background: #303640; }
QProgressBar { border: 1px solid #414956; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: #6b593f; }
QCheckBox::indicator { width: 14px; height: 14px; }
"""

GROUPS = [
    ("01  Print", "print", ["blur", "texture", "warm"]),
    ("02  Scan", "scan", ["aberration", "bands", "scanlines", "bloom", "curvature", "vignette", "grain", "dust", "dust_opacity", "brightness"]),
    ("03  Motion", "wobble", ["px", "deg"]),
    ("04  Grade", "grade", ["contrast", "shadows", "highlights", "toning"]),
    ("Time & variation", None, ["fps", "drift", "seed"]),
]
LABELS = {"px": "Translation · px", "deg": "Rotation · °", "blur": "Blur · px",
          "aberration": "Channel offset · px", "fps": "Frames per second", "grain": "Grain",
          "dust_opacity": "Dust opacity", "warm": "Warmth", "toning": "Split toning",
          "bands": "Scan bands", "drift": "Temporal drift", "seed": "Random seed"}
HINTS = {
    "blur": "Low / high blur radius at original resolution; varies smoothly with time.",
    "grain": "Low / high grain intensity; varies smoothly with time.",
    "px": "Low / high translation magnitude at original resolution.",
    "deg": "Low / high rotation magnitude; direction varies per frame.",
    "fps": "Treatment and output frame rate. Lower values hold frames longer. Changing this clears A.",
    "drift": "Smooth variation in channel offset, bands, brightness and warmth.",
    "seed": "Change this to choose a new random realization for every effect.",
}


class Viewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(340, 240)
        self.packet = None
        self.compare = False
        self.split = 0.5
        self.setMouseTracking(True)
        self.setToolTip("With A/B enabled, drag across the image to move the comparison divider.")

    def set_packet(self, packet):
        self.packet = packet
        self.update()

    def mousePressEvent(self, event):
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.split = max(0.02, min(0.98, event.position().x() / self.width()))
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101216"))
        if not self.packet:
            painter.setPen(QColor("#929ba9"))
            painter.setFont(QFont("Helvetica", 15))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Open a clip to begin\n\nPrint · Scan · Motion · Grade")
            return
        (w, h), b, a = self.packet
        size = self.size()
        ratio = min(size.width() / w, size.height() / h)
        target = QRect(round((size.width() - w * ratio) / 2), round((size.height() - h * ratio) / 2), round(w * ratio), round(h * ratio))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, QImage(b, w, h, w * 3, QImage.Format.Format_RGB888))
        if self.compare and a:
            divider = round(self.width() * self.split)
            painter.save()
            painter.setClipRect(0, 0, divider, self.height())
            painter.drawImage(target, QImage(a, w, h, w * 3, QImage.Format.Format_RGB888))
            painter.restore()
            painter.setPen(QPen(QColor("#f1c37c"), 2))
            painter.drawLine(divider, 0, divider, self.height())
            for text, x in [("A · snapshot", 12), ("B · current", self.width() - 112)]:
                painter.fillRect(x - 4, 9, 107, 26, QColor("#181b20"))
                painter.drawText(x, 27, text)


class Control(QWidget):
    def __init__(self, key, value, changed):
        super().__init__()
        self.key = key
        self.changed = changed
        self.spins = []
        self.sliders = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 5)
        label = QLabel(LABELS.get(key, key.replace("_", " ").capitalize()))
        label.setToolTip(HINTS.get(key, label.text()))
        layout.addWidget(label)
        vals = value if key in RANGES else [value]
        for index, val in enumerate(vals):
            row = QHBoxLayout()
            spin = QSpinBox() if key == "seed" else QDoubleSpinBox()
            spin.setRange(1 if key == "fps" else 0, LIMITS.get(key, 1))
            if key != "seed":
                spin.setDecimals(2)
                spin.setSingleStep(1 if key == "fps" else 0.05)
            spin.setValue(val)
            spin.setKeyboardTracking(False)
            spin.setFixedWidth(88 if key != "seed" else 135)
            spin.setAccessibleName(f"{key} {'low' if index == 0 else 'high'}" if key in RANGES else key)
            self.spins.append(spin)
            if key in RANGES:
                row.addWidget(QLabel("Lo" if index == 0 else "Hi"))
            if key != "seed":
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(round(spin.minimum() * 100), round(spin.maximum() * 100))
                slider.setValue(round(val * 100))
                slider.valueChanged.connect(lambda v, s=spin: s.setValue(v / 100))
                spin.valueChanged.connect(lambda v, s=slider: self.sync_slider(s, v))
                self.sliders.append(slider)
                row.addWidget(slider, 1)
            else:
                row.addStretch(1)
            spin.valueChanged.connect(lambda _v, i=index: self.update_value(i))
            row.addWidget(spin)
            layout.addLayout(row)

    def sync_slider(self, slider, value):
        blocker = QSignalBlocker(slider)
        slider.setValue(round(value * 100))

    def update_value(self, index):
        if len(self.spins) == 2:
            lo, hi = [s.value() for s in self.spins]
            if lo > hi:
                other = self.spins[1 - index]
                blocker = QSignalBlocker(other)
                other.setValue(self.spins[index].value())
                self.sync_slider(self.sliders[1 - index], other.value())
        vals = [s.value() for s in self.spins]
        self.changed(self.key, tuple(vals) if self.key in RANGES else vals[0])

    def set_value(self, value):
        vals = value if self.key in RANGES else [value]
        for i, (spin, val) in enumerate(zip(self.spins, vals)):
            blocker = QSignalBlocker(spin)
            spin.setValue(val)
            if self.key != "seed":
                self.sync_slider(self.sliders[i], val)


class Studio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Nebula Studio — {__version__}")
        self.resize(1280, 860)
        self.params = normalize()
        self.info = None
        self.snapshot = None
        self.generation = 0
        self.open_generation = 0
        self.cancel = Cancellation()
        self.export_cancel = Cancellation()
        self.frames = OrderedDict()
        self.frames_bytes = 0
        self.preview_future = None
        self.export_future = None
        self.open_future = None
        self.closing = False
        self.preview_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="preview")
        self.io_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="media")
        self.events = Events()
        self.events.message.connect(self.on_event)
        self.worker = PreviewWorker(self.events)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(100)
        self.debounce.timeout.connect(self.submit_preview)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.advance)
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(100)
        self.close_timer.timeout.connect(self.finish_close)
        self.build_ui()
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.choose_clip)
        QShortcut(QKeySequence("Space"), self, activated=self.play.click)

    def button(self, text, callback, primary=False):
        b = QPushButton(text)
        b.clicked.connect(callback)
        if primary:
            b.setObjectName("primary")
        return b

    def build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(12)
        top = QHBoxLayout()
        brand = QLabel("NEBULA")
        brand.setObjectName("brand")
        top.addWidget(brand)
        subtitle = QLabel("ANALOG MOTION STUDIO")
        subtitle.setObjectName("muted")
        top.addWidget(subtitle)
        top.addStretch()
        self.open_button = self.button("Open clip…", self.choose_clip, True)
        top.addWidget(self.open_button)
        top.addWidget(self.button("Load preset…", self.load_preset))
        top.addWidget(self.button("Save preset…", self.save_preset))
        root.addLayout(top)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        work = QVBoxLayout(left)
        work.setContentsMargins(0, 0, 10, 0)
        self.clip_label = QLabel("No clip selected")
        self.clip_label.setObjectName("muted")
        work.addWidget(self.clip_label)
        tools = QHBoxLayout()
        tools.addWidget(QLabel("View"))
        self.stage = QComboBox()
        for title, value in [("Final grade", "grade"), ("Source", "source"), ("After print", "print"), ("After scan", "scan"), ("After motion", "wobble")]:
            self.stage.addItem(title, value)
        self.stage.currentIndexChanged.connect(self.invalidate)
        tools.addWidget(self.stage)
        self.quality = QComboBox()
        self.quality.addItem("Fast · 480 px", 480)
        self.quality.addItem("Detailed · 720 px", 720)
        self.quality.currentIndexChanged.connect(self.invalidate)
        tools.addWidget(self.quality)
        tools.addStretch()
        self.full = self.button("Full-size still", self.full_still)
        tools.addWidget(self.full)
        work.addLayout(tools)
        self.viewer = Viewer()
        work.addWidget(self.viewer, 1)
        compare_row = QHBoxLayout()
        self.capture = self.button("Capture A", self.capture_a)
        compare_row.addWidget(self.capture)
        self.compare = QCheckBox("Compare A / B")
        self.compare.setEnabled(False)
        self.compare.toggled.connect(self.toggle_compare)
        compare_row.addWidget(self.compare)
        self.a_label = QLabel("A stores settings and follows the same source frame")
        self.a_label.setObjectName("muted")
        compare_row.addWidget(self.a_label, 1)
        work.addLayout(compare_row)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.timeline.setAccessibleName("Timeline")
        self.timeline.valueChanged.connect(self.scrub)
        work.addWidget(self.timeline)
        transport = QHBoxLayout()
        self.play = QPushButton("▶ Play loop")
        self.play.setCheckable(True)
        self.play.toggled.connect(self.toggle_play)
        transport.addWidget(self.play)
        self.time_label = QLabel("00:00.00 / 00:00.00")
        transport.addWidget(self.time_label)
        transport.addStretch()
        transport.addWidget(QLabel("Loop starts"))
        self.loop_start = QDoubleSpinBox()
        self.loop_start.setSuffix(" s")
        self.loop_start.setDecimals(2)
        self.loop_start.valueChanged.connect(self.invalidate)
        transport.addWidget(self.loop_start)
        transport.addWidget(self.button("Set here", lambda: self.loop_start.setValue(self.timeline.value() / self.params["fps"])))
        self.loop_length = QComboBox()
        for seconds in (1, 2, 3):
            self.loop_length.addItem(f"{seconds} seconds", seconds)
        self.loop_length.setCurrentIndex(1)
        self.loop_length.currentIndexChanged.connect(self.invalidate)
        transport.addWidget(self.loop_length)
        work.addLayout(transport)
        self.status = QLabel("Open a video. Adjust a treatment, then play a short loop.")
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        work.addWidget(self.status)
        exports = QHBoxLayout()
        self.export_scope = QComboBox()
        self.export_scope.addItems(["Export loop", "Export whole clip"])
        exports.addWidget(self.export_scope)
        self.export_button = self.button("Export MP4…", self.choose_export, True)
        exports.addWidget(self.export_button)
        self.export_progress = QProgressBar()
        self.export_progress.setValue(0)
        exports.addWidget(self.export_progress, 1)
        self.cancel_export_button = self.button("Cancel", lambda: self.export_cancel.cancel())
        self.cancel_export_button.setEnabled(False)
        exports.addWidget(self.cancel_export_button)
        work.addLayout(exports)
        splitter.addWidget(left)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(295)
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(4, 0, 4, 0)
        self.controls = {}
        self.stage_checks = {}
        for title, stage, keys in GROUPS:
            group = QGroupBox(title)
            layout = QVBoxLayout(group)
            if stage:
                check = QCheckBox("Enabled")
                check.setChecked(True)
                check.toggled.connect(lambda enabled, s=stage: self.stage_enabled(s, enabled))
                self.stage_checks[stage] = check
                layout.addWidget(check)
            for key in keys:
                control = Control(key, self.params[key], self.parameter_changed)
                self.controls[key] = control
                layout.addWidget(control)
            controls_layout.addWidget(group)
        controls_layout.addWidget(self.button("Reset to defaults", self.reset_params))
        controls_layout.addStretch()
        scroll.setWidget(controls_widget)
        splitter.addWidget(scroll)
        splitter.setSizes([915, 325])
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)
        self.set_media_enabled(False)

    def set_media_enabled(self, enabled):
        for widget in (self.play, self.capture, self.full, self.timeline, self.loop_start, self.loop_length, self.export_scope):
            widget.setEnabled(enabled)
        self.export_button.setEnabled(enabled and not (self.export_future and not self.export_future.done()))

    def choose_clip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open a video", str(Path.home()), "Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*)")
        if path:
            self.open_clip(path)

    def open_clip(self, path):
        self.play.setChecked(False)
        self.open_generation += 1
        generation = self.open_generation
        self.open_button.setEnabled(False)
        self.status.setText("Reading clip…")
        def job():
            try:
                info = probe(path)
                stat = Path(path).stat()
                info["identity"] = (stat.st_size, stat.st_mtime_ns)
                self.events.message.emit(generation, "opened", info)
            except Exception as exc:
                self.events.message.emit(generation, "open_error", str(exc))
        self.open_future = self.io_pool.submit(job)

    def configure_time(self):
        if self.info:
            self.timeline.setMaximum(frame_count(self.info, self.params["fps"]) - 1)
            self.loop_start.setMaximum(self.timeline.maximum() / self.params["fps"])
        self.update_time()

    def update_time(self):
        fps = self.params["fps"]
        current = self.timeline.value() / fps
        duration = self.info["duration"] if self.info else 0
        self.time_label.setText(f"{current:06.2f} / {duration:06.2f} s · frame {self.timeline.value()}")

    def loop_bounds(self):
        fps = self.params["fps"]
        start = min(self.timeline.maximum(), round(self.loop_start.value() * fps))
        count = min(self.timeline.maximum() + 1 - start, max(1, round(self.loop_length.currentData() * fps)))
        return start, count

    def parameter_changed(self, key, value):
        old_fps = self.params["fps"]
        self.params[key] = value
        if key == "fps":
            self.play.setChecked(False)
            time = self.timeline.value() / old_fps
            self.clear_a()
            self.configure_time()
            blocker = QSignalBlocker(self.timeline)
            self.timeline.setValue(round(time * value))
            self.update_time()
        self.invalidate()

    def stage_enabled(self, stage, enabled):
        self.params["_stages"][stage] = enabled
        if stage == "grade":
            self.params["grade"] = int(enabled)
        self.invalidate()

    def invalidate(self, *_args):
        self.cancel.cancel()
        if self.preview_future:
            self.preview_future.cancel()
        self.generation += 1
        self.frames.clear()
        self.frames_bytes = 0
        if self.info:
            self.status.setText("Updating current frame…")
            self.debounce.start()

    def scrub(self, *_args):
        self.update_time()
        index = self.timeline.value()
        if index in self.frames:
            self.viewer.set_packet(self.frames[index])
        else:
            self.invalidate()

    def submit_preview(self, full=False):
        if not self.info or self.closing:
            return
        self.cancel.cancel()
        if self.preview_future:
            self.preview_future.cancel()
        self.cancel = Cancellation()
        start, count = self.loop_bounds()
        if full:
            start, count = self.timeline.value(), 1
        edge = None if full else self.quality.currentData()
        if edge:
            # Keep the entire loop (including both A/B images) within its budget.
            pixels = self.info["width"] * self.info["height"]
            max_scale = math.sqrt(110 * 1024 * 1024 / (3 * pixels * (count + 1) * (2 if self.snapshot else 1)))
            edge = max(64, min(edge, int(max(self.info["width"], self.info["height"]) * max_scale)))
        self.preview_future = self.preview_pool.submit(
            self.worker.run, self.generation, copy.deepcopy(self.info), copy.deepcopy(self.params),
            copy.deepcopy(self.snapshot), self.timeline.value(), start, count,
            edge, self.stage.currentData(), self.cancel)

    def full_still(self):
        self.play.setChecked(False)
        self.invalidate()
        self.debounce.stop()
        self.status.setText("Rendering full-size current frame…")
        self.submit_preview(full=True)

    def toggle_play(self, playing):
        self.play.setText("Ⅱ Pause" if playing else "▶ Play loop")
        if playing and self.info:
            start, count = self.loop_bounds()
            if not start <= self.timeline.value() < start + count:
                self.timeline.setValue(start)
            self.play_timer.start(max(1, round(1000 / self.params["fps"])))
            # A full-size still does not fill the proxy loop.
            if len(self.frames) < count:
                self.invalidate()
        else:
            self.play_timer.stop()

    def advance(self):
        start, count = self.loop_bounds()
        index = start + (self.timeline.value() - start + 1) % count
        if index in self.frames:
            self.timeline.setValue(index)
        # Hold the visible frame while buffering; do not pretend this is realtime.

    def capture_a(self):
        self.snapshot = copy.deepcopy(self.params)
        self.compare.setEnabled(True)
        self.compare.setChecked(True)
        self.a_label.setText("A captured · drag the divider · capture again to replace")
        self.invalidate()

    def clear_a(self):
        self.snapshot = None
        self.compare.setChecked(False)
        self.compare.setEnabled(False)
        self.a_label.setText("A stores settings and follows the same source frame")

    def toggle_compare(self, checked):
        self.viewer.compare = checked
        self.viewer.update()

    def apply_params(self, params):
        self.play.setChecked(False)
        self.params = normalize(params)
        self.clear_a()
        for key, control in self.controls.items():
            control.set_value(self.params[key])
        for stage, check in self.stage_checks.items():
            blocker = QSignalBlocker(check)
            check.setChecked(self.params["_stages"][stage])
        self.configure_time()
        self.invalidate()

    def reset_params(self):
        self.apply_params(DEFAULTS)

    def load_preset(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load preset or tune_params.json", str(PRESETS_DIR), "Nebula settings (*.json)")
        if path:
            try:
                self.apply_params(load(path))
            except (OSError, ValueError, TypeError) as exc:
                self.show_error(str(exc))

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save preset", str(PRESETS_DIR / "studio.json"), "Nebula settings (*.json)")
        if path:
            try:
                save(path, self.params)
                self.status.setText(f"Settings saved · {Path(path).name}")
            except OSError as exc:
                self.show_error(str(exc))

    def choose_export(self):
        if not self.info:
            return
        default = Path(self.info["path"]).with_name(Path(self.info["path"]).stem + "-nebula.mp4")
        path, _ = QFileDialog.getSaveFileName(self, "Export full-resolution treatment (silent MP4)", str(default), "MP4 video (*.mp4)")
        if path:
            self.start_export(path)

    def start_export(self, path):
        if not self.info or (self.export_future and not self.export_future.done()):
            return
        if Path(path).resolve() == Path(self.info["path"]).resolve():
            self.show_error("Choose a different output path to preserve the source clip.")
            return
        self.export_cancel = Cancellation()
        info, params = copy.deepcopy(self.info), copy.deepcopy(self.params)
        start, count = self.loop_bounds() if self.export_scope.currentIndex() == 0 else (0, None)
        token = self.export_cancel
        self.export_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.cancel_export_button.setEnabled(True)
        self.export_progress.setValue(0)
        self.export_progress.setFormat("Rendering %p%")
        def job():
            try:
                result = export_video(info, params, path, start, count, token,
                                      lambda done, total: self.events.message.emit(0, "export_progress", round(done / total * 100)))
                self.events.message.emit(0, "export_done", str(result))
            except Cancelled:
                self.events.message.emit(0, "export_cancelled", None)
            except Exception as exc:
                self.events.message.emit(0, "export_error", str(exc))
        self.export_future = self.io_pool.submit(job)

    def on_event(self, generation, kind, data):
        if self.closing:
            return
        if kind.startswith("export_"):
            if kind == "export_progress":
                self.export_progress.setValue(data)
                return
            self.export_button.setEnabled(bool(self.info))
            self.open_button.setEnabled(True)
            self.cancel_export_button.setEnabled(False)
            self.export_progress.setFormat("Complete" if kind == "export_done" else "Cancelled" if kind == "export_cancelled" else "Failed")
            if kind == "export_done":
                self.status.setText(f"Exported · {data}")
                self.export_progress.setValue(100)
            elif kind == "export_error":
                self.show_error(data)
            return
        if kind in ("opened", "open_error"):
            if generation != self.open_generation:
                return
            self.open_button.setEnabled(True)
            if kind == "open_error":
                self.show_error(data)
                return
            self.cancel.cancel()
            self.info = data
            self.viewer.set_packet(None)
            self.clear_a()
            self.clip_label.setText(f'{Path(data["path"]).name}   ·   {data["width"]} × {data["height"]}   ·   {data["duration"]:.2f} s')
            self.clip_label.setToolTip(data["path"])
            self.timeline.setValue(0)
            self.loop_start.setValue(0)
            self.configure_time()
            self.set_media_enabled(True)
            self.invalidate()
            return
        if generation != self.generation:
            return
        if kind == "frame":
            index, packet, elapsed = data
            size = len(packet[1]) + (len(packet[2]) if packet[2] else 0)
            if index in self.frames:
                old = self.frames.pop(index)
                self.frames_bytes -= len(old[1]) + (len(old[2]) if old[2] else 0)
            self.frames[index] = packet
            self.frames_bytes += size
            while self.frames_bytes > 128 * 1024 * 1024 and len(self.frames) > 1:
                _, old = self.frames.popitem(last=False)
                self.frames_bytes -= len(old[1]) + (len(old[2]) if old[2] else 0)
            if index == self.timeline.value():
                self.viewer.set_packet(packet)
                self.status.setText(f"Current frame · {elapsed * 1000:.0f} ms · {packet[0][0]} × {packet[0][1]} · building loop…")
        elif kind == "done":
            start, count = self.loop_bounds()
            buffered = sum(i in self.frames for i in range(start, start + count))
            resolution = self.viewer.packet[0] if self.viewer.packet else (0, 0)
            full = resolution == (self.info["width"], self.info["height"])
            self.status.setText(f"{'Full-size' if full else 'Proxy'} ready · {buffered}/{count} loop frames · {data:.2f} s build" +
                                (" · shorten loop or use Fast quality to fit cache" if 1 < buffered < count else ""))
        elif kind == "error":
            self.play.setChecked(False)
            self.status.setText(f"Preview error · {data}")

    def show_error(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, "Nebula Studio", message)

    def finish_close(self):
        futures = (self.preview_future, self.export_future, self.open_future)
        if all(f is None or f.done() for f in futures):
            self.close_timer.stop()
            self.close()

    def closeEvent(self, event):
        self.closing = True
        self.play_timer.stop()
        self.debounce.stop()
        self.cancel.cancel()
        self.export_cancel.cancel()
        for future in (self.preview_future, self.export_future, self.open_future):
            if future:
                future.cancel()
        if any(f and not f.done() for f in (self.preview_future, self.export_future, self.open_future)):
            self.status.setText("Stopping background work…")
            event.ignore()
            self.close_timer.start()
            return
        self.preview_pool.shutdown(wait=False, cancel_futures=True)
        self.io_pool.shutdown(wait=False, cancel_futures=True)
        event.accept()


def main():
    parser = argparse.ArgumentParser(description="Nebula native desktop studio")
    parser.add_argument("--version", action="version", version=f"Nebula Studio {__version__}")
    parser.add_argument("clip", nargs="?", type=Path)
    parser.add_argument("--preset", type=Path)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Nebula Studio")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Studio()
    if args.preset:
        try:
            window.apply_params(load(args.preset))
        except Exception as exc:
            window.show_error(str(exc))
    window.show()
    if args.clip:
        window.open_clip(args.clip)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
