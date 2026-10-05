"""Creative/base editing, inheritance and lifecycle in the native composer."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QSettings, QThreadPool, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from studio_theme import apply_theme
from synth_composition import load_composition
from synth_composer_ui import CompositionPanel
from synth_creative import CREATIVE_CONTROLS
from synth_effects import state_values
from synth_starting_points import new_piece
from synth_studio import SynthStudio
from test_synth_creative import animated


@pytest.fixture
def panels():
    app = QApplication.instance() or QApplication([]); apply_theme(app)
    widgets = []
    def make(effect='tape', width=380):
        widget = CompositionPanel(animated(effect)); widget.resize(width, 750)
        widget.show(); widgets.append(widget)
        widget.effects_panel.inspect_effect(effect); app.processEvents()
        return widget
    yield make
    for widget in widgets: widget.close()
    app.processEvents()


@pytest.mark.parametrize('effect', tuple(CREATIVE_CONTROLS))
def test_pilot_navigation_is_read_only_and_first_creative_value_visible(panels, effect):
    panel = panels(effect); editor = panel.effects_panel
    original = copy.deepcopy(panel.document)
    assert editor.parameter_tabs.tabText(0) == 'Creative'
    assert editor.creative_panel.isVisible() and not editor.parameter_host.isVisible()
    first = next(iter(editor.creative_panel.controls.values()))
    assert editor.parameter_scroll.viewport().rect().contains(first.input.mapTo(editor.parameter_scroll.viewport(), first.input.rect().center()))
    editor.parameter_tabs.setCurrentIndex(1); editor.filter.setText('rate')
    editor.filter.clear(); editor.parameter_tabs.setCurrentIndex(0)
    editor.show_overview(); editor.inspect_effect(effect)
    assert panel.document == original
    if effect != 'ghosts':
        assert next(iter(editor.creative_panel.controls.values())).input.decimals() == 2


def test_relative_slider_keeps_animation_and_parameters_edit_the_base(panels):
    panel = panels(); editor = panel.effects_panel
    control = editor.creative_panel.controls['damage']
    # Drag feedback updates the number without authoring; release commits even
    # though that same number is already displayed.
    control.slider.sliderMoved.emit(150)
    assert 'tape' not in panel.document['effects']
    control.slider.setValue(150)
    assert panel.document['effects']['tape']['creative']['values']['damage'] == 1.5
    assert panel.document['effects']['tape']['params'] == {}
    assert editor.authored_summary['tape']['ranges']['tape.tracking'] == (.025, .07)
    assert editor.summary['tape']['ranges']['tape.tracking'] == pytest.approx((.0375, .105))
    editor.parameter_tabs.setCurrentIndex(1)
    detailed = editor.controls['tape.tracking']
    assert detailed.animated_value.text() and detailed.fixed_choice.isVisible()
    assert 'adjusted by' in detailed.origin.text()
    editor.filter.setText('tracking'); editor.filter.clear()
    assert detailed.origin.text().count('adjusted by') == 1
    detailed.use_fixed.click()
    assert panel.document['effects']['tape']['params']['tape.tracking'] == .025
    assert state_values(panel.compiled['states']['section-1:s0'])[0]['tape.tracking'] == pytest.approx(.0375)
    editor.restore_creative(None)
    assert panel.document['effects']['tape']['params']['tape.tracking'] == .025
    assert 'creative' not in panel.document['effects']['tape']


def test_context_switch_from_broadcast_tab_opens_creative(panels):
    panel = panels(); editor = panel.effects_panel
    editor.inspect_effect('broadcast'); editor.parameter_tabs.setCurrentIndex(2)
    editor.set_context({}, {}, list(panel.compiled['states'].values()),
                       'Entire project', False, ('next-document',), allowed_effects=('tape',))
    assert editor.effect_id == 'tape' and editor.parameter_tabs.currentIndex() == 0
    assert editor.creative_panel.isVisible() and not editor.parameter_host.isVisible()


def test_local_neutral_restoration_and_preset_replacement(panels):
    panel = panels('frame_jitter'); editor = panel.effects_panel
    editor.creative_panel.controls['distance'].input.setValue(150)
    panel.duplicate_section(); panel.select_section(1); panel.change_scope(1)
    assert editor.creative_panel.controls['distance'].input.value() == 150
    assert 'inherited' in editor.creative_panel.controls['distance'].origin.text()
    editor.creative_panel.controls['distance'].input.setValue(100)
    assert state_values(panel.compiled['states']['section-2:s0'])[0]['frame_jitter.x'] == 2.
    editor.creative_panel.controls['distance'].reset.click()
    assert editor.creative_panel.controls['distance'].input.value() == 150
    editor.apply_look()
    assert state_values(panel.compiled['states']['section-2:s0'])[0]['frame_jitter.x'] == 5.
    assert editor.creative_panel.controls['distance'].input.value() == 100
    assert panel.document['effects']['frame_jitter']['creative']['values']['distance'] == 1.5


def test_bypass_and_effect_restore_keep_other_adjustments(panels):
    panel = panels(); editor = panel.effects_panel
    editor.creative_panel.controls['damage'].input.setValue(150)
    settings = copy.deepcopy(panel.document['effects']['tape'])
    editor.toggle_bypass('tape')
    assert editor.creative_panel.controls['damage'].input.value() == 150
    assert editor.authored_summary['tape']['ranges']['tape.tracking'] == (.025, .07)
    editor.toggle_bypass('tape')
    assert panel.document['effects']['tape']['creative'] == settings['creative']
    editor.inspect_effect('frame_jitter'); editor.change_creative('distance', 1.4)
    other = copy.deepcopy(panel.document['effects']['frame_jitter'])
    editor.inspect_effect('tape'); editor.restore_effect()
    assert 'tape' not in panel.document['effects']
    assert panel.document['effects']['frame_jitter'] == other


def test_particle_controls_explain_required_motion_and_groups(panels):
    panel = panels('particles'); editor = panel.effects_panel
    assert editor.creative_panel.controls['outward'].input.isEnabled()
    panel.document = new_piece('model', model='particles'); panel.refresh(); editor.inspect_effect('particles')
    assert not editor.creative_panel.controls['outward'].input.isEnabled()
    assert not editor.creative_panel.controls['distance'].input.isEnabled()
    assert 'Assembly cycle' in editor.creative_panel.compatibility.text()
    assert 'Impulse' in editor.creative_panel.compatibility.text()
    editor.parameter_tabs.setCurrentIndex(1)
    editor.group.setCurrentIndex(editor.group.findText('Motion & timing'))
    assert editor.controls['particles.breathing'].isVisible()
    assert editor.controls['particles.motion'].isVisible()
    panel.object_panel.timing.click()
    assert editor.parameter_tabs.currentIndex() == 0
    assert editor.creative_panel.isVisible()
    panel.object_panel.details.click()
    assert editor.parameter_tabs.currentIndex() == 1


def test_copy_offset_drag_and_scroll_safe_values(panels):
    panel = panels('ghosts'); control = panel.effects_panel.creative_panel.controls['copies']
    control.slider.sliderMoved.emit(2); control.slider.setValue(2)
    assert panel.document['effects']['ghosts']['creative']['values']['copies'] == 2
    assert state_values(panel.compiled['states']['section-1:s0'])[0]['smear.ghosts'] == 4
    event = QWheelEvent(control.input.rect().center(), control.input.mapToGlobal(control.input.rect().center()), QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(control.input, event)
    assert control.input.value() == 2


def test_workspace_history_dirty_status_and_save_open(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([]); apply_theme(app)
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    window = SynthStudio(composition=animated('tape'), settings=QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat))
    window.resize(1280, 720); window.show(); app.processEvents()
    try:
        editor = window.composer.effects_panel; editor.inspect_effect('tape')
        original = copy.deepcopy(window.composition)
        editor.creative_panel.controls['damage'].input.setValue(150)
        assert window.has_unsaved_changes()
        edited = copy.deepcopy(window.composition)
        window.undo_composition(); assert window.composition == original
        window.redo_composition(); assert window.composition == edited
        path = tmp_path / 'creative.json'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
        assert window.save_sequence_dialog() and not window.has_unsaved_changes()
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
        window.load_sequence_dialog()
        assert window.composition == load_composition(path) == edited
        window.composer.effects_panel.inspect_effect('tape')
        assert window.composer.effects_panel.creative_panel.controls['damage'].input.value() == 150
    finally:
        window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()
