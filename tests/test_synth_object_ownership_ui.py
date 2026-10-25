"""Content has one editing home; treatments cannot open duplicate source editors."""
import copy
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from test_synth_effects_editor_integration import make_window
from synth_starters import starter_composition
from synth_composition import compile_composition, load_composition, save_composition
from synth_sequence import render_sequence_frame
from synth_subject import SOURCE_EFFECTS


def test_text_and_subtitle_share_object_and_navigation_does_not_author_changes(make_window):
    window = make_window(composition=starter_composition('text-contact-film'))
    c = window.composer; obj = c.object_panel
    original = copy.deepcopy(window.composition)
    c.look_tabs.setCurrentWidget(obj); QApplication.processEvents()
    assert obj.controls['text.content'].isVisible()
    assert obj.controls['text.badge_subtitle'].isVisible()
    assert obj.controls['text.badge_show_subtitle'].isVisible()
    assert obj.controls['text.font'].isVisible()
    assert obj.wording_layout.itemAt(0).widget() is obj.controls['text.font']
    assert obj.controls['text.content'].input.value() == 'FAC51'
    assert obj.controls['text.badge_subtitle'].input.value()
    subtitle = obj.controls['text.badge_subtitle'].input
    obj.text_tabs.setCurrentIndex(1)
    assert obj.controls['text.badge_shape'].isVisible()
    assert obj.controls['text.badge_padding_x'].isVisible()
    assert obj.position_host.isVisible()
    assert not obj.controls['text.font'].isVisible()
    obj.text_tabs.setCurrentIndex(2)
    assert obj.controls['text.reveal'].isVisible()
    c.look_tabs.setCurrentWidget(c.effects_panel)
    assert c.effects_panel.effect_id not in SOURCE_EFFECTS
    c.effects_panel.inspect_effect('text')
    assert c.look_tabs.currentWidget() is obj
    assert 'text' not in c.effects_panel.control_cache
    assert obj.controls['text.badge_subtitle'].input is subtitle
    assert window.composition == original and not window.has_unsaved_changes()
    for t in (0., 2.08, 7.3):
        assert render_sequence_frame(compile_composition(original),t,(96,72)).tobytes() == render_sequence_frame(window.sequence,t,(96,72)).tobytes()


def test_typeface_edits_scope_renders_and_restores_without_losing_wording(make_window, tmp_path):
    window = make_window(composition=starter_composition('text-contact-film'))
    c = window.composer; obj = c.object_panel
    c.look_tabs.setCurrentWidget(obj)
    c.change_scope(1)
    original = copy.deepcopy(window.composition)
    before = render_sequence_frame(window.sequence, 2.08, (192,144)).tobytes()
    weight_was_visible = obj.controls['text.weight'].isVisible()
    main = obj.controls['text.content'].input
    subtitle = obj.controls['text.badge_subtitle'].input
    wording = (main.value(), subtitle.value())
    font = obj.controls['text.font'].input
    font.setCurrentIndex(4)  # Fraunces supports variable weight.
    assert obj.controls['text.weight'].isVisible()
    assert window.composition['sections'][0]['effects']['text']['params']['text.font'] == 4
    assert window.composition['effects'] == original['effects']
    assert (main.value(), subtitle.value()) == wording
    assert render_sequence_frame(window.sequence,2.08,(192,144)).tobytes() != before
    path = tmp_path/'typeface.nebula.json'; save_composition(path, window.composition)
    assert load_composition(path)['sections'][0]['effects']['text']['params']['text.font'] == 4
    obj.text_tabs.setCurrentIndex(1)
    assert obj.reveal_control('text.font') and obj.text_tabs.currentIndex() == 0
    window.undo_composition()
    assert window.composition == original
    assert obj.controls['text.weight'].isVisible() == weight_was_visible
    assert render_sequence_frame(window.sequence,2.08,(192,144)).tobytes() == before
    font.setCurrentIndex(0)  # Archivo Black has a fixed weight.
    assert not obj.controls['text.weight'].isVisible()
    window.undo_composition()
    assert window.composition == original
    assert obj.controls['text.weight'].isVisible() == weight_was_visible


def test_subtitle_draft_survives_tabs_effects_scopes_and_hidden_subtitle(make_window):
    window = make_window(composition=starter_composition('text-contact-film'))
    c=window.composer; obj=c.object_panel; c.look_tabs.setCurrentWidget(obj)
    c.change_scope(1)
    sub=obj.controls['text.badge_subtitle'].input
    sub.editor.setPlainText('MY SUBTITLE\nSECOND LINE')
    obj.text_tabs.setCurrentIndex(1)
    c.look_tabs.setCurrentWidget(c.effects_panel); c.effects_panel.inspect_effect('broadcast')
    c.change_scope(0); c.change_scope(1)
    c.look_tabs.setCurrentWidget(obj); obj.text_tabs.setCurrentIndex(0)
    assert sub.editor.toPlainText()=='MY SUBTITLE\nSECOND LINE'
    obj.controls['text.badge_show_subtitle'].input.click()
    assert sub.editor.toPlainText()=='MY SUBTITLE\nSECOND LINE'
    assert window.prepare_document_save()
    entry=window.composition['sections'][0]['effects']['text']['params']
    assert entry['text.badge_subtitle']=='MY SUBTITLE\nSECOND LINE'
    assert entry['text.badge_show_subtitle']==0
    assert 'text' not in window.composition['effects']


def test_source_details_and_shared_timing_stay_in_object(make_window):
    window=make_window(composition=starter_composition('mixed-media'))
    c=window.composer; obj=c.object_panel
    c.look_tabs.setCurrentWidget(obj); obj.timing.click()
    assert c.look_tabs.currentWidget() is obj
    assert obj.pages.currentWidget() is c.object_editor
    assert c.object_editor.effect_id=='ink_bloom'
    assert c.timing_scope_label.isVisible() and not c.scope_combo.isVisible()
    c.object_editor.controls['ink_bloom.folded_seconds'].input.setValue(2.)
    assert window.composition['ink_timing']['ink_bloom.folded_seconds']==2.
    c.object_editor.back_button.click()
    assert obj.pages.currentWidget() is obj.overview_scroll
    assert c.scope_combo.isVisible()
    assert c.look_tabs.currentWidget() is obj


def test_layout_parameter_keeps_scroll_on_edit(make_window):
    window=make_window(composition=starter_composition('text-contact-film'))
    c=window.composer; obj=c.object_panel
    c.look_tabs.setCurrentWidget(obj); obj.text_tabs.setCurrentIndex(1)
    row=obj.controls['text.badge_padding_x']
    QApplication.processEvents(); obj.overview_scroll.ensureWidgetVisible(row)
    QApplication.processEvents()
    scroll=obj.overview_scroll.verticalScrollBar(); before=scroll.value()
    y=row.mapTo(obj.overview_scroll.viewport(),QPoint()).y()
    assert before>0
    row.input.setValue(100.)
    QApplication.processEvents()
    assert scroll.value()==before
    assert row.mapTo(obj.overview_scroll.viewport(),QPoint()).y()==y


def test_object_creative_variations_use_the_object_editor(make_window, monkeypatch):
    from synth_exploration_ui import VaryEffectDialog
    from synth_studio import SynthStudio
    calls=[]
    monkeypatch.setattr(SynthStudio,'open_effect_variation',lambda self,key:calls.append(key))
    window=make_window(composition=starter_composition('particle-orbit'))
    c=window.composer; c.open_object_details('particles',True)
    c.object_editor.creative_panel.vary.click()
    assert calls==['particles']
    dialog=VaryEffectDialog(window,'particles')
    assert set(dialog.controls)==set(c.object_editor.creative_panel.controls)
    for key, check in dialog.controls.items():
        assert check.isEnabled()==c.object_editor.creative_panel.controls[key].input.isEnabled()
    dialog.reject()
