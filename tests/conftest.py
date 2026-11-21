"""Close edited GUI fixtures without an unattended modal dialog."""
import pytest


@pytest.fixture(autouse=True)
def discard_unsaved_fixture_windows(monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance()
    existing = set(app.topLevelWidgets()) if isinstance(app, QApplication) else set()

    warning = QMessageBox.warning

    def answer(parent, title, *args, **kwargs):
        if title == 'Unsaved changes':
            return QMessageBox.StandardButton.Discard
        return warning(parent, title, *args, **kwargs)

    monkeypatch.setattr(QMessageBox, 'warning', answer)
    from nebula.ui.synth_sound_session_ui import SoundSession
    monkeypatch.setattr(SoundSession, 'choose_pending_sound', lambda *_, **__: 'discard')
    yield
    app = QApplication.instance()
    if isinstance(app, QApplication):
        # Closing a Qt widget can leave its entire tree alive until process exit.
        for window in app.topLevelWidgets():
            if window not in existing and window.parent() is None and not window.isVisible():
                window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
