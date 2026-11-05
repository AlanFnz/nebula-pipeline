import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from synth_effects import EFFECT_BY_ID, describe_effects
from synth_starters import starter_composition
from synth_subject import scope_states
from synth_subject_ui import SubjectPanel


def test_new_source_opens_its_editable_inspector_and_details():
    app=QApplication.instance() or QApplication([])
    project=starter_composition('pleated-signal')
    panel=SubjectPanel()
    try:
        panel.refresh(describe_effects(scope_states(project)),project['effects'],{},False)
        assert panel.kind=='pleated'
        assert set(panel.controls)==set(EFFECT_BY_ID['pleated_field'].paths)
        assert panel.selector.currentData()=='pleated'
        detail=QSignalSpy(panel.details_requested)
        panel.open_details(False)
        assert detail.count()==1 and detail.at(0)[0]=='pleated_field'
        # Reuse the same inspector with an older study, as happens on Load.
        older=starter_composition('chromatic-lattice')
        panel.refresh(describe_effects(scope_states(older)),older['effects'],{},False)
        assert panel.kind=='lattice'
        assert not any(path.startswith('pleated_field.') for path in panel.controls)
    finally:
        panel.deleteLater();app.processEvents()
