import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from test_synth_effects_editor_integration import make_window
from synth_starters import starter_composition


def test_band_mode_exposes_only_relevant_controls_and_undo(make_window):
    w=make_window(composition=starter_composition('image-memory'))
    panel=w.composer.effects_panel
    panel.inspect_effect('broadcast');panel.parameter_tabs.setCurrentIndex(2)
    panel.filter.clear();panel.group.setCurrentText('Motion & timing');QApplication.processEvents()
    mode=panel.controls['broadcast.band_motion'].input
    assert mode.currentIndex()==0
    assert panel.controls['broadcast.band_interval'].isHidden()
    assert not panel.controls['broadcast.roll'].isHidden()
    mode.setCurrentIndex(1);QApplication.processEvents()
    assert panel.controls['broadcast.roll'].isHidden()
    assert not panel.controls['broadcast.band_interval'].isHidden()
    assert panel.controls['broadcast.band_interval'].input.suffix()==' s'
    panel.controls['broadcast.band_interval'].input.setValue(2.7)
    assert w.composition['effects']['broadcast']['params']['broadcast.band_interval']==2.7
    w.undo_composition();w.undo_composition()
    assert mode.currentIndex()==0
    assert panel.controls['broadcast.band_interval'].isHidden()
