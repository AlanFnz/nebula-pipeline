"""Every source keeps its controls and data when using the shared inspector."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from synth_object_catalog import OBJECT_PATHS, PARAMETER_OWNER
from synth_effects import describe_effects
from synth_subject import scope_states
from synth_starters import starter_composition
from synth_subject_ui import SubjectPanel
from test_synth_effects_editor_integration import make_window

STUDIES = ('pleated-signal', 'image-memory', 'chromatic-lattice', 'color-film-die',
           'prismatic-film', 'radial-bloom', 'text-contact-film', 'refined',
           'mixed-media', 'particle-orbit', 'profile-doryphoros')


def settle():
    for _ in range(4): QApplication.processEvents()


@pytest.fixture
def panel():
    app = QApplication.instance() or QApplication([])
    p = SubjectPanel(); p.resize(420, 660); p.show()
    yield p
    p.close(); p.deleteLater(); app.processEvents()


@pytest.mark.parametrize('study', STUDIES)
def test_all_sources_have_unique_groups_and_navigation_never_edits(panel, study):
    doc = starter_composition(study); original = copy.deepcopy(doc)
    panel.refresh(describe_effects(scope_states(doc)), doc['effects'], {}, False)
    settle()
    assert panel.object_navigation.isVisible()
    assigned = [p for _, _, _, members in panel.object_definitions for p in members]
    if panel.kind == 'text': assigned += ['text.font', 'text.weight', 'text.content']
    assert len(assigned) == len(set(assigned))
    assert set(assigned) == set(OBJECT_PATHS[panel.kind])
    changed = QSignalSpy(panel.parameter_changed)
    for _, title, _, members in panel.object_definitions:
        panel.reveal_object_group(title); settle()
        for p in members:
            assert p in panel.object_ranges[PARAMETER_OWNER[p]]['ranges']
    panel.object_filter.setText('no match anywhere'); settle()
    assert panel.no_object_matches.isVisible()
    panel.object_filter.clear(); panel.show_all_controls.click(); panel.show_all_controls.click(); settle()
    assert panel.overview_scroll.horizontalScrollBar().maximum() == 0
    assert changed.count() == 0 and doc == original


def test_shape_eligibility_survives_search_and_show_all(panel):
    doc = starter_composition('chromatic-lattice')
    panel.refresh(describe_effects(scope_states(doc)), doc['effects'], {}, False)
    panel.object_filter.setText('sides'); panel.show_all_controls.setChecked(True); settle()
    assert not panel.controls['chromatic_lattice.sides'].isVisible()
    panel.object_filter.setText('bpm'); settle()
    assert not panel.controls['chromatic_lattice.bpm'].isVisible()
    panel.object_filter.setText('period'); settle()
    assert panel.controls['chromatic_lattice.period'].isVisible()
    panel.object_filter.clear(); panel.show_all_controls.setChecked(False)
    assert panel.object_groups['Rhythm & timing'].body.isHidden()


def test_switching_sources_keeps_position_and_memory_center_action(panel):
    changed = QSignalSpy(panel.parameter_changed)
    centered = QSignalSpy(panel.center_path_requested)
    for study in ('image-memory', 'refined', 'text-contact-film', 'color-film-die', 'image-memory'):
        doc = starter_composition(study)
        panel.refresh(describe_effects(scope_states(doc)), doc['effects'], {}, False); settle()
        panel.object_filter.setText('position'); settle()
        assert panel.position_controls['x'].isVisible()
        panel.object_filter.clear()
    panel.object_filter.setText('center path'); settle()
    QTest.keyClick(panel.object_filter, Qt.Key.Key_Return); settle()
    assert panel.center_path.hasFocus()
    panel.center_path.click()
    assert centered.count() == 1 and changed.count() == 0


@pytest.mark.parametrize('study,path,value', [
    ('chromatic-lattice', 'chromatic_lattice.glow_radius', 7.),
    ('image-memory', 'image_memory.color_shift', .3),
    ('radial-bloom', 'radial_bloom.vibration', .3),
    ('color-film-die', 'solid.roughness', .35),
    ('particle-orbit', 'particles.turbulence', .3),
    ('refined', 'slab.edge_softness', .3),
])
def test_newly_exposed_controls_keep_clip_scope_and_undo(make_window, study, path, value):
    w = make_window(composition=starter_composition(study))
    c = w.composer; obj = c.object_panel; c.look_tabs.setCurrentWidget(obj); c.change_scope(1); settle()
    original = copy.deepcopy(w.composition)
    assert obj.reveal_control(path); settle()
    control = obj.controls[path]
    if control.value_stack.currentIndex() == 1: control.use_fixed.click()
    control.input.setValue(value); settle()
    assert w.composition['effects'] == original['effects']
    assert w.composition['sections'][0]['effects'][PARAMETER_OWNER[path]]['params'][path] == pytest.approx(value)
    for _ in range(2):
        if w.composition != original: w.undo_composition()
    assert w.composition == original
