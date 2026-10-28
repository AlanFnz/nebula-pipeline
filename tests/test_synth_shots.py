"""The authored montage exposes ordinary clips without losing its optical look."""
import copy
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition, load_composition, save_composition, section_ranges
from synth_retime import mapped_time
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from test_synth_effects_editor_integration import make_window


def test_all_authored_cuts_survive_exact_fifteen_seconds_with_original_pixels():
    old = compile_composition(load_composition(Path(__file__).resolve().parents[1] / 'presets/text-dye-transfer-v6.json'))
    project = starter_composition('text-dye-transfer')
    new = compile_composition(project)
    assert len(project['sections']) == len(new['cues']) == len(old['cues']) == 73
    assert new['duration'] == 15 and new['fps'] == 30
    assert sum(round(s['duration'] * 30) for s in project['sections']) == 450
    for cue, original in zip(new['cues'], old['cues']):
        assert round(cue['time'] * 30) == round(round(original['time'] * 30) * 450 / 473)
        assert new['states'][cue['state']] == old['states'][original['state']]
    # Exercise the continuous film clock inside every shot, not only at cuts.
    for section, (start, end) in zip(project['sections'], section_ranges(project)):
        t = start + (round(section['duration'] * 30) // 2) / 30
        source_t = mapped_time(new['time_map'], t)
        assert render_sequence_frame(new, t, (160, 90)).tobytes() == render_sequence_frame(old, source_t, (160, 90)).tobytes()
    assert new['states'][new['cues'][-1]['state']]['overrides']['text.content'] == '&\nYOU\nKNOW'


def test_shot_selection_edit_text_duration_save_and_undo(make_window, tmp_path):
    w = make_window(composition=starter_composition('text-dye-transfer'))
    original = copy.deepcopy(w.composition)
    cards = w.shot_strip.cards
    assert w.shot_strip.isVisible() and w.section_scroll.isHidden()
    assert cards.count() == 73 and w.composer.scope == 0
    QTest.mouseClick(cards.viewport(), Qt.MouseButton.LeftButton, pos=cards.visualItemRect(cards.item(2)).center())
    assert w.composer.index == 2 and w.composer.scope == 0
    QTest.mouseDClick(cards.viewport(), Qt.MouseButton.LeftButton, pos=cards.visualItemRect(cards.item(2)).center())
    assert w.composer.scope == 1 and w.composer.index == 2
    assert w.composer.look_tabs.currentWidget() is w.composer.object_panel
    control = w.composer.object_panel.controls['text.content'].input
    control.editor.setPlainText('A DIFFERENT\nSHOT')
    control.apply.click()
    assert w.composition['sections'][2]['effects']['text']['params']['text.content'] == 'A DIFFERENT\nSHOT'
    assert w.composition['sections'][:2] == original['sections'][:2]
    assert w.composition['sections'][3:] == original['sections'][3:]
    assert 'A DIFFERENT SHOT' in cards.item(2).text()
    edited = copy.deepcopy(w.composition)
    w.shot_strip.duration.setValue(.5)
    assert w.composition['sections'][2]['duration'] == .5
    assert w.sequence['duration'] == pytest.approx(15 + .5 - original['sections'][2]['duration'])
    save_composition(tmp_path / 'shots.json', w.composition)
    assert load_composition(tmp_path / 'shots.json') == w.composition
    w.undo_composition(); assert w.composition == edited
    w.undo_composition(); assert w.composition == original
    w.redo_composition(); assert w.composition == edited
    # Timeline and cards operate on the same clip and keep the same selection.
    w.timeline_view.setCurrentIndex(0)
    assert w.section_scroll.isVisible() and w.shot_strip.isHidden()
    assert w.section_timeline.index == 2
    w.section_timeline.select_at(5)
    w.timeline_view.setCurrentIndex(1)
    assert cards.currentRow() == 5


def test_old_project_keeps_compact_timeline_and_thumbnail_refresh_is_bounded(make_window):
    w = make_window()
    assert w.shot_strip.isHidden() and w.section_scroll.isVisible()
    w.set_composition(starter_composition('text-dye-transfer'), guard=False)
    QApplication.processEvents()
    assert w.shot_strip.isVisible()
    QTest.qWait(1500)
    assert w.shot_strip.completed
    assert len(w.shot_strip.work.jobs) <= 12
    before = w.shot_strip.generation
    w.shot_strip.cards.setCurrentRow(3)
    assert w.shot_strip.generation == before
    w.shot_strip.duration.setValue(.5)
    assert w.shot_strip.generation > before
    w.close()
    assert w.shot_strip.work.stopped
