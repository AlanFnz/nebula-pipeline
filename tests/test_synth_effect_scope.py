"""Effect ownership is presentation only; shared and clip looks retain identity."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

from studio_theme import apply_theme
from synth_composer_ui import CompositionPanel
from synth_composition import compile_composition, reference_composition, save_composition, load_composition
from synth_effects import EFFECTS, effect_preset, describe_effects
from synth_sequence import render_sequence_frame


def document():
    project = reference_composition(True)
    project['effects'] = {effect.id: {'mode': 'off', 'params': {}} for effect in EFFECTS}
    project['effects']['raster'] = effect_preset('raster')
    first = project['sections'][0]
    first['effects'] = {'raster': {'mode': 'off', 'params': {}}, 'tape@2': effect_preset('tape@2')}
    first['automations'] = [dict(id='pull', path='tape@2.pull', amount=.2, enabled=True,
                                 easing='smooth', start_fraction=.2, attack_fraction=.1,
                                 hold_fraction=.1, recovery_fraction=.1)]
    return project


@pytest.fixture
def composer():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    widget = CompositionPanel(document()); widget.resize(430, 750); widget.show(); app.processEvents()
    yield widget
    widget.close(); widget.deleteLater(); app.processEvents()


def test_project_collector_excludes_local_settings_without_changing_render_or_save(tmp_path):
    project = document(); original = copy.deepcopy(project)
    expected = compile_composition(project)
    shared, base = {'stale': {}}, {'stale': {}}
    actual = compile_composition(project, project_states=shared, project_base_states=base)
    assert actual == expected and project == original
    assert shared.keys() == actual['states'].keys() and 'stale' not in base
    prefix = project['sections'][0]['id'] + ':'
    name = next(key for key in shared if key.startswith(prefix))
    shared_info = describe_effects([shared[name]])
    actual_info = describe_effects([actual['states'][name]])
    assert shared_info['raster']['active']
    assert 'tape@2' not in shared_info
    assert not actual_info['raster']['active']
    assert actual_info['tape@2']['active']
    for time in (.1, .4):
        assert render_sequence_frame(actual, time, (96, 72)).tobytes() == render_sequence_frame(expected, time, (96, 72)).tobytes()
    path = tmp_path/'project.json'; save_composition(path, project)
    assert compile_composition(load_composition(path)) == actual


def test_project_hides_clip_settings_until_scope_is_explicitly_changed(composer):
    panel = composer.effects_panel
    original = copy.deepcopy(composer.document)
    assert f"{len(composer.document['sections'])} clips" in composer.timeline_summary.text()
    assert panel.project_effect_ids == ('raster',)
    assert panel.clip_effect_ids == ()
    assert 'tape@2' not in panel.applied_ids
    assert panel.project_title.text() == 'PROJECT EFFECTS · 1'
    assert panel.clip_title.isHidden() and panel.clip_host.isHidden()
    assert not any('Inspect effects for clip' in b.accessibleName() for b in panel.findChildren(QPushButton))
    assert panel.available_button.text() == 'Add project effect…'
    edits = []; composer.changed.connect(lambda *args: edits.append(args))
    composer.select_section(0, preserve_scope=True)
    assert composer.scope == 0 and panel.clip_title.isHidden()
    composer.change_scope(1)
    assert composer.scope == 1 and composer.index == 0
    assert 'Editing: Clip 1' in composer.scope_combo.currentText()
    assert set(panel.clip_effect_ids) == {'raster', 'tape@2'}
    assert panel.effect_choices['raster'].badge.text() == 'Off'
    assert composer.document == original and edits == []


def test_follow_project_removes_override_keeps_automation_then_shared_changes_follow(composer):
    composer.select_section(0); panel = composer.effects_panel
    assert not panel.effect_choices['raster'].restore.isHidden()
    panel.effect_choices['raster'].restore.click()
    assert 'raster' not in composer.document['sections'][0]['effects']
    assert len(composer.document['sections'][0]['automations']) == 1
    assert panel.project_effect_ids == ('raster',)
    assert panel.clip_effect_ids == ('tape@2',)
    assert panel.effect_choices['raster'].badge.text() == 'On'
    composer.change_scope(0)
    entry = effect_preset('raster'); entry['params']['raster.grain'] = .33
    composer.change_effect('raster', entry, 'effect-parameter')
    composer.select_section(0)
    assert panel.summary['raster']['ranges']['raster.grain'] == (.33, .33)
    panel.effect_choices['tape@2'].restore.click()
    assert 'tape@2' not in composer.document['sections'][0]['effects']
    assert panel.clip_effect_ids == ('tape@2',)  # still owned by its automation
    assert len(composer.document['sections'][0]['automations']) == 1


def test_no_local_settings_explains_inheritance_and_off_overrides_fit_narrow_rack(composer):
    composer.select_section(1); panel = composer.effects_panel
    assert not panel.clip_title.isHidden() and panel.clip_effect_ids == ()
    assert 'No clip overrides' in panel.clip_note.text()
    composer.select_section(0)
    panel.show_overview(); panel.setParent(None); panel.resize(380, 620); panel.show(); QApplication.processEvents()
    try:
        assert panel.width() == 380
        assert panel.overview.findChild(QScrollArea).horizontalScrollBar().maximum() == 0
        for key in ('raster', 'tape@2'):
            row = panel.effect_choices[key]
            assert row.isVisible() and row.parentWidget() is panel.clip_host
            for action in (row.restore, row.bypass, row.remove):
                point = action.mapTo(row, QPoint())
                assert point.x() >= 0 and point.x()+action.width() <= row.width()
    finally:
        panel.setParent(composer.look_tabs)


def test_project_bypass_summary_retains_authored_values(composer):
    entry = effect_preset('raster'); entry['bypassed'] = True
    composer.change_effect('raster', entry, 'effect-bypass')
    panel = composer.effects_panel
    assert panel.project_effect_ids == ('raster',)
    assert panel.effect_choices['raster'].badge.text() == 'Bypassed'
    assert not panel.summary['raster']['active']
    assert panel.authored_summary['raster']['active']


from synth_starters import STARTERS, starter_composition

@pytest.mark.parametrize('identifier', [key for key, _label, _factory in STARTERS])
def test_every_built_in_study_keeps_its_compiled_sequence_with_project_inspection(identifier):
    project = starter_composition(identifier)
    original = copy.deepcopy(project)
    assert compile_composition(project, project_states={}, project_base_states={}) == compile_composition(project)
    assert project == original
