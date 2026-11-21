"""Companion for Nebula Studio. Does not modify a Live Set or intercept notes."""
import time
from _Framework.ControlSurface import ControlSurface
from .watch import InstrumentWatcher, REFRESH_PREFIX


class NebulaVisuals(ControlSurface):
    def __init__(self, c_instance):
        super(NebulaVisuals, self).__init__(c_instance)
        self._watcher = InstrumentWatcher()
        self._reported_error = False
        self.log_message('Nebula Visuals: instrument recovery enabled')

    def update_display(self):
        super(NebulaVisuals, self).update_display()
        try:
            for channel in self._watcher.update(self.song().tracks, time.monotonic()):
                self._send_midi(REFRESH_PREFIX + (channel, 0xF7))
                self.log_message('Nebula Visuals: restore channel %d' % (channel + 1))
            self._reported_error = False
        except Exception as exc:
            if not self._reported_error:
                self.log_message('Nebula Visuals: recovery unavailable: %s' % exc)
            self._reported_error = True
