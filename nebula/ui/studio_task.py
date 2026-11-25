"""Cancellable Qt worker shared by the export and montage windows."""
from PySide6.QtCore import QObject, QRunnable, Signal

from nebula.core.media import Cancellation, Cancelled


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.cancel = Cancellation()
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.done.emit(self.function(self.cancel, self.signals.progress.emit))
        except Cancelled:
            self.signals.failed.emit('Cancelled')
        except Exception as error:
            self.signals.failed.emit(str(error))
