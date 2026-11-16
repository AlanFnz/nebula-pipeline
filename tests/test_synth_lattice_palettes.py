import copy

import pytest
from PySide6.QtWidgets import QApplication

from synth_composition import compile_composition, load_composition, save_composition
from synth_lattice_palettes import PALETTES, palette_values
from synth_lattice_recipes import watching_eye_composition, printed_orbit_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from test_synth_effects_editor_integration import make_window


def choose(composer, key):
    menu = composer.object_panel.palette_selector.combo
    index = menu.findData(key)
    menu.setCurrentIndex(index); menu.activated.emit(index)


def resolved(doc, t=0):
    preset = resolve_sequence_frame(compile_composition(doc),t)[-1]
    return {m['id']+'.'+k:v for m in preset['modules'] for k,v in m['params'].items()}


def test_palette_navigation_and_current_choice_are_read_only(make_window):
    w=make_window(composition=watching_eye_composition());c=w.composer;p=c.object_panel
    c.look_tabs.setCurrentWidget(p);before=copy.deepcopy(c.document)
    assert p.palette_selector.isVisible()
    assert p.palette_selector.combo.currentData()=='original'
    choose(c,'original')
    for query in ('skin','palette','color','Eye ripple',''):
        p.object_filter.setText(query);QApplication.processEvents()
        assert p.palette_selector.isVisible()==(query!='Eye ripple')
        if query=='skin':assert p.no_object_matches.isHidden()
    assert c.document==before and not w.has_unsaved_changes()


@pytest.mark.parametrize('key',[p.key for p in PALETTES if p.key!='original'])
def test_palette_changes_only_colors_and_round_trips_with_one_undo(make_window,tmp_path,key):
    doc=watching_eye_composition()
    doc['effects']['chromatic_lattice']={'mode':'recipe','params':{
        'chromatic_lattice.eye_ripple':.8,'chromatic_lattice.eye_ripple_response':3,
        'chromatic_lattice.eye_ripple_glow':90.,'chromatic_lattice.eye_placement':1}}
    w=make_window(composition=doc);c=w.composer;before=copy.deepcopy(c.document)
    original_pixels=render_sequence_frame(compile_composition(before),2.75,(90,160)).tobytes()
    choose(c,key);after=copy.deepcopy(c.document)
    expected=copy.deepcopy(before)
    expected['effects']['chromatic_lattice']['params'].update(palette_values(key))
    assert after==expected
    assert c.object_panel.palette_selector.combo.currentData()==key
    values=resolved(after)
    assert all(values[path]==v for path,v in palette_values(key).items())
    save_composition(tmp_path/'palette.json',after)
    loaded=load_composition(tmp_path/'palette.json')
    assert loaded==after
    assert render_sequence_frame(compile_composition(loaded),2.75,(90,160)).tobytes()!=original_pixels
    w.undo_composition();assert c.document==before
    w.redo_composition();assert c.document==after
    choose(c,'original')
    assert render_sequence_frame(compile_composition(c.document),2.75,(90,160)).tobytes()==original_pixels
    c.change_color('lattice_face_a',(.2,.3,.4),None)
    assert c.object_panel.palette_selector.combo.currentData() is None


def test_palette_scope_preserves_other_clips_and_automation(make_window):
    doc=watching_eye_composition()
    second=copy.deepcopy(doc['sections'][0]);second['id']='second';doc['sections'].append(second)
    w=make_window(composition=doc);c=w.composer;c.select_section(1)
    before=copy.deepcopy(c.document)
    choose(c,'indigo')
    assert c.document['effects']==before['effects']
    assert c.document['sections'][0]==before['sections'][0]
    for path,value in palette_values('indigo').items():assert resolved(c.document,9)[path]==value
    assert resolved(c.document,0)['chromatic_lattice.face_a_hue']==.39
    c.change_scope(0);choose(c,'saffron')
    assert resolved(c.document,9)['chromatic_lattice.face_a_hue']==palette_values('indigo')['chromatic_lattice.face_a_hue']
    # Palette selection leaves authored clip gestures intact.
    from synth_automation import normalize_automations
    events=normalize_automations([dict(id='wash',path='print_surface.paint_wash',amount=.1,
        start_fraction=0.,attack_fraction=.1,hold_fraction=.2,recovery_fraction=.1)])
    modified=copy.deepcopy(c.document);modified['sections'][1]['automations']=events
    c.commit(modified,'test-automation');c.select_section(1);choose(c,'jade')
    assert c.document['sections'][1]['automations']==events


def test_existing_broadcast_accents_follow_palette_without_activating_effects(make_window):
    doc=watching_eye_composition()
    doc['effects']['broadcast']={'mode':'on','params':{'broadcast.halo':.86,'broadcast.field':.18}}
    w=make_window(composition=doc);c=w.composer;before=copy.deepcopy(c.document)
    choose(c,'jade')
    expected=copy.deepcopy(before)
    for path,value in palette_values('jade',broadcast=True).items():
        module=path.split('.',1)[0]
        expected['effects'].setdefault(module,{'mode':'recipe','params':{}})['params'][path]=value
    assert c.document==expected
    assert c.object_panel.palette_selector.combo.currentData()=='jade'
    assert 'Broadcast wear accents' in c.object_panel.palette_selector.note.text()
    w.undo_composition();assert c.document==before


def test_palette_works_without_eye_and_hides_for_other_surfaces(make_window):
    w=make_window(composition=printed_orbit_composition());c=w.composer
    choose(c,'lotus');values=c.document['effects']['chromatic_lattice']['params']
    assert values==palette_values('lotus',eye=False)
    c.change_object_parameter('chromatic_lattice','chromatic_lattice.surface',0)
    assert c.object_panel.palette_selector.isHidden()
