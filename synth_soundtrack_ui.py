"""Project-clock soundtrack widgets. Media probing belongs to the caller."""
import copy
import math

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                             QFormLayout, QLabel, QPushButton, QCheckBox)
from studio_theme import COLORS
from studio_widgets import ComboBox, DoubleSpinBox, Slider


class SoundtrackLane(QWidget):
    seekRequested = Signal(float)
    editRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.track = None
        self.project_duration = 0.
        self.peaks = []
        self.time = 0.
        self.status = ''
        self.setFixedHeight(48)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Soundtrack timeline')
        self.setToolTip('Click to seek; double-click to edit soundtrack. Arrow keys seek one second.')
        self.hide()

    def set_track(self, track, project_duration):
        old = self.track
        self.track = copy.deepcopy(track)
        self.project_duration = max(0., float(project_duration))
        if not old or not track or old.get('path') != track.get('path') or old.get('duration') != track.get('duration'):
            self.peaks = []
        self.setVisible(track is not None)
        self.update()

    def set_peaks(self, peaks):
        self.peaks = [min(1., abs(float(p))) if math.isfinite(float(p)) else 0. for p in peaks]
        self.update()

    def set_time(self, seconds):
        self.time = max(0., min(self.project_duration, float(seconds)))
        self.update()

    def set_status(self, status):
        self.status = str(status)
        self.setAccessibleDescription(self.status)
        self.update()

    def mousePressEvent(self, event):
        if self.track and self.project_duration > 0 and event.button() == Qt.MouseButton.LeftButton:
            self.seekRequested.emit(max(0., min(1., event.position().x() / max(1, self.width()))) * self.project_duration)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.track and event.button() == Qt.MouseButton.LeftButton:
            self.editRequested.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        targets = {Qt.Key.Key_Left: self.time - 1., Qt.Key.Key_Right: self.time + 1.,
                   Qt.Key.Key_Home: 0., Qt.Key.Key_End: self.project_duration}
        if self.track and event.key() in targets:
            self.seekRequested.emit(max(0., min(self.project_duration, targets[event.key()])))
            event.accept()
        elif self.track and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.editRequested.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(COLORS['panel']))
        if not self.track:
            return
        track = self.track
        duration = self.project_duration
        offset = track.get('offset', 0.)
        start = track.get('in', 0.)
        stop = track.get('out', track.get('duration', 0.))
        used = stop - start
        source_duration = track.get('duration', 0.)
        loop = track.get('end_mode') == 'loop'
        # One bounded sample per screen column, including all loop cycles.
        if duration > 0 and used > 0:
            x0 = int(min(self.width(), offset / duration * self.width()))
            x1 = self.width() if loop else int(min(self.width(), (offset + used) / duration * self.width()))
            p.fillRect(QRectF(x0, 18, max(0, x1 - x0), 27), QColor(COLORS['selected']))
            p.setPen(QColor(COLORS['accent']))
            if self.peaks and source_duration > 0:
                for x in range(max(0, x0), x1):
                    elapsed = (x + .5) / max(1, self.width()) * duration - offset
                    if elapsed < 0:
                        continue
                    source = start + (elapsed % used if loop else elapsed)
                    index = min(len(self.peaks) - 1, int(source / source_duration * len(self.peaks)))
                    amplitude = self.peaks[max(0, index)] * 11.
                    p.drawLine(x, int(32 - amplitude), x, int(32 + amplitude))
            else:
                p.drawLine(x0, 32, x1, 32)
            p.setPen(QColor(COLORS['border_hover']))
            p.drawLine(x0, 18, x0, 45)
        p.setPen(QColor(COLORS['muted']))
        name = track.get('name', 'Soundtrack')
        label = f'{name} · {start:.2f}–{stop:.2f} s · Start {offset:.2f} s · {"Loop" if loop else "Silence at end"}'
        if self.status:
            label += ' · ' + self.status
        p.drawText(QRectF(6, 1, max(0, self.width() - 12), 16), Qt.AlignmentFlag.AlignLeft,
                   p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, max(0, self.width() - 12)))
        if duration > 0:
            p.setPen(QPen(QColor(COLORS['cursor']), 1.5))
            x = min(self.width() - 1, self.time / duration * self.width())
            p.drawLine(int(x), 0, int(x), self.height())
        if self.hasFocus():
            p.setPen(QColor(COLORS['focus']))
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))


class SoundtrackDialog(QDialog):
    trackEdited = Signal(dict)
    importRequested = Signal()
    relinkRequested = Signal()
    removeRequested = Signal()
    monitorVolumeChanged = Signal(float)
    monitorMutedChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Soundtrack')
        self.setModal(False)
        self.resize(420, 570)
        self.track = None
        self.project_duration = 0.
        self._loading = False
        self._busy = False
        layout = QVBoxLayout(self)
        self.summary = QLabel('Import a soundtrack to hear it with your piece.')
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        self.import_button = QPushButton('Import…')
        self.relink_button = QPushButton('Relink…')
        self.remove_button = QPushButton('Remove')
        self.remove_button.setProperty('destructive', True)
        for button, signal in ((self.import_button, self.importRequested), (self.relink_button, self.relinkRequested), (self.remove_button, self.removeRequested)):
            actions.addWidget(button)
            button.clicked.connect(signal.emit)
        layout.addLayout(actions)
        self.editor = QWidget()
        form = QFormLayout(self.editor)
        self.in_control = self._seconds('Soundtrack In')
        self.out_control = self._seconds('Soundtrack Out')
        self.offset_control = self._seconds('Soundtrack start on project timeline')
        self.end_mode = ComboBox()
        self.end_mode.addItem('Silence at end', 'silence')
        self.end_mode.addItem('Loop trimmed audio', 'loop')
        self.end_mode.setAccessibleName('Soundtrack end behavior')
        self.gain = DoubleSpinBox()
        self.gain.setRange(0., 1.)
        self.gain.display_scale = 100.
        self.gain.setSuffix(" %")
        self.gain.setDecimals(12)
        self.gain.setSingleStep(.05)
        self.gain.setKeyboardTracking(False)
        self.gain.setAccessibleName('Soundtrack output volume')
        self.export_audio = ComboBox()
        for label, value in [('Soundtrack', 'soundtrack'), ('Footage audio', 'footage'), ('Silent', 'silent')]:
            self.export_audio.addItem(label, value)
        self.export_audio.setAccessibleName('Export audio')
        for label, control in [('In', self.in_control), ('Out', self.out_control), ('Start', self.offset_control), ('At end', self.end_mode), ('Output volume', self.gain), ('Export audio', self.export_audio)]:
            form.addRow(label, control)
        layout.addWidget(self.editor)
        self.used_label = QLabel()
        layout.addWidget(self.used_label)
        hint = QLabel('Clips set the project duration. Soundtrack edits do not change clip durations. Apply saves these edits. Preview always monitors the soundtrack; Export audio can select footage audio or silence.')
        self.hint_label = hint
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status_label)
        monitor_label = QLabel('Preview monitor (separate from saved output volume)')
        monitor_label.setWordWrap(True)
        layout.addWidget(monitor_label)
        monitor = QHBoxLayout()
        self.monitor_volume = Slider(Qt.Orientation.Horizontal)
        self.monitor_volume.setRange(0, 100)
        self.monitor_volume.setAccessibleName('Preview monitor volume')
        self.monitor_mute = QCheckBox('Mute')
        self.monitor_mute.setAccessibleName('Mute soundtrack preview monitor')
        monitor.addWidget(self.monitor_volume)
        monitor.addWidget(self.monitor_mute)
        layout.addLayout(monitor)
        self.monitor_volume.valueChanged.connect(lambda v: None if self._loading else self.monitorVolumeChanged.emit(v / 100.))
        self.monitor_mute.toggled.connect(lambda v: None if self._loading else self.monitorMutedChanged.emit(v))
        footer = QHBoxLayout()
        footer.addStretch()
        self.apply_button = QPushButton('Apply')
        self.apply_button.setObjectName('primary')
        self.apply_button.clicked.connect(self.apply)
        close = QPushButton('Close')
        close.clicked.connect(self.close)
        footer.addWidget(self.apply_button)
        footer.addWidget(close)
        layout.addLayout(footer)
        for control in (self.in_control, self.out_control, self.offset_control, self.gain):
            control.valueChanged.connect(self._draft_changed)
        for control in (self.end_mode, self.export_audio):
            control.currentIndexChanged.connect(self._draft_changed)
        self.set_monitor(1., False)
        self.set_track(None)

    @staticmethod
    def _seconds(name):
        control = DoubleSpinBox()
        control.setDecimals(12)
        control.setRange(0., 1e9)
        control.setSingleStep(.01)
        control.setSuffix(' s')
        control.setKeyboardTracking(False)
        control.setAccessibleName(name)
        return control

    def set_track(self, track, project_duration=None):
        authored_changed = track != self.track
        self._loading = True
        self.track = copy.deepcopy(track)
        if project_duration is not None:
            self.project_duration = max(0., float(project_duration))
        self.import_button.setText('Replace…' if track else 'Import…')
        if track:
            duration = track['duration']
            self.summary.setText(f'{track.get("name", "Soundtrack")}\nSource {duration:.2f} s · Project {self.project_duration:.2f} s')
            self.summary.setToolTip(track.get('path', ''))
            if authored_changed:
                self.in_control.setRange(0., duration)
                self.out_control.setRange(0., duration)
                for control, key, default in ((self.in_control, 'in', 0.), (self.out_control, 'out', duration), (self.offset_control, 'offset', 0.), (self.gain, 'gain', 1.)):
                    control.setValue(track.get(key, default))
                self.end_mode.setCurrentIndex(self.end_mode.findData(track.get('end_mode', 'silence')))
                self.export_audio.setCurrentIndex(self.export_audio.findData(track.get('export_audio', 'soundtrack')))
        else:
            self.summary.setText('Import a soundtrack to hear it with your piece.')
            self.summary.setToolTip('')
        self._loading = False
        self._draft_changed()
        self._update_enabled()

    load = set_track

    def _draft(self):
        if not self.track:
            return None
        draft = copy.deepcopy(self.track)
        draft.update({'in': self.in_control.value(), 'out': self.out_control.value(),
                      'offset': self.offset_control.value(), 'gain': self.gain.value(),
                      'end_mode': self.end_mode.currentData(), 'export_audio': self.export_audio.currentData()})
        return draft

    def _draft_changed(self, *args):
        if self._loading:
            return
        draft = self._draft()
        if draft:
            used = draft['out'] - draft['in']
            self.used_label.setText(f'Used audio {max(0., used):.2f} s' + (' · In must be before Out' if used <= 0 else ''))
        else:
            self.used_label.clear()
        self._update_enabled()

    def _update_enabled(self):
        exists = self.track is not None
        self.editor.setEnabled(exists and not self._busy)
        self.import_button.setEnabled(not self._busy)
        self.relink_button.setEnabled(exists and not self._busy)
        self.remove_button.setEnabled(exists and not self._busy)
        draft = self._draft()
        valid = draft and draft['in'] < draft['out'] <= draft['duration']
        self.apply_button.setEnabled(bool(valid and draft != self.track and not self._busy))

    def apply(self):
        if not self.apply_button.isEnabled():
            return
        draft = self._draft()
        self.track = copy.deepcopy(draft)
        self._update_enabled()
        self.trackEdited.emit(draft)

    def set_monitor(self, volume, muted):
        previous = self._loading
        self._loading = True
        self.monitor_volume.setValue(round(max(0., min(1., volume)) * 100))
        self.monitor_mute.setChecked(bool(muted))
        self._loading = previous

    def set_busy(self, busy):
        self._busy = bool(busy)
        self._update_enabled()

    def set_status(self, status):
        self.status_label.setText(str(status))
