"""Radial objects share treatment anchors and clear inspector grouping."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from synth import MODULE_BY_ID, default_synth_preset
from synth_composition import compile_composition
from synth_effects import effect_preset
from synth_effects_ui import EffectsPanel
from synth_inspector import control_group
from synth_radial_recipes import radial_composition
from synth_regions import LocalFrame
from synth_source_adapters import ANCHORS, phosphor_inputs, source_frame


def radial_preset():
    preset = default_synth_preset()
    preset.update(speed=1.5, width=200, height=160)
    for module in preset['modules']:
        module['enabled'] = module['id'] == 'radial_bloom'
        if module['id'] == 'radial_bloom':
            module['params'].update(expansion=1.2, rotation=3., center_drift=.4)
    return preset


def test_radial_auto_and_explicit_anchor_follow_continuous_motion_and_position():
    preset = radial_preset()
    automatic = source_frame(preset, (200, 160), 0., continuous_time=2.)
    explicit = source_frame(preset, (200, 160), 2., 'radial_bloom')
    assert isinstance(automatic, LocalFrame)
    assert automatic == explicit
    assert automatic.angle == -9.
    assert automatic.unit == pytest.approx(160*.5*1.2)
    held = source_frame(preset, (200, 160), 0., 'radial_bloom')
    assert automatic.origin != held.origin
    moved = source_frame(dict(preset, object_x=18., object_y=-6.), (200, 160), 0., continuous_time=2.)
    assert np.subtract(moved.origin, automatic.origin) == pytest.approx((18., -6.))


def test_radial_appended_anchor_keeps_legacy_indexes_and_primary_text_priority():
    assert ANCHORS[:7] == ('auto', 'silhouette', 'slab', 'ink_bloom', 'particles', 'blinds', 'text')
    assert ANCHORS[7] == 'radial_bloom'
    preset = radial_preset()
    # Text retains priority when deliberately layered with another source.
    text = next(module for module in preset['modules'] if module['id'] == 'text')
    text['enabled'] = True
    assert source_frame(preset, (200, 160), 1.) == source_frame(preset, (200, 160), 1., 'text')


def test_phosphor_object_region_uses_radial_frame_for_auto_and_explicit_anchor():
    preset = radial_preset()
    params = {spec.key: spec.default for spec in MODULE_BY_ID['edge_phosphor'].params}
    params.update(fade_mode=1, fade_strength=.8, fade_start=.1, fade_width=.4)
    arr = np.ones((160, 200, 3), np.float32)
    automatic, context, region, _ = phosphor_inputs(arr, params, .5, preset, 7, 2.)
    explicit, _, explicit_region, _ = phosphor_inputs(arr, dict(params, fade_anchor=7), .5, preset, 7, 2.)
    assert automatic.frame == explicit.frame == source_frame(preset, (200, 160), 2.)
    assert context.continuous_time == 2. and context.held_time == .5
    assert region is not None
    assert np.array_equal(region.evaluate((200, 160), automatic.frame), explicit_region.evaluate((200, 160), explicit.frame))


@pytest.mark.parametrize('key,group', [
    ('expansion', 'Shape & layout'), ('petals', 'Shape & layout'),
    ('detail', 'Texture & detail'), ('branching', 'Texture & detail'),
    ('softness', 'Texture & detail'), ('grain', 'Texture & detail'),
    ('flow', 'Motion & timing'), ('variation', 'Motion & timing'),
    ('rotation', 'Motion & timing'), ('phase', 'Motion & timing'),
    ('center_drift', 'Motion & timing'), ('drift_speed', 'Motion & timing'),
    ('palette', 'Color & light'), ('color_phase', 'Color & light'),
    ('color_speed', 'Color & light'), ('light', 'Color & light'),
])
def test_radial_control_groups(key, group):
    assert control_group('radial_bloom.'+key) == group


@pytest.mark.parametrize('anchor', (0, 7))
def test_phosphor_editor_recognizes_radial_object_anchor(anchor):
    app = QApplication.instance() or QApplication([])
    project = radial_composition()
    entry = effect_preset('edge_phosphor')
    entry['params'].update({'edge_phosphor.fade_mode': 1, 'edge_phosphor.fade_anchor': anchor,
                            'edge_phosphor.fade_strength': .8})
    project['effects']['edge_phosphor'] = entry
    states = list(compile_composition(project)['states'].values())
    panel = EffectsPanel()
    panel.set_context(project['effects'], {}, states, 'Entire project', False, ('radial',))
    panel.inspect_effect('edge_phosphor')
    panel.parameter_tabs.setCurrentIndex(1)
    panel.show()
    app.processEvents()
    assert 'anchor is not present' not in panel.status.text()
    panel.close()
