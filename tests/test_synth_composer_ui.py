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
from synth_composition import compile_composition, load_composition
from synth_sequence import render_sequence_frame, reference_sequence


def wait_until(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate(): return
        time.sleep(.01)
    raise AssertionError("Composer did not settle")


def choose_starter(window, identifier):
    window.starter_combo.setCurrentIndex(window.starter_combo.findData(identifier))
    window.load_starter_button.click()


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
    choose_starter(window, "approved")
    approved = render_sequence_frame(reference_sequence(), 11.6, (120, 96)).tobytes()
    assert render_sequence_frame(window.sequence, 11.6, (120, 96)).tobytes() == approved
    assert approved != refined
    choose_starter(window, "refined")
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
    choose_starter(window, "particle-head")
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
    choose_starter(window, "particle-orbit")
    effects = window.composer.effects_panel
    assert len(window.composition["sections"]) == 2
    assert effects.controls["particles.release"].input.currentText() == "Expand / orbit"
    assert effects.controls["particles.motion"].input.currentText() == "Impulse"
    assert effects.controls["particles.attractor"].input.currentText() == "Portrait head"
    assert effects.controls["particles.occlusion"].input.value() == 1.
    assert effects.controls["particles.rotation_speed"].input.value() == 18.
    assert effects.controls["particles.turn_scope"].input.currentText() == "Assembled only"
    assert effects.controls["particles.axis_mode"].input.currentText() == "Centered"
    assert effects.controls["particles.neck_fade"].input.value() == .42
    assert effects.controls["particles.orbit_handoff"].input.currentText() == "Carry orbit"
    assert effects.summary["tape"]["active"]
    assert not effects.summary["rays"]["active"]
    assert effects.controls["particles.period"].input.value() == 7.5
    before = render_sequence_frame(window.sequence, 2.36, (120, 96)).tobytes()
    effects.controls["particles.motion_peak"].input.setValue(0.)
    assert render_sequence_frame(window.sequence, 2.36, (120, 96)).tobytes() != before
    window.undo_composition()
    assert render_sequence_frame(window.sequence, 2.36, (120, 96)).tobytes() == before
    effects = window.composer.effects_panel
    before = render_sequence_frame(window.sequence, 4., (120, 96)).tobytes()
    effects.controls["particles.orbit_speed"].input.setValue(-40.)
    assert render_sequence_frame(window.sequence, 4., (120, 96)).tobytes() != before
    window.undo_composition()
    assert render_sequence_frame(window.sequence, 4., (120, 96)).tobytes() == before
    assert Path(window.suggested_output_path(".mp4")).name == "particle-orbit.mp4"
    effects = window.composer.effects_panel
    effects.inspect_effect("tape")
    before = render_sequence_frame(window.sequence, 1., (120, 96)).tobytes()
    effects.controls["tape.tracking"].input.setValue(.2)
    assert render_sequence_frame(window.sequence, 1., (120, 96)).tobytes() != before
    window.undo_composition()
    assert render_sequence_frame(window.sequence, 1., (120, 96)).tobytes() == before
    effects = window.composer.effects_panel
    effects.inspect_effect("particles")
    for path, value, t in (("particles.rotation_speed", 0., 1.8), ("particles.axis_mode", 0, 4.), ("particles.neck_fade", 0., 0.), ("particles.orbit_handoff", 0, 6.2)):
        before = render_sequence_frame(window.sequence, t, (120, 96)).tobytes()
        control = effects.controls[path].input
        if path in ("particles.axis_mode", "particles.orbit_handoff"):
            control.setCurrentIndex(value)
        else:
            control.setValue(value)
        assert render_sequence_frame(window.sequence, t, (120, 96)).tobytes() != before
        window.undo_composition()
        assert render_sequence_frame(window.sequence, t, (120, 96)).tobytes() == before
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
    choose_starter(window, "original-particles")
    assert len(window.composition["sections"]) == 1
    assert window.composer.effects_panel.controls["particles.motion"].input.currentText() == "Gentle"
    choose_starter(window, "refined")
    assert not window.composer.effects_panel.summary["particles"]["active"]


def test_canvas_switch_is_undoable_and_preserves_scene_and_playhead(window, tmp_path, monkeypatch):
    choose_starter(window, "particle-orbit")
    window.timeline.setValue(160)
    before = copy.deepcopy(window.composition)
    old_pixels = render_sequence_frame(window.sequence, 6.4, (180, 144)).tobytes()
    window.canvas_combo.setCurrentIndex(window.canvas_combo.findData("stories"))
    assert window.composition["source"] == before["source"]
    assert window.composition["sections"] == before["sections"]
    assert window.current_time == 6.4
    assert window.current_canvas() == {"width": 1080, "height": 1920, "framing": "preserve", 'reference': before['canvas']}
    wait_until(lambda: window.viewer.packet is not None and window.viewer.packet[0] == (202, 360))
    assert window.viewer.packet[0] == (202, 360)
    assert "1080 × 1920" in window.canvas_label.text()
    window.undo_composition()
    assert window.composition == before
    assert window.canvas_combo.currentData() == "original"
    assert render_sequence_frame(window.sequence, 6.4, (180, 144)).tobytes() == old_pixels
    window.redo_composition()
    assert window.canvas_combo.currentData() == "stories"
    path = tmp_path / "story.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
    window.save_sequence_dialog()
    window.canvas_combo.setCurrentIndex(window.canvas_combo.findData("square"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))
    window.load_sequence_dialog()
    assert window.canvas_combo.currentData() == "stories"
    window.open_detailed_copy()
    assert window.detail_windows[-1].current_canvas() == window.current_canvas()
    window.composer.duration.setValue(.16)
    # Draft preview must still export the selected full-resolution canvas.
    output = tmp_path / "story.mp4"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(output), ""))
    window.export_dialog()
    assert window.export_job.size == (1080, 1920)
    wait_until(lambda: window.export_job is None, seconds=30)
    assert output.exists(), window.status.text()


def test_starter_menu_requires_load_and_uses_current_canvas(window):
    before = copy.deepcopy(window.composition)
    window.starter_combo.setCurrentIndex(window.starter_combo.findData("particle-orbit"))
    assert window.composition == before
    window.canvas_combo.setCurrentIndex(window.canvas_combo.findData("stories"))
    window.load_starter_button.click()
    assert len(window.composition["sections"]) == 2
    assert window.canvas_combo.currentData() == "stories"
    assert window.composition["canvas"]["height"] == 1920
    window.composer.effects_panel.controls["particles.rotation_speed"].input.setValue(45.)
    window.load_starter_button.click()
    assert window.composer.effects_panel.controls["particles.rotation_speed"].input.value() == 18.
    assert window.canvas_combo.currentData() == "stories"


def test_ink_starter_exposes_both_effects_and_persists_customization(window, tmp_path, monkeypatch):
    window.canvas_combo.setCurrentIndex(window.canvas_combo.findData('square'))
    choose_starter(window, 'ink-bloom')
    assert window.composition['fps'] == 15
    assert len(window.composition['sections']) == 1
    assert window.composer.effects_panel.effect_id == 'ink_bloom'
    before = copy.deepcopy(window.composition)
    panel = window.composer.effects_panel
    panel.controls['ink_bloom.count'].input.setValue(9)
    panel.controls['ink_bloom.size'].input.setValue(.18)
    panel.inspect_effect('print_surface')
    panel.controls['print_surface.ink_wear'].input.setValue(.6)
    changed = copy.deepcopy(window.composition)
    assert changed['effects']['ink_bloom']['params']['ink_bloom.count'] == 9
    assert changed['effects']['print_surface']['params']['print_surface.ink_wear'] == .6
    window.undo_composition()
    assert 'print_surface' not in window.composition['effects']
    window.redo_composition()
    assert window.composition == changed
    path = tmp_path / 'printed.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    window.save_sequence_dialog()
    assert load_composition(path) == changed
    window.canvas_combo.setCurrentIndex(window.canvas_combo.findData('stories'))
    assert window.composition['effects'] == changed['effects']
    assert window.composition['source'] == before['source']
    window.open_detailed_copy()
    assert window.detail_windows[-1].current_canvas()['height'] == 1920


def test_frame_noise_controls_are_editable_and_undoable(window, tmp_path, monkeypatch):
    choose_starter(window, 'ink-bloom')
    panel = window.composer.effects_panel
    panel.inspect_effect('print_surface')
    assert panel.controls['print_surface.background_mode'].input.currentIndex() == 1
    before = copy.deepcopy(window.composition)
    panel.controls['print_surface.noise_amount'].input.setValue(1.4)
    changed = copy.deepcopy(window.composition)
    assert changed['effects']['print_surface']['params']['print_surface.noise_amount'] == 1.4
    assert changed['source'] == before['source']
    window.undo_composition()
    assert window.composition == before
    window.redo_composition()
    assert window.composition == changed
    path = tmp_path / 'noise-background.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    window.save_sequence_dialog()
    assert load_composition(path) == changed
    panel.controls['print_surface.background_mode'].input.setCurrentIndex(0)
    assert window.composition['effects']['print_surface']['params']['print_surface.background_mode'] == 0


def test_imported_stamp_is_undoable_portable_and_available_in_detailed_editor(window, tmp_path, monkeypatch):
    from PIL import Image, ImageDraw
    from synth_artwork import decode_artwork
    choose_starter(window, 'ink-bloom')
    panel = window.composer.effects_panel
    panel.inspect_effect('ink_bloom')
    before = copy.deepcopy(window.composition)
    image = Image.new('RGBA', (100, 160))
    ImageDraw.Draw(image).ellipse((10, 10, 89, 149), fill='white')
    source = tmp_path / 'cutout.png'; image.save(source)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(source), ''))
    panel.controls['ink_bloom.artwork'].input.import_button.click()
    imported = copy.deepcopy(window.composition)
    params = imported['effects']['ink_bloom']['params']
    assert params['ink_bloom.shape'] == 5
    assert decode_artwork(params['ink_bloom.artwork']).size == (80, 140)
    assert panel.controls['ink_bloom.shape'].input.currentIndex() == 5
    assert imported['source'] == before['source']
    window.undo_composition(); assert window.composition == before
    window.redo_composition(); assert window.composition == imported
    source.unlink()
    saved = tmp_path / 'portable.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(saved), ''))
    window.save_sequence_dialog()
    assert load_composition(saved) == imported
    window.open_detailed_copy()
    detailed = window.detail_windows[-1]
    assert detailed.sequence_state_controls['ink_bloom.artwork'].value() == params['ink_bloom.artwork']
    assert detailed.sequence_state_controls['ink_bloom.shape'].value() == 5
    # Generating variations must never try to randomize a binary asset.
    detailed.generate_variation()
    assert detailed.sequence_state_controls['ink_bloom.artwork'].value() == params['ink_bloom.artwork']
    panel.controls['ink_bloom.shape'].input.setCurrentIndex(1)
    assert panel.controls['ink_bloom.artwork'].input.value() == params['ink_bloom.artwork']
    window.undo_composition(); assert window.composition == imported
    panel.controls['ink_bloom.artwork'].input.clear_button.click()
    assert not panel.controls['ink_bloom.artwork'].input.value()
    assert 'Import artwork' in panel.status.text()
    window.undo_composition(); assert window.composition == imported


def test_cancelled_or_bad_artwork_import_does_not_change_document(window, tmp_path, monkeypatch):
    from synth_artwork_ui import QMessageBox, QInputDialog
    from PIL import Image
    choose_starter(window, 'ink-bloom')
    panel = window.composer.effects_panel
    panel.inspect_effect('ink_bloom')
    before = copy.deepcopy(window.composition)
    importer = panel.controls['ink_bloom.artwork'].input
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: ('', ''))
    importer.import_button.click()
    assert window.composition == before
    source = tmp_path / 'empty.png'; Image.new('RGBA', (20, 20)).save(source)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(source), ''))
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    importer.import_button.click()
    assert errors and window.composition == before
    Image.new('RGB', (20, 20), 'white').save(source)
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: ('', False))
    importer.import_button.click()
    assert window.composition == before


def test_frame_jitter_starter_scope_undo_save_and_detailed_controls(window, tmp_path, monkeypatch):
    choose_starter(window, 'mixed-media')
    panel = window.composer; effects = panel.effects_panel
    assert effects.effect_id == 'frame_jitter'
    assert len(window.composition['sections']) == 2
    assert effects.controls['frame_jitter.x'].input.value() == 5.
    before = copy.deepcopy(window.composition)
    effects.controls['frame_jitter.x'].input.setValue(7.)
    changed = copy.deepcopy(window.composition)
    assert changed['source'] == before['source']
    assert changed['effects']['frame_jitter']['params']['frame_jitter.x'] == 7.
    window.undo_composition(); assert window.composition == before
    window.redo_composition(); assert window.composition == changed
    panel.select_section(1)
    effects.controls['frame_jitter.rate'].input.setValue(10)
    assert window.composition['sections'][1]['effects']['frame_jitter']['params']['frame_jitter.rate'] == 10
    assert not window.composition['sections'][0]['effects']
    saved = copy.deepcopy(window.composition)
    path = tmp_path / 'hand-registration.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    window.save_sequence_dialog()
    assert load_composition(path) == saved
    window.open_detailed_copy()
    child = window.detail_windows[-1]
    assert 'frame_jitter.x' in child.sequence_state_controls
    assert 'frame_jitter.seed' in child.sequence_state_controls
    child.sequence_state_controls['frame_jitter.x'].set_value(2.)
    assert window.composition == saved


def test_low_res_finish_native_controls_scope_undo_and_save(window, tmp_path, monkeypatch):
    choose_starter(window, 'mixed-media')
    panel = window.composer; effects = panel.effects_panel
    before = copy.deepcopy(window.composition)
    effects.inspect_effect('low_res')
    effects.apply_button.click()
    assert effects.controls['low_res.resolution'].input.value() == 360
    assert effects.controls['low_res.sampling'].input.currentText() == 'Soft'
    effects.controls['low_res.resolution'].input.setValue(240)
    effects.controls['low_res.sampling'].input.setCurrentIndex(1)
    changed = copy.deepcopy(window.composition)
    assert changed['source'] == before['source']
    assert changed['effects']['low_res']['params'] == {'low_res.resolution': 240, 'low_res.sampling': 1}
    window.undo_composition()
    assert window.composition['effects']['low_res']['params']['low_res.sampling'] == 0
    window.redo_composition(); assert window.composition == changed
    panel.select_section(1)
    effects.controls['low_res.resolution'].input.setValue(180)
    assert window.composition['sections'][1]['effects']['low_res']['params']['low_res.resolution'] == 180
    assert not window.composition['sections'][0]['effects']
    saved = copy.deepcopy(window.composition)
    path = tmp_path / 'low-res.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    window.save_sequence_dialog()
    assert load_composition(path) == saved
    window.open_detailed_copy()
    assert 'low_res.resolution' in window.detail_windows[-1].sequence_state_controls
    assert 'low_res.sampling' in window.detail_windows[-1].sequence_state_controls


def test_ink_timing_tabs_seconds_scope_reset_undo_and_save(window, tmp_path, monkeypatch):
    choose_starter(window, 'mixed-media')
    panel = window.composer; effects = panel.effects_panel
    effects.inspect_effect('ink_bloom')
    effects.parameter_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    assert not effects.controls['ink_bloom.shape'].isVisible()
    assert effects.controls['ink_bloom.motion_speed'].isVisible()
    assert effects.controls['ink_bloom.unfold_seconds'].animated_value.isVisible()
    assert effects.controls['ink_bloom.folded_seconds'].input.value() > 0
    assert not effects.controls['ink_bloom.period'].isVisible()
    before = copy.deepcopy(window.composition)
    effects.controls['ink_bloom.unfold_seconds'].input.setValue(.4)
    effects.controls['ink_bloom.unfolded_seconds'].input.setValue(1.5)
    changed = copy.deepcopy(window.composition)
    assert changed['ink_timing']['ink_bloom.unfold_seconds'] == .4
    assert changed['source'] == before['source']
    window.undo_composition()
    assert window.composition['ink_timing']['ink_bloom.unfolded_seconds'] == pytest.approx(53 / 15 * .16)
    window.redo_composition(); assert window.composition == changed
    panel.select_section(1)
    effects.controls['ink_bloom.folded_seconds'].input.setValue(2.)
    assert window.composition['ink_timing']['ink_bloom.folded_seconds'] == 2.
    assert not window.composition['sections'][1]['effects']
    assert not panel.scope_combo.isVisible()
    assert panel.timing_scope_label.isVisible()
    panel.select_section(0)
    assert effects.controls['ink_bloom.folded_seconds'].input.value() == 2.
    effects.controls['ink_bloom.folded_seconds'].reset_button.click()
    assert effects.controls['ink_bloom.folded_seconds'].input.value() == pytest.approx(53 / 15 * .29, abs=.001)
    saved = copy.deepcopy(window.composition)
    path = tmp_path / 'ink-timing.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    window.save_sequence_dialog(); assert load_composition(path) == saved
    effects.more.setChecked(True)
    QApplication.processEvents()
    assert effects.controls['ink_bloom.phase'].isVisible()
    assert not effects.controls['ink_bloom.period'].isVisible()
    effects.parameter_tabs.setCurrentIndex(0)
    assert effects.controls['ink_bloom.shape'].isVisible()
    assert not effects.controls['ink_bloom.unfold_seconds'].isVisible()
    assert not effects.more.isChecked()
    assert panel.scope_combo.isVisible()
    assert not panel.timing_scope_label.isVisible()
    window.open_detailed_copy()
    child = window.detail_windows[-1]
    assert 'ink_bloom.unfold_seconds' in child.sequence_state_controls
    assert child.sequence_state_controls['ink_bloom.fold_seconds'].value() == pytest.approx(53 / 15 * .27, abs=.01)
    child.sequence_state_controls['ink_bloom.unfold_seconds'].set_value(.6)
    assert window.composition == saved
    panel.change_scope(0); panel.reset_controls()
    assert not window.composition['ink_timing']
    assert [s['duration'] for s in window.composition['sections']] == [53 / 15] * 2
    window.undo_composition(); assert window.composition == saved


def test_master_tab_is_global_reversible_and_preserved_in_detailed_copies(window, tmp_path, monkeypatch):
    from synth_master import DEFAULT_MASTER
    choose_starter(window, 'mixed-media')
    panel = window.composer; master = panel.master_panel
    panel.select_section(1); panel.look_tabs.setCurrentWidget(master)
    QApplication.processEvents()
    assert not panel.scope_combo.isVisible()
    assert panel.master_scope_label.isVisible()
    assert not panel.timing_scope_label.isVisible()
    original = copy.deepcopy(window.composition)
    master.sliders['contrast'].setValue(130)
    master.controls['contrast'].setValue(140)
    assert window.composition['master']['contrast'] == 1.4
    assert master.sliders['contrast'].value() == 140
    # A drag is one undo step, even while a section is selected.
    window.undo_composition(); assert window.composition == original
    window.redo_composition(); assert window.composition['master']['contrast'] == 1.4
    master.controls['brightness'].setValue(8)
    master.controls['saturation'].setValue(45)
    saved = copy.deepcopy(window.composition)
    panel.select_section(0)
    assert master.controls['contrast'].value() == 140
    assert window.composition['source'] == original['source']
    assert window.composition['sections'] == original['sections']
    for time in (1.4, 4.8):
        original_frame = render_sequence_frame(compile_composition(original), time, (96, 96))
        assert render_sequence_frame(window.sequence, time, (96, 96)).tobytes() != original_frame.tobytes()
        master.enabled.click()
        assert render_sequence_frame(window.sequence, time, (96, 96)).tobytes() == original_frame.tobytes()
        master.enabled.click()
    assert window.composition == saved
    path = tmp_path / 'master.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    window.save_sequence_dialog(); assert load_composition(path) == saved
    window.open_detailed_copy()
    child = window.detail_windows[-1]
    assert child.sequence_master_panel.controls['contrast'].value() == 140
    child.sequence_master_panel.controls['saturation'].setValue(0)
    assert child.sequence['master']['saturation'] == 0
    assert window.composition == saved
    panel.reset_controls()
    assert window.composition['master'] == DEFAULT_MASTER
    assert window.composition['sections'] == saved['sections']
    window.undo_composition(); assert window.composition == saved
    master.resets['brightness'].click()
    assert window.composition['master']['brightness'] == 0
    assert window.composition['master']['contrast'] == 1.4
    panel.look_tabs.setCurrentIndex(0)
    assert panel.scope_combo.isVisible() and not panel.master_scope_label.isVisible()


def test_all_native_parameter_controls_are_protected_from_wheel_edits(window):
    from PySide6.QtWidgets import QComboBox, QAbstractSpinBox, QSlider
    from studio_widgets import ScrollThrough
    for key in ('refined', 'mixed-media', 'particle-orbit'):
        choose_starter(window, key)
        for kind in (QComboBox, QAbstractSpinBox, QSlider):
            assert all(isinstance(control, ScrollThrough) for control in window.findChildren(kind))
    window.open_detailed_copy()
    for kind in (QComboBox, QAbstractSpinBox, QSlider):
        assert all(isinstance(control, ScrollThrough) for control in window.detail_windows[-1].findChildren(kind))
