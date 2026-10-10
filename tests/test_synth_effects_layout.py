"""Inspector hierarchy keeps direct actions and navigation safe at narrow widths."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from studio_theme import apply_theme
from synth_composition import compile_composition, reference_composition
from synth_effect_diagnostics import EffectExplanation
from synth_effects import EFFECTS, effect_preset
from synth_effects_ui import EffectsPanel
from synth_inspector import control_group


@pytest.fixture
def make_panel():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    panels = []

    def make(effect_id='tape', width=380, local=False):
        document = reference_composition(True)
        document['effects'] = {effect.id: {'mode': 'off', 'params': {}} for effect in EFFECTS}
        for key in ('rays', effect_id): document['effects'][key] = effect_preset(key)
        states = list(compile_composition(document)['states'].values())
        panel = EffectsPanel()
        panel.set_context(document['effects'], {}, states, 'Selected clip' if local else 'Entire project', local, ('clip' if local else 'whole',))
        panel.inspect_effect(effect_id); panel.resize(width, 650); panel.show(); app.processEvents()
        panels.append(panel)
        return panel, document, states

    yield make
    for panel in panels: panel.close(); panel.deleteLater()
    app.processEvents()


@pytest.mark.parametrize('width', (380, 490, 650))
@pytest.mark.parametrize('local', (False, True))
def test_editor_identity_and_direct_actions_fit(make_panel, width, local):
    panel, _, _ = make_panel(width=width, local=local)
    assert panel.width() == width
    assert panel.inspector_title.objectName() == 'effectTitle'
    assert panel.inspector_title.isVisible()
    assert not panel.activation_host.isVisible()
    for widget in (panel.back_button, panel.add_button, panel.bypass_button,
                   panel.instance_button, panel.remove_button, panel.restore):
        assert widget.isVisible()
        position = widget.mapTo(panel.editor, QPoint())
        assert position.x() >= 0 and position.x() + widget.width() <= panel.editor.width()
        assert widget.width() >= widget.minimumSizeHint().width()
        assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert panel.restore.mapTo(panel.editor, QPoint()).y() == panel.bypass_button.mapTo(panel.editor, QPoint()).y()
    assert panel.parameter_scroll.horizontalScrollBar().maximum() == 0


def test_group_collapse_search_and_scope_refresh_never_author(make_panel):
    panel, document, states = make_panel()
    original = copy.deepcopy(document); edits = []
    panel.edited.connect(lambda *edit: edits.append(edit))
    panel.parameter_tabs.setCurrentIndex(1)
    path = 'tape.pull'; title = control_group(path); header = panel.group_labels[title]
    header.setFocus(); QTest.keyClick(header, Qt.Key.Key_Space)
    assert not panel.controls[path].isVisible() and not header.isChecked()
    panel.filter.setText('pull')
    assert panel.controls[path].isVisible() and header.isChecked()
    panel.filter.clear()
    assert not panel.controls[path].isVisible() and not header.isChecked()
    panel.set_context(document['effects'], {}, states, 'Selected clip', True, ('clip',))
    assert not panel.controls[path].isVisible()
    assert document == original and not edits


def test_first_group_opens_by_default_and_explicit_group_filter_reveals_others(make_panel):
    panel, _, _ = make_panel()
    panel.parameter_tabs.setCurrentIndex(1)
    headers = list(panel.group_labels.values())
    assert headers[0].isChecked()
    assert all(not header.isChecked() for header in headers[1:])
    path = 'tape.mix'; title = control_group(path)
    assert not panel.controls[path].isVisible()
    panel.group.setCurrentIndex(panel.group.findData(title))
    assert panel.controls[path].isVisible()
    assert panel.group_labels[title].isChecked()
    panel.group.setCurrentIndex(0)
    assert not panel.controls[path].isVisible()
    panel.group_labels[title].setChecked(True)
    panel.inspect_effect('bloom'); panel.inspect_effect('tape'); panel.parameter_tabs.setCurrentIndex(1)
    assert panel.controls[path].isVisible()


@pytest.mark.parametrize('path,tab', (('broadcast.reverse', 1), ('broadcast.static', 2), ('broadcast.screen', 3)))
def test_diagnostic_navigation_reveals_correct_tab_and_collapsed_group(make_panel, path, tab):
    panel, document, _ = make_panel('broadcast')
    original = copy.deepcopy(document); edits = []
    panel.edited.connect(lambda *edit: edits.append(edit))
    panel.parameter_tabs.setCurrentIndex(tab)
    panel.group_labels[control_group(path)].setChecked(False)
    panel.parameter_tabs.setCurrentIndex(0)
    fact = EffectExplanation('zero', 'At this frame', 'resolved', 'Change this contributing control.', path)
    panel.set_explanations((fact,)); panel.navigate_explanation()
    QApplication.processEvents()
    assert panel.parameter_tabs.currentIndex() == tab
    assert panel.controls[path].isVisible()
    assert panel.group_labels[control_group(path)].isChecked()
    assert panel.group.currentData() is None
    assert document == original and not edits


def test_routine_status_keeps_details_and_guidance_while_diagnostics_stay_visible(make_panel):
    panel, _, _ = make_panel('bloom')
    configured = EffectExplanation('configured', 'At this frame', 'resolved', 'Configured at 1.00 s.')
    guidance = EffectExplanation('brightness-guidance', 'At this frame', 'guidance', 'Bright source areas contribute.', 'bloom.threshold')
    panel.set_explanations((configured, guidance))
    assert not panel.frame_status.isVisible()
    assert configured.message in panel.inspector_title.toolTip()
    assert guidance.message in panel.explanation_link.toolTip()
    assert panel.explanation_link.isVisible()
    zero = EffectExplanation('zero', 'At this frame', 'resolved', 'Zero contributing strength.', 'bloom.strength')
    panel.set_explanations((configured, zero, guidance))
    assert panel.frame_status.isVisible() and zero.message in panel.frame_status.text()
    assert configured.message not in panel.frame_status.text()
    assert panel.explanation_target == 'bloom.strength'


def test_direct_restore_retains_scope_payload_without_opening_activation(make_panel):
    panel, _, _ = make_panel(local=True)
    edits = []; panel.edited.connect(lambda *edit: edits.append(edit))
    panel.restore.setFocus(); QTest.keyClick(panel.restore, Qt.Key.Key_Space)
    assert edits == [('tape', None, 'effect-restore')]
    assert not panel.activation_host.isVisible()
