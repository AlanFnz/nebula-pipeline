"""Sequence edits must change the model consumed by both preview and export."""
import copy
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from synth_studio import SynthStudio
from synth import curated_presets
from synth_sequence import load_sequence, reference_sequence, render_sequence_frame, save_sequence


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    window = SynthStudio(preset=curated_presets()["Reference blinds"], sequence=reference_sequence())
    app.processEvents()
    yield window
    window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()


def test_selected_state_edit_survives_round_trip_and_changes_pixels(window, tmp_path):
    original = render_sequence_frame(window.sequence, 0, (120, 96)).tobytes()
    control = window.sequence_state_controls["blinds.aperture"]
    control.set_value(.55)
    path = tmp_path / "edited.json"
    save_sequence(path, window.sequence)
    restored = load_sequence(path)
    assert restored["states"]["blinds"]["overrides"]["blinds.aperture"] == .55
    result = render_sequence_frame(restored, 0, (120, 96)).tobytes()
    assert result != original
    assert result == render_sequence_frame(window.sequence, 0, (120, 96)).tobytes()


def test_toggle_keeps_inherited_modules_and_variation_respects_locks(window):
    window.sequence_module_enabled_changed("warp", False)
    enabled = window.sequence["states"]["blinds"]["enabled"]
    assert "blinds" in enabled and "raster" in enabled and "warp" not in enabled
    control = window.sequence_state_controls["blinds.aperture"]
    control.lock.setChecked(True)
    before = control.value()
    original = copy.deepcopy(window.sequence)
    window.generate_variation()
    assert control.value() == before
    assert window.sequence != original


def test_invalid_cue_and_duration_edits_do_not_poison_sequence(window):
    before = copy.deepcopy(window.sequence)
    window.sequence_table.item(0, 0).setText("nan")
    assert window.sequence == before
    window.sequence_field_controls["duration"].setValue(1)
    assert window.sequence == before
    assert window.sequence_field_controls["duration"].value() == 15


def test_add_cue_accepts_custom_state_names(window):
    state = copy.deepcopy(window.sequence["states"]["blinds"])
    window.sequence["states"] = {"custom": state}
    window.sequence["cues"] = [{"time": 0., "state": "custom", "transition": "cut", "duration": 0.}]
    window.sequence_state_name = "custom"
    window.rebuild_modules()
    window.add_sequence_cue()
    assert all(cue["state"] == "custom" for cue in window.sequence["cues"])


def test_cue_selection_scrubs_and_duplicate_is_bound_to_that_cue(window):
    index = next(index for index, cue in enumerate(window.sequence["cues"]) if cue["state"] == "magenta")
    cue = copy.deepcopy(window.sequence["cues"][index])
    window.sequence_table.selectRow(index)
    assert window.current_time == cue["time"]
    assert window.sequence_state_name == "magenta"
    window.duplicate_sequence_state()
    name = window.sequence_state_name
    assert name != "magenta"
    assert window.sequence["cues"][index]["state"] == name
    before = copy.deepcopy(window.sequence["states"]["magenta"])
    window.sequence_state_controls["slab.width"].set_value(.6)
    assert window.sequence["states"]["magenta"] == before
    assert window.sequence["states"][name]["overrides"]["slab.width"] == .6
