"""Shared controls must never author values through inspection or navigation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QLocale, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PIL import Image

from synth_artwork import encode_artwork
from synth_effect_parameter_ui import EffectParameter, format_value
from test_synth_effects_editor_integration import make_window


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('path,bounds', [
    ('tape.jitter', (.00073123456, .0027)),
    ('text.font', (0, 2)),
    ('text.content', ('First wording', 'Second wording')),
    ('ink_bloom.artwork', ('', encode_artwork(Image.new('RGBA', (2, 2), 'white')))),
])
def test_animation_range_is_read_only_with_visible_proposal_and_deliberate_keyboard_action(app, path, bounds):
    control = EffectParameter(path); changes = []; control.changed.connect(changes.append)
    control.refresh(bounds, None, False, True)
    control.show(); app.processEvents()
    assert isinstance(control.animated_value, QLabel)
    assert control.value_stack.currentWidget() is control.animated_value
    assert control.fixed_choice.isVisible()
    assert control.proposed_value.text() == 'Start: ' + format_value(path, bounds[0])
    assert 'not a sampled playhead' in control.proposed_value.toolTip()
    QTest.mouseClick(control.animated_value, Qt.MouseButton.LeftButton)
    control.refresh(bounds, None, False, True)
    assert changes == []
    control.use_fixed.setFocus(); QTest.keyClick(control.use_fixed, Qt.Key.Key_Space)
    assert changes == [bounds[0]]
    control.close()


def test_disabled_animation_cannot_author_fixed_value_and_restore_is_local_only(app):
    control = EffectParameter('text.size'); changes = []; resets = []
    control.changed.connect(changes.append); control.reset.connect(lambda: resets.append(True))
    control.refresh((.2, .5), None, False, False)
    assert control.value_stack.currentWidget() is control.animated_value
    assert not control.use_fixed.isEnabled() and not control.reset_button.isEnabled()
    control.use_fixed.click(); control.reset_button.click(); assert changes == resets == []
    control.refresh((.4, .4), None, True, True, parent_value=.4, scope_label='Clip 2 — Verse')
    assert control.input.value() == .4 and not control.reset_button.isEnabled()
    assert control.origin.text() == 'Fixed · Entire project'
    control.input.setValue(.46); assert changes == [.46]
    control.refresh((.46, .46), .46, True, True, parent_value=.4, scope_label='Clip 2 — Verse')
    assert control.origin.text() == 'Fixed · Clip'
    control.reset_button.click(); assert resets == [True]
    assert 'only this parameter' in control.reset_button.toolTip()
    # Reset emits intent; the owning panel removes the local override.
    control.refresh((.4, .4), None, True, True, parent_value=.4)
    assert control.input.value() == .4 and not control.reset_button.isEnabled()
    control.close()


@pytest.mark.parametrize('path,value', [('text.font', 2), ('text.content', 'Entire project wording'),
                                        ('ink_bloom.artwork', encode_artwork(Image.new('RGBA', (2, 2), 'red')))])
def test_inherited_non_numeric_fixed_values_remain_editable_without_local_restore(app, path, value):
    control = EffectParameter(path); changes = []; control.changed.connect(changes.append)
    control.refresh((value, value), None, True, True, parent_value=value)
    assert control.value_stack.currentWidget() is control.input
    assert control.origin.text() == 'Fixed · Entire project'
    assert not control.reset_button.isEnabled() and changes == []
    assert (control.input.currentIndex() if control.spec.choices else control.input.value()) == value
    control.close()


def test_pending_text_survives_refresh_scope_navigation_and_recreated_control(app):
    control = EffectParameter('text.content'); changes = []; control.changed.connect(changes.append)
    control.refresh(('Original', 'Original'), None, False, True, context_key=('document', 1))
    control.input.editor.setPlainText('Unapplied\nwording')
    control.refresh(('Original', 'Original'), None, False, True, context_key=('document', 1))
    assert control.input.editor.toPlainText() == 'Unapplied\nwording'
    control.hide(); control.show(); app.processEvents()
    assert changes == []
    control.refresh(('Another scope', 'Another scope'), None, False, True, context_key=('document', 2))
    assert control.input.editor.toPlainText() == 'Another scope'
    control.refresh(('Original', 'Original'), None, False, True, context_key=('document', 1))
    assert control.input.editor.toPlainText() == 'Unapplied\nwording' and changes == []
    replacement = EffectParameter('text.content')
    replacement.refresh(('Original', 'Original'), None, False, True)
    replacement.restore_draft(control.draft_state())
    assert replacement.input.editor.toPlainText() == 'Unapplied\nwording'
    replacement.input.apply.click(); assert replacement.input.value() == 'Unapplied\nwording'
    # An authored change supersedes a draft based on a different authored value.
    replacement.refresh(('Changed externally', 'Changed externally'), None, False, True)
    replacement.restore_draft(control.draft_state())
    assert replacement.input.editor.toPlainText() == 'Changed externally'
    control.close(); replacement.close()


def test_animation_navigation_does_not_apply_pending_wording(app):
    control = EffectParameter('text.content'); changes = []; control.changed.connect(changes.append)
    control.refresh(('Alpha', 'Zulu'), None, False, True)
    control.input.editor.setPlainText('Pending')
    control.refresh(('Alpha', 'Zulu'), None, False, True)
    assert control.input.editor.toPlainText() == 'Pending' and changes == []
    control.use_fixed.click(); assert changes == ['Alpha']
    # Pending wording still needs its own Apply text action.
    control.refresh(('Alpha', 'Alpha'), 'Alpha', False, True)
    assert control.input.editor.toPlainText() == 'Pending'
    control.input.apply.click(); assert changes == ['Alpha', 'Pending']
    control.close()


def test_precision_locale_and_known_units_are_presentation_only(app):
    control = EffectParameter('tape.jitter'); changes = []; control.changed.connect(changes.append)
    control.input.setLocale(QLocale('de_DE'))
    value = .00073123456
    control.refresh((value, value), value, False, True)
    assert control.input.text() == '0,07 %'
    control.input.interpretText(); control.refresh((value, value), value, False, True)
    assert control.input.value() == pytest.approx(value, abs=1e-12) and changes == []
    assert format_value('edge_phosphor.hue', .295) == '29.50 %'
    assert format_value('particles.period', 12.) == '12.00 s'
    assert format_value('particles.rotation_speed', 4.) == '4.00°/s'
    assert format_value('text.rotation', 45.) == '45.00°'
    assert format_value('low_res.resolution', 360) == '360 px'
    assert format_value('separation.angle', .15) == '0.15'
    seconds = EffectParameter('particles.period'); seconds.input.setLocale(QLocale('en_US')); seconds.refresh((12., 12.), None, False, True)
    assert seconds.input.text() == '12.00 s' and seconds.input.value() == 12.
    seconds.input.lineEdit().setText('13.25 s'); seconds.input.interpretText()
    assert seconds.input.value() == 13.25
    control.close(); seconds.close()


def test_supported_hues_show_indication_and_animated_hues_have_no_single_color(app):
    control = EffectParameter('text.hue'); changes = []; control.changed.connect(changes.append)
    control.refresh((0., 0.), None, False, True)
    assert '#ff0000' in control.hue_swatch.styleSheet()
    assert 'compositing' in control.hue_swatch.toolTip()
    control.input.setValue(1/3)
    assert '#00ff00' in control.hue_swatch.styleSheet()
    control.refresh((.1, .8), None, False, True)
    assert 'transparent' in control.hue_swatch.styleSheet()
    assert changes == [pytest.approx(1/3)]
    unknown = EffectParameter('broadcast.hue_spread'); assert unknown.hue_swatch is None
    control.close(); unknown.close()


@pytest.mark.parametrize('path,bounds', [('particles.rotation_speed', (-30., 45.)),
                                        ('particles.axis_mode', (0, 1)),
                                        ('text.content', ('Long source wording ' * 8, 'Z')),
                                        ('text.hue', (.1, .8))])
def test_controls_fit_narrow_inspector_content_width(app, path, bounds):
    host = QWidget(); layout = QVBoxLayout(host)
    control = EffectParameter(path); layout.addWidget(control)
    control.refresh(bounds, None, False, True)
    host.resize(340, 280); host.show(); app.processEvents()
    assert host.minimumSizeHint().width() <= 340
    for child in (control.use_fixed, control.reset_button, control.proposed_value):
        assert child.mapTo(host, child.rect().topRight()).x() <= host.width()
    host.close()


def test_equal_wording_scopes_keep_separate_drafts_and_save_acknowledgement(app):
    control = EffectParameter('text.content'); changes = []; control.changed.connect(changes.append)
    control.refresh(('Same wording', 'Same wording'), None, False, True, context_key='section-one')
    control.input.editor.setPlainText('Draft one')
    control.refresh(('Same wording', 'Same wording'), None, False, True, context_key='section-two')
    assert control.input.editor.toPlainText() == 'Same wording'
    control.input.editor.setPlainText('Draft two')
    control.refresh(('Same wording', 'Same wording'), None, False, True, context_key='section-one')
    assert control.input.editor.toPlainText() == 'Draft one'
    assert dict(control.pending_text_drafts()) == {
        'section-one': {'value': 'Same wording', 'text': 'Draft one'},
        'section-two': {'value': 'Same wording', 'text': 'Draft two'},
    }
    control.acknowledge_text_draft('section-one', 'Draft one')
    control.acknowledge_text_draft('section-two', 'Draft two')
    assert control.pending_text_drafts() == () and changes == []
    control.close()


def test_themed_inactive_broadcast_inputs_keep_text_and_slider_geometry(app):
    import copy
    from studio_theme import apply_theme
    from synth_composition import reference_composition
    from synth_composer_ui import CompositionPanel

    old_style, old_sheet = app.style().objectName(), app.styleSheet()
    old_font, old_palette = app.font(), app.palette()
    panel = None
    try:
        apply_theme(app)
        panel = CompositionPanel(reference_composition(True)); panel.resize(391, 605)
        before = copy.deepcopy(panel.document)
        panel.show(); panel.effects_panel.inspect_effect('broadcast'); app.processEvents()
        for path in ('broadcast.field', 'broadcast.hue', 'broadcast.hue_spread', 'broadcast.drift'):
            panel.effects_panel.reveal_control(path); app.processEvents()
            control = panel.effects_panel.controls[path]
            assert control.isVisible()
            assert not control.input.isEnabled()
            assert control.input.height() >= control.input.minimumSizeHint().height()
            assert control.input.lineEdit().height() >= control.input.fontMetrics().height()
            assert not control.slider.geometry().intersects(control.value_stack.geometry())
            assert control.origin.y() > max(control.slider.geometry().bottom(), control.value_stack.geometry().bottom())
        assert panel.document == before
    finally:
        if panel: panel.close(); panel.deleteLater(); app.processEvents()
        app.setStyle(old_style); app.setFont(old_font); app.setPalette(old_palette)
        app.setStyleSheet(old_sheet)


@pytest.mark.parametrize('width', [380, 490, 650])
@pytest.mark.parametrize('path', ['tape.pull', 'particles.rotation_speed', 'text.hue',
                                  'text.motion', 'text.font', 'particles.orbit_handoff',
                                  'text.content', 'ink_bloom.artwork'])
def test_responsive_rows_keep_fields_actions_and_long_choices_inside_inspector(app, width, path):
    from studio_theme import apply_theme
    old_style, old_sheet = app.style().objectName(), app.styleSheet()
    old_font, old_palette = app.font(), app.palette()
    host = QWidget()
    try:
        apply_theme(app)
        layout = QVBoxLayout(host)
        control = EffectParameter(path); layout.addWidget(control); layout.addStretch()
        value = (max(range(len(control.spec.choices)), key=lambda i: len(control.spec.choices[i]))
                 if control.spec.choices else control.spec.default)
        control.refresh((value, value), value, False, True, scope_label='Entire project')
        control.set_automation_count(3)
        host.resize(650, 350); host.show(); app.processEvents()
        host.resize(width, 350); app.processEvents()
        assert host.width() == width and host.minimumSizeHint().width() <= width
        assert control.origin.isHidden()
        children = [control.input, control.reset_button, control.label]
        if control.slider: children.append(control.slider)
        if control.animate_button: children.append(control.animate_button)
        for child in children:
            assert child.isVisible()
            assert child.mapTo(control, child.rect().topLeft()).x() >= 0
            assert child.mapTo(control, child.rect().bottomRight()).x() < control.width()
            assert child.mapTo(control, child.rect().bottomRight()).y() < control.height()
        assert control.input.height() >= control.input.minimumSizeHint().height()
        if control.spec.choices:
            text_width = control.input.fontMetrics().horizontalAdvance(control.input.currentText())
            assert control.input.width() >= text_width + 35
        if control.slider:
            assert control.slider.width() >= 100
            assert not control.slider.geometry().intersects(control.value_stack.geometry())
            if width == 650:
                assert abs(control.slider.geometry().center().y() - control.value_stack.geometry().center().y()) <= 1
                assert control.height() < 65
            if width == 380:
                assert control.slider.y() > control.reset_button.geometry().bottom()
        if path == 'text.content':
            assert control.input.editor.height() >= 100
            assert control.input.width() == control.width()
        if path == 'ink_bloom.artwork':
            assert control.input.import_button.width() >= 80
            assert control.input.width() == control.width()
    finally:
        host.close(); host.deleteLater(); app.processEvents()
        app.setStyle(old_style); app.setFont(old_font); app.setPalette(old_palette)
        app.setStyleSheet(old_sheet)


def test_ordinary_project_provenance_is_quiet_but_context_and_exceptions_remain(app):
    control = EffectParameter('text.size')
    control.refresh((.4, .4), .4, False, True, scope_label='Entire project')
    assert control.origin.isHidden()
    assert 'Fixed' in control.accessibleDescription()
    assert 'Entire project' in control.input.accessibleDescription()
    assert 'Editing authors' in control.input.toolTip()
    for bounds, fixed, inherited, available, scope, parent in [
        ((.2, .5), None, False, True, 'Entire project', None),
        ((.4, .4), None, True, True, 'Clip 2', .4),
        ((.4, .4), .4, False, True, 'Clip 2', None),
        ((.4, .4), .4, False, False, 'Entire project', None),
    ]:
        control.refresh(bounds, fixed, inherited, available, scope_label=scope, parent_value=parent)
        assert not control.origin.isHidden()
        assert control.origin.accessibleDescription()
    control.refresh((.4, .4), .4, False, True, scope_label='Entire project', origin_label='Entire project · shared timing')
    assert not control.origin.isHidden() and 'shared timing' in control.origin.text()
    control.close()


def test_responsive_slider_drag_commits_once_on_release_and_automation_stays_reachable(app):
    host = QWidget(); layout = QVBoxLayout(host)
    control = EffectParameter('tape.pull'); layout.addWidget(control); layout.addStretch()
    changes = []; automations = []; resets = []
    control.changed.connect(changes.append); control.animate.connect(automations.append)
    control.reset.connect(lambda: resets.append(True))
    control.refresh((.1, .1), .1, False, True, scope_label='Entire project')
    host.resize(380, 250); host.show(); app.processEvents()
    assert not control.slider.hasTracking()
    control.slider.setSliderDown(True); control.slider.setSliderPosition(750)
    assert changes == []
    assert control.input.value() == control.slider_value(750)
    control.slider.setSliderDown(False)
    assert changes == [control.slider_value(750)]
    host.resize(650, 250); app.processEvents()
    assert changes == [control.slider_value(750)]
    control.set_automation_count(3); control.animate_button.click(); control.reset_button.click()
    assert automations == ['tape.pull'] and resets == [True]
    assert control.animate_button.text() == 'Automations (3)…'
    host.close()


def test_integrated_inspector_resizes_rows_before_placing_neighbors(make_window):
    import copy
    from synth_composition import blank_composition

    composition = blank_composition()
    composition['effects']['scan_modulation'] = {
        'mode': 'on', 'params': {'scan_modulation.region': 2},
    }
    window = make_window(composition=composition)
    window.auto_prepare.setChecked(False)
    panel = window.composer.effects_panel
    panel.inspect_effect('scan_modulation')
    before = copy.deepcopy(window.composition)
    for size in ((1280, 720), (1440, 900), (1728, 1017)):
        window.resize(*size)
        QApplication.processEvents(); QApplication.processEvents()

    def check_rows():
        controls = sorted((control for control in panel.controls.values() if control.isVisible()),
                          key=lambda control: control.y())
        assert len(controls) >= 7
        for first, second in zip(controls, controls[1:]):
            assert first.geometry().bottom() < second.y()
        for control in controls:
            if not control.slider: continue
            assert control.slider.height() >= control.slider.sizeHint().height()
            assert control.input.height() >= control.input.minimumSizeHint().height()
            for child in (control.slider, control.input, control.reset_button):
                assert control.rect().contains(child.mapTo(control, child.rect().topLeft()))
                assert control.rect().contains(child.mapTo(control, child.rect().bottomRight()))
        return {control.path: control.height() for control in controls if control.slider}

    window.splitter.setSizes([1320, 380])
    QApplication.processEvents(); QApplication.processEvents()
    narrow = check_rows()
    window.splitter.setSizes([950, 750])
    QApplication.processEvents(); QApplication.processEvents()
    wide = check_rows()
    assert narrow and all(narrow[path] > wide[path] for path in narrow)
    assert window.composition == before
