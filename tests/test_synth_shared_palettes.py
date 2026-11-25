"""Palette indices are part of the file format; the swatches follow each renderer."""
import copy

import pytest

from nebula.documents.synth_composition import composition_from_sequence
from nebula.documents.synth_sequence import normalize_sequence
from nebula.render.synth import MODULE_BY_ID, default_synth_preset, load_synth, render_synth_frame, save_synth
from nebula.sources.synth_lattice_palettes import palette_values
from nebula.sources.synth_palettes import SHARED_PALETTES
from test_synth_effects_editor_integration import make_window


@pytest.mark.parametrize('module_id, first_shared, ink_count', (
    ('ink_bloom', 3, 4), ('radial_bloom', 3, 9), ('prismatic_field', 3, 8),
    ('color_field', 3, 8), ('solid', 3, 8), ('chromatic_lattice', 4, 9),
    ('image_memory', 4, 3), ('signal_tension', 4, 2), ('pleated_field', 5, 5),
))
def test_shared_choices_render_and_keep_their_saved_index(module_id, first_shared, ink_count, tmp_path):
    spec = next(p for p in MODULE_BY_ID[module_id].params if p.key == 'palette')
    assert spec.choices[first_shared:] == tuple(p.label for p in SHARED_PALETTES)
    assert spec.maximum == len(spec.choices) - 1
    preset = default_synth_preset()
    preset.update(width=128, height=160, speed=1.)
    modules = {m['id']: m for m in preset['modules']}
    for key, entry in modules.items():
        entry['enabled'] = key == module_id or (module_id == 'signal_tension' and key == 'prismatic_field')
    frames = set()
    for index, shared in enumerate(SHARED_PALETTES, first_shared):
        assert len(spec.swatches[index]) == ink_count
        assert set(spec.swatches[index]) <= set(shared.colors)
        modules[module_id]['params']['palette'] = index
        frames.add(render_synth_frame(preset, time_seconds=1.37).tobytes())
    assert len(frames) == len(SHARED_PALETTES)
    path = tmp_path / 'palette.nebula'
    save_synth(path, preset)
    assert load_synth(path) == preset


def test_printed_cells_apply_only_visible_color_roles_and_undo_as_one_edit(make_window):
    state = dict(preset='Reference blinds', enabled=['chromatic_lattice'],
                 overrides={'chromatic_lattice.surface': 1, 'chromatic_lattice.eye_enabled': 0})
    seq = normalize_sequence(dict(schema_version=1, render_version=2, name='Cells',
        duration=2., fps=24, states={'cells': state}, cues=[dict(time=0., state='cells', transition='cut')]))
    window = make_window(composition=composition_from_sequence(seq))
    composer = window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    before = copy.deepcopy(composer.document)
    menu = composer.object_panel.palette_selector.combo
    selected = SHARED_PALETTES[1]
    index = menu.findData(selected.key)
    assert not menu.itemIcon(index).isNull()
    menu.activated.emit(index)
    assert menu.currentData() == selected.key
    assert composer.document['effects']['chromatic_lattice']['params'] == palette_values(selected.key, eye=False)
    window.undo_composition()
    assert composer.document == before
