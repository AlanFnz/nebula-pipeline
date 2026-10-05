import copy
import os
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from synth_composition import compile_composition, load_composition, save_composition
from synth_effects import effect_preset
from synth_section_sources import video_source_at
from synth_video import video_composition
from test_synth_effects_editor_integration import make_window
from test_synth_section_sources import clip, other_clip, two_sources


def test_duplicate_replace_only_one_section_preserves_effects_and_undo(make_window,clip,other_clip,tmp_path):
    p=video_composition(clip); p['effects']['tape']=effect_preset('tape',1)
    window=make_window(composition=p); panel=window.composer
    panel.duplicate_section(); panel.select_section(1); panel.look_tabs.setCurrentWidget(panel.video_panel)
    assert not panel.scope_combo.isHidden()
    source=panel.video_panel
    assert 'this section' in source.relink.text()
    assert not source.controls['in'].isEnabled()
    original=copy.deepcopy(window.composition)
    job=SimpleNamespace(document_identity=window.document_identity,section_id=original['sections'][1]['id'])
    window.import_job=job
    # While importing, user switches to the first section; stable ID wins.
    panel.select_section(0)
    window.video_imported(job,other_clip,True)
    assert window.composition['footage']==original['footage']
    assert window.composition['sections'][0]==original['sections'][0]
    second=window.composition['sections'][1]
    assert second['footage']['path']==other_clip['path']
    assert second['effects']==original['sections'][1]['effects']
    assert window.composition['effects']==original['effects']
    panel.select_section(1)
    assert source.controls['in'].isEnabled()
    source.controls['in'].setValue(.25)
    assert window.composition['sections'][1]['footage']['in']==.25
    assert window.composition['footage']['in']==0.
    window.undo_composition(); assert window.composition['sections'][1]['footage']['in']==0.
    window.undo_composition(); assert window.composition==original
    window.redo_composition(); window.redo_composition()
    path=tmp_path/'local.json'; save_composition(path,window.composition)
    reopened=make_window(composition=load_composition(path)); reopened.composer.select_section(1)
    assert reopened.composer.video_panel.controls['in'].value()==.25
    assert reopened.protected_document_destination(other_clip['path'])


def test_independent_mode_trim_position_reset_and_return_to_shared_are_scoped(make_window,clip):
    p=video_composition(clip); window=make_window(composition=p); panel=window.composer
    panel.duplicate_section(); panel.select_section(1); panel.look_tabs.setCurrentWidget(panel.video_panel)
    source=panel.video_panel; source.source_mode.setCurrentIndex(1)
    source.controls['in'].setValue(.25); source.controls['x'].setValue(80)
    assert window.composition['sections'][1]['footage']['x']==80
    assert window.composition['footage']==p['footage']
    panel.reset_controls()
    assert window.composition['sections'][1]['footage']['x']==0
    assert window.composition['sections'][1]['footage']['in']==.25
    source.source_mode.setCurrentIndex(0)
    assert 'footage' not in window.composition['sections'][1]
    assert not source.controls['in'].isEnabled()
    window.undo_composition()
    assert window.composition['sections'][1]['footage']['in']==.25


def test_speed_shortens_selected_section_or_keeps_duration_and_trim_button_respects_speed(make_window,clip,other_clip):
    p=two_sources(clip,other_clip); window=make_window(composition=p); panel=window.composer
    panel.select_section(1); panel.look_tabs.setCurrentWidget(panel.video_panel); source=panel.video_panel
    source.speed.setValue(2.)
    assert window.composition['sections'][0]==p['sections'][0]
    section=window.composition['sections'][1]
    assert section['duration']==.25 and section['video_rate']==2. and section['effects_rate']==2.
    assert window.sequence['duration']==.75
    assert video_source_at(window.sequence,.625)[1]==.25
    window.undo_composition(); assert window.composition==p
    window.redo_composition()
    source.match_duration.setChecked(False); source.speed.setValue(1.)
    assert window.composition['sections'][1]['duration']==.25
    assert window.composition['sections'][1].get('video_rate',1.)==1.
    assert window.composition['sections'][1]['effects_rate']==2.
    source.duration.click()
    assert window.composition['sections'][1]['duration']==1.
    assert window.composition['sections'][0]==p['sections'][0]


def test_stale_import_does_not_replace_another_section(make_window,clip,other_clip):
    window=make_window(composition=video_composition(clip)); before=copy.deepcopy(window.composition)
    job=SimpleNamespace(document_identity=window.document_identity,section_id='deleted')
    window.import_job=job; window.video_imported(job,other_clip,True)
    assert window.composition==before
    assert 'removed' in window.status.text()


def test_detailed_duration_still_editable_with_multiple_sources(make_window,clip,other_clip):
    seq=compile_composition(two_sources(clip,other_clip))
    window=make_window(sequence=seq)
    window.sequence_field_controls['duration'].setValue(2.)
    assert window.sequence['duration']==2.
    assert window.sequence['video_segments'][-1]['end']==2.
    window.sequence_field_controls['duration'].setValue(.75)
    assert window.sequence['video_segments'][-1]['end']==.75


def test_section_file_picker_captures_the_selected_target(make_window,clip,other_clip,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    window=make_window(composition=video_composition(clip)); panel=window.composer
    panel.duplicate_section(); panel.select_section(1)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args: (other_clip['path'],''))
    imports=[]
    monkeypatch.setattr(window,'start_video_import',lambda path,relink=False,**kwargs: imports.append((path,relink,kwargs)))
    panel.video_panel.relink.click()
    assert imports==[(other_clip['path'],True,{'section_id':window.composition['sections'][1]['id']})]
