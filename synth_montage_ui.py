"""Native montage workspace: source selection, musical cuts and editable studies."""
from __future__ import annotations

import copy
import json
import math
import time
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool, QTimer, QSize, QRectF, QMimeData, QEvent, QSignalBlocker
from PySide6.QtGui import QImage, QPixmap, QIcon, QPainter, QColor, QPen, QDrag, QAction, QKeySequence
from PySide6.QtWidgets import (QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QAbstractItemView, QSplitter, QScrollArea,
    QFileDialog, QMessageBox, QDialogButtonBox, QInputDialog, QCheckBox, QProgressBar, QTabWidget, QToolTip)

from studio_widgets import SpinBox, DoubleSpinBox, Slider, ComboBox
from media import Cancellation
from synth_montage import (FORMAT, identifier, new_montage, normalize_montage, load_montage, save_montage,
    placements, source_duration, clip_project, add_asset, insert_clip, replace_clip, split_clip,
    treatment, apply_treatment, MontageRenderer, export_montage)
from synth_soundtrack_ui import SoundtrackLane, SoundtrackDialog
from synth_soundtrack_preview import SoundtrackPreview
from synth_output_ui import ExportSummaryButton, export_rows, PREVIEW_HINT, cache_caption
from synth_workspace_widgets import FlowLayout, inline
from synth_montage_selection import MontageSelection
from synth_montage_blocks import BlockBrowser, MontageBlockNavigation, block_details, clip_label, time_label


def image_packet(image): return image.size, image.convert('RGB').tobytes()


def pixmap(packet):
    (w,h), data = packet
    return QPixmap.fromImage(QImage(data, w, h, w*3, QImage.Format.Format_RGB888).copy())


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__(); self.function = function; self.cancel = Cancellation(); self.signals = TaskSignals()

    def run(self):
        try: self.signals.done.emit(self.function(self.cancel, self.signals.progress.emit))
        except Exception as error: self.signals.failed.emit(str(error))


class ImageMonitor(QLabel):
    def __init__(self, text='Select material to preview'):
        super().__init__(text); self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 180); self.original = None
        self.setStyleSheet('background:#090d0e; border:1px solid #354044;')

    def show_packet(self, packet):
        self.original = pixmap(packet); self.scale_image()

    def scale_image(self):
        if self.original: self.setPixmap(self.original.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event); self.scale_image()


class LibraryList(QListWidget):
    def __init__(self):
        super().__init__(); self.setIconSize(QSize(110,72)); self.setDragEnabled(True)
        self.setAccessibleName('Montage media library')

    def startDrag(self, actions):
        if not self.currentItem(): return
        mime = QMimeData(); mime.setData('application/x-nebula-asset', self.currentItem().data(Qt.ItemDataRole.UserRole).encode())
        drag = QDrag(self); drag.setMimeData(mime); drag.exec(Qt.DropAction.CopyAction)


class MontageTimeline(QWidget):
    selectRequested = Signal(str, bool)
    seekRequested = Signal(int)
    moveRequested = Signal(str, int)
    insertRequested = Signal(str, int)
    resizeRequested = Signal(str, int)
    editRequested = Signal(str)
    revealRequested = Signal(str)

    def __init__(self):
        super().__init__(); self.document = new_montage(); self.selected = set(); self.frame = 0
        self.scale = 65.; self.snap = True; self.gesture = None
        self.setFixedHeight(116); self.setAcceptDrops(True); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Montage timeline')
        self.setToolTip('Drag clips to reorder. Drag their right edge to trim. Drop library material to insert. Shift-click to select several clips.')

    def set_document(self, document, selected):
        self.document = document; self.selected = set(selected)
        total = sum(c['frames'] for c in document['clips'])
        self.setMinimumWidth(max(650, round(total / document['fps'] * self.scale)+24)); self.update()

    def x(self, frame): return 12 + frame / self.document['fps'] * self.scale
    def frame_at(self, x): return max(0, round((x-12) / self.scale * self.document['fps']))

    def rectangles(self):
        return [(c, a, b, QRectF(self.x(a), 30, max(2, self.x(b)-self.x(a)-2), 70)) for c,a,b in placements(self.document)]

    def insertion(self, x):
        rects = self.rectangles()
        return next((i for i,(_,a,b,r) in enumerate(rects) if x < r.center().x()), len(rects))

    def paintEvent(self, event):
        p = QPainter(self); p.fillRect(self.rect(), QColor('#121819'))
        p.setPen(QColor('#879391'))
        total = sum(c['frames'] for c in self.document['clips'])
        for second in range(int(total / self.document['fps'])+1):
            x=self.x(second*self.document['fps']); p.drawText(int(x),17,f'{second}s')
        for index,(clip,a,b,rect) in enumerate(self.rectangles(),1):
            chosen=clip['id'] in self.selected
            p.setBrush(QColor('#30493d' if chosen else '#20292c')); p.setPen(QColor('#acd991' if chosen else '#465153'))
            p.drawRoundedRect(rect,4,4)
            p.save(); p.setClipRect(rect.adjusted(4,2,-3,-2)); p.setPen(QColor('#e4e9e5'))
            label=clip_label(index,clip['name'],rect.width()-10,p.fontMetrics())
            p.drawText(rect.adjusted(5,4,-5,-2), Qt.AlignmentFlag.AlignTop, label)
            duration=f"{clip['frames']/self.document['fps']:.3f}s"
            if p.fontMetrics().horizontalAdvance(duration)<=rect.width()-10:
                p.drawText(rect.adjusted(5,35,-5,-2), Qt.AlignmentFlag.AlignTop, duration)
            p.restore()
        for marker in self.document['markers']:
            x=self.x(marker['frame']); p.setPen(QPen(QColor('#e7b8d8'),1)); p.drawLine(int(x),22,int(x),108)
        markers=self.document['markers']
        for index,marker in enumerate(markers):
            x=self.x(marker['frame'])
            next_x=self.x(markers[index+1]['frame']) if index+1<len(markers) else self.width()
            width=max(0,int(next_x-x-6))
            if width>18:
                label=p.fontMetrics().elidedText(marker['name'],Qt.TextElideMode.ElideRight,width)
                p.drawText(int(x)+3,28,label)
        p.setPen(QPen(QColor('#ffffff'),2)); x=int(self.x(self.frame)); p.drawLine(x,30,x,114)

    def event(self, event):
        if event.type()==QEvent.Type.ToolTip:
            text=''
            if event.pos().y()<30:
                markers=self.document['markers']
                for i,marker in enumerate(markers):
                    x=self.x(marker['frame'])
                    end=self.x(markers[i+1]['frame']) if i+1<len(markers) else self.width()
                    if x-3<=event.pos().x()<end-3:
                        text=f"{time_label(marker['frame'],self.document['fps'])} · {marker['name']}"; break
            else:
                for clip,a,b,rect in self.rectangles():
                    if rect.contains(event.pos()): text=block_details(self.document,clip['id']); break
            if text: QToolTip.showText(event.globalPos(),text,self)
            else: QToolTip.hideText()
            return True
        return super().event(event)

    def mousePressEvent(self, event):
        if event.button()!=Qt.MouseButton.LeftButton: return
        x=event.position().x(); self.setFocus()
        for clip,a,b,rect in self.rectangles():
            if rect.contains(event.position()):
                additive=bool(event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
                expected=self.selected ^ {clip['id']} if additive else {clip['id']}
                self.selectRequested.emit(clip['id'],additive)
                if self.selected != expected: return  # A pending timing edit can keep the current target.
                self.gesture=(clip['id'],x,a,b,abs(x-rect.right())<7)
                self.seekRequested.emit(a); return
        self.seekRequested.emit(self.frame_at(x))

    def mouseReleaseEvent(self, event):
        if not self.gesture: return
        key,x,a,b,trim = self.gesture; self.gesture=None
        target=event.position().x()
        if abs(target-x)<5: return
        if trim:
            frame=self.frame_at(target)
            if self.snap:
                near=[m['frame'] for m in self.document['markers'] if abs(self.x(m['frame'])-target)<10]
                if near: frame=min(near,key=lambda f:abs(f-frame))
            self.resizeRequested.emit(key,max(1,frame-a))
        else: self.moveRequested.emit(key,self.insertion(target))

    def mouseDoubleClickEvent(self, event):
        for clip,a,b,rect in self.rectangles():
            if rect.contains(event.position()): self.editRequested.emit(clip['id']); return

    def keyPressEvent(self,event):
        clips=self.document['clips']
        if not clips: return super().keyPressEvent(event)
        index=next((i for i,c in enumerate(clips) if c['id'] in self.selected),0)
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Home,Qt.Key.Key_End):
            if event.key()==Qt.Key.Key_Home: index=0
            elif event.key()==Qt.Key.Key_End: index=len(clips)-1
            else: index=max(0,min(len(clips)-1,index+(-1 if event.key()==Qt.Key.Key_Left else 1)))
            self.selectRequested.emit(clips[index]['id'],False)
            if self.selected != {clips[index]['id']}: event.accept(); return
            self.revealRequested.emit(clips[index]['id'])
            self.seekRequested.emit(sum(c['frames'] for c in clips[:index])); event.accept()
        elif event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            self.editRequested.emit(clips[index]['id']); event.accept()
        else: super().keyPressEvent(event)

    def dragEnterEvent(self,event):
        if event.mimeData().hasFormat('application/x-nebula-asset'): event.acceptProposedAction()

    def dragMoveEvent(self,event): self.dragEnterEvent(event)

    def dropEvent(self,event):
        key=bytes(event.mimeData().data('application/x-nebula-asset')).decode()
        if key in self.document['assets']:
            self.insertRequested.emit(key,self.insertion(event.position().x())); event.acceptProposedAction()


class SourceRangeDialog(QDialog):
    """Preview an original or a study, then choose a frame-accurate range."""
    def __init__(self, document, asset_id, parent=None, *, target=None, destination='End of timeline'):
        super().__init__(parent); self.setWindowTitle('Replace target block' if target else 'Insert range'); self.resize(800,690)
        self.document = copy.deepcopy(document); self.asset_id=asset_id; self.closed=False; self.pending=None; self.generation=0
        self.pool=QThreadPool.globalInstance()
        temp, self.clip_id=insert_clip(new_montage(document['canvas'],document['fps']) | {'assets':{asset_id:document['assets'][asset_id]}},asset_id,frames=1)
        self.duration=source_duration(temp,temp['clips'][0]); self.target=copy.deepcopy(target)
        self.total=max(1,math.ceil((self.duration-1e-8)*document['fps']))
        temp['clips'][0]['frames']=self.total; self.source=normalize_montage(temp)
        self.timer=QTimer(self); self.timer.setInterval(round(1000/document['fps'])); self.timer.timeout.connect(self.advance)
        layout=QVBoxLayout(self)
        asset=document['assets'][asset_id]
        self.context=QLabel(f"Material source: {asset['name']}\n{'Target' if target else 'Insert'}: {destination}")
        self.context.setWordWrap(True); self.context.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.context)
        rate=asset['footage']['fps'] if asset['kind']=='video' else asset['document']['fps']
        self.clock=QLabel(f"Range positions use the montage rate: {document['fps']} fps. Source: {rate:g} fps.\n"
                          'The source is sampled at these times; its playback speed is unchanged when inserted.')
        self.clock.setWordWrap(True); layout.addWidget(self.clock)
        self.monitor=ImageMonitor(); layout.addWidget(self.monitor,1)
        self.scrub=Slider(Qt.Orientation.Horizontal); self.scrub.setRange(0,self.total-1); self.scrub.setAccessibleName('Source preview frame'); layout.addWidget(self.scrub)
        row=QHBoxLayout(); self.play=QPushButton('Play'); self.play.setCheckable(True); self.play.toggled.connect(lambda b:self.timer.start() if b else self.timer.stop()); row.addWidget(self.play)
        self.timecode=QLabel(); row.addWidget(self.timecode)
        for label,callback in [('Set In [I]',self.set_in)]+([] if target else [('Set Out [O]',self.set_out)]):
            button=QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row); form=QFormLayout()
        self.start=SpinBox(); self.start.setRange(0,self.total-1); self.start.setAccessibleName('Source In frame')
        self.end=DoubleSpinBox() if target else SpinBox()
        if target: self.end.setDecimals(12)
        self.end.setRange(0 if target else 1,432000*16 if target else self.total); self.end.setValue(self.total); self.end.setAccessibleName('Source Out frame exclusive')
        form.addRow('In · frame',self.start); form.addRow('Out · frame (exclusive)',self.end); layout.addLayout(form)
        self.note=QLabel()
        self.note.setWordWrap(True); layout.addWidget(self.note)
        if target: self.end.setEnabled(False)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.confirm=buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        for key,callback in [('I',self.set_in),('O',self.set_out)]:
            action=QAction(self); action.setShortcut(QKeySequence(key)); action.triggered.connect(callback); self.addAction(action)
        self.preview_error=QLabel(); self.preview_error.setWordWrap(True); self.preview_error.hide(); layout.addWidget(self.preview_error)
        self.start.valueChanged.connect(self.refresh_range)
        if not target: self.end.valueChanged.connect(self.refresh_range)
        self.refresh_range(); self.scrub.valueChanged.connect(self.preview); QTimer.singleShot(0,self.preview)

    def refresh_range(self,*_):
        start=self.start.value(); fps=self.document['fps']
        if self.target:
            frames=self.target['frames']; speed=self.target['speed']; last=start+(frames-1)*speed
            self.end.setValue(start+frames*speed)
            self.valid=last/fps < self.duration-1e-8
            summary=f"Keeps target duration ({frames} frames · {frames/fps:.3f}s), speed ({speed:g}×) and treatment.\n"
            summary+=f"Source samples: {start:g} through {last:g} at {fps} fps. Out is the next step boundary."
            if not self.valid: summary+='\nThis range exceeds the source. Choose an earlier In point or a longer material.'
            self.confirm.setText('Replace target block')
        else:
            end=self.end.value(); frames=end-start; self.valid=0<=start<end<=self.total
            summary=f'In {start} inclusive · Out {end} exclusive · {max(0,frames)} frames at {fps} fps.\n'
            summary+=f'Adds {max(0,frames)/fps:.3f}s to the timeline. Insertion uses the stated boundary, not the playhead.'
            if not self.valid: summary+='\nOut must be after In and inside the source.'
            self.confirm.setText(f'Insert {max(0,frames)}-frame range')
        self.note.setText(summary); self.confirm.setEnabled(self.valid)

    def set_in(self): self.start.setValue(self.scrub.value())
    def set_out(self):
        if self.target is None: self.end.setValue(self.scrub.value()+1)
    def advance(self): self.scrub.setValue((self.scrub.value()+1)%self.total)

    def preview(self,*_):
        frame=self.scrub.value(); fps=self.document['fps']; self.timecode.setText(f'{frame/fps:.3f}s · frame {frame}')
        if self.pending: return
        self.generation+=1; generation=self.generation
        def render(cancel,progress):
            with MontageRenderer(self.source,cancel,preview=True) as r:
                c=self.source['canvas']; ratio=min(640/c['width'],420/c['height'])
                return image_packet(r.frame(frame,(round(c['width']*ratio),round(c['height']*ratio))))
        task=Task(render); self.pending=task
        def done(packet):
            self.pending=None
            if not self.closed:
                self.monitor.show_packet(packet)
                if self.scrub.value()!=frame: self.preview()
        def failed(error):
            self.pending=None
            if not self.closed: self.preview_error.setText(error); self.preview_error.show()
        task.signals.done.connect(done); task.signals.failed.connect(failed); self.pool.start(task)

    def accept(self):
        self.start.interpretText(); self.end.interpretText(); self.refresh_range()
        if not self.valid: return
        super().accept()

    def done(self,result):
        self.closed=True; self.timer.stop()
        if self.pending: self.pending.cancel.cancel()
        super().done(result)


class MontageWindow(MontageSelection, MontageBlockNavigation, QMainWindow):
    def __init__(self,document=None,path=None,parent=None,*,embedded=False):
        super().__init__(parent,Qt.WindowType.Widget if embedded else Qt.WindowType.Window)
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
            self.menuBar().setNativeMenuBar(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.workspace_navigation=None; self.preview_suspended=False
        self.document=normalize_montage(document or new_montage()); self.path=Path(path) if path else None
        self.clean=copy.deepcopy(self.document); self.undo_stack=[]; self.redo_stack=[]; self.selected=set(); self.frame=0
        self.timing_key=None; self.timing_base=None
        self.previous_timeline_view=None; self.view_request=0
        self.revision=0; self.identity=object(); self.closed=False; self.pending=[]; self.preview_task=None; self.prepare_task=None; self.export_task=None; self.editors=[]
        self.cache=OrderedDict(); self.cache_bytes=0; self.look=None; self.thumbnails={}; self.pool=QThreadPool(self); self.pool.setMaxThreadCount(2)
        self.audio=SoundtrackPreview(self); self.timer=QTimer(self); self.timer.setInterval(25); self.timer.timeout.connect(self.tick)
        self.resize(1360,900); self.build(); self.refresh(); self.audio.statusChanged.connect(self.status.setText)
        QTimer.singleShot(0,self.initialize_media)

    def initialize_media(self):
        if self.closed: return
        for key in list(self.document['assets'])[:32]: self.thumbnail(key)
        self.refresh_waveform()

    def refresh_waveform(self):
        track=copy.deepcopy(self.document.get('soundtrack'))
        identity=self.identity
        if track:
            from synth_soundtrack import waveform_peaks
            def done(peaks):
                if identity is self.identity and track==self.document.get('soundtrack'): self.wave.set_peaks(peaks)
            self.task(lambda c,p:waveform_peaks(track,c),done)

    def button(self,label,callback,layout):
        b=QPushButton(label); b.clicked.connect(callback); layout.addWidget(b); return b

    def build(self):
        root=QWidget(); layout=QVBoxLayout(root); self.setCentralWidget(root)
        top=QHBoxLayout(); brand=QLabel('nebula_  /  Montage'); brand.setObjectName('brand'); top.addWidget(brand)
        for label,method in [('Open',self.open_dialog),('Save',self.save),('Save as',lambda:self.save(True))]: self.button(label,method,top)
        self.undo_button=self.button('Undo',self.undo,top); self.redo_button=self.button('Redo',self.redo,top)
        top.addStretch(); self.export_button=self.button('Export MP4',self.export_dialog,top); self.export_button.setObjectName('primary')
        self.export_summary=ExportSummaryButton(self,self.export_summary_rows,self.export_button); top.addWidget(self.export_summary); layout.addLayout(top)
        split=QSplitter(); layout.addWidget(split,1)
        library=QWidget(); left=QVBoxLayout(library)
        self.material_tabs=QTabWidget(); self.material_tabs.setAccessibleName('Montage navigation'); left.addWidget(self.material_tabs,1)
        material=QWidget(); material_layout=QVBoxLayout(material); material_layout.setContentsMargins(0,4,0,0)
        self.button('Import videos / studies…',self.import_dialog,material_layout)
        self.library=LibraryList(); material_layout.addWidget(self.library,1)
        self.material_tabs.addTab(material,'Material')
        self.block_browser=BlockBrowser(); self.material_tabs.addTab(self.block_browser,'Block list')
        self.block_browser.selectionRequested.connect(self.select_from_block_list)
        self.block_browser.editRequested.connect(self.edit_from_block_list)
        self.library.currentItemChanged.connect(self.update_material_context)
        self.material_context=QLabel('Material source: None'); self.material_context.setWordWrap(True); self.material_context.setTextFormat(Qt.TextFormat.PlainText); left.addWidget(self.material_context)
        self.library.itemDoubleClicked.connect(lambda _:self.choose_range())
        self.insert_button=self.button('Insert range…',self.choose_range,left)
        self.replace_button=self.button('Replace target block…',self.replace_selected,left)
        self.material_hint=QLabel(); self.material_hint.setWordWrap(True); left.addWidget(self.material_hint)
        split.addWidget(library)
        center=QWidget(); middle=QVBoxLayout(center); self.monitor=ImageMonitor('Import videos or a study to begin'); middle.addWidget(self.monitor,1)
        transport=QHBoxLayout(); self.play=self.button('Play',self.toggle_play,transport); self.scrub=Slider(Qt.Orientation.Horizontal); self.scrub.setAccessibleName('Montage playhead'); transport.addWidget(self.scrub,1)
        self.timecode=QLabel(); transport.addWidget(self.timecode); self.detail=ComboBox(); self.detail.addItems(['360 px','720 px','Full canvas']); self.detail.setAccessibleName('Preview resolution'); self.detail.setToolTip(PREVIEW_HINT); self.detail.currentIndexChanged.connect(self.preview_detail_changed)
        middle.addLayout(transport); self.scrub.valueChanged.connect(self.seek)
        detail_host=QWidget(); detail_flow=FlowLayout(detail_host,spacing=6)
        self.preview_dimensions=QLabel(); self.preview_dimensions.setObjectName('monitorMeta')
        detail_flow.addWidget(inline(QLabel('Preview resolution'),self.detail,self.preview_dimensions)); middle.addWidget(detail_host)
        self.cache_status=QLabel(); self.cache_status.setWordWrap(True); self.cache_status.setObjectName('monitorMeta'); self.cache_status.setAccessibleName('Montage prepared frames'); middle.addWidget(self.cache_status)
        self.prepare_button=self.button('Prepare range',self.prepare,middle)
        self.prepare_button.setToolTip('Prepare a bounded playback range near the playhead at the selected resolution. Export renders every frame of the montage.')
        split.addWidget(center)
        inspector=QWidget(); right=QVBoxLayout(inspector); right.addWidget(QLabel('TARGET BLOCK'))
        self.clip_name=QLabel('Target: None'); self.clip_name.setWordWrap(True); self.clip_name.setTextFormat(Qt.TextFormat.PlainText); right.addWidget(self.clip_name)
        self.timing_empty=QLabel(); self.timing_empty.setWordWrap(True); right.addWidget(self.timing_empty)
        self.timing_fields=QWidget(); form=QFormLayout(self.timing_fields); form.setContentsMargins(0,0,0,0)
        self.source_in=DoubleSpinBox(); self.source_in.setDecimals(12); self.source_in.setRange(0,432000); self.source_in.setAccessibleName('Block source In frame')
        self.length=SpinBox(); self.length.setRange(1,432000); self.length.setAccessibleName('Clip duration frames')
        self.speed=DoubleSpinBox(); self.speed.setDecimals(12); self.speed.setRange(.05,16); self.speed.setValue(1); self.speed.setSuffix(' ×'); self.speed.setAccessibleName('Montage block speed')
        for label,control in [('Source In · frames',self.source_in),('Duration · frames',self.length),('Speed',self.speed)]: form.addRow(label,control)
        for control in (self.source_in,self.length,self.speed):
            control.setKeyboardTracking(False); control.valueChanged.connect(self.update_timing_state)
            control.lineEdit().textEdited.connect(self.timing_text_edited)
            control.editingFinished.connect(self.update_timing_state)
        right.addWidget(self.timing_fields)
        self.timing_state=QLabel(); self.timing_state.setWordWrap(True); self.timing_state.setTextFormat(Qt.TextFormat.PlainText); right.addWidget(self.timing_state)
        self.apply_timing_button=self.button('Apply timing',self.apply_timing,right)
        self.revert_timing_button=self.button('Revert timing draft',self.revert_timing,right)
        self.edit_button=self.button('Edit study / effects…',self.edit_selected,right)
        self.copy_button=self.button('Copy treatment',self.copy_look,right); self.paste_button=self.button('Apply treatment to selection',self.paste_look,right)
        self.duplicate_button=self.button('Duplicate selection',self.duplicate,right); self.remove_button=self.button('Remove selection',self.remove_selected,right)
        right.addWidget(QLabel('MUSIC MARKERS')); self.marker_list=QListWidget(); self.marker_list.setMaximumHeight(150); right.addWidget(self.marker_list)
        self.marker_list.setAccessibleName('Montage music markers')
        self.marker_context=QLabel(); self.marker_context.setWordWrap(True); self.marker_context.setTextFormat(Qt.TextFormat.PlainText); right.addWidget(self.marker_context)
        self.marker_list.currentItemChanged.connect(self.update_marker_context)
        self.marker_list.itemDoubleClicked.connect(lambda item:self.seek(item.data(Qt.ItemDataRole.UserRole)))
        self.button('Add marker at playhead…',self.add_marker,right); self.button('Remove marker',self.remove_marker,right)
        self.snap=QCheckBox('Snap clip edges to markers'); self.snap.setChecked(True); right.addWidget(self.snap)
        self.snap.toggled.connect(lambda b:setattr(self.timeline,'snap',b)); right.addStretch()
        inspector_scroll=QScrollArea(); inspector_scroll.setWidgetResizable(True); inspector_scroll.setWidget(inspector)
        inspector_scroll.setMinimumWidth(270); split.addWidget(inspector_scroll); split.setSizes([250,780,300])
        tools=QHBoxLayout()
        for label,method in [('Split at playhead',self.split),('Select all',self.select_all),('Soundtrack',self.soundtrack_dialog)]: self.button(label,method,tools)
        tools.addWidget(QLabel('Timeline zoom')); self.zoom_control=Slider(Qt.Orientation.Horizontal); self.zoom_control.setRange(25,220); self.zoom_control.setValue(65); self.zoom_control.setMaximumWidth(160); self.zoom_control.valueChanged.connect(self.zoom); self.zoom_control.setAccessibleName('Montage timeline zoom'); tools.addWidget(self.zoom_control)
        layout.addLayout(tools)
        identity=QHBoxLayout(); self.block_summary=QLabel(); self.block_summary.setWordWrap(True); self.block_summary.setTextFormat(Qt.TextFormat.PlainText); self.block_summary.setAccessibleName('Selected montage block'); identity.addWidget(self.block_summary,1)
        view_controls=QVBoxLayout(); self.show_block_button=self.button('Show selected block',self.show_selected_block,view_controls)
        self.show_block_button.setToolTip('Zoom and scroll to the selected block without moving playback.')
        self.previous_view_button=self.button('Previous view',self.restore_timeline_view,view_controls); self.previous_view_button.setEnabled(False)
        self.previous_view_button.setToolTip('Restore the timeline zoom and scroll from before Show selected block.')
        identity.addLayout(view_controls); layout.addLayout(identity)
        self.timeline=MontageTimeline(); self.timeline.selectRequested.connect(self.select_clip); self.timeline.seekRequested.connect(self.seek)
        self.timeline.revealRequested.connect(self.reveal_block)
        self.timeline.moveRequested.connect(self.move_clip); self.timeline.resizeRequested.connect(self.resize_clip); self.timeline.insertRequested.connect(self.drop_asset); self.timeline.editRequested.connect(lambda key:self.edit_clip(key))
        tracks=QWidget(); self.tracks=tracks; track_layout=QVBoxLayout(tracks); track_layout.setContentsMargins(0,0,0,0); track_layout.addWidget(self.timeline)
        self.wave=SoundtrackLane(); wave_row=QHBoxLayout(); wave_row.setContentsMargins(12,0,12,0); wave_row.addWidget(self.wave); wave_row.addStretch(); track_layout.addLayout(wave_row)
        self.wave.seekRequested.connect(lambda seconds:self.seek(round(seconds*self.document['fps']))); self.wave.editRequested.connect(self.soundtrack_dialog)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setWidget(tracks); self.scroll.setMinimumHeight(184); self.scroll.setMaximumHeight(210); layout.addWidget(self.scroll)
        self.status=QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        row=QHBoxLayout(); self.progress=QProgressBar(); self.progress.hide(); row.addWidget(self.progress)
        self.cancel_button=self.button('Cancel export',self.cancel_export,row); self.cancel_button.hide(); layout.addLayout(row)
        file_menu=self.menuBar().addMenu('File'); edit_menu=self.menuBar().addMenu('Edit')
        self.history_actions=[]
        for menu,label,key,callback in [
            (file_menu,'Open…','Ctrl+O',self.open_dialog),
            (file_menu,'Save','Ctrl+S',self.save),
            (file_menu,'Save as…','Ctrl+Shift+S',lambda:self.save(True)),
            (file_menu,'Export MP4…','',self.export_dialog),
            (file_menu,'Close window','Ctrl+W',lambda:self.window().close()),
            (edit_menu,'Undo','Ctrl+Z',self.undo),(edit_menu,'Redo','Ctrl+Shift+Z',self.redo),
            (edit_menu,'Select all clips','Ctrl+A',self.select_all),
            (edit_menu,'Duplicate selection','Ctrl+D',self.duplicate),
            (edit_menu,'Remove selection','',self.remove_selected)]:
            action=QAction(label,self)
            if key: action.setShortcut(QKeySequence(key))
            action.triggered.connect(callback); menu.addAction(action)
            if label in ('Undo','Redo'): self.history_actions.append(action)

    def guarded(self,function):
        try: return function()
        except Exception as error: self.status.setText(str(error))

    def task(self,function,done,failed=None,priority=0):
        task=Task(function); self.pending.append(task)
        def complete(value):
            if task in self.pending: self.pending.remove(task)
            if not self.closed: done(value)
        def failure(error):
            if task in self.pending: self.pending.remove(task)
            if not self.closed: (failed or self.status.setText)(error)
        task.signals.done.connect(complete); task.signals.failed.connect(failure); self.pool.start(task,priority); return task

    def commit(self,document,*,selected=None):
        doc=normalize_montage(document)
        if doc==self.document: return
        self.stop(); self.undo_stack.append((self.document,set(self.selected))); self.undo_stack=self.undo_stack[-30:]; self.redo_stack=[]
        if selected is not None: self.selected=set(selected)
        self.document=doc; self.invalidate(); self.refresh()

    def invalidate(self):
        self.revision+=1; self.cache.clear(); self.cache_bytes=0
        self.refresh_preview_details()
        if self.preview_task: self.preview_task.cancel.cancel(); self.preview_task=None
        if self.prepare_task: self.prepare_task.cancel.cancel(); self.prepare_task=None

    def undo(self):
        if self.undo_stack and self.resolve_timing('undoing the montage edit'):
            self.stop(); self.redo_stack.append((self.document,set(self.selected))); self.document,self.selected=self.undo_stack.pop(); self.invalidate(); self.refresh()
            self.status.setText('Edit undone · '+(self.block_label(next(iter(self.selected))) if len(self.selected)==1 else 'no target selected' if not self.selected else f'{len(self.selected)} blocks selected'))
    def redo(self):
        if self.redo_stack and self.resolve_timing('redoing the montage edit') and self.redo_stack:
            self.stop(); self.undo_stack.append((self.document,set(self.selected))); self.document,self.selected=self.redo_stack.pop(); self.invalidate(); self.refresh()

    def refresh(self):
        self.setWindowTitle(f"Nebula · Montage / {self.document['name']}{' *' if self.document!=self.clean else ''}")
        self.undo_button.setEnabled(bool(self.undo_stack)); self.redo_button.setEnabled(bool(self.redo_stack))
        for action,stack in zip(self.history_actions,(self.undo_stack,self.redo_stack)): action.setEnabled(bool(stack))
        current=self.library.currentItem().data(Qt.ItemDataRole.UserRole) if self.library.currentItem() else None
        self.library.clear()
        for key,asset in self.document['assets'].items():
            uses=sum(c['asset']==key for c in self.document['clips'])
            item=QListWidgetItem(f"{asset['name']}\n{asset['kind'].title()} · {uses} use{'s' if uses!=1 else ''}"); item.setData(Qt.ItemDataRole.UserRole,key)
            if key in self.thumbnails: item.setIcon(QIcon(self.thumbnails[key]))
            self.library.addItem(item)
            if key==current: self.library.setCurrentItem(item)
        self.selected.intersection_update(c['id'] for c in self.document['clips'])
        self.update_track_geometry()
        total=sum(c['frames'] for c in self.document['clips']); self.scrub.blockSignals(True); self.scrub.setRange(0,max(0,total-1)); self.scrub.blockSignals(False)
        marker_item=self.marker_list.currentItem()
        marker_identity=marker_item.data(Qt.ItemDataRole.UserRole+1) if marker_item else None
        with QSignalBlocker(self.marker_list):
            self.marker_list.clear()
            for marker in self.document['markers']:
                text=f"{time_label(marker['frame'],self.document['fps'])} · {marker['name']}"
                item=QListWidgetItem(text); item.setToolTip(text); item.setData(Qt.ItemDataRole.UserRole,marker['frame'])
                item.setData(Qt.ItemDataRole.UserRole+1,(marker['frame'],marker['name'])); self.marker_list.addItem(item)
                if marker_identity==(marker['frame'],marker['name']): self.marker_list.setCurrentItem(item)
        self.update_marker_context(); self.refresh_block_navigation()
        track=self.document.get('soundtrack'); self.wave.set_track(track,total/self.document['fps']); self.audio.set_track(track)
        self.update_inspector(); self.seek(min(self.frame,max(0,total-1)))

    def update_track_geometry(self):
        self.timeline.set_document(self.document,self.selected)
        self.tracks.setMinimumWidth(self.timeline.minimumWidth())
        width=round(sum(c['frames'] for c in self.document['clips'])/self.document['fps']*self.timeline.scale)
        self.wave.setFixedWidth(max(1,width))
    def zoom(self,value):
        with QSignalBlocker(self.zoom_control): self.zoom_control.setValue(value)
        self.timeline.scale=value; self.update_track_geometry()

    def seek(self,frame):
        total=sum(c['frames'] for c in self.document['clips']); self.frame=max(0,min(int(frame),max(0,total-1)))
        self.scrub.blockSignals(True); self.scrub.setValue(self.frame); self.scrub.blockSignals(False)
        self.timeline.frame=self.frame; self.timeline.update(); self.wave.set_time(self.frame/self.document['fps'])
        self.timecode.setText(f"{self.frame/self.document['fps']:.2f} / {total/self.document['fps']:.2f}s")
        if not self.timer.isActive(): self.audio.sync(self.frame/self.document['fps'],False)
        elif abs(self.frame-(time.monotonic()-self.anchor)*self.document['fps'])>2:
            self.anchor=time.monotonic()-self.frame/self.document['fps']; self.audio.sync(self.frame/self.document['fps'],True,force=True)
        self.request_frame()

    def preview_size(self):
        canvas=self.document['canvas']; edge=[360,720,max(canvas['width'],canvas['height'])][self.detail.currentIndex()]
        ratio=min(1.,edge/max(canvas['width'],canvas['height']))
        return max(1,round(canvas['width']*ratio)),max(1,round(canvas['height']*ratio))

    def refresh_preview_details(self):
        if not hasattr(self,'cache_status'): return
        size=self.preview_size(); total=sum(c['frames'] for c in self.document['clips'])
        ready=sum(revision==self.revision and dimensions==size and 0<=frame<total for revision,dimensions,frame in self.cache)
        self.preview_dimensions.setText(f'{size[0]} × {size[1]} px')
        self.preview_dimensions.setToolTip(PREVIEW_HINT)
        self.cache_status.setText(cache_caption('Montage',ready,total))
        self.cache_status.setToolTip('Prepared frames at this resolution for the current montage edits. Preparation can cover a bounded range; export always renders the entire montage.')

    def preview_detail_changed(self,*_):
        if self.prepare_task:
            self.prepare_task.cancel.cancel(); self.prepare_task=None
        self.refresh_preview_details()
        self.status.setText('Preview resolution changed · updating the monitor')
        self.request_frame()

    def cache_packet(self,key,packet,*,refresh=True):
        if key in self.cache: return
        self.cache[key]=packet; self.cache_bytes+=len(packet[1])
        while self.cache_bytes>256*1024**2 and len(self.cache)>1:
            _,p=self.cache.popitem(last=False); self.cache_bytes-=len(p[1])
        if refresh: self.refresh_preview_details()

    def request_frame(self,*_):
        if self.preview_suspended: return
        if not self.document['clips'] or self.closed: return
        size=self.preview_size(); key=(self.revision,size,self.frame)
        if key in self.cache: self.monitor.show_packet(self.cache[key]); return
        if self.preview_task: return
        doc=copy.deepcopy(self.document); frame=self.frame; revision=self.revision
        def render(cancel,progress):
            with MontageRenderer(doc,cancel,preview=True) as renderer: return image_packet(renderer.frame(frame,size))
        def done(packet):
            if self.preview_task is task: self.preview_task=None
            if revision!=self.revision: self.request_frame(); return
            self.cache_packet(key,packet)
            if frame==self.frame and size==self.preview_size(): self.monitor.show_packet(packet)
            else: self.request_frame()
        def failed(error):
            if self.preview_task is task: self.preview_task=None
            if revision==self.revision: self.status.setText(error)
        task=self.task(render,done,failed,priority=1); self.preview_task=task

    def prepare(self):
        if not self.document['clips']: return
        if self.prepare_task: self.prepare_task.cancel.cancel()
        doc=copy.deepcopy(self.document); revision=self.revision; size=self.preview_size()
        total=sum(c['frames'] for c in doc['clips']); capacity=max(1,(220*1024**2)//(size[0]*size[1]*3))
        first=0 if total<=capacity else self.frame; last=min(total,first+capacity)
        self.status.setText(f'Preparing montage range · 0/{last-first} frames · {first/doc["fps"]:.2f}–{last/doc["fps"]:.2f}s')
        def render(cancel,progress):
            packets=[]
            with MontageRenderer(doc,cancel,preview=True) as renderer:
                for frame in range(first,last):
                    cancel.check(); packets.append((frame,image_packet(renderer.frame(frame,size)))); progress(frame-first+1,last-first)
            return packets
        def done(packets):
            if self.prepare_task is not task or revision!=self.revision or size!=self.preview_size(): return
            self.prepare_task=None
            for frame,packet in packets: self.cache_packet((revision,size,frame),packet,refresh=False)
            self.refresh_preview_details()
            self.status.setText(f'Prepared range · {first/doc["fps"]:.2f}–{last/doc["fps"]:.2f}s · see montage frame count'); self.request_frame()
        def failed(error):
            if self.prepare_task is task:
                self.prepare_task=None; self.status.setText(f'Preview preparation stopped: {error}')
        task=self.task(render,done,failed); self.prepare_task=task
        def progress(done,total):
            if self.prepare_task is task:
                self.status.setText(f'Preparing montage range · {done}/{total} frames')
        task.signals.progress.connect(progress)

    def toggle_play(self):
        if self.timer.isActive(): self.stop(); return
        if not self.document['clips']: return
        self.anchor=time.monotonic()-self.frame/self.document['fps']; self.play.setText('Pause')
        self.audio.sync(self.frame/self.document['fps'],True,force=True); self.timer.start()
    def stop(self):
        self.timer.stop(); self.play.setText('Play'); self.audio.sync(self.frame/self.document['fps'],False)
    def tick(self):
        frame=round((time.monotonic()-self.anchor)*self.document['fps'])
        if frame>=sum(c['frames'] for c in self.document['clips']): self.stop(); return
        self.seek(frame)

    def import_dialog(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Import videos or native studies','','Media (*.mp4 *.mov *.mkv *.m4v *.webm *.json)')
        if paths: self.import_paths(paths)

    def import_paths(self,paths):
        from synth_video import inspect_video
        from synth_composition import load_composition
        self.status.setText('Importing material…'); identity=self.identity
        def inspect(cancel,progress):
            imported=[]
            for path in paths:
                cancel.check()
                if Path(path).suffix.lower()=='.json':
                    doc=load_composition(path); imported.append(dict(name=doc['name'],study=doc))
                else: imported.append(dict(name=Path(path).stem,footage=inspect_video(path)))
            return imported
        def done(items):
            if identity is not self.identity: return
            document=self.document; keys=[]
            for item in items: document,key=add_asset(document,**item); keys.append(key)
            self.commit(document); self.status.setText(f'{len(items)} items imported. Double-click to choose a range.')
            for key in keys: self.thumbnail(key)
        self.task(inspect,done)

    def thumbnail(self,key):
        doc=copy.deepcopy(self.document)
        def render(cancel,progress):
            temp=new_montage(doc['canvas'],doc['fps']); temp['assets']={key:doc['assets'][key]}; temp,_=insert_clip(temp,key,frames=1)
            with MontageRenderer(temp,cancel,preview=True) as renderer: return image_packet(renderer.frame(0,(110,72)))
        def done(packet):
            self.thumbnails[key]=pixmap(packet)
            for i in range(self.library.count()):
                item=self.library.item(i)
                if item.data(Qt.ItemDataRole.UserRole)==key: item.setIcon(QIcon(self.thumbnails[key]))
        self.task(render,done,lambda _:None,priority=-1)

    def library_key(self): return self.library.currentItem().data(Qt.ItemDataRole.UserRole) if self.library.currentItem() else None
    def choose_range(self,checked=False,*,asset=None,at=None,replace_id=None):
        key=asset or self.library_key()
        if key is None: self.status.setText('Select material in the library first.'); return
        if not self.resolve_timing('choosing a source range'): return
        clip=next((c for c in self.document['clips'] if c['id']==replace_id),None)
        if replace_id is not None and (clip is None or self.selected!={replace_id}):
            self.status.setText('Select exactly one target block to replace.'); return
        if at is None:
            at=max((i+1 for i,c in enumerate(self.document['clips']) if c['id'] in self.selected),default=len(self.document['clips']))
        at=max(0,min(len(self.document['clips']),at))
        destination=self.block_label(clip['id']) if clip else ('At the start of the timeline' if at==0 else 'After '+self.block_label(self.document['clips'][at-1]['id']))
        self.stop(); dialog=SourceRangeDialog(self.document,key,self,target=clip,destination=destination)
        if not dialog.exec(): return
        def apply():
            if clip: self.commit(replace_clip(self.document,clip['id'],key,dialog.start.value()))
            else:
                doc,identifier=insert_clip(self.document,key,at,dialog.start.value(),dialog.end.value()-dialog.start.value()); self.commit(doc,selected={identifier})
            self.status.setText(('Replaced ' if clip else 'Inserted ')+self.block_label(self.active_clip()['id'])+' · Save stores the montage.')
        self.guarded(apply)
    def replace_selected(self):
        clip=self.active_clip()
        if clip: self.choose_range(replace_id=clip['id'])
        else: self.status.setText('Select exactly one timeline block and choose material in the library.')
    def drop_asset(self,key,index): self.choose_range(asset=key,at=index)

    def resize_clip(self,key,frames):
        if not self.resolve_timing('trimming a block'): return
        doc=copy.deepcopy(self.document); next(c for c in doc['clips'] if c['id']==key)['frames']=frames; self.guarded(lambda:self.commit(doc))
    def move_clip(self,key,index):
        if not self.resolve_timing('moving a block'): return
        doc=copy.deepcopy(self.document); old=next(i for i,c in enumerate(doc['clips']) if c['id']==key)
        clip=doc['clips'].pop(old); doc['clips'].insert(index-(old<index),clip); self.commit(doc)
    def duplicate(self):
        if not self.selected or not self.resolve_timing('duplicating blocks'): return
        doc=copy.deepcopy(self.document); copies=[copy.deepcopy(c) for c in doc['clips'] if c['id'] in self.selected]
        after=max(i for i,c in enumerate(doc['clips']) if c['id'] in self.selected)+1
        for clip in copies: clip['id']=identifier()
        doc['clips'][after:after]=copies; self.guarded(lambda:self.commit(doc))
    def remove_selected(self):
        if not self.selected or not self.resolve_timing('removing blocks'): return
        doc=copy.deepcopy(self.document); doc['clips']=[c for c in doc['clips'] if c['id'] not in self.selected]; self.commit(doc)
    def split(self):
        if self.resolve_timing('splitting a block'): self.guarded(lambda:self.commit(split_clip(self.document,self.frame)))
    def copy_look(self):
        clip=self.active_clip()
        if clip:
            self.look=treatment(self.document,clip); self.update_inspector(); self.status.setText('Treatment copied. Select target blocks and apply it.')
    def paste_look(self):
        if self.look and self.selected and self.resolve_timing('applying a treatment'): self.guarded(lambda:self.commit(apply_treatment(self.document,self.selected,self.look)))

    def edit_selected(self):
        clip=self.active_clip()
        if clip: self.edit_clip(clip['id'])
    def edit_clip(self,key):
        if not self.resolve_timing('editing a block'): return
        from synth_navigation import WorkspaceNavigation
        navigation=self.workspace_navigation or WorkspaceNavigation(self)
        return navigation.edit_clip(self,key)
    def apply_editor(self,key,editor):
        navigation=self.workspace_navigation
        if navigation and navigation.editor is editor and navigation.clip_id==key:
            return navigation.return_to_montage()

    def add_marker(self):
        name,ok=QInputDialog.getText(self,'Music marker','Name:',text=f'Cut {len(self.document["markers"])+1}')
        if ok:
            doc=copy.deepcopy(self.document); doc['markers'].append(dict(frame=self.frame,name=name)); self.commit(doc)
    def remove_marker(self):
        row=self.marker_list.currentRow()
        if row>=0:
            doc=copy.deepcopy(self.document); doc['markers'].pop(row); self.commit(doc)

    def soundtrack_dialog(self):
        from synth_soundtrack import probe_soundtrack, waveform_peaks
        dialog=SoundtrackDialog(self); self.sound_dialog=dialog
        def load():
            path,_=QFileDialog.getOpenFileName(self,'Choose soundtrack','','Audio (*.wav *.mp3 *.m4a *.aif *.aiff *.flac)')
            if not path: return
            def done(track):
                doc=copy.deepcopy(self.document); doc['soundtrack']=track; self.commit(doc); refresh(); peaks()
            self.task(lambda c,p:probe_soundtrack(path,c),done)
        def refresh(): dialog.set_track(self.document.get('soundtrack'),sum(c['frames'] for c in self.document['clips'])/self.document['fps'])
        def peaks():
            self.refresh_waveform()
        def apply(track):
            doc=copy.deepcopy(self.document); doc['soundtrack']=track; self.guarded(lambda:self.commit(doc)); refresh(); peaks()
        def remove():
            doc=copy.deepcopy(self.document); doc.pop('soundtrack',None); self.commit(doc); refresh()
        dialog.importRequested.connect(load); dialog.relinkRequested.connect(load); dialog.removeRequested.connect(remove)
        dialog.trackEdited.connect(apply); dialog.monitorVolumeChanged.connect(self.audio.set_monitor_volume); dialog.monitorMutedChanged.connect(self.audio.set_monitor_muted)
        # Assembly soundtracks are an absolute project track; source mixing is a later feature.
        index=dialog.export_audio.findData('footage'); dialog.export_audio.removeItem(index)
        dialog.reactivity_button.hide(); refresh(); peaks(); dialog.show()

    def save(self,save_as=False):
        if not self.resolve_timing('saving the montage'): return False
        path=str(self.path) if self.path and not save_as else QFileDialog.getSaveFileName(self,'Save montage',str(self.path or Path.home()/'Untitled.montage.json'),'Nebula montage (*.json)')[0]
        if not path: return False
        try: save_montage(path,self.document)
        except Exception as error: self.status.setText(str(error)); return False
        self.path=Path(path); self.clean=copy.deepcopy(self.document); self.refresh(); self.status.setText('Montage saved.'); return True
    def may_replace(self):
        if not self.resolve_timing('closing or opening another document'): return False
        if self.document==self.clean: return True
        answer=QMessageBox.question(self,'Save montage?','Save your changes before closing?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        return self.save() if answer==QMessageBox.StandardButton.Save else answer==QMessageBox.StandardButton.Discard
    def open_dialog(self):
        if self.workspace_navigation and self.workspace_navigation.host is not self:
            return self.workspace_navigation.host.load_sequence_dialog()
        if any(editor.isVisible() for editor in self.editors):
            self.status.setText('Apply or close the open clip editor before opening another montage.'); return
        path,_=QFileDialog.getOpenFileName(self,'Open montage','','Nebula montage (*.json)')
        if not path or not self.may_replace(): return
        def load():
            doc=load_montage(path); self.stop(); self.identity=object(); self.document=doc; self.clean=copy.deepcopy(doc); self.path=Path(path); self.undo_stack=[]; self.redo_stack=[]; self.invalidate(); self.refresh(); self.initialize_media()
        self.guarded(load)
    def export_summary_rows(self):
        rows=export_rows(self.document,montage=True)
        if self.has_timing_draft():
            rows.insert(-1,('Timing draft','Unapplied timing changes. Export will ask you to apply or revert them. Timing above describes the applied montage.'))
        return rows

    def export_dialog(self):
        if self.export_task or not self.document['clips']: return
        if not self.resolve_timing('exporting the montage'): return
        path,_=QFileDialog.getSaveFileName(self,'Export montage',str((self.path or Path.home()/'Montage').with_suffix('.mp4')),'MP4 video (*.mp4)')
        if path: self.start_export(path)
    def start_export(self,path):
        if not self.resolve_timing('exporting the montage'): return
        self.stop(); doc=copy.deepcopy(self.document); self.export_button.setEnabled(False); self.progress.show(); self.progress.setValue(0); self.cancel_button.show()
        self.status.setText('Rendering the complete montage at full canvas quality…')
        def finished(value):
            self.export_task=None; self.export_button.setEnabled(True); self.progress.hide(); self.cancel_button.hide(); self.status.setText(f'Export complete: {value}')
        def failed(error):
            self.export_task=None; self.export_button.setEnabled(True); self.progress.hide(); self.cancel_button.hide(); self.status.setText(f'Export stopped: {error}')
        task=self.task(lambda c,p:export_montage(doc,path,c,p),finished,failed); self.export_task=task
        task.signals.progress.connect(lambda a,b:self.progress.setValue(round(a*100/b)))
    def cancel_export(self):
        if self.export_task: self.export_task.cancel.cancel()
    def closeEvent(self,event):
        navigation=self.workspace_navigation
        if navigation:
            if not navigation.disposing:
                if navigation.host is not self:
                    self.window().close(); event.ignore(); return
                if not navigation.can_leave(): event.ignore(); return
                navigation.shutdown()
            self.closed=True; self.timer.stop(); self.audio.close()
            for task in self.pending: task.cancel.cancel()
            event.accept(); return
        if any(editor.isVisible() for editor in self.editors):
            self.status.setText('Apply or close the open clip editor before closing this montage.'); event.ignore(); return
        if self.export_task:
            self.status.setText('Cancel the export before closing the montage.'); event.ignore(); return
        if not self.may_replace(): event.ignore(); return
        self.closed=True; self.timer.stop(); self.audio.close()
        for task in self.pending: task.cancel.cancel()
        event.accept()
