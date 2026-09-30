"""Close edited GUI fixtures without an unattended modal dialog."""
import pytest


@pytest.fixture(autouse=True)
def discard_unsaved_fixture_windows(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warning = QMessageBox.warning

    def answer(parent, title, *args, **kwargs):
        if title == 'Unsaved changes':
            return QMessageBox.StandardButton.Discard
        return warning(parent, title, *args, **kwargs)

    monkeypatch.setattr(QMessageBox, 'warning', answer)
