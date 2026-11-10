"""Native video/effect navigation shares folding and preserves edits/scopes."""
import copy, os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication
from synth_video_ui import VideoSourcePanel
from synth_video import video_composition
from synth_intensity import intensity_path
from test_synth_video import clip
from test_synth_compact_effects import make_panel


def settle():
    for _ in range(4): QApplication.processEvents()


def test_effect_search_escapes_group_filter_and_restores_navigation(make_panel):
    panel, document, _ = make_panel()
    panel.inspect_effect('broadcast'); settle()
    original = copy.deepcopy(document); edited = QSignalSpy(panel.edited)
    panel.group.setCurrentIndex(1)
    title = panel.group.currentData()
    panel.filter.setText('hue'); settle()
    assert panel.search_results
    QTest.keyClick(panel.filter, Qt.Key.Key_Return); settle()
    first = panel.controls[panel.search_results[0]]
    assert first.input.hasFocus() or first.use_fixed.hasFocus()
    panel.filter.clear(); settle()
    assert panel.group.currentData() == title
    panel.group.setCurrentIndex(0)
    expansion = dict(panel.group_expansion)
    panel.show_all_controls.setChecked(True); settle()
    assert all(label.isChecked() for label in panel.group_labels.values() if label.isVisible())
    panel.show_all_controls.setChecked(False); settle()
    assert panel.group_expansion == expansion
    panel.filter.setText('broadcast.curve'); settle()
    # Curvature lives in Screen; a link finds it without guessing a tab.
    assert panel.other_match_buttons[3].isVisible()
    panel.other_match_buttons[3].click(); settle()
    assert panel.parameter_tabs.currentIndex() == 3
    panel.filter.clear(); settle()
    assert panel.parameter_tabs.currentIndex() == 0
    # Enter also reaches the pinned intensity and valid controls in other tabs.
    panel.filter.setText('intensity'); settle()
    QTest.keyClick(panel.filter, Qt.Key.Key_Return); settle()
    intensity = panel.controls[intensity_path('broadcast')]
    assert intensity.input.hasFocus() or intensity.use_fixed.hasFocus()
    panel.filter.setText('broadcast.curve'); settle()
    QTest.keyClick(panel.filter, Qt.Key.Key_Return); settle()
    assert panel.controls['broadcast.curve'].input.hasFocus()
    panel.filter.clear(); settle()
    # Periodic bands hide stochastic intervals; search must not offer a dead link.
    panel.summary['broadcast']['ranges']['broadcast.band_motion'] = (0, 0)
    panel.filter.setText('broadcast.band_interval'); settle()
    assert not panel.other_matches.isVisible() and panel.no_matches.isVisible()
    assert edited.count() == 0 and document == original


def test_video_search_folding_and_inherited_controls_preserve_payload(clip):
    app = QApplication.instance() or QApplication([])
    panel = VideoSourcePanel(); panel.resize(420, 680); panel.show()
    source = video_composition(clip)['footage']; source.update({'in':.25,'out':.75})
    original = copy.deepcopy(source); edited = QSignalSpy(panel.edited)
    try:
        panel.refresh(source); settle()
        nav = panel.sections
        assert not panel.controls['rotation'].isVisible()
        nav.search.setText('rotation'); settle()
        assert panel.controls['rotation'].isVisible()
        nav.search.setFocus(); QTest.keyClick(nav.search, Qt.Key.Key_Return); settle()
        assert panel.controls['rotation'].hasFocus()
        nav.search.clear(); settle()
        assert not panel.controls['rotation'].isVisible()
        nav.show_all.setChecked(True); settle()
        assert panel.controls['rotation'].isVisible()
        assert nav.scroll.horizontalScrollBar().maximum() == 0
        # A shared source cannot become editable by expanding or searching.
        panel.refresh(source, {'duration':4.,'video_rate':1.}); nav.search.setText('rotation'); settle()
        assert not panel.source_controls.isVisible() and not panel.controls['rotation'].isEnabled()
        assert nav.no_matches.isVisible()
        panel.refresh(source, {'duration':4.,'video_rate':1.,'footage':source}); settle()
        assert panel.controls['rotation'].isVisible() and panel.controls['rotation'].isEnabled()
        assert edited.count() == 0 and source == original
        assert panel.controls['in'].value() == .25
        missing = dict(source, path=str(Path(source['path']).with_name('missing.mp4')))
        panel.refresh(missing); nav.search.clear(); nav.show_all.setChecked(False); settle()
        assert 'MISSING' in nav.groups['Source file'].summary.text()
        assert nav.groups['Source file'].summary.isVisible()
    finally:
        panel.close(); panel.deleteLater(); app.processEvents()
