"""Timeline selection never redirects an effect edit to another scope."""
import copy
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from test_synth_effect_discovery_ui import window, select
from test_synth_effect_scope import document


def click_clip(window, index):
    rectangle = window.section_timeline.rectangles()[index]
    QTest.mouseClick(window.section_timeline, Qt.MouseButton.LeftButton, pos=rectangle.center().toPoint())
    QApplication.processEvents()


@pytest.mark.parametrize('local', [False, True])
def test_timeline_click_preserves_scope_and_routes_new_effect_to_that_scope(window, local):
    window.set_composition(document()); panel = window.composer; effects = panel.effects_panel
    panel.change_scope(int(local)); effects.show_overview()
    original = copy.deepcopy(window.composition)
    click_clip(window, 1)
    assert panel.index == 1 and panel.scope == int(local)
    assert window.composition == original and not window.undo_compositions
    assert window.section_timeline.editing_section_id == (original['sections'][1]['id'] if local else None)
    assert effects.available_button.text() == ('Add clip effect…' if local else 'Add project effect…')
    assert effects.add_button.text() == effects.available_button.text()
    assert effects.clip_title.isHidden() == (not local)
    effects.available_button.click(); QApplication.processEvents()
    dialog = window.discovery_dialog
    assert dialog.session.section_id == (original['sections'][1]['id'] if local else None)
    select(dialog, 'bloom'); dialog.debounce.stop(); dialog.render_selection()
    dialog.session.accept_packet(); dialog.refresh_preview(); dialog.action.click()
    assert panel.scope == int(local) and panel.index == 1
    target = window.composition['sections'][1] if local else window.composition
    assert target['effects']['bloom']['mode'] == 'on'
    if local:
        assert window.composition['effects'] == original['effects']
    else:
        assert window.composition['sections'] == original['sections']
    window.undo_composition(); assert window.composition == original


def test_project_view_remains_shared_after_returning_from_a_clip_inspector(window):
    window.set_composition(document()); panel = window.composer; effects = panel.effects_panel
    panel.change_scope(1); effects.inspect_effect('tape@2')
    panel.change_scope(0); effects.show_overview()
    assert effects.clip_title.isHidden() and 'tape@2' not in effects.applied_ids
    assert effects.effect_choices['tape@2'].isHidden()
    click_clip(window, 2)
    assert panel.scope == 0 and 'tape@2' not in effects.applied_ids
    assert effects.project_effect_ids == ('raster',)
    panel.change_scope(1)
    assert panel.index == 2 and panel.scope == 1
    click_clip(window, 0)
    assert panel.scope == 1 and set(effects.clip_effect_ids) == {'tape@2', 'raster'}
