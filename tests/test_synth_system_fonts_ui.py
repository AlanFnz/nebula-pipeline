import copy
import pytest
from PySide6.QtWidgets import QApplication
from test_synth_effects_editor_integration import make_window
from test_synth_system_fonts import external_font, TEXT_STUDIES
from synth_font_ui import FontControl, FontPicker
from synth_starters import starter_composition
from synth_composition import compile_composition, save_composition, load_composition
from synth_sequence import render_sequence_frame


@pytest.mark.parametrize('key',TEXT_STUDIES)
def test_all_text_objects_expose_same_picker_without_changing_study(make_window,key):
    c=starter_composition(key);window=make_window(composition=c); obj=window.composer.object_panel
    before=copy.deepcopy(window.composition)
    window.composer.look_tabs.setCurrentWidget(obj)
    assert isinstance(obj.controls['text.font'].input,FontControl)
    assert obj.controls['text.font'].isVisible()
    assert window.composition==before and not window.has_unsaved_changes()


def test_system_font_clip_scope_undo_draft_and_save(make_window,external_font,tmp_path):
    window=make_window(composition=starter_composition('text-contact-film'))
    c=window.composer;obj=c.object_panel;c.look_tabs.setCurrentWidget(obj);c.change_scope(1)
    original=copy.deepcopy(window.composition)
    wording=obj.controls['text.content'].input;wording.editor.setPlainText('MY PENDING TEXT')
    obj.controls['text.font'].input.setValue(external_font)
    assert not obj.controls['text.weight'].isVisible()
    assert wording.editor.toPlainText()=='MY PENDING TEXT'
    assert window.composition['effects']==original['effects']
    assert window.composition['sections'][0]['effects']['text']['params']['text.font']==external_font
    path=tmp_path/'font.json';save_composition(path,window.composition)
    assert load_composition(path)['sections'][0]['effects']['text']['params']['text.font']==external_font
    c.change_scope(0);c.change_scope(1)
    assert obj.controls['text.font'].input.value()==external_font
    window.undo_composition();assert window.composition==original


def test_picker_search_preview_cancel_and_select(make_window,external_font,monkeypatch):
    import json
    row=json.loads(external_font)
    monkeypatch.setattr('synth_font_ui.system_catalog',lambda:(row,))
    window=make_window(composition=starter_composition('text-contact-film'));original=copy.deepcopy(window.composition)
    dialog=FontPicker(5,parent=window);dialog.show();QApplication.processEvents()
    dialog.library.setCurrentIndex(2);dialog.search.setText('space mono')
    assert dialog.list.count()==1 and dialog.use_button.isEnabled()
    assert not dialog.preview.pixmap().isNull()
    assert dialog.selected==external_font
    dialog.reject();assert window.composition==original
    dialog=FontPicker(5,parent=window);dialog.show();QApplication.processEvents()
    dialog.search.setText('no such font');assert dialog.list.count()==0 and not dialog.use_button.isEnabled()
    dialog.reject()
