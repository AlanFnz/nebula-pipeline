"""Suspended assembly routing, legacy requests and per-part editing."""
import math

from PIL import Image
import pytest

from nebula.documents.synth_composition import compile_composition, composition_from_sequence, stretch_section
from nebula.documents.synth_sequence import normalize_sequence, render_sequence_frame
from nebula.sources import synth_blender_bridge
from nebula.sources.synth_blender import SUSPENDED_KEYS
from nebula.sources.synth_blender_parts import parts_for
from test_synth_effects_editor_integration import make_window


def composition(scene, **settings):
    params = dict(scene=scene, period=4., ease=0., pose_steps=0, **settings)
    state = dict(preset='Reference blinds', enabled=['blender_scene'],
                 overrides={'speed': 1., **{'blender_scene.'+key: value for key,value in params.items()}})
    seq = normalize_sequence(dict(schema_version=1, render_version=2, duration=4., fps=12,
                                  states={'shape': state}, cues=[dict(time=0., state='shape', transition='cut')]))
    return composition_from_sequence(seq)


@pytest.fixture
def requests(monkeypatch):
    calls = []
    def render(settings, angle, size, *, parts=None):
        calls.append((settings, angle, parts))
        return Image.new('RGB', size)
    monkeypatch.setattr(synth_blender_bridge, 'render_frame', render)
    return calls


@pytest.mark.parametrize('scene', (0, 1))
def test_earlier_assemblies_ignore_suspended_controls(scene, requests):
    for changes in ({}, {'ring_count': 2, 'lens_squeeze': .5, 'part_ring6_position_x': .4}):
        render_sequence_frame(compile_composition(composition(scene, **changes)), .25, (48, 64))
    assert requests[0] == requests[1]
    assert SUSPENDED_KEYS.isdisjoint(requests[0][0])
    assert 'ring6' not in {part for part,_,_ in parts_for(scene)}


def test_suspended_source_uses_all_six_rings_and_continues_after_extend(requests):
    project = composition(2, part_ring6_rotation_x=40., orbit_tilt_3=80.)
    longer = stretch_section(project, project['sections'][0]['id'], 8., 'smart')
    for document, time in ((project,.5), (longer,.5), (longer,4.5), (longer,5.)):
        render_sequence_frame(compile_composition(document), time, (48,64))
    assert requests[0] == requests[1] == requests[2]
    settings, angle, parts = requests[0]
    assert settings['orbit_tilt_3'] == 80 and angle == pytest.approx(math.pi/4)
    assert parts['ring6']['rotation'][0] == 40
    assert requests[-1][1] != angle
    assert [key for key,_,_ in parts_for(2,2)] == ['ring1','ring2','core']


def test_object_navigation_filters_parts_and_exposes_the_light_rig(make_window, requests):
    studio = make_window(composition=composition(2, ring_count=3))
    panel = studio.composer.object_panel
    studio.composer.look_tabs.setCurrentWidget(panel)
    assert [panel.part_selector.itemData(i) for i in range(panel.part_selector.count())] == [
        None, 'ring1', 'ring2', 'ring3', 'core']
    assert 'blender_scene.lens_squeeze' in panel.object_eligible
    assert 'blender_scene.base_width' not in panel.object_eligible
    assert panel.color_panel.cards['blender_strip'].isVisible()


def test_center_shape_is_opt_in_and_the_center_turn_continues_after_extension(requests):
    for scene in (0, 1, 2):
        for settings in ({}, {'center_shape': int(scene != 2)}):
            render_sequence_frame(compile_composition(composition(scene, **settings)), .5, (48, 64))
        assert requests[-1] == requests[-2]
        assert 'center_shape' not in requests[-1][0]
    project = composition(2, center_shape=1, ring_count=1, part_core_follow=0,
                          part_core_turns_x=-1, part_core_period=4.)
    longer = stretch_section(project, project['sections'][0]['id'], 8., 'smart')
    for doc, seconds in ((project, .5), (longer, 4.5), (longer, 5.)):
        render_sequence_frame(compile_composition(doc), seconds, (48, 64))
    assert requests[-3] == requests[-2]
    params, _, parts = requests[-1]
    assert synth_blender_bridge._runner(params) == synth_blender_bridge.SUSPENDED_CENTER
    assert parts['core']['rotation'][0] == pytest.approx(270.)
    assert not parts['core']['follow']
    assert synth_blender_bridge._runner({'scene': 2}) == synth_blender_bridge.SUSPENDED


def test_center_geometry_has_its_own_part_and_shape_controls(make_window, requests):
    studio = make_window(composition=composition(2, ring_count=1, center_shape=1))
    panel = studio.composer.object_panel
    studio.composer.look_tabs.setCurrentWidget(panel)
    assert [panel.part_selector.itemText(i) for i in range(panel.part_selector.count())] == [
        'Whole assembly', 'Ring 1 / outer', 'Infinity loop']
    assert panel.controls['blender_scene.hoop_bow'].label.text() == 'Crossing depth'
    assert {'blender_scene.center_shape', 'blender_scene.tube_radius', 'blender_scene.hoop_bow'} <= panel.object_eligible
