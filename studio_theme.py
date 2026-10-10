"""Shared Studio chrome, independent of artwork and rendering."""
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette, QIcon

from _version import __version__


# Keep the original names stable: custom-painted timeline/viewer widgets use them.
# Green signals an action or selection; ordinary surfaces and borders are neutral.
COLORS = {
    "background": "#171a1c",
    "monitor": "#0b0d0f",
    "panel": "#1e2225",
    "selected": "#304336",
    "border": "#3b4246",
    "text": "#eceee9",
    "muted": "#a4adad",
    "accent": "#b3d99c",
    "cursor": "#d2aed2",
    "canvas": "#0b0d0f",
    "input": "#131719",
    "raised": "#282e31",
    "hover": "#323a3e",
    "border_hover": "#657175",
    "selection": "#304336",
    "selection_text": "#eef5e9",
    "on_accent": "#182015",
    "accent_hover": "#c5e8b0",
    "accent_pressed": "#9dbf88",
    "focus": "#c5e8b0",
    "disabled": "#737d80",
    "disabled_surface": "#202528",
    "disabled_border": "#30373a",
    "warning": "#dec58f",
    "destructive": "#e6a096",
}

_STYLE = """
QWidget { background: @background@; color: @text@; font-size: 12px; }
QMainWindow, QDialog { background: @background@; }
QWidget#inspectorSurface { background: @panel@; }
QWidget:disabled { color: @disabled@; }
QLabel { background: transparent; }
QLabel#brand { color: @accent@; font-size: 22px; font-weight: 700; }
QLabel#muted { color: @muted@; }
QLabel#sectionTitle { color: @text@; font-size: 11px; font-weight: 600; }
QLabel#effectTitle { color: @text@; font-size: 15px; font-weight: 600; }
QLabel#controlGroup { color: @text@; font-size: 11px; font-weight: 600; border-top: 1px solid @border@; padding-top: 8px; margin-top: 8px; margin-bottom: 4px; }
QLabel#monitorMeta { color: @muted@; font-size: 11px; }
QLabel#monitorState { color: @cursor@; font-size: 11px; }
QLabel#timecode { color: @text@; background: @input@; border: 1px solid @border@; border-radius: 4px; padding: 5px 7px; }
QLabel[warning="true"] { color: @warning@; }
QLabel[destructive="true"] { color: @destructive@; }
QFrame#monitorFrame { border: 1px solid @border@; border-radius: 6px; background: @monitor@; }
QWidget#monitorHeader { background: @panel@; border-bottom: 1px solid @border@; }
QFrame#effectChoice { border: 1px solid @disabled_border@; border-radius: 4px; background: @panel@; }
QFrame#effectChoice[selected="true"] { border-color: @accent@; background: @selected@; }
QPushButton#effectChoiceButton { text-align: left; padding: 4px 6px; border: 1px solid transparent; background: transparent; }
QPushButton#effectChoiceButton:hover { background: @hover@; }
QPushButton#effectChoiceButton:focus { border-color: @focus@; }
QLabel#effectState { color: @muted@; font-size: 11px; }
QLabel#effectState[active="true"] { color: @accent@; }
QPushButton, QToolButton {
    background: @raised@; border: 1px solid @border@;
    border-radius: 4px; padding: 6px 10px;
}
QPushButton:hover, QToolButton:hover { background: @hover@; border-color: @border_hover@; }
QPushButton:pressed, QToolButton:pressed { background: @panel@; border-color: @border_hover@; }
QPushButton:checked, QToolButton:checked { background: @selected@; border-color: @accent@; color: @selection_text@; }
QPushButton:focus, QToolButton:focus { border-color: @focus@; }
QPushButton:disabled, QToolButton:disabled { background: @disabled_surface@; color: @disabled@; border-color: @disabled_border@; }
QPushButton#primary, QPushButton[primary="true"], QDialogButtonBox QPushButton:default {
    background: @accent@; color: @on_accent@; border-color: @accent@; font-weight: 600;
}
QPushButton#primary:hover, QPushButton[primary="true"]:hover, QDialogButtonBox QPushButton:default:hover { background: @accent_hover@; border-color: @accent_hover@; }
QPushButton#primary:pressed, QPushButton[primary="true"]:pressed, QDialogButtonBox QPushButton:default:pressed { background: @accent_pressed@; border-color: @accent_pressed@; }
QPushButton#primary:focus, QPushButton[primary="true"]:focus, QDialogButtonBox QPushButton:default:focus { border-color: @text@; }
QPushButton#primary:disabled, QPushButton[primary="true"]:disabled, QDialogButtonBox QPushButton:default:disabled { background: @selected@; color: @disabled@; border-color: @disabled_border@; }
QPushButton[secondaryAction="true"] { background: transparent; border-color: transparent; color: @muted@; }
QPushButton[secondaryAction="true"]:hover { background: @hover@; border-color: @border_hover@; color: @text@; }
QPushButton[secondaryAction="true"]:focus { border-color: @focus@; color: @text@; }
QPushButton[secondaryAction="true"]:checked { background: @selected@; border-color: @accent@; color: @selection_text@; }
QPushButton[secondaryAction="true"]:checked:hover { background: @selected@; border-color: @accent_hover@; color: @selection_text@; }
QPushButton[secondaryAction="true"]:checked:focus { background: @selected@; border-color: @focus@; color: @selection_text@; }
QPushButton[secondaryAction="true"]:disabled { background: transparent; border-color: transparent; color: @disabled@; }
QPushButton[secondaryAction="true"]:checked:disabled { background: @disabled_surface@; border-color: @disabled_border@; color: @disabled@; }
QPushButton[destructive="true"] { color: @destructive@; }
QPushButton[destructive="true"]:disabled { color: @disabled@; }
QPushButton#controlGroup { background: transparent; color: @text@; text-align: left; font-size: 11px; font-weight: 600; border: none; border-top: 1px solid @border@; border-radius: 0; padding: 6px 4px; margin-top: 4px; }
QPushButton#controlGroup:checked { background: transparent; color: @text@; border-top-color: @border@; }
QPushButton#controlGroup:hover { background: @raised@; }
QPushButton#controlGroup:focus { background: @selected@; color: @selection_text@; border-top-color: @focus@; }
QPushButton#controlGroup:disabled { color: @disabled@; border-top-color: @disabled_border@; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPlainTextEdit, QTextEdit {
    background: @input@; border: 1px solid @border@; border-radius: 4px;
    padding: 5px; selection-background-color: @accent@; selection-color: @on_accent@;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover { border-color: @border_hover@; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border-color: @focus@; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled { background: @disabled_surface@; color: @disabled@; border-color: @disabled_border@; }
QLineEdit[readOnly="true"], QPlainTextEdit[readOnly="true"], QTextEdit[readOnly="true"] { background: @panel@; color: @muted@; }
QComboBox { padding-right: 24px; }
QComboBox::drop-down { width: 21px; border-left: 1px solid @border@; }
QComboBox::down-arrow { image: url("@CHEVRON@"); width: 8px; height: 6px; }
QComboBox::down-arrow:disabled { image: url("@CHEVRON_DISABLED@"); }
QComboBox QAbstractItemView { background: @panel@; border: 1px solid @border_hover@; padding: 3px; selection-background-color: @selected@; selection-color: @selection_text@; outline: 0; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 17px; border-left: 1px solid @border@; border-top-right-radius: 4px; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 17px; border-left: 1px solid @border@; border-bottom-right-radius: 4px; }
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background: @hover@; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("@CHEVRON_UP@"); width: 8px; height: 6px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("@CHEVRON@"); width: 8px; height: 6px; }
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:off { image: url("@CHEVRON_UP_DISABLED@"); }
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:off { image: url("@CHEVRON_DISABLED@"); }
QGroupBox { background: @panel@; border: 1px solid @border@; border-radius: 6px; margin-top: 14px; padding: 10px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 4px; color: @text@; }
QTabWidget::pane { border: 1px solid @border@; border-radius: 4px; top: -1px; }
QTabBar::tab { background: @background@; color: @muted@; border: 1px solid transparent; border-bottom: 2px solid transparent; padding: 6px 11px; margin-right: 2px; }
QTabBar::tab:selected { background: @panel@; color: @text@; border-bottom-color: @accent@; }
QTabBar::tab:hover:!selected { color: @text@; background: @raised@; }
QTabBar::tab:disabled { color: @disabled@; }
QTabBar::tab:focus { border-color: @focus@; }
QSlider { background: transparent; }
QSlider::groove:horizontal { background: @border@; height: 3px; border-radius: 1px; }
QSlider::sub-page:horizontal { background: @accent_pressed@; height: 3px; border-radius: 1px; }
QSlider::handle:horizontal { background: @text@; border: 1px solid @text@; width: 9px; margin: -5px 0; border-radius: 4px; }
QSlider::handle:horizontal:hover { background: @accent_hover@; border-color: @accent_hover@; }
QSlider::handle:horizontal:focus { background: @accent@; border-color: @focus@; }
QSlider::sub-page:horizontal:disabled { background: @disabled@; }
QSlider::handle:horizontal:disabled { background: @disabled@; border-color: @disabled@; }
QScrollArea { border: none; background: @background@; }
QScrollBar:vertical { width: 10px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: @border_hover@; min-height: 28px; border: 2px solid @background@; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: @muted@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 10px; background: transparent; margin: 0; }
QScrollBar::handle:horizontal { background: @border_hover@; min-width: 28px; border: 2px solid @background@; border-radius: 4px; }
QScrollBar::handle:horizontal:hover { background: @muted@; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QSplitter::handle { background: @border@; }
QSplitter::handle:hover { background: @border_hover@; }
QProgressBar { background: @input@; border: 1px solid @border@; border-radius: 4px; text-align: center; color: @text@; }
QProgressBar::chunk { background: @selected@; border-radius: 3px; }
QCheckBox, QRadioButton { spacing: 6px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 13px; height: 13px; border: 1px solid @border_hover@; background: @input@; border-radius: 3px; }
QRadioButton::indicator { border-radius: 7px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: @muted@; }
QCheckBox::indicator:checked { image: url("@CHECK@"); background: @accent@; border-color: @accent@; }
QCheckBox::indicator:indeterminate { background: @selected@; border-color: @accent@; }
QRadioButton::indicator:checked { background: @accent@; border: 3px solid @selected@; }
QCheckBox::indicator:focus, QRadioButton::indicator:focus { border-color: @focus@; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background: @disabled_surface@; border-color: @disabled_border@; }
QCheckBox::indicator:checked:disabled { image: url("@CHECK_DISABLED@"); background: @disabled_surface@; }
QRadioButton::indicator:checked:disabled { background: @disabled@; }
QCheckBox:focus, QRadioButton:focus { color: @accent_hover@; }
QAbstractItemView { background: @input@; alternate-background-color: @panel@; border: 1px solid @border@; border-radius: 4px; selection-background-color: @selected@; selection-color: @selection_text@; outline: 0; }
QAbstractItemView:focus { border-color: @focus@; }
QAbstractItemView:disabled { color: @disabled@; border-color: @disabled_border@; }
QListView::item, QTreeView::item { padding: 5px 6px; border: 1px solid transparent; }
QListView::item:hover:!selected, QTreeView::item:hover:!selected, QTableView::item:hover:!selected { background: @raised@; }
QListView::item:selected, QTreeView::item:selected, QTableView::item:selected { background: @selected@; color: @selection_text@; }
QListView::item:focus, QTreeView::item:focus { border-color: @focus@; }
QTableView { gridline-color: @disabled_border@; }
QTableView::item { padding: 4px; }
QHeaderView { background: @panel@; }
QHeaderView::section { background: @panel@; color: @muted@; border: none; border-bottom: 1px solid @border@; border-right: 1px solid @disabled_border@; padding: 6px; font-weight: 600; }
QHeaderView::section:hover { color: @text@; background: @raised@; }
QTableCornerButton::section { background: @panel@; border: none; border-bottom: 1px solid @border@; }
QToolTip { background: @raised@; color: @text@; border: 1px solid @border_hover@; padding: 6px; }
/* Compact workspace chrome; ordinary fields and dialogs retain readable targets. */
QWidget[chrome="true"] QPushButton, QPushButton[compact="true"] { padding: 3px 7px; }
QWidget[chrome="true"] QComboBox { padding-top: 3px; padding-bottom: 3px; }
QWidget[chrome="true"] QSpinBox, QWidget[chrome="true"] QDoubleSpinBox { padding: 3px 5px; }
QWidget[chrome="true"] QLabel#timecode { padding: 3px 5px; }
QToolButton { padding: 3px 20px 3px 7px; }
QToolButton::menu-button { width: 16px; border-left: 1px solid @border@; }
QToolButton::menu-arrow { image: url("@CHEVRON@"); width: 8px; height: 6px; }
QMenuBar { background: @panel@; }
QMenuBar::item { background: transparent; padding: 5px 8px; }
QMenuBar::item:selected { background: @raised@; }
QMenuBar::item:pressed { background: @selected@; }
QMenu { background: @panel@; border: 1px solid @border@; padding: 4px; }
QMenu::item { background: transparent; padding: 6px 24px; border-radius: 4px; }
QMenu::item:selected { background: @selected@; color: @selection_text@; }
QMenu::item:disabled { color: @disabled@; }
QMenu::separator { background: @border@; height: 1px; margin: 4px 8px; }
QStatusBar { background: @panel@; border-top: 1px solid @border@; }
QStatusBar::item { border: none; }
QSlider#transportScrubber::handle:horizontal { background: @cursor@; border-color: @cursor@; width: 7px; margin: -4px 0; }
QSlider#transportScrubber::handle:horizontal:focus { border-color: @text@; }
QSlider#transportScrubber::sub-page:horizontal { background: @border_hover@; }
"""


def _stylesheet():
    sheet = _STYLE
    for name, color in COLORS.items():
        sheet = sheet.replace(f"@{name}@", color)
    assets = Path(__file__).parent / "assets"
    for token, filename in {
        "CHEVRON": "terminal-chevron.svg",
        "CHEVRON_DISABLED": "studio-chevron-disabled.svg",
        "CHEVRON_UP": "studio-chevron-up.svg",
        "CHEVRON_UP_DISABLED": "studio-chevron-up-disabled.svg",
        "CHECK": "studio-check.svg",
        "CHECK_DISABLED": "studio-check-disabled.svg",
    }.items():
        sheet = sheet.replace(f"@{token}@", (assets / filename).as_posix())
    return sheet


STYLE = _stylesheet()


def ui_font():
    """Native sans-serif labels; values can explicitly opt into terminal_font."""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    families = set(QFontDatabase.families())
    # The offscreen macOS platform reports the unresolved alias "Sans Serif".
    # Use an installed UI family there, avoiding Qt's costly alias discovery.
    if font.family() not in families:
        family = next((name for name in (".AppleSystemUIFont", "Segoe UI", "Helvetica Neue",
                       "Noto Sans", "DejaVu Sans", "Arial") if name in families), None)
        if family:
            font.setFamily(family)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPointSize(11)
    return font


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
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "nebula-icon.png")))
    app.setStyle("Fusion")
    app.setFont(ui_font())
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "background",
        QPalette.ColorRole.Base: "input",
        QPalette.ColorRole.AlternateBase: "panel",
        QPalette.ColorRole.Button: "raised",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.Highlight: "selected",
        QPalette.ColorRole.HighlightedText: "selection_text",
        QPalette.ColorRole.ToolTipBase: "raised",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.Link: "accent",
        QPalette.ColorRole.LinkVisited: "cursor",
        QPalette.ColorRole.Light: "border_hover",
        QPalette.ColorRole.Mid: "border",
        QPalette.ColorRole.Dark: "input",
        QPalette.ColorRole.Shadow: "monitor",
        QPalette.ColorRole.BrightText: "warning",
    }
    for role, token in roles.items():
        palette.setColor(role, QColor(COLORS[token]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.ButtonText, QPalette.ColorRole.PlaceholderText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(COLORS["disabled"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(COLORS["disabled_surface"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(COLORS["disabled"]))
    app.setPalette(palette)
    numeric_family = terminal_font().family().replace('\\', '\\\\').replace('"', '\\"')
    app.setStyleSheet(STYLE + '\nQSpinBox, QDoubleSpinBox, QLabel#timecode, '
                     'QLabel[numeric="true"] { font-family: "' + numeric_family + '"; }')
