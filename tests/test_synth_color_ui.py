"""Visual color edits preserve scopes, HDR precision and undo semantics."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog
from synth_color_ui import COLORS, ColorPicker, display_color
from synth_composition import composition_from_sequence, normalize_composition, compile_composition
from synth_sequence import normalize_sequence, resolve_sequence_frame
from test_synth_effects_editor_integration import make_window


def document():
    seq = normalize_sequence(dict(schema_version=1, name='Palette', fps=30, duration=3,
        states={name: dict(preset='Reference blinds', enabled=['text', 'dye_transfer'],
                          overrides={'text.content': name, 'dye_transfer.paper_hue': h,
                                     'dye_transfer.paper_saturation': s, 'dye_transfer.paper_light': v})
                for name, (h, s, v) in zip(('pink', 'red', 'white'), ((.905, .77, 1.08), (.026, 1., 1.08), (.96, .025, .98)))},
        cues=[dict(time=i, state=name, transition='cut') for i, name in enumerate(('pink', 'red', 'white'))]))
    doc = composition_from_sequence(seq); template = doc['sections'][0]
    doc['sections'] = []; doc['phrases'] = {}
    for i in range(3):
        key = f'shot-{i}'
        doc['phrases'][key] = dict(name=key, start=i, end=i+1)
        doc['sections'].append(dict(copy.deepcopy(template), id=key, phrase=key, duration=1.))
    doc['effects']['dye_transfer'] = dict(mode='recipe', params={'dye_transfer.grain': .023})
    return normalize_composition(doc)


def paper(doc, seconds):
    base = resolve_sequence_frame(compile_composition(doc), seconds)[-1]
    params = next(m['params'] for m in base['modules'] if m['id'] == 'dye_transfer')
    return tuple(params[k] for k in COLORS[0].channels)


def test_preview_samples_playhead_and_selected_scope_without_authoring(make_window):
    window = make_window(composition=document()); composer = window.composer
    before = copy.deepcopy(composer.document)
    composer.effects_panel.inspect_effect('dye_transfer')
    composer.playhead_seconds = lambda: 1.25
    context = composer.color_context('paper')
    assert context['hsv'] == (.026, 1., 1.08)
    assert context['section_id'] == 'shot-1'
    assert (.905, .77, 1.08) in context['palette']
    composer.select_section(0)  # A selected clip wins even when the playhead is elsewhere.
    assert composer.color_context('paper')['hsv'] == (.905, .77, 1.08)
    assert composer.document == before and not window.has_unsaved_changes()


def test_picker_cancel_and_unchanged_accept_do_not_freeze_animation(make_window, monkeypatch):
    window = make_window(composition=document()); composer = window.composer
    panel = composer.effects_panel.color_panel; before = copy.deepcopy(composer.document)
    def cancel(dialog):
        dialog.select_swatch((.026, 1., 1.08))
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(ColorPicker, 'exec', cancel)
    panel.open_picker('paper')
    monkeypatch.setattr(ColorPicker, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    panel.open_picker('paper')
    assert composer.document == before and not window.has_unsaved_changes()


def test_palette_selection_is_exact_atomic_local_undoable_and_keeps_other_effects(make_window, monkeypatch):
    window = make_window(composition=document()); composer = window.composer
    before = copy.deepcopy(composer.document)
    def choose(dialog):
        assert dialog.scope.currentData() == 'shot-0'
        red = next(hsv for hsv in dialog.context['palette'] if hsv[0] == .026)
        dialog.select_swatch(red)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ColorPicker, 'exec', choose)
    composer.effects_panel.color_panel.open_picker('paper')
    after = copy.deepcopy(composer.document)
    assert paper(after, .25) == paper(after, 1.25) == (.026, 1., 1.08)
    assert paper(after, 2.25) == paper(before, 2.25)
    assert after['effects'] == before['effects']
    assert after['sections'][1:] == before['sections'][1:]
    assert composer.scope == 1
    window.undo_composition(); assert window.composition == before
    window.redo_composition(); assert window.composition == after
    composer.restore_color('paper'); assert composer.document == before


def test_project_color_preserves_explicit_clip_override_and_restores_only_color(make_window):
    doc = document()
    doc['sections'][2]['effects']['dye_transfer'] = dict(mode='recipe', params=dict(zip(COLORS[0].paths, (.5, 1., .7))))
    window = make_window(composition=doc); composer = window.composer
    before = copy.deepcopy(composer.document)
    composer.change_color('paper', (.026, 1., 1.08), None)
    assert paper(composer.document, .2) == paper(composer.document, 1.2) == (.026, 1., 1.08)
    assert paper(composer.document, 2.2) == (.5, 1., .7)
    assert composer.document['effects']['dye_transfer']['params']['dye_transfer.grain'] == .023
    composer.restore_color('paper'); assert composer.document == before


def test_current_color_can_explicitly_be_applied_across_the_project(make_window, monkeypatch):
    window = make_window(composition=document()); composer = window.composer
    def choose_project(dialog):
        dialog.scope.setCurrentIndex(1)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ColorPicker, 'exec', choose_project)
    composer.effects_panel.color_panel.open_picker('paper')
    assert paper(composer.document, 1.2) == (.905, .77, 1.08)
    assert composer.scope == 0


def test_picker_rgb_matches_hex_and_unedited_palette_preserves_hdr(make_window):
    window = make_window(composition=document())
    context = window.composer.color_context('paper')
    dialog = ColorPicker(COLORS[0], context)
    assert dialog.selected_hsv() == (.905, .77, 1.08)
    assert dialog.picker.currentColor().name() == display_color(context['hsv']).name()
    dialog.picker.setCurrentColor(QColor('#8462a5'))
    assert display_color(dialog.selected_hsv()).name() == '#8462a5'
    dialog.select_swatch((.026, 1., 1.08)); assert dialog.selected_hsv() == (.026, 1., 1.08)
    dialog.close()


@pytest.mark.parametrize('width', [390, 700])
def test_cards_and_numeric_animation_ranges_fit_without_editing(make_window, width):
    window = make_window(composition=document()); composer = window.composer
    composer.effects_panel.inspect_effect('dye_transfer')
    window.resize(1280, 850); window.splitter.setSizes([1280-width, width])
    QApplication.processEvents()
    panel = composer.effects_panel
    assert panel.color_panel.isVisible()
    card = panel.color_panel.cards['paper']
    assert card.swatch.geometry().right() < card.button.geometry().left()
    assert card.button.geometry().right() < card.reset.geometry().left()
    assert card.reset.geometry().right() < card.width()
    panel.reveal_control('dye_transfer.paper_hue'); QApplication.processEvents()
    control = panel.controls['dye_transfer.paper_hue']
    assert control.animated_value.text().startswith('Animated range')
    assert control.value_stack.currentWidget() == control.animated_value
    assert not window.has_unsaved_changes()
