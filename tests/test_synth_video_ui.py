import copy
import os
from pathlib import Path
import time
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication
from nebula.ui.synth_studio import SynthStudio
from nebula.documents.synth_composition import load_composition, save_composition
from nebula.sources.synth_video import VIDEO_EFFECTS, video_composition
from test_synth_video import clip

def wait_until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('Video studio did not settle')

@pytest.fixture
def window(clip, tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    window = SynthStudio(composition=video_composition(clip))
    window.show()
    wait_until(lambda: not window.render_running)
    yield window
    window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()
