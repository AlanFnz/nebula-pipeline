"""Graphite surfaces for the composition workspace (logical Qt pixels)."""
from string import Template


_GRAPHITE = {
    'canvas': '#0E1012', 'background': '#17191C', 'panel': '#202328',
    'raised': '#292D32', 'divider': '#383D44', 'control': '#75808D',
    'text': '#E7E9EC', 'secondary': '#ADB4BE', 'disabled': '#818791',
    'accent': '#B4CF98', 'on_accent': '#171E13', 'selection': '#303C2D',
    'accent_hover': '#C2DDA6', 'accent_pressed': '#9AB880', 'focus': '#9CC5F4',
}

GRAPHITE_STYLE = Template("""
#workspaceHeader QWidget#documentBar { background: $panel; border-bottom: 1px solid $divider; }
#workspaceHeader QWidget#canvasBar { background: $background; border-bottom: 1px solid $divider; }
#workspaceHeader .QWidget, #monitorHeader .QWidget { background: transparent; }

#workspaceHeader QLabel#brand { color: $accent; font-size: 23px; font-weight: 700; }
#workspaceHeader QLabel#documentTitle { color: $text; font-size: 14px; font-weight: 600; }
#canvasBar QLabel, #monitorHeader QLabel#monitorMeta { color: $secondary; }
#workspaceHeader QPushButton[secondaryAction="true"]:enabled { color: $text; }
#workspaceHeader QPushButton[secondaryAction="true"]:focus { border-color: $focus; }
#workspaceHeader QPushButton[secondaryAction="true"]:hover { background: $raised; }
#workspaceHeader QPushButton#primary:enabled { background: $accent; border-color: $accent; color: $on_accent; }
#workspaceHeader QPushButton#primary:hover { background: $accent_hover; }
#workspaceHeader QPushButton#primary:pressed { background: $accent_pressed; }

QFrame#monitorFrame { background: $canvas; border: 1px solid $divider; border-radius: 0; }
SynthViewer#studioViewer { background: $canvas; }
QWidget#monitorHeader { background: $panel; border-bottom: 1px solid $divider; }
#monitorHeader QLabel#sectionTitle { color: $text; font-size: 12px; font-weight: 600; }
#monitorHeader QPushButton:enabled:!checked { background: transparent; border-color: transparent; color: $secondary; }
#monitorHeader QPushButton:hover:!checked { background: $raised; color: $text; border-color: $control; }
#monitorHeader QPushButton:checked { background: $selection; color: $text; border-color: $accent; }
#monitorHeader QDoubleSpinBox { background: $background; color: $text; }

#monitorHeader QPushButton:enabled:focus, #monitorHeader QPushButton:enabled:!checked:focus { border-color: $focus; }

QWidget#inspectorColumn { background: $panel; border-left: 1px solid $divider; }
#inspectorColumn .QWidget, #inspectorColumn QWidget#inspectorSurface,
#inspectorColumn QStackedWidget, #inspectorColumn QScrollArea,
#inspectorColumn CompositionPanel, #inspectorColumn EffectsPanel,
#inspectorColumn SubjectPanel, #inspectorColumn EffectParameter { background: $panel; }
#inspectorColumn ContextHeader { background: $panel; border-bottom: 1px solid $divider; }
#inspectorColumn ContextLabel { color: $secondary; font-size: 12px; }
#inspectorColumn QLabel#inspectorTitle { color: $text; font-size: 16px; font-weight: 600; }
#inspectorColumn QLabel#effectTitle { color: $text; font-size: 18px; font-weight: 600; padding-top: 3px; }
#inspectorColumn QLabel#muted { color: $secondary; }
#inspectorColumn QComboBox#editingScope:enabled { background: $raised; color: $text; font-weight: 600; }
#inspectorColumn InspectorTabs::pane { border: none; border-top: 1px solid $divider; }
#inspectorColumn InspectorTabs > QTabBar::tab { background: $panel; color: $secondary; padding: 6px 10px; }
#inspectorColumn InspectorTabs > QTabBar::tab:selected { color: $text; background: $raised; border-bottom-color: $accent; }
#inspectorColumn InspectorTabs > QTabBar::tab:hover:!selected { background: $raised; color: $text; }
#inspectorColumn InspectorTabs > QTabBar::tab:disabled { color: $disabled; }
#inspectorColumn QPushButton#controlGroup { border-top-color: $divider; color: $text; font-size: 13px; padding: 6px 2px; }
#inspectorColumn QPushButton#controlGroup:checked { border-top-color: $divider; }
#inspectorColumn QPushButton#controlGroup:hover { background: $raised; }
#inspectorColumn QLabel#sectionTitle { color: $secondary; font-size: 12px; }
#inspectorColumn EffectParameter QLabel[parameterLabel="true"] { color: $text; font-size: 13px; }
#inspectorColumn QSlider::groove:horizontal { background: $divider; height: 2px; }
#inspectorColumn QSlider::sub-page:horizontal:enabled { background: $accent; height: 2px; }
#inspectorColumn QSlider::handle:horizontal:enabled { background: $text; border-color: $text; width: 8px; margin: -5px 0; border-radius: 3px; }
#inspectorColumn QSlider::handle:horizontal:focus { background: $focus; border-color: $focus; }

#workspaceHeader QComboBox, #workspaceHeader QSpinBox,
#inspectorColumn QComboBox, #inspectorColumn QAbstractSpinBox, #inspectorColumn QLineEdit {
    background: $background; border-color: $divider;
}
#workspaceHeader QAbstractSpinBox > QLineEdit, #monitorHeader QAbstractSpinBox > QLineEdit,
#inspectorColumn QAbstractSpinBox > QLineEdit { border: none; background: transparent; }
#workspaceHeader QComboBox:hover, #workspaceHeader QSpinBox:hover,
#inspectorColumn QComboBox:hover, #inspectorColumn QAbstractSpinBox:hover,
#inspectorColumn QLineEdit:hover { border-color: $control; }

#workspaceHeader QAbstractButton:focus, #workspaceHeader QAbstractSpinBox:focus,
#workspaceHeader QComboBox:focus, #workspaceHeader QPushButton#primary:focus,
#monitorHeader QDoubleSpinBox:focus,
#inspectorColumn QAbstractButton:focus, #inspectorColumn QLineEdit:focus,
#inspectorColumn QAbstractSpinBox:focus, #inspectorColumn QComboBox:focus,
#inspectorColumn QComboBox#editingScope:focus, #inspectorColumn QPushButton#controlGroup:focus,
#inspectorColumn InspectorTabs > QTabBar::tab:focus { border-color: $focus; }
""").substitute(_GRAPHITE)
