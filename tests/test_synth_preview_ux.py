"""Interaction and preview contracts; cached frames never replace export data."""
import time
from PIL import Image
import pytest
from PySide6.QtCore import QLocale, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from studio_widgets import DoubleSpinBox
from synth_effects_ui import EffectParameter
from synth_preview import PreviewFrames
from synth_starters import starter_composition
from synth_sequence import render_sequence_frame
from synth_video import VideoFrameProvider
from test_synth_composer_ui import window, wait_until
from test_synth_video import clip


def test_percentage_editing_preserves_hidden_precision_and_locale():
    app = QApplication.instance() or QApplication([])
    control = EffectParameter('tape.jitter'); spin = control.input
    spin.setLocale(QLocale('de_DE'))
    spin.setValue(.00073123456)
    assert spin.text() == '0,07 %'
    spin.interpretText()
    assert spin.value() == pytest.approx(.00073123456, abs=1e-12)
    spin.lineEdit().setText('0,12 %'); spin.interpretText()
    assert spin.value() == pytest.approx(.0012)
    spin.stepUp(); assert spin.value() == pytest.approx(.0017)
    control.close()


def test_slider_edits_only_commit_on_release_and_keep_wheel_protection():
    app = QApplication.instance() or QApplication([])
    control = EffectParameter('text.size'); changes=[];control.changed.connect(changes.append)
    control.refresh((.34,.34),None,False,True)
    control.slider.setSliderDown(True)
    control.slider.setSliderPosition(650)
    assert changes == []
    control.slider.setSliderDown(False)
    assert len(changes)==1
    assert control.input.value()==changes[0]
    control.close()


def test_all_effect_controls_are_discoverable_without_more_button(window):
    panel=window.composer.effects_panel
    panel.inspect_effect('raster')
    assert all(not c.isHidden() for c in panel.controls.values())
    panel.filter.setText('chroma')
    assert not panel.controls['raster.chroma'].isHidden()
    assert panel.controls['raster.softness'].isHidden()
    panel.filter.setText('no such control'); assert not panel.no_matches.isHidden()
    panel.inspect_effect('tape')
    assert panel.filter.text()==''
    assert not panel.controls['tape.mix'].isHidden()


def test_short_inspector_tab_has_no_hidden_page_blank_scroll_tail(window):
    window.set_composition(starter_composition('text-transmission'))
    composer=window.composer
    composer.look_tabs.setCurrentWidget(composer.object_panel)
    QApplication.processEvents()
    panel=composer.effects_panel;panel.inspect_effect('broadcast');panel.parameter_tabs.setCurrentIndex(2)
    panel.filter.setText('static');composer.look_tabs.setCurrentWidget(panel)
    QTest.qWait(30)
    scroll=window.inspector_scroll
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    QTest.qWait(30)
    bottom_control=panel.controls['broadcast.roll']
    point=bottom_control.mapTo(scroll.viewport(),QPoint(0,0))
    assert 0 <= point.y() < scroll.viewport().height()


def test_preview_cache_is_bounded_and_copies_no_export_settings():
    cache=PreviewFrames(budget=18)
    for i in range(4): cache.put(i,((2,1),bytes([i])*6))
    assert cache.bytes==18 and cache.get(0) is None
    assert cache.get(1)[1]==bytes([1])*6
    cache.put(4,((2,1),b'a'*6));assert cache.get(2) is None
    cache.clear();assert cache.bytes==0 and not cache.items


def test_prepare_preview_matches_renderer_and_invalidates_on_edit(window):
    window.set_composition(starter_composition('text-transmission'))
    window.composer.duration.setValue(.2)
    wait_until(lambda:not window.render_running and not window.render_queued)
    before=window.composition.copy()
    window.prepare_playback()
    wait_until(lambda:window.prepare_job is None)
    assert window.preview_frames.complete(4)
    for frame in range(4):
        size,raw=window.preview_frames.get(frame)
        assert raw==render_sequence_frame(window.sequence,frame/20,size).tobytes()
    assert window.composition==before
    window.timeline.setValue(2)
    assert not window.render_running
    assert 'cached' in window.preview_status.text()
    window.composer.object_panel.controls['text.size'].input.setValue(.4)
    assert not window.preview_frames.items
    assert window.render_queued
    wait_until(lambda:not window.render_running and not window.render_queued)
    assert window.preview_frames.get(2) is not None
    assert not window.preview_frames.complete(4)


def test_stale_preparation_and_render_cannot_replace_newer_settings(window):
    wait_until(lambda:not window.render_running and not window.render_queued)
    old=window.settings_generation
    job=object();window.prepare_job=job
    # Simulate an old packet arriving after cancellation and an edit.
    window.prepare_job=None;window.invalidate()
    old_packet=window.viewer.packet
    window.prepared_frame(job,(old,0,((1,1),b'old')))
    window.frame_ready((old,999,0,(1,1),b'old',.01))
    assert not window.preview_frames.items and window.viewer.packet==old_packet


def test_playback_clock_skips_to_wall_time_instead_of_slowing_clip(window,monkeypatch):
    clock=[100.]
    monkeypatch.setattr('synth_studio.time.monotonic',lambda:clock[0])
    window.play.setChecked(True)
    clock[0]+=.8
    window.advance()
    assert window.timeline.value()==20  # 25 fps, even after a delayed event loop.
    window.play.setChecked(False)


def test_memory_limit_and_cancellation_are_visible(window):
    window.preview_frames.budget=1
    window.prepare_playback()
    assert window.prepare_job is None and '192 MB' in window.preview_status.text()
    assert '360 px' in window.preview_status.text()


def test_held_mask_cache_reuses_results_but_tracks_framing_and_retention(clip,tmp_path,monkeypatch):
    calls=[]
    def build(self,*args): calls.append(args);return Image.new('L',(20,20),90)
    monkeypatch.setattr(VideoFrameProvider,'_mask',build)
    footage=dict(clip,motion_fps=3.)
    with VideoFrameProvider(directory=tmp_path) as provider:
        canvas={'width':120,'height':90}
        first=provider.mask(footage,.01,canvas,2,.8,.12)
        first.putpixel((0,0),255)
        assert provider.mask(footage,.1,canvas,2,.8,.12).getpixel((0,0))==90
        assert len(calls)==1
        for f,c,m,r,s in ((dict(footage,x=1),canvas,2,.8,.12),
                           (footage,dict(canvas,width=121),2,.8,.12),
                           (footage,canvas,1,.8,.12),(footage,canvas,2,.9,.12),
                           (footage,canvas,2,.8,.2),(dict(footage,out=.8),canvas,2,.8,.12)):
            provider.mask(f,.1,c,m,r,s)
        assert len(calls)==7
