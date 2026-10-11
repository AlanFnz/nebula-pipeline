import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication
from synth_audio_reactivity_ui import AudioReactivityDialog
from synth_soundtrack_ui import SoundtrackDialog


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def project():
    return {'soundtrack': dict(id='track-1', name='Tone & rhythm', path='/tone.wav',
                              duration=10., sample_rate=48000, channels=2),
            'audio_reactivity': {'enabled': True, 'mappings': [
                dict(id='response-1', track_id='track-1', path='bloom.strength',
                     low_hz=40., high_hz=180., amount=.2, sensitivity=1.,
                     attack=.05, release=.25, enabled=True)]}}


def test_apply_reset_cancel_and_refresh_preserve_draft(app, project):
    dialog = AudioReactivityDialog()
    edited = QSignalSpy(dialog.configEdited)
    dialog.set_project(project)
    assert not dialog.apply_button.isEnabled()
    dialog.amount.setValue(.31)
    dialog.set_project(copy.deepcopy(project))
    assert dialog.amount.value() == .31
    assert edited.count() == 0
    dialog.reset()
    assert dialog.amount.value() == .2
    dialog.amount.setValue(.41)
    dialog.reject()
    assert dialog.amount.value() == .2
    assert edited.count() == 0
    dialog.amount.setValue(.51)
    dialog.apply()
    assert edited.count() == 1
    assert edited.at(0)[0]['mappings'][0]['amount'] == .51
    dialog.apply()
    assert edited.count() == 1
    updated = copy.deepcopy(project)
    updated['audio_reactivity']['mappings'][0]['amount'] = .11
    dialog.set_project(updated)
    assert dialog.amount.value() == .11
    dialog.close()


def test_invalid_ranges_presets_nyquist_and_busy(app, project):
    dialog = AudioReactivityDialog()
    dialog.set_project(project)
    spy = QSignalSpy(dialog.configEdited)
    dialog.low_hz.setValue(200.)
    assert dialog.band.currentData() == 'Custom'
    assert not dialog.apply_button.isEnabled()
    assert dialog.error_label.text()
    dialog.apply()
    assert spy.count() == 0
    dialog.band.setCurrentIndex(dialog.band.findData('Full range'))
    assert dialog.low_hz.value() == 0.
    assert dialog.high_hz.value() == 24000.
    assert dialog.high_hz.maximum() == 24000.
    assert dialog.apply_button.isEnabled()
    dialog.set_busy(True)
    assert not dialog.editor.isEnabled()
    assert not dialog.add_button.isEnabled()
    assert not dialog.apply_button.isEnabled()
    dialog.set_busy(False)
    assert dialog.apply_button.isEnabled()
    dialog.close()


def test_add_remove_stable_identity_limit_and_no_track(app, project):
    dialog = AudioReactivityDialog()
    dialog.set_project(project)
    dialog.add_mapping()
    result = dialog.draft()
    added = result['mappings'][1]
    assert added['id'] != 'response-1'
    assert added['track_id'] == 'track-1'
    dialog.amount.setValue(.3)
    assert dialog.draft()['mappings'][1]['id'] == added['id']
    for _ in range(20):
        dialog.add_mapping()
    assert len(dialog.draft()['mappings']) == 16
    assert not dialog.add_button.isEnabled()
    dialog.remove_mapping()
    assert len(dialog.draft()['mappings']) == 15
    dialog.set_project({'soundtrack': None})
    assert 'Import a soundtrack' in dialog.summary.text()
    assert not dialog.editor.isEnabled()
    assert not dialog.prepare_button.isEnabled()
    assert not dialog.enabled.isEnabled()
    dialog.close()


def test_meter_and_global_bypass_do_not_edit_saved_configuration(app, project):
    dialog = AudioReactivityDialog()
    dialog.set_project(project)
    edited = QSignalSpy(dialog.configEdited)
    baseline = dialog.draft()
    dialog.set_responses({'response-1': .6})
    assert dialog.response_meter.value() == 600
    assert dialog.draft() == baseline
    assert edited.count() == 0
    dialog.enabled.setChecked(False)
    assert dialog.response_meter.value() == 0
    assert dialog.editor.isEnabled()  # Bypass keeps authored responses editable.
    dialog.apply()
    assert edited.count() == 1
    assert edited.at(0)[0]['enabled'] is False
    assert edited.at(0)[0]['mappings'] == baseline['mappings']
    dialog.enabled.setChecked(True)
    dialog.bypass.setChecked(True)
    assert dialog.response_meter.value() == 0
    dialog.bypass.setChecked(False)
    assert dialog.response_meter.value() == 600
    dialog.set_responses(None)
    assert dialog.response_meter.value() == 0
    dialog.close()


def test_analysis_signal_plain_text_active_hint_and_narrow_layout(app, project):
    dialog = AudioReactivityDialog()
    project['soundtrack']['name'] = '<b>Tone</b>'
    dialog.set_project(project)
    prepared = QSignalSpy(dialog.prepareRequested)
    edited = QSignalSpy(dialog.configEdited)
    dialog.prepare_button.click()
    assert prepared.count() == 1 and edited.count() == 0
    assert dialog.summary.textFormat() == Qt.TextFormat.PlainText
    assert '<b>Tone</b>' in dialog.summary.text()
    dialog.set_status('<b>Preparing</b>')
    assert dialog.status_label.textFormat() == Qt.TextFormat.PlainText
    dialog.set_active_paths([])
    assert 'inactive' in dialog.target_hint.text()
    assert dialog.target.isEnabled()
    dialog.resize(420, 680)
    dialog.show()
    app.processEvents()
    assert dialog.minimumSizeHint().width() <= 420
    assert dialog.amount.decimals() == 12
    dialog.close()


def test_soundtrack_entry_button_requires_track_and_idle(app, project):
    dialog = SoundtrackDialog()
    spy = QSignalSpy(dialog.reactivityRequested)
    assert not dialog.reactivity_button.isEnabled()
    dialog.set_track(project['soundtrack'])
    dialog.reactivity_button.click()
    assert spy.count() == 1
    dialog.set_busy(True)
    assert not dialog.reactivity_button.isEnabled()
    dialog.set_busy(False)
    assert dialog.reactivity_button.isEnabled()
    dialog.set_track(None)
    assert not dialog.reactivity_button.isEnabled()
    dialog.close()
