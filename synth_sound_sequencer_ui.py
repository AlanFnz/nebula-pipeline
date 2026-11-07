"""Complete pattern overview and one precise editor; selection is UI state only."""
import bisect
import copy
from PySide6.QtCore import Qt, Signal, QSignalBlocker, QEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton)
from synth_sound_sequence import sequence_defaults, DIVISIONS, note_name, frequency_note, step_seconds, note_frequency
from synth_sound_step_cell import StepCell


class StepSequencer(QWidget):
    changed = Signal()
    gestureStarted = Signal()
    gestureFinished = Signal()
    focusRequested = Signal(bool)

    def __init__(self):
        super().__init__()
        self.loading = False; self.root = 146.83; self.selected = 0; self.active = -1
        self.schedule = []; self.times = []; self.period = .125; self.pattern = sequence_defaults()
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6)
        row = QHBoxLayout()
        self.bpm = QDoubleSpinBox(); self.bpm.setRange(30, 240); self.bpm.setDecimals(3)
        self.bpm.setSuffix(' BPM'); self.bpm.setKeyboardTracking(False); self.bpm.setAccessibleName('Sequencer tempo')
        self.bpm.setToolTip('Tempo of the sound only. Does not change video speed.')
        self.division = QComboBox(); self.division.setAccessibleName('Step division')
        for key in DIVISIONS: self.division.addItem(key, key)
        self.length = QSpinBox(); self.length.setRange(1, 16); self.length.setSuffix(' steps')
        self.length.setAccessibleName('Sequence length'); self.length.setKeyboardTracking(False)
        self.length.setToolTip('Steps outside this length are retained. Extend the pattern to hear them again.')
        for label, widget in (('Tempo', self.bpm), ('Division', self.division), ('Length', self.length)):
            row.addWidget(QLabel(label)); row.addWidget(widget)
        row.addStretch(); layout.addLayout(row)
        row = QHBoxLayout(); row.addWidget(QLabel('Start'))
        self.trigger = QComboBox(); self.trigger.setAccessibleName('Sequencer trigger')
        self.trigger.addItem('Visual gestures', 'gesture'); self.trigger.addItem('Loop with timeline', 'loop')
        self.trigger.setToolTip('Visual gestures: one pattern per gesture, then wait. Loop with timeline: repeat continuously. The image still shapes loudness and filter.')
        row.addWidget(self.trigger, 1)
        self.focus_button = QPushButton('Focus pattern'); self.focus_button.setCheckable(True)
        self.focus_button.setToolTip('Hide the video panel to give the pattern more room. Playback and sound are unchanged.')
        self.focus_button.toggled.connect(self.focusRequested); row.addWidget(self.focus_button); layout.addLayout(row)
        self.grid = QWidget(); grid = QHBoxLayout(self.grid); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(2)
        labels = QWidget(); labels.setFixedSize(54, 196)
        for text, y, height in (('Step', 2, 20), ('On / rest', 24, 20), ('Note', 78, 20), ('Velocity', 136, 20), ('Gate', 166, 20)):
            label = QLabel(text, labels); label.setGeometry(0, y, 54, height)
        labels.setToolTip('Note = pitch. Velocity = strength. Gate = note duration within its step; release continues afterward.')
        grid.addWidget(labels); self.cells = []
        for i in range(16):
            if i and i % 4 == 0: grid.addSpacing(5)
            cell = StepCell(i); self.cells.append(cell); grid.addWidget(cell, 1)
            cell.selected.connect(self.select_step); cell.navigate.connect(self.focus_step)
            cell.edited.connect(self.edit_step); cell.editRequested.connect(self.edit_selected_note)
            cell.gestureStarted.connect(self.gestureStarted); cell.gestureFinished.connect(self.gestureFinished)
        layout.addWidget(self.grid)
        self.selection_label = QLabel(); self.selection_label.setTextFormat(Qt.TextFormat.PlainText)
        self.selection_label.setWordWrap(True); layout.addWidget(self.selection_label)
        self.editor = QWidget(); row = QHBoxLayout(self.editor); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(6)
        self.step_on = QCheckBox('On'); self.step_on.setAccessibleName('Selected step enabled')
        self.step_note = QSpinBox(); self.step_note.setRange(-12, 24); self.step_note.setSuffix(' st')
        self.step_note.setAccessibleName('Selected step semitones'); self.step_note.setKeyboardTracking(False)
        self.step_velocity = QDoubleSpinBox(); self.step_velocity.setRange(0, 100)
        self.step_gate = QDoubleSpinBox(); self.step_gate.setRange(10, 100)
        for widget, name in ((self.step_velocity, 'velocity'), (self.step_gate, 'gate')):
            widget.setDecimals(2); widget.setSuffix(' %'); widget.setSingleStep(1); widget.setKeyboardTracking(False)
            widget.setAccessibleName('Selected step ' + name)
        row.addWidget(self.step_on)
        for title, widget in (('Note', self.step_note), ('Velocity', self.step_velocity), ('Gate', self.step_gate)):
            row.addWidget(QLabel(title)); widget.setFixedWidth(104); row.addWidget(widget)
            widget.installEventFilter(self)
        row.addStretch(); layout.addWidget(self.editor)
        self.step_gate.setToolTip('Duration within this step. Attack and release are separate envelope controls.')
        self.step_on.toggled.connect(lambda value: self.edit_step(self.selected, 'enabled', value))
        self.step_note.valueChanged.connect(lambda value: self.edit_step(self.selected, 'semitones', value))
        self.step_velocity.valueChanged.connect(lambda value: self.edit_step(self.selected, 'velocity', value/100))
        self.step_gate.valueChanged.connect(lambda value: self.edit_step(self.selected, 'gate', value/100))
        self.bpm.valueChanged.connect(lambda value: self.edit_pattern('bpm', value))
        self.length.valueChanged.connect(lambda value: self.edit_pattern('sequence_length', value))
        self.division.currentIndexChanged.connect(lambda: self.edit_pattern('subdivision', self.division.currentData()))
        self.trigger.currentIndexChanged.connect(lambda: self.edit_pattern('sequence_trigger', self.trigger.currentData()))
        self.load(sequence_defaults())

    def select_step(self, index):
        if self.selected == index: return
        self.selected = index; self.refresh()

    def focus_step(self, index):
        self.select_step(index); self.cells[index].setFocus(Qt.FocusReason.OtherFocusReason)

    def edit_selected_note(self):
        self.step_note.setFocus(); self.step_note.selectAll()

    def edit_step(self, index, key, value):
        if self.loading or self.pattern['sequence'][index][key] == value: return
        self.pattern['sequence'][index][key] = value; self.refresh(); self.changed.emit()

    def edit_pattern(self, key, value):
        if self.loading or self.pattern[key] == value: return
        self.pattern[key] = value; self.refresh(); self.changed.emit()

    def set_root(self, hz): self.root = hz; self.refresh()

    def refresh(self):
        nearest = frequency_note(self.root)
        approximate = abs(self.root - note_frequency(nearest)) / self.root > .0001
        for i, cell in enumerate(self.cells):
            entry = self.pattern['sequence'][i]
            cell.show_step(entry, note_name(nearest + entry['semitones']), i < self.pattern['sequence_length'], i == self.selected, i == self.active)
        entry = self.pattern['sequence'][self.selected]
        for widget, value in ((self.step_on, entry['enabled']), (self.step_note, entry['semitones']),
                              (self.step_velocity, entry['velocity']*100), (self.step_gate, entry['gate']*100)):
            with QSignalBlocker(widget):
                if isinstance(widget, QCheckBox): widget.setChecked(value)
                else: widget.setValue(value)
        state = 'Outside pattern · retained' if self.selected >= self.pattern['sequence_length'] else 'On' if entry['enabled'] else 'Rest'
        hz = self.root * 2 ** (entry['semitones']/12)
        self.selection_label.setText(f"Step {self.selected+1} · {state} · {'≈ ' if approximate else ''}{note_name(nearest+entry['semitones'])} · {hz:.2f} Hz")

    def load(self, config):
        self.loading = True
        # Keep exact stored values. Display precision must never rewrite a pattern.
        self.pattern = copy.deepcopy({key: config[key] for key in ('bpm', 'subdivision', 'sequence_length', 'sequence_trigger', 'sequence')})
        self.bpm.setValue(config['bpm']); self.length.setValue(config['sequence_length'])
        self.division.setCurrentIndex(self.division.findData(config['subdivision']))
        self.trigger.setCurrentIndex(self.trigger.findData(config['sequence_trigger']))
        self.loading = False; self.refresh()

    def config(self): return copy.deepcopy(self.pattern)

    def set_schedule(self, notes, config):
        self.schedule = notes; self.times = [n['time'] for n in notes]; self.period = step_seconds(config)

    def set_time(self, seconds):
        index = bisect.bisect_right(self.times, seconds)-1
        step = self.schedule[index]['step'] if index >= 0 and seconds < self.times[index]+self.period else -1
        if step == self.active: return
        # Playback updates two indicators only, never selection or editor text.
        for i in (self.active, step):
            if i >= 0: self.cells[i].playing = i == step; self.cells[i].update()
        self.active = step

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            watched.lineEdit().setText(watched.textFromValue(watched.value()) + watched.suffix())
            self.focus_step(self.selected); return True
        return super().eventFilter(watched, event)
