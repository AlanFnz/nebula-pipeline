"""Frequency knob with an optional chromatic note lock."""
import math
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel
from synth_sound_knob import SoundKnob
from synth_sound_sequence import frequency_note, note_frequency, note_name, SOLFEGE


class PitchControl(QWidget):
    valueChanged = Signal(float)

    def __init__(self, name, low, high):
        super().__init__(); self.low=low; self.high=high; self.loading=False;self.compact=False;self.name=name
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(3)
        self.knob=SoundKnob(name,low,high,1,' Hz',log=True); layout.addWidget(self.knob)
        # Preserve the existing accessible number/dial API.
        self.number=self.knob.number; self.dial=self.knob.dial
        self.mode=QComboBox(); self.mode.setAccessibleName(name+' tuning')
        self.mode.addItem('Free · Hz','hz'); self.mode.addItem('Notes','note'); layout.addWidget(self.mode)
        self.note=QComboBox(); self.note.setAccessibleName(name+' note'); layout.addWidget(self.note)
        self.description=QLabel(); layout.addWidget(self.description)
        self.compact_row=QWidget();self.compact_layout=QHBoxLayout(self.compact_row);self.compact_layout.setContentsMargins(0,0,0,0)
        self.compact_layout.addWidget(QLabel(name));layout.addWidget(self.compact_row);self.compact_row.hide()
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.note.currentIndexChanged.connect(self.change_note)
        self.knob.valueChanged.connect(self.change_frequency)
        self.setRange(low,high); self.load(low,'hz')

    def set_compact(self,compact):
        if compact==self.compact:return
        self.compact=compact
        if compact:
            for widget in (self.number,self.mode,self.note):self.compact_layout.addWidget(widget);widget.show()
            self.knob.hide();self.description.hide();self.compact_row.show()
        else:
            self.knob.layout().addWidget(self.number);self.knob.show()
            for widget in (self.mode,self.note,self.description):self.layout().addWidget(widget);widget.show()
            self.compact_row.hide()
        self.update_labels()

    def value(self):
        return note_frequency(self.note.currentData()) if self.mode.currentData()=='note' else self.knob.value()

    def tuning(self): return self.mode.currentData()
    def setValue(self,hz):
        self.load(hz,self.tuning()); self.valueChanged.emit(self.value())

    def setRange(self,low,high):
        self.low=low; self.high=high
        old=self.loading; self.loading=True
        self.knob.setRange(low,high)
        self.note.clear()
        first=math.ceil(69+12*math.log2(low/440.)-1e-9); last=math.floor(69+12*math.log2(high/440.)+1e-9)
        for n in range(first,last+1): self.note.addItem(f'{note_name(n)} · {SOLFEGE[n%12]}',n)
        self.loading=old

    def load(self,hz,mode):
        self.loading=True
        self.mode.setCurrentIndex(self.mode.findData(mode)); self.knob.setValue(hz)
        note=max(self.note.itemData(0),min(self.note.itemData(self.note.count()-1),frequency_note(hz)))
        self.note.setCurrentIndex(self.note.findData(note))
        if mode=='note': self.knob.setValue(note_frequency(note))
        self.loading=False; self.update_labels()

    def update_labels(self):
        locked=self.tuning()=='note'; self.note.setVisible(locked)
        n=frequency_note(self.value());self.number.setSingleStep(note_frequency(n+1)-note_frequency(n) if locked else 1.)
        self.description.setText(f'{self.value():.2f} Hz' if locked else note_name(frequency_note(self.value()))+' · nearest note')

    def change_mode(self):
        if self.loading: return
        self.load(self.knob.value(),self.tuning()); self.valueChanged.emit(self.value())

    def change_note(self):
        if self.loading: return
        self.loading=True; self.knob.setValue(note_frequency(self.note.currentData())); self.loading=False
        self.update_labels(); self.valueChanged.emit(self.value())

    def change_frequency(self,hz):
        if self.loading: return
        if self.tuning()=='note': self.load(hz,'note')
        self.update_labels(); self.valueChanged.emit(self.value())
