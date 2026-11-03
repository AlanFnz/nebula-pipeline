"""Undoable instrument drafts; one knob/slider drag is one history entry."""
import copy
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget, QAbstractSpinBox


class SoundHistory:
    def init_history(self):
        self.sound_undo=[];self.sound_redo=[];self.history_value=None
        self.history_gesture=False;self.gesture_recorded=False
        self.sound_undo_action=QAction('Undo sound edit',self)
        self.sound_redo_action=QAction('Redo sound edit',self)
        for action,shortcut,callback in ((self.sound_undo_action,QKeySequence.StandardKey.Undo,self.request_undo),
                                         (self.sound_redo_action,QKeySequence.StandardKey.Redo,self.request_redo)):
            action.setShortcut(shortcut);action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(callback);self.addAction(action)
        QApplication.instance().installEventFilter(self)
        self.refresh_history_actions()

    def reset_history(self):
        self.sound_undo.clear();self.sound_redo.clear();self.history_gesture=False;self.gesture_recorded=False
        self.history_value=copy.deepcopy(self.read_config());self.historyChanged.emit();self.refresh_history_actions()

    def begin_sound_gesture(self):self.history_gesture=True;self.gesture_recorded=False
    def end_sound_gesture(self):self.history_gesture=False;self.gesture_recorded=False

    def record_sound_edit(self):
        try:value=self.read_config()
        except ValueError:return
        if value==self.history_value:return
        if self.history_value is not None and (not self.history_gesture or not self.gesture_recorded):
            self.sound_undo.append(copy.deepcopy(self.history_value));self.sound_undo=self.sound_undo[-100:]
            self.gesture_recorded=True
        self.sound_redo.clear();self.history_value=copy.deepcopy(value)
        self.historyChanged.emit();self.refresh_history_actions()

    def restore_sound_history(self,source,destination):
        if not source:return False
        self.draft_timer.stop();destination.append(copy.deepcopy(self.history_value));value=source.pop()
        self.load_values(value);self.history_value=copy.deepcopy(value);self.end_sound_gesture()
        self.draftChanged.emit(value);self.historyChanged.emit();self.refresh_history_actions();return True

    def commit_pending_number(self):
        widget=QApplication.focusWidget()
        while widget and widget is not self:
            if isinstance(widget,QAbstractSpinBox) and self.isAncestorOf(widget):
                widget.interpretText();break
            widget=widget.parentWidget()
    def undo_draft(self):
        self.commit_pending_number()
        return self.restore_sound_history(self.sound_undo,self.sound_redo)
    def redo_draft(self):return self.restore_sound_history(self.sound_redo,self.sound_undo)

    def request_undo(self):
        if not self.undo_draft() and hasattr(self.parent(),'undo_composition'):self.parent().undo_composition()

    def request_redo(self):
        if not self.redo_draft() and hasattr(self.parent(),'redo_composition'):self.parent().redo_composition()

    def refresh_history_actions(self):
        undo=bool(self.sound_undo or getattr(self.parent(),'undo_compositions',[]))
        redo=bool(self.sound_redo or getattr(self.parent(),'redo_compositions',[]))
        self.sound_undo_action.setEnabled(undo);self.sound_redo_action.setEnabled(redo)
        self.undo_button.setEnabled(undo);self.redo_button.setEnabled(redo)

    def eventFilter(self,watched,event):
        if (event.type()==QEvent.Type.ShortcutOverride and isinstance(watched,QWidget)
                and watched.window() is self and
                (event.matches(QKeySequence.StandardKey.Undo) or event.matches(QKeySequence.StandardKey.Redo))):
            # Numeric fields otherwise consume Cmd-Z as text-only undo. The
            # instrument history restores the whole sound, including audition.
            if event.matches(QKeySequence.StandardKey.Undo):self.commit_pending_number()
            event.ignore();return True
        return super().eventFilter(watched,event)
