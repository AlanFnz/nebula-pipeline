"""Draft-first, project-wide soundtrack response editor; never reads media."""
from __future__ import annotations

import copy
import math
import uuid

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFormLayout, QHBoxLayout,
                              QLabel, QListWidget, QProgressBar, QPushButton,
                              QScrollArea, QSizePolicy, QVBoxLayout, QWidget)
from studio_widgets import ComboBox, DoubleSpinBox, configure_parameter_spin
from synth_audio_reactivity import normalize_reactivity, reactivity_targets, target_parameter


BANDS = (('Bass', 40., 180.), ('Mids', 180., 2500.),
         ('Highs', 2500., 12000.), ('Full range', 0., None))


class AudioReactivityDialog(QDialog):
    configEdited = Signal(object)
    prepareRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('React to audio')
        self.setModal(False)
        self.resize(460, 680)
        self._loading = False
        self._busy = False
        self._track = None
        self._authored = None
        self._draft_config = {'enabled': False, 'mappings': []}
        self._responses = {}
        self._active_paths = None
        outer = QVBoxLayout(self)
        self.summary = self._label('Import a soundtrack to make your piece respond to it.')
        outer.addWidget(self.summary)
        self.enabled = QCheckBox('Enable audio response')
        self.enabled.setToolTip('Bypass every audio response without removing your settings.')
        outer.addWidget(self.enabled)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mapping_list = QListWidget()
        self.mapping_list.setAccessibleName('Audio responses')
        self.mapping_list.setFixedHeight(100)
        layout.addWidget(self.mapping_list)
        actions = QHBoxLayout()
        self.add_button = QPushButton('Add response')
        self.remove_button = QPushButton('Remove')
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.editor = QWidget()
        form = QFormLayout(self.editor)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.target = ComboBox()
        self.target.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for path, label in reactivity_targets():
            self.target.addItem(label, path)
            self.target.setItemData(self.target.count()-1, path, Qt.ItemDataRole.ToolTipRole)
        self.target.setAccessibleName('Audio response target')
        form.addRow('Parameter', self.target)
        self.band = ComboBox()
        for label, low, high in BANDS:
            self.band.addItem(label, label)
        self.band.addItem('Custom', 'Custom')
        self.band.setAccessibleName('Audio frequency band')
        form.addRow('Listen to', self.band)
        band_row = QWidget()
        band_layout = QHBoxLayout(band_row)
        band_layout.setContentsMargins(0, 0, 0, 0)
        self.low_hz = self._number('Lowest frequency', 0., 384000., 10., ' Hz')
        self.high_hz = self._number('Highest frequency', 0., 384000., 10., ' Hz')
        band_layout.addWidget(self.low_hz, 1)
        band_layout.addWidget(QLabel('to'))
        band_layout.addWidget(self.high_hz, 1)
        form.addRow('Frequency', band_row)
        self.amount = self._number('Audio change amount', -1., 1., .01)
        self.amount_label = QLabel('Change amount')
        self.amount.setToolTip('The loudest response adds this change to the existing animation. Negative values reduce the parameter. Responses to the same parameter add together and stay within its limits.')
        form.addRow(self.amount_label, self.amount)
        self.sensitivity = self._number('Audio sensitivity', 0., 16., .1, ' ×')
        self.sensitivity.setToolTip('Higher sensitivity makes quieter sound produce a stronger response.')
        form.addRow('Sensitivity', self.sensitivity)
        self.attack = self._number('Audio rise time', 0., 10., .01, ' s')
        self.attack.setToolTip('How quickly the response rises after a louder sound.')
        form.addRow('Rise', self.attack)
        self.release = self._number('Audio fall time', 0., 10., .01, ' s')
        self.release.setToolTip('How slowly the response settles after the sound becomes quieter.')
        form.addRow('Fall', self.release)
        self.bypass = QCheckBox('Bypass this response')
        form.addRow('', self.bypass)
        self.response_meter = QProgressBar()
        self.response_meter.setRange(0, 1000)
        self.response_meter.setTextVisible(False)
        self.response_meter.setFixedHeight(12)
        self.response_meter.setAccessibleName('Current audio response')
        form.addRow('Response', self.response_meter)
        layout.addWidget(self.editor)
        self.target_hint = self._label('')
        layout.addWidget(self.target_hint)
        hint = self._label('Responses apply across the whole piece and add to existing animation. Changes to the same parameter add together and stay within its limits. Enable the chosen effect in your piece to see its response.')
        hint.setObjectName('muted')
        layout.addWidget(hint)
        layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.error_label = self._label('')
        outer.addWidget(self.error_label)
        self.status_label = self._label('')
        outer.addWidget(self.status_label)
        footer = QHBoxLayout()
        self.prepare_button = QPushButton('Analyze audio')
        self.prepare_button.setToolTip('Prepare frequency responses for this soundtrack.')
        self.reset_button = QPushButton('Reset edits')
        self.apply_button = QPushButton('Apply')
        self.apply_button.setObjectName('primary')
        self.close_button = QPushButton('Close')
        for button in (self.prepare_button, self.reset_button, self.apply_button, self.close_button):
            footer.addWidget(button)
        outer.addLayout(footer)
        self.add_button.clicked.connect(self.add_mapping)
        self.remove_button.clicked.connect(self.remove_mapping)
        self.mapping_list.currentRowChanged.connect(self._select_mapping)
        self.target.currentIndexChanged.connect(self._target_changed)
        self.band.currentIndexChanged.connect(self._band_changed)
        for control in (self.low_hz, self.high_hz, self.amount, self.sensitivity, self.attack, self.release):
            control.valueChanged.connect(self._controls_changed)
        self.bypass.toggled.connect(self._controls_changed)
        self.enabled.toggled.connect(self._global_changed)
        self.prepare_button.clicked.connect(self.prepareRequested.emit)
        self.reset_button.clicked.connect(self.reset)
        self.apply_button.clicked.connect(self.apply)
        self.close_button.clicked.connect(self.reject)
        self._update_enabled()

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        return label

    @staticmethod
    def _number(name, low, high, step, suffix=''):
        control = DoubleSpinBox()
        control.setDecimals(12)
        control.setRange(low, high)
        control.setSingleStep(step)
        control.setSuffix(suffix)
        control.setKeyboardTracking(False)
        control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        control.setAccessibleName(name)
        return control

    def set_project(self, project):
        track = copy.deepcopy(project.get('soundtrack'))
        raw = project.get('audio_reactivity')
        config = normalize_reactivity(raw if raw is not None else {'enabled': False, 'mappings': []}, track)
        authored = (track, config)
        changed = authored != self._authored
        self._track = track
        self._authored = copy.deepcopy(authored)
        if track:
            self.summary.setText(f'Soundtrack: {track.get("name", "Soundtrack")}')
            self.summary.setToolTip(track.get('path', ''))
        else:
            self.summary.setText('Import a soundtrack to make your piece respond to it.')
            self.summary.setToolTip('')
        if changed:
            self._draft_config = copy.deepcopy(config)
            self._refresh_list()
        self._update_enabled()

    def draft(self):
        return copy.deepcopy(self._draft_config)

    def reset(self):
        if self._authored:
            self._draft_config = copy.deepcopy(self._authored[1])
            self._refresh_list()
        self._update_enabled()

    def reject(self):
        self.reset()
        super().reject()

    def add_mapping(self):
        if not self.add_button.isEnabled():
            return
        path = self.target.currentData() or self.target.itemData(0)
        spec = target_parameter(path)
        self._draft_config['mappings'].append(dict(
            id=str(uuid.uuid4()), track_id=self._track['id'], path=path,
            low_hz=min(40., max(0., self._nyquist()-1.)), high_hz=min(180., self._nyquist()),
            amount=(spec.maximum-spec.minimum)*.25, sensitivity=1.,
            attack=.05, release=.25, enabled=True))
        self._refresh_list(len(self._draft_config['mappings'])-1)
        self._update_enabled()

    def remove_mapping(self):
        row = self.mapping_list.currentRow()
        if not self.remove_button.isEnabled() or row < 0:
            return
        del self._draft_config['mappings'][row]
        self._refresh_list(row)
        self._update_enabled()

    def _nyquist(self):
        return float((self._track or {}).get('sample_rate', 48000))/2.

    def _current(self):
        row = self.mapping_list.currentRow()
        mappings = self._draft_config['mappings']
        return mappings[row] if 0 <= row < len(mappings) else None

    def _refresh_list(self, selected=None):
        self._loading = True
        selected = self.mapping_list.currentRow() if selected is None else selected
        self.enabled.setChecked(self._draft_config['enabled'])
        self.mapping_list.clear()
        for mapping in self._draft_config['mappings']:
            self.mapping_list.addItem(self._mapping_label(mapping))
        self.mapping_list.setCurrentRow(min(max(0, selected), self.mapping_list.count()-1))
        self._loading = False
        self._select_mapping()

    def _mapping_label(self, mapping):
        index = self.target.findData(mapping['path'])
        label = self.target.itemText(index) if index >= 0 else 'Unavailable parameter'
        return f'{label} · {mapping["low_hz"]:g}–{mapping["high_hz"]:g} Hz' + (' · Bypassed' if not mapping['enabled'] else '')

    def _select_mapping(self, *_args):
        if self._loading:
            return
        mapping = self._current()
        self._loading = True
        if mapping:
            self.target.setCurrentIndex(self.target.findData(mapping['path']))
            self._configure_amount()
            for key in ('low_hz', 'high_hz'):
                getattr(self, key).setMaximum(self._nyquist())
            for key in ('low_hz', 'high_hz', 'amount', 'sensitivity', 'attack', 'release'):
                getattr(self, key).setValue(mapping[key])
            self.bypass.setChecked(not mapping['enabled'])
            self._sync_band()
        self._loading = False
        self._update_hint()
        self._update_meter()
        self._update_enabled()

    def _configure_amount(self):
        if self.target.currentData() is None:
            return
        spec = target_parameter(self.target.currentData())
        configure_parameter_spin(self.amount, spec)
        span = spec.maximum-spec.minimum
        self.amount.setRange(-span, span)
        self.amount_label.setText('Change amount (%)' if self.amount.display_scale == 100. else 'Change amount')
        self.target.setToolTip(self.target.currentData())

    def _target_changed(self, *_args):
        if self._loading or not self._current():
            return
        self._loading = True
        self._configure_amount()
        self._loading = False
        self._controls_changed()

    def _band_changed(self, *_args):
        if self._loading or self.band.currentData() == 'Custom' or not self._current():
            return
        preset = next(item for item in BANDS if item[0] == self.band.currentData())
        self._loading = True
        self.low_hz.setValue(min(preset[1], max(0., self._nyquist()-1.)))
        self.high_hz.setValue(min(preset[2] or self._nyquist(), self._nyquist()))
        self._loading = False
        self._controls_changed()

    def _sync_band(self):
        selected = 'Custom'
        for label, low, high in BANDS:
            if self.low_hz.value() == low and self.high_hz.value() == min(high or self._nyquist(), self._nyquist()):
                selected = label
                break
        self.band.setCurrentIndex(self.band.findData(selected))

    def _controls_changed(self, *_args):
        mapping = self._current()
        if self._loading or not mapping:
            return
        mapping.update({key: getattr(self, key).value() for key in ('low_hz', 'high_hz', 'amount', 'sensitivity', 'attack', 'release')})
        mapping.update(path=self.target.currentData(), enabled=not self.bypass.isChecked())
        self._loading = True
        self._sync_band()
        self._loading = False
        self.mapping_list.currentItem().setText(self._mapping_label(mapping))
        self._update_hint()
        self._update_meter()
        self._update_enabled()

    def _global_changed(self, *_args):
        if not self._loading:
            self._draft_config['enabled'] = self.enabled.isChecked()
            self._update_meter()
            self._update_enabled()

    def _update_hint(self):
        mapping = self._current()
        inactive = mapping and self._active_paths is not None and mapping['path'] not in self._active_paths
        self.target_hint.setText('This effect is currently inactive. Enable it in your piece to see this response.' if inactive else '')

    def set_active_paths(self, paths):
        self._active_paths = None if paths is None else set(paths)
        self._update_hint()

    def _update_enabled(self):
        available = self._track is not None and not self._busy
        self.enabled.setEnabled(available)
        self.mapping_list.setEnabled(available)
        self.editor.setEnabled(available and self._current() is not None)
        self.add_button.setEnabled(available and len(self._draft_config['mappings']) < 16)
        self.remove_button.setEnabled(available and self._current() is not None)
        self.prepare_button.setEnabled(available)
        error = ''
        try:
            normalize_reactivity(self._draft_config, self._track)
        except (ValueError, TypeError) as exc:
            error = str(exc)
        self.error_label.setText(error)
        changed = self._authored is not None and self._draft_config != self._authored[1]
        self.apply_button.setEnabled(bool(available and changed and not error))
        self.reset_button.setEnabled(bool(changed and not self._busy))

    def apply(self):
        if not self.apply_button.isEnabled():
            return
        config = normalize_reactivity(self._draft_config, self._track)
        self._draft_config = copy.deepcopy(config)
        self._authored = (copy.deepcopy(self._track), copy.deepcopy(config))
        self._update_enabled()
        self.configEdited.emit(copy.deepcopy(config))

    def set_status(self, status):
        self.status_label.setText(str(status))

    def set_busy(self, busy):
        self._busy = bool(busy)
        self._update_enabled()

    def set_responses(self, responses):
        self._responses = dict(responses or {})
        self._update_meter()

    def _update_meter(self):
        mapping = self._current()
        value = self._responses.get(mapping['id'], 0.) if mapping and mapping['enabled'] and self._draft_config['enabled'] else 0.
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.
        value = min(1., max(0., value)) if math.isfinite(value) else 0.
        self.response_meter.setValue(round(value*1000))
        self.response_meter.setAccessibleDescription(f'{value*100:.0f} percent')
