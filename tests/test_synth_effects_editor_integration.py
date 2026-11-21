"""The focused editor participates in the real workspace and document lifecycle."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QPoint, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from nebula.ui.studio_theme import apply_theme
from nebula.documents.synth_composition import load_composition
from nebula.effects.synth_effects import effect_preset
from nebula.documents.synth_sequence import reference_sequence
from nebula.documents.synth_starters import starter_composition
from nebula.ui.synth_studio import SynthStudio

@pytest.fixture
def make_window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    windows = []

    def make(**kwargs):
        window = SynthStudio(**kwargs)
        windows.append(window)
        window.resize(1280, 800)
        window.show()
        app.processEvents()
        return window
    yield make
    for window in windows:
        window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
