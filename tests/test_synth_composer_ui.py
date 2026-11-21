import copy
import os
import subprocess
import time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QTableWidget, QPushButton
from nebula.ui.synth_studio import SynthStudio
from nebula.documents.synth_composition import compile_composition, load_composition
from nebula.documents.synth_sequence import render_sequence_frame, reference_sequence

def wait_until(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('Composer did not settle')

def choose_starter(window, identifier):
    window.starter_combo.setCurrentIndex(window.starter_combo.findData(identifier))
    window.load_starter_button.click()

@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    window = SynthStudio()
    window.show()
    app.processEvents()
    yield window
    for child in window.detail_windows:
        child.close()
    window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
