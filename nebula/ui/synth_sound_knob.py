"""Accessible rotary controls with vertical drag and direct numeric entry."""
import math
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QSignalBlocker
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QDial, QDoubleSpinBox


class SoundDial(QDial):
    def __init__(self,parent=None):
        super().__init__(parent);self.setRange(0,10000);self.setFixedSize(78,78)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.origin=None;self.number=None

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent=QColor('#acd88f' if self.isEnabled() else '#58625c');rect=QRectF(9,9,60,60)
        p.setPen(QPen(QColor('#39413f'),4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.drawArc(rect,225*16,-270*16)
        ratio=self.value()/10000
        p.setPen(QPen(accent,4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.drawArc(rect,225*16,round(-270*16*ratio))
        p.setPen(QPen(QColor('#829981' if self.hasFocus() else '#3d4742'),1));p.setBrush(QColor('#26312d'));p.drawEllipse(QRectF(17,17,44,44))
        angle=math.radians(225-270*ratio);center=QPointF(39,39)
        p.setPen(QPen(accent,3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawLine(center+QPointF(math.cos(angle)*11,-math.sin(angle)*11),center+QPointF(math.cos(angle)*20,-math.sin(angle)*20))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.setFocus();self.origin=(event.position().y(),self.value());self.setSliderDown(True);event.accept()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.origin is None: return
        scale=.15 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.
        self.setValue(round(self.origin[1]+(self.origin[0]-event.position().y())*65*scale));event.accept()

    def mouseReleaseEvent(self,event):
        self.origin=None;self.setSliderDown(False);event.accept()

    def wheelEvent(self,event): event.ignore()

    def keyPressEvent(self,event):
        directions={Qt.Key.Key_Up:1,Qt.Key.Key_Right:1,Qt.Key.Key_Down:-1,Qt.Key.Key_Left:-1}
        if self.number is not None and event.key() in directions:
            step=self.number.singleStep()
            if self.number.decimals() and event.modifiers() & Qt.KeyboardModifier.ShiftModifier: step*=.1
            self.number.setValue(self.number.value()+step*directions[event.key()]);event.accept()
        else: super().keyPressEvent(event)


class SoundNumber(QDoubleSpinBox):
    def wheelEvent(self,event): event.ignore()


class SoundKnob(QWidget):
    valueChanged=Signal(float)

    def __init__(self,name,low,high,step=1.,suffix='',*,log=False,integer=False,parent=None):
        super().__init__(parent);self.log=log;self.low=low;self.high=high;self.setMinimumWidth(106)
        layout=QVBoxLayout(self);layout.setContentsMargins(3,2,3,2);layout.setSpacing(2)
        label=QLabel(name);label.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(label)
        self.dial=SoundDial();self.dial.setAccessibleName(name+' knob');layout.addWidget(self.dial,0,Qt.AlignmentFlag.AlignHCenter)
        self.number=SoundNumber();self.number.setRange(low,high);self.number.setDecimals(0 if integer else 2);self.dial.number=self.number
        self.number.setSingleStep(step);self.number.setSuffix(suffix);self.number.setAccessibleName(name)
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter);self.number.setFixedWidth(110)
        self.number.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons);self.number.setKeyboardTracking(False)
        layout.addWidget(self.number,0,Qt.AlignmentFlag.AlignHCenter)
        self.dial.setToolTip('Drag up/down. Shift: fine adjustment. Arrow keys: adjust. Type a value below.')
        self.number.valueChanged.connect(self._number_changed);self.dial.valueChanged.connect(self._dial_changed);self.setValue(low)

    def value(self): return self.number.value()
    def setValue(self,value): self.number.setValue(value);self._sync_dial()
    def setRange(self,low,high):
        self.low=low;self.high=high;self.number.setRange(low,high);self._sync_dial()

    def _sync_dial(self):
        value=self.number.value()
        ratio=math.log(value/self.low)/math.log(self.high/self.low) if self.log else (value-self.low)/(self.high-self.low)
        with QSignalBlocker(self.dial): self.dial.setValue(round(ratio*10000))

    def _number_changed(self,value): self._sync_dial();self.valueChanged.emit(value)
    def _dial_changed(self,position):
        ratio=position/10000;value=self.low*(self.high/self.low)**ratio if self.log else self.low+(self.high-self.low)*ratio
        self.number.setValue(value)
