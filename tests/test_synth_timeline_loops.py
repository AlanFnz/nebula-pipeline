"""Timeline gestures and sequence loops preserve ordering, state and edits."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from nebula.documents.synth_composition import compile_composition, load_composition, normalize_composition, reference_composition, save_composition, section_placements, section_ranges
from nebula.ui.synth_studio import SynthStudio

@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    from pathlib import Path
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    window = SynthStudio()
    window.resize(1440, 960)
    window.show()
    app.processEvents()
    yield window
    window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()

def click_section(window, occurrence, modifiers=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
    timeline = window.section_timeline
    point = timeline.rectangles()[occurrence].center().toPoint()
    QTest.mouseClick(timeline, button, modifiers, point)
    return point

def context_menu(window, occurrence):
    timeline = window.section_timeline
    point = click_section(window, occurrence, button=Qt.MouseButton.RightButton)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point, timeline.mapToGlobal(point))
    QApplication.sendEvent(timeline, event)
    assert timeline.context_menu.isVisible()
    return timeline.context_menu
