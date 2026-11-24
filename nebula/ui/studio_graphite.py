"""Graphite surfaces for the composition workspace (logical Qt pixels)."""
from string import Template


GRAPHITE = {
    'canvas': '#0E1012', 'background': '#17191C', 'panel': '#202328',
    'raised': '#292D32', 'divider': '#383D44', 'control': '#75808D',
    'text': '#E7E9EC', 'secondary': '#ADB4BE', 'disabled': '#818791',
    'accent': '#B4CF98', 'on_accent': '#171E13', 'selection': '#303C2D',
    'marker': '#CDA0C5', 'warning': '#E3BD7E',
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

QListWidget#montageMaterial { background: $panel; border: 1px solid $divider; border-radius: 3px; }
QListWidget#montageMaterial:focus { border-color: $focus; }

QFrame#montageTiming { background: $panel; border: 1px solid $divider; border-radius: 4px; }
#montageTiming .QWidget, #montageTiming QLabel { background: transparent; }
#montageTiming QLabel#timingTarget { color: $text; font-weight: 600; }
#montageTiming QAbstractSpinBox { background: $background; border-color: $control; }
#montageTiming QAbstractSpinBox > QLineEdit { border: 0; background: transparent; }
#montageTiming QPushButton#applyTiming:enabled { background: $accent; color: $on_accent; }
#montageTiming QPushButton:enabled:focus, #montageTiming QPushButton#applyTiming:enabled:focus,
#montageTiming QAbstractSpinBox:enabled:focus { border-color: $focus; }

QWidget#soundMixer { background: $background; }
#soundMixer QGroupBox {
    background: $panel; border: 1px solid $divider; border-radius: 4px;
    margin-top: 16px; padding: 5px 3px 3px;
}
#soundMixer QGroupBox::title { color: $text; font-weight: 600; left: 9px; padding: 0 3px; }
#soundMixer SoundKnob, #soundMixer QWidget#mixerBands, #soundMixer QLabel { background: transparent; }
#soundMixer QLabel#mixerHint { color: $secondary; }
#soundMixer QDoubleSpinBox { background: $background; border-color: $control; color: $text; }
#soundMixer QDoubleSpinBox > QLineEdit { background: transparent; border: 0; }
#soundMixer QDoubleSpinBox:disabled { border-color: $divider; color: $disabled; background: $panel; }
#soundMixer QDoubleSpinBox:enabled:focus, #soundMixer QCheckBox::indicator:focus { border-color: $focus; }
#soundMixer QCheckBox:focus { color: $focus; }
#soundMixer QCheckBox::indicator:checked { background: $accent; border-color: $accent; }
#soundMixer QCheckBox::indicator:checked:focus { border-color: $focus; }

QWidget#playbackTransport { background: $panel; border-bottom: 1px solid $divider; }
#playbackTransport .QWidget, #previewReadout .QWidget, #timelineWorkspace .QWidget { background: transparent; }
#playbackTransport PlaybackButton:enabled { background: $raised; border-color: $control; }
#playbackTransport PlaybackButton:enabled:hover, #playbackTransport PlaybackButton:checked { background: $selection; border-color: $accent; }
#playbackTransport PlaybackButton:enabled:focus { border-color: $focus; }
#playbackTransport QLabel#timecode { background: transparent; border: none; color: $text; font-size: 14px; font-weight: 600; }
#playbackTransport QSlider#transportScrubber::groove:horizontal { background: $divider; height: 3px; }
#playbackTransport QSlider#transportScrubber::sub-page:horizontal { background: $control; }
#playbackTransport QSlider#transportScrubber::handle:horizontal { background: $marker; border-color: $marker; width: 9px; border-radius: 3px; margin: -5px 0; }
#playbackTransport QSlider#transportScrubber::handle:horizontal:focus { border-color: $focus; }
#playbackTransport QLabel#monitorMeta, #previewReadout QLabel, #timelineWorkspace QLabel#monitorMeta { color: $secondary; }

QWidget#previewReadout, QWidget#timelineWorkspace { background: $background; }
#timelineWorkspace QWidget#timelineToolbar { background: $panel; border-bottom: 1px solid $divider; }
#timelineWorkspace ContextSummary { color: $secondary; }
#timelineWorkspace QComboBox:enabled, #timelineWorkspace QAbstractSpinBox:enabled,
#previewReadout QComboBox:enabled { background: $panel; border-color: $control; color: $text; }
#timelineWorkspace QAbstractSpinBox > QLineEdit { background: transparent; border: none; }
#timelineToolbar QPushButton[secondaryAction="true"]:enabled { background: transparent; color: $text; }
#timelineWorkspace QPushButton:enabled:hover, #timelineWorkspace QToolButton:enabled:hover { background: $raised; border-color: $control; }
#timelineWorkspace QPushButton:checked:enabled { background: $selection; color: $text; border-color: $accent; }
#timelineWorkspace QCheckBox::indicator:checked:enabled { background-color: $accent; border-color: $accent; }
#timelineWorkspace QComboBox:enabled:focus, #timelineWorkspace QAbstractSpinBox:enabled:focus,
#timelineWorkspace QAbstractButton:enabled:focus, #previewReadout QComboBox:enabled:focus { border-color: $focus; }
#timelineWorkspace QCheckBox::indicator:focus { border-color: $focus; }

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
#inspectorColumn EffectParameter QPushButton#animateParameter,
#inspectorColumn EffectParameter QPushButton#restoreParameter {
    background: transparent; border: 1px solid transparent; color: $secondary;
}
#inspectorColumn EffectParameter QPushButton#animateParameter:hover:enabled,
#inspectorColumn EffectParameter QPushButton#restoreParameter:hover:enabled {
    color: $text; background: $raised; border-color: $control;
}
#inspectorColumn EffectParameter QPushButton#animateParameter:focus:enabled,
#inspectorColumn EffectParameter QPushButton#restoreParameter:focus:enabled { border-color: $focus; }
#inspectorColumn EffectParameter QPushButton#restoreParameter:disabled,
#inspectorColumn EffectParameter QPushButton#animateParameter:disabled { color: $disabled; }
#inspectorColumn EffectParameter QLabel#animatedRange {
    background: $raised; color: $text; border: 0; border-left: 2px solid $marker; border-radius: 0;
}
#inspectorColumn QLabel#intensityScope { color: $accent; font-weight: 600; }
#inspectorColumn SelectionIntensity QLabel#intensityRange { color: $text; font-weight: 600; }
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

#inspectorColumn QFrame#effectChoice {
    background: $panel; border: 0; border-left: 3px solid transparent;
    border-bottom: 1px solid $divider; border-radius: 0;
}
#inspectorColumn QFrame#effectChoice[selected="true"] { background: $selection; border-left-color: $accent; }
#effectChoice QPushButton#effectChoiceButton { color: $text; font-weight: 600; background: transparent; }
#effectChoice EffectDragHandle, #effectChoice QPushButton[secondaryAction="true"] {
    background: transparent; color: $secondary; border-color: transparent;
}
#effectChoice QPushButton:enabled:hover { background: $raised; color: $text; border-color: $control; }
#effectChoice QPushButton#effectChoiceButton:hover { background: $raised; }
#effectChoice QPushButton#effectChoiceButton:focus, #effectChoice QPushButton:enabled:focus { border-color: $focus; }
#effectChoice QLabel#effectState { color: $secondary; padding: 0 3px; font-weight: 600; }
#effectChoice QLabel#effectState[active="true"] { color: $accent; }

QDialog#effectAudition, #effectAudition QScrollArea, #effectAudition .QWidget { background: $background; }
#effectAudition QWidget#auditionControls {
    background: $panel; border: 1px solid $divider; border-radius: 5px;
}
#auditionControls .QWidget { background: transparent; }
#effectAudition QLabel#auditionTitle { color: $text; font-size: 16px; font-weight: 600; }
#effectAudition QLabel#auditionState { color: $text; font-weight: 600; }
#effectAudition QLabel#auditionReadout, #effectAudition QLabel#auditionScope,
#effectAudition DialogContext, #effectAudition QLabel#muted { color: $secondary; }
#effectAudition QListWidget { background: $panel; color: $text; border: 1px solid $divider; border-radius: 4px; }
#effectAudition QListWidget::item { padding: 4px 7px; border-left: 3px solid transparent; }
#effectAudition QListWidget::item:selected { background: $selection; color: $text; border-left-color: $accent; }
#effectAudition QListWidget::item:hover:!selected { background: $raised; }
#effectAudition QLineEdit, #effectAudition QComboBox, #effectAudition QAbstractSpinBox { background: $panel; color: $text; border-color: $control; }
#effectAudition QAbstractSpinBox > QLineEdit { background: transparent; border: 0; }
#effectAudition QPushButton[comparisonSide="true"] { background: $background; color: $secondary; }
#effectAudition QPushButton[comparisonSide="true"]:checked { background: $selection; color: $text; border-color: $accent; }
#effectAudition QPushButton#primary:enabled { background: $accent; color: $on_accent; border-color: $accent; }
#effectAudition QPushButton#primary:enabled:hover { background: $accent_hover; }
#effectAudition QPushButton#primary:enabled:pressed { background: $accent_pressed; }
#effectAudition QPushButton:disabled { color: $disabled; }
#effectAudition QPushButton#primary:disabled { background: $raised; border-color: $divider; color: $disabled; }
#effectAudition QSlider::groove:horizontal { background: $divider; height: 2px; }
#effectAudition QSlider::sub-page:horizontal:enabled { background: $accent; }
#effectAudition QSlider::handle:horizontal:enabled { background: $text; border-color: $text; width: 8px; margin: -5px 0; border-radius: 3px; }
#effectAudition QSlider::handle:horizontal:focus { background: $focus; border-color: $focus; }
#effectAudition QAbstractButton:enabled:focus, #effectAudition QPushButton#primary:enabled:focus,
#effectAudition QPushButton[comparisonSide="true"]:enabled:focus, #effectAudition QListWidget:focus,
#effectAudition QComboBox:focus, #effectAudition QLineEdit:focus, #effectAudition QAbstractSpinBox:focus { border-color: $focus; }
""").substitute(GRAPHITE)
