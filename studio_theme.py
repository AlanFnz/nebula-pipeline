"""Terminal-inspired chrome for the native editors, independent of rendering."""
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette, QIcon

from _version import __version__


COLORS = {
    "background": "#0c110e",
    "monitor": "#060a08",
    "panel": "#101812",
    "selected": "#1b2c20",
    "border": "#304536",
    "text": "#d6e3d4",
    "muted": "#94aa98",
    "accent": "#b5e49b",
    "cursor": "#d6a3ce",
}

STYLE = """
QWidget { background: #0c110e; color: #d6e3d4; font-size: 12px; }
QMainWindow { background: #0c110e; }
QLabel { background: transparent; }
QLabel#brand { color: #b5e49b; font-size: 22px; font-weight: 700; }
QLabel#muted { color: #94aa98; }
QLabel#sectionTitle { color: #b5e49b; font-size: 11px; font-weight: 600; }
QLabel#monitorMeta { color: #94aa98; font-size: 10px; }
QLabel#monitorState { color: #d6a3ce; font-size: 10px; }
QLabel#timecode { color: #b5e49b; border: 1px solid #304536; padding: 5px 7px; }
QFrame#monitorFrame { border: 1px solid #304536; background: #060a08; }
QWidget#monitorHeader { background: #101812; border-bottom: 1px solid #304536; }
QPushButton {
    background: #111b14; border: 1px solid #3b5141;
    border-radius: 0; padding: 6px 10px;
}
QPushButton:hover { background: #203225; border-color: #91b286; color: #e3f1dd; }
QPushButton:pressed, QPushButton:checked { background: #2b4230; border-color: #b5e49b; color: #cdefba; }
QPushButton:disabled { background: #0c110e; color: #65786a; border-color: #26382c; }
QPushButton#primary { background: #b5e49b; color: #0c110e; border-color: #b5e49b; font-weight: 700; }
QPushButton#primary:hover { background: #ceefbc; border-color: #ceefbc; }
QPushButton#primary:pressed { background: #94be7d; }
QPushButton#primary:disabled { background: #203225; color: #71856b; border-color: #304536; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background: #080e0a; border: 1px solid #3b5141; border-radius: 0;
    padding: 5px; selection-background-color: #b5e49b; selection-color: #0c110e;
}
QComboBox { padding-right: 22px; }
QComboBox::drop-down { width: 19px; border-left: 1px solid #304536; }
QComboBox::down-arrow { image: url("@CHEVRON@"); width: 8px; height: 6px; }
QComboBox QAbstractItemView { background: #101812; border: 1px solid #91b286; selection-background-color: #2b4230; selection-color: #e3f1dd; }
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { color: #718579; border-color: #26382c; }
QGroupBox { border: 1px solid #304536; border-radius: 0; margin-top: 14px; padding: 10px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 4px; color: #a7c19f; }
QTabWidget::pane { border: 1px solid #304536; top: -1px; }
QTabBar::tab { background: #0c110e; color: #94aa98; border: 1px solid #304536; padding: 6px 13px; margin-right: 3px; }
QTabBar::tab:selected { background: #18271d; color: #b5e49b; border-bottom: 2px solid #b5e49b; }
QTabBar::tab:hover { color: #d6e3d4; background: #18271d; }
QSlider { background: transparent; }
QSlider::groove:horizontal { background: #263d2c; height: 3px; }
QSlider::sub-page:horizontal { background: #7d9d70; height: 3px; }
QSlider::handle:horizontal { background: #b5e49b; border: 1px solid #d0f0be; width: 7px; margin: -5px 0; border-radius: 0; }
QSlider::handle:horizontal:hover { background: #e0f7d3; }
QScrollArea { border: none; }
QScrollBar:vertical { width: 10px; background: #0c110e; margin: 0; }
QScrollBar::handle:vertical { background: #405b45; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #7d9d70; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #0c110e; }
QScrollBar:horizontal { height: 10px; background: #0c110e; margin: 0; }
QScrollBar::handle:horizontal { background: #405b45; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: #7d9d70; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #0c110e; }
QSplitter::handle { background: #304536; }
QProgressBar { background: #080e0a; border: 1px solid #304536; border-radius: 0; text-align: center; color: #d6e3d4; }
QProgressBar::chunk { background: #405b45; }
QCheckBox { spacing: 5px; background: transparent; }
QCheckBox::indicator { width: 11px; height: 11px; border: 1px solid #607a62; background: #080e0a; }
QCheckBox::indicator:checked { background: #b5e49b; border-color: #b5e49b; }
QCheckBox::indicator:disabled { background: #17231a; border-color: #304536; }
QTableView { background: #0c110e; alternate-background-color: #111d15; gridline-color: #304536; selection-background-color: #2b4230; selection-color: #e3f1dd; }
QHeaderView::section { background: #18271d; color: #a7c19f; border: 1px solid #304536; padding: 5px; }
QToolTip { background: #1b2c20; color: #e3f1dd; border: 1px solid #7d9d70; padding: 6px; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus { border-color: #b5e49b; }
QSlider::handle:horizontal:focus { border-color: #d6a3ce; background: #e0f7d3; }
QCheckBox:focus { color: #b5e49b; }
""".replace("@CHEVRON@", (Path(__file__).parent / "assets" / "terminal-chevron.svg").as_posix())


def terminal_font():
    families = set(QFontDatabase.families())
    family = next((name for name in ("Menlo", "DejaVu Sans Mono", "Consolas", "Liberation Mono", "Andale Mono") if name in families), None)
    font = QFont(family) if family else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(11)
    return font


def apply_theme(app):
    app.setApplicationName("Nebula Studio")
    app.setApplicationDisplayName("Nebula Studio")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "nebula-icon.svg")))
    app.setStyle("Fusion")
    app.setFont(terminal_font())
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, COLORS["background"]),
                        (QPalette.ColorRole.Base, COLORS["monitor"]),
                        (QPalette.ColorRole.AlternateBase, COLORS["panel"]),
                        (QPalette.ColorRole.Button, COLORS["panel"]),
                        (QPalette.ColorRole.Text, COLORS["text"]),
                        (QPalette.ColorRole.WindowText, COLORS["text"]),
                        (QPalette.ColorRole.ButtonText, COLORS["text"]),
                        (QPalette.ColorRole.Highlight, COLORS["selected"]),
                        (QPalette.ColorRole.HighlightedText, COLORS["accent"])):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
