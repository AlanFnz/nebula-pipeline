import copy
import os
import subprocess
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QTableWidget, QPushButton

from synth_studio import SynthStudio
from synth_composition import load_composition
from synth_sequence import render_sequence_frame, reference_sequence


def wait_until(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate(): return
        time.sleep(.01)
    raise AssertionError("Composer did not settle")


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    window = SynthStudio(); window.show(); app.processEvents()
    yield window
    for child in window.detail_windows: child.close()
    window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()


def test_default_view_is_sections_and_macros_with_pixel_exact_undo(window):
    assert window.findChildren(QTableWidget) == []
    assert len(window.composition["sections"]) == 6
    assert len(window.composer.macro_controls) == 7
    before = render_sequence_frame(window.sequence, 6.2, (120, 96)).tobytes()
    window.composer.macro_controls["width"].spin.setValue(1.5)
    after = render_sequence_frame(window.sequence, 6.2, (120, 96)).tobytes()
    assert after != before
    window.undo_composition()
    assert render_sequence_frame(window.sequence, 6.2, (120, 96)).tobytes() == before
    window.redo_composition()
    assert render_sequence_frame(window.sequence, 6.2, (120, 96)).tobytes() == after


def test_section_arrangement_and_local_take(window):
    panel = window.composer
    panel.select_section(1)
    assert window.current_time == 5.24
    assert panel.scope == 1
    panel.macro_controls["color"].lock.setChecked(True)
    before = copy.deepcopy(window.composition)
    panel.new_take()
    assert window.composition["macros"] == before["macros"]
    assert window.composition["sections"][0] == before["sections"][0]
    assert window.composition["sections"][1]["macros"]["color"] == 1
    panel.duplicate_section()
    assert len(window.composition["sections"]) == 7
    assert window.sequence["duration"] == 18
    panel.move_section(-1)
    panel.remove_section()
    assert len(window.composition["sections"]) == 6
    panel.duration.setValue(20)
    assert window.sequence["duration"] == 20


def test_save_open_and_actual_composer_export(window, tmp_path, monkeypatch):
    # A short composition makes the GUI's real threaded export inexpensive.
    panel = window.composer
    panel.geometry_shape.setCurrentIndex(panel.geometry_shape.findData("polygon"))
    panel.geometry_controls["sides"].setValue(5)
    effects = panel.effects_panel
    effects.selector.setCurrentIndex(effects.selector.findData("breakup"))
    effects.apply_button.click()
    window.composer.duration.setValue(.48)
    original = copy.deepcopy(window.composition)
    document = tmp_path / "composition.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(document), ""))
    window.save_sequence_dialog()
    assert load_composition(document) == original
    window.composer.new_take()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(document), ""))
    window.load_sequence_dialog()
    assert window.composition == original
    output = tmp_path / "clip.mp4"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(output), ""))
    window.export_dialog()
    wait_until(lambda: window.export_job is None)
    assert output.exists(), window.status.text()
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1", str(output)], text=True)
    assert "nb_frames=12" in probe


def test_detailed_copy_can_be_edited_without_changing_composition(window):
    original = copy.deepcopy(window.composition)
    window.open_detailed_copy()
    child = window.detail_windows[-1]
    assert child.composition is None
    child.sequence_state_controls["blinds.aperture"].set_value(.8)
    assert window.composition == original
    assert child.sequence != window.sequence


def test_both_studies_are_accessible_without_changing_the_approved_recipe(window):
    assert window.composition["name"] == "Refined signal"
    refined = render_sequence_frame(window.sequence, 11.6, (120, 96)).tobytes()
    buttons = {button.text(): button for button in window.findChildren(QPushButton)}
    buttons["Approved 15s"].click()
    approved = render_sequence_frame(reference_sequence(), 11.6, (120, 96)).tobytes()
    assert render_sequence_frame(window.sequence, 11.6, (120, 96)).tobytes() == approved
    assert approved != refined
    buttons["Refined 15s"].click()
    assert render_sequence_frame(window.sequence, 11.6, (120, 96)).tobytes() == refined


def test_geometry_controls_inherit_override_and_undo(window):
    panel = window.composer
    original = render_sequence_frame(window.sequence, 5.8, (120, 96)).tobytes()
    panel.geometry_shape.setCurrentIndex(panel.geometry_shape.findData("circle"))
    assert panel.geometry_rows["height"].isHidden()
    assert panel.geometry_rows["sides"].isHidden()
    assert not panel.geometry_rows["diameter"].isHidden()
    panel.geometry_controls["diameter"].setValue(45.)
    assert window.composition["geometry"]["diameter"] == .45
    circle = render_sequence_frame(window.sequence, 5.8, (120, 96)).tobytes()
    assert circle != original
    panel.select_section(1)
    assert panel.geometry_shape.currentData() == "inherit"
    assert not panel.geometry_controls["diameter"].isEnabled()
    assert panel.geometry_controls["diameter"].value() == 45.
    panel.geometry_shape.setCurrentIndex(panel.geometry_shape.findData("polygon"))
    panel.geometry_controls["sides"].setValue(3)
    triangle = render_sequence_frame(window.sequence, 5.8, (120, 96)).tobytes()
    assert triangle != circle
    window.undo_composition()
    assert window.composition["sections"][1]["geometry"]["sides"] == 6
    window.redo_composition()
    assert render_sequence_frame(window.sequence, 5.8, (120, 96)).tobytes() == triangle
    panel.reset_controls()
    assert render_sequence_frame(window.sequence, 5.8, (120, 96)).tobytes() == circle
    panel.change_scope(0); panel.reset_controls()
    assert render_sequence_frame(window.sequence, 5.8, (120, 96)).tobytes() == original


def test_detailed_editor_has_named_geometry_choices(window):
    window.open_detailed_copy()
    child = window.detail_windows[-1]
    control = child.sequence_state_controls["blinds.shape"]
    control.spin.setCurrentText("Polygon")
    assert child.sequence["states"][child.sequence_state_name]["overrides"]["blinds.shape"] == 3
    child.sequence_state_controls["blinds.sides"].set_value(5)
    render_sequence_frame(child.sequence, 0., (120, 96))


def test_effect_inspector_shows_animation_and_local_absolute_edits(window):
    panel = window.composer
    panel.select_section(0)
    effects = panel.effects_panel
    effects.selector.setCurrentIndex(effects.selector.findData("rays"))
    assert "Animated" in effects.controls["blinds.rows"].origin.text()
    row = effects.controls["blinds.rows"]
    assert row.value_stack.currentWidget() is row.animated_value
    row.animated_value.click()
    assert row.value_stack.currentWidget() is row.input
    assert "Fixed" in row.origin.text()
    row.reset_button.click()
    assert row.value_stack.currentWidget() is row.animated_value
    panel.select_section(1)
    effects.inspect_effect("rays")
    assert "off" in effects.selector.currentText()
    assert not effects.controls["blinds.rows"].input.isEnabled()
    before = render_sequence_frame(window.sequence, 6.2, (120, 96)).tobytes()
    effects.look.setCurrentText("Venetian blinds")
    effects.apply_button.click()
    assert effects.controls["blinds.rows"].input.isEnabled()
    effects.controls["blinds.rows"].input.setValue(17)
    assert panel.document["sections"][1]["effects"]["rays"]["params"]["blinds.rows"] == 17
    assert "Fixed" in effects.controls["blinds.rows"].origin.text()
    assert render_sequence_frame(window.sequence, 6.2, (120, 96)).tobytes() != before
    effects.restore.click()
    assert render_sequence_frame(window.sequence, 6.2, (120, 96)).tobytes() == before
    window.undo_composition()
    assert panel.document["sections"][1]["effects"]["rays"]["params"]["blinds.rows"] == 17
    window.redo_composition()
    assert not panel.document["sections"][1]["effects"]


def test_new_clip_supports_combining_effects_and_local_bypass(window):
    window.new_composition()
    panel = window.composer; effects = panel.effects_panel
    for effect in ("forms", "ghosts", "breakup"):
        effects.selector.setCurrentIndex(effects.selector.findData(effect))
        effects.apply_button.click()
    assert set(window.composition["effects"]) == {"forms", "ghosts", "breakup"}
    effects.controls["breakup.bands"].input.setValue(9)
    assert window.composition["effects"]["breakup"]["params"]["breakup.bands"] == 9
    panel.select_section(0)
    assert effects.controls["breakup.bands"].input.value() == 9
    assert "whole clip" in effects.controls["breakup.bands"].origin.text()
    effects.mode.setCurrentIndex(effects.mode.findData("off"))
    assert window.composition["effects"]["breakup"]["mode"] == "on"
    assert window.composition["sections"][0]["effects"]["breakup"]["mode"] == "off"
    panel.reset_controls()
    assert effects.controls["breakup.bands"].input.value() == 9


def test_timeline_click_shows_effects_used_by_blocks_and_ghosts(window):
    original = copy.deepcopy(window.composition)
    effects = window.composer.effects_panel
    effects.inspect_effect("rays")
    rect = window.section_timeline.rectangles()[1]
    QTest.mouseClick(window.section_timeline, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
    assert window.composer.index == 1
    assert effects.effect_id == "forms"
    assert effects.summary["forms"]["active"]
    assert effects.summary["ghosts"]["active"]
    assert not effects.summary["rays"]["active"]
    assert "Luminous forms" in effects.used_effects.text()
    assert "Ghosts / trails" in effects.used_effects.text()
    assert "Rays / Venetian blinds" not in effects.used_effects.text()
    # The summary is a navigation control, not an edit to the recipe.
    effects.used_effects.linkActivated.emit("ghosts")
    assert effects.effect_id == "ghosts"
    assert window.composition == original
    assert window.undo_compositions == []
    # Inspecting or turning off an effect deliberately must not switch away.
    effects.inspect_effect("rays")
    assert "Rays / Venetian blinds is off" in effects.status.text()
    window.composer.refresh()
    assert effects.effect_id == "rays"
    effects.inspect_effect("forms")
    effects.mode.setCurrentIndex(effects.mode.findData("off"))
    assert effects.effect_id == "forms"
    assert not effects.summary["forms"]["active"]


def test_particle_example_controls_undo_save_and_threaded_export(window, tmp_path, monkeypatch):
    buttons = {button.text(): button for button in window.findChildren(QPushButton)}
    buttons["Particle head 15s"].click()
    assert len(window.composition["sections"]) == 3
    effects = window.composer.effects_panel
    assert effects.effect_id == "particles"
    assert effects.summary["particles"]["active"]
    assert effects.controls["particles.attractor"].input.currentText() == "Human head"
    assert effects.controls["particles.motion"].input.currentText() == "Surges"
    assert Path(window.suggested_output_path(".mp4")).is_absolute()
    assert Path(window.suggested_output_path(".mp4")).name == "particle-signal.mp4"
    before = render_sequence_frame(window.sequence, 6, (120, 96)).tobytes()
    effects.controls["particles.attractor"].input.setCurrentText("Ring")
    assert render_sequence_frame(window.sequence, 6, (120, 96)).tobytes() != before
    window.undo_composition()
    assert render_sequence_frame(window.sequence, 6, (120, 96)).tobytes() == before
    effects = window.composer.effects_panel
    effects.controls["particles.breathing"].input.setValue(0.)
    effects.controls["particles.assembly"].input.setValue(.6)
    window.composer.duration.setValue(.24)
    document = tmp_path / "particles.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(document), ""))
    window.save_sequence_dialog()
    assert load_composition(document) == window.composition
    output = tmp_path / "particles.mp4"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(output), ""))
    window.export_dialog()
    wait_until(lambda: window.export_job is None)
    assert output.exists(), window.status.text()
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1", str(output)], text=True)
    assert "nb_frames=6" in probe
    buttons["Original particles"].click()
    assert len(window.composition["sections"]) == 1
    assert window.composer.effects_panel.controls["particles.motion"].input.currentText() == "Gentle"
    buttons["Refined 15s"].click()
    assert not window.composer.effects_panel.summary["particles"]["active"]
