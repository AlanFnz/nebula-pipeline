#!/usr/bin/env python3
"""Opt-in SynthStudio audit. No production modules or user documents are changed.
See docs/preview-performance-audit-runner.md for boundaries and reproduction.
"""
from __future__ import annotations
import argparse
import copy
import cProfile
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'output/preview-performance-audit'
CASES = ('guerrilla', 'text-dye-transfer', 'image-memory', 'color-film-die', 'video')
EDIT_PATHS = {'guerrilla':('text','text.opacity'),'text-dye-transfer':('text','text.opacity'),'image-memory':('image_memory','image_memory.light'),'color-film-die':('solid','solid.light'),'video':('bloom','bloom.strength')}

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def command(*args):
    return subprocess.check_output(args, text=True).strip()

def freeze():
    os.environ['NEBULA_STATE_DIR'] = str(OUT / 'freeze-state')
    from synth_starters import starter_composition
    from synth_composition import load_composition, compile_composition
    source = ROOT / 'output/guerrilla-radio-soft-red/Guerrilla-Radio-soft-red.nebula.json'
    cases = {'guerrilla': load_composition(source)}
    cases.update({name: starter_composition(name) for name in CASES[1:-1]})
    fixtures = OUT / 'fixtures'; fixtures.mkdir(parents=True, exist_ok=True)
    video = fixtures / 'testsrc-1080p.mkv'
    began = time.monotonic()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30:duration=3', '-an', '-c:v', 'ffv1', '-level', '3', '-threads', '1', '-fflags', '+bitexact', '-flags:v', '+bitexact', str(video)], check=True)
    manifest = {'source_commit': command('git', '-C', str(ROOT), 'rev-parse', 'HEAD'),
                'source_original': {'path': str(source), 'sha256': digest(source)},
                'guide_audio': {'path': str(ROOT/'output/guerrilla-radio-v2/media/Guerrilla-Radio-guide.wav'), 'sha256': digest(ROOT/'output/guerrilla-radio-v2/media/Guerrilla-Radio-guide.wav')},
                'video': {'path': str(video), 'sha256': digest(video), 'generation_s': time.monotonic()-began, 'generator': 'ffmpeg testsrc2 1920x1080 30fps 3s FFV1 level3 threads1 bitexact', 'ffmpeg': command('ffmpeg', '-version').splitlines()[0]},
                'protocol':{'edit_paths':EDIT_PATHS,'single_edit_values':[.90,.91],'rapid_committed_values':[.90+i*.01 for i in range(8)],'rapid_repeat_offset':[0,.01],'nominal_input_interval_ms':15,'navigation':'frames[i % len] when i % 4 < 2, else frames[-(i % len)-1]','cache_budget_bytes':192*1024**2},'cases': {}, 'assets': []}
    from synth_section_sources import resolve_media_paths
    for name, doc in cases.items():
        doc = copy.deepcopy(doc)
        resolve_media_paths(doc, source.parent if name == 'guerrilla' else ROOT)
        path = fixtures / f'{name}.nebula.json'; dump(path, doc)
        seq = compile_composition(doc)
        count = round(seq['duration']*seq['fps'])
        from synth_composition import section_ranges
        cuts = [round(a*seq['fps']) for a,b in section_ranges(doc)]
        frames = list(dict.fromkeys([0, 1, count//3, count//2, count-1] + [max(0,c-1) for c in cuts[:4]] + cuts[:4]))
        manifest['cases'][name] = {'path': str(path), 'sha256': digest(path), 'canvas': doc['canvas'], 'fps': seq['fps'], 'duration':seq['duration'], 'sections':len(doc['sections']), 'effects':doc.get('effects'), 'frames':frames, 'prepare_frames':frames[:4]}
    for path in sorted((ROOT/'assets').rglob('*')):
        if path.is_file(): manifest['assets'].append({'path':str(path), 'sha256':digest(path)})
    # Include referenced external assets/fonts as well as the bundled set.
    def referenced(value):
        if isinstance(value, dict):
            for v in value.values(): yield from referenced(v)
        elif isinstance(value,list):
            for v in value: yield from referenced(v)
        elif isinstance(value,str) and value.startswith('/') and Path(value).is_file(): yield Path(value)
    seen = {x['path'] for x in manifest['assets']}
    for path in referenced(cases):
        if str(path) not in seen:
            manifest['assets'].append({'path':str(path), 'sha256':digest(path)}); seen.add(str(path))
    manifest['environment'] = {'python':sys.version,'platform':platform.platform(), 'macos': command('sw_vers'), 'hardware':command('sysctl','-n','hw.model','machdep.cpu.brand_string','hw.memsize','hw.ncpu'), 'power': command('pmset','-g'), 'power_source':command('pmset','-g','batt'), 'dependencies': {p:importlib.metadata.version(p) for p in ('PySide6','numpy','pillow','fonttools','trimesh')}, 'background':command('ps','-Ao','pid,ppid,%cpu,rss,comm'), 'installed_version':command('/usr/libexec/PlistBuddy','-c','Print :CFBundleShortVersionString','/Users/ixtlan/Applications/Nebula Studio.app/Contents/Info.plist')}
    dump(OUT/'manifest.json', manifest)
    print('Frozen', list(cases), flush=True)

class Audit:
    def __init__(self, args):
        self.args=args; self.folder=OUT/args.label; self.folder.mkdir(parents=True, exist_ok=True)
        self.log=(self.folder/'events.jsonl').open('x',buffering=1)
        self.log_lock=threading.Lock(); self.records=[]; self.jobs=[]; self.painted=None; self.display=None; self.active=None
        self.observer_error=None;self.saved_frames=set(); self.last_tick=time.monotonic(); self.stop=threading.Event(); self.sequence=0;self.ui_profile=None
    def emit(self, kind, **fields):
        with self.log_lock:
            self.log.write(json.dumps({'t':time.monotonic(), 'kind':kind, **fields})+'\n')
    def instrument(self):
        import synth_video
        synth_video.proxy_directory=lambda:Path(os.environ['NEBULA_STATE_DIR'])/'proxies'
        import synth_studio as studio
        original_proxy=synth_video.prepare_proxy
        def proxy(*args,**kwargs):
            start=time.monotonic();result=original_proxy(*args,**kwargs)
            self.emit('proxy',elapsed_s=time.monotonic()-start,path=str(result))
            return result
        synth_video.prepare_proxy=proxy;studio.prepare_proxy=proxy
        original_decode=synth_video.VideoFrameProvider.frame
        def decode(provider,footage,seconds,edge=None):
            start=time.monotonic();before=provider.decode_count
            result=original_decode(provider,footage,seconds,edge)
            self.emit('video_frame',elapsed_s=time.monotonic()-start,seconds=seconds,edge=edge,decoded=provider.decode_count-before,provider=id(provider),cache_bytes=provider.bytes)
            return result
        synth_video.VideoFrameProvider.frame=decode
        from synth_viewer import SynthViewer
        original=SynthViewer.paintEvent
        def paint(view,event,original=original):
            began=time.monotonic(); result=original(view,event)
            if view is getattr(getattr(self,'window',None),'viewer',None) and view.packet:
                self.painted=(id(view.packet),time.monotonic())

                if not self.args.quiet_observers:self.emit('paint_end', packet=id(view.packet), elapsed_s=time.monotonic()-began)
            return result
        SynthViewer.paintEvent=paint
        original_display=studio.SynthStudio.display_frame
        def display(w,seconds,packet,cached=False):
            began=time.monotonic(); result=original_display(w,seconds,packet,cached)
            self.display={'packet':id(w.viewer.packet),'time':seconds,'cached':cached,'receipt':began,'return':time.monotonic(),'generation':w.settings_generation,'side':w.comparison['side'] if w.comparison else None,'owner':id(w.comparison['token']) if w.comparison else None,'effect':w.discovery_session.effect_id if w.discovery_session else None}

            if not self.args.quiet_observers:self.emit('display',**self.display)
            return result
        studio.SynthStudio.display_frame=display
        for cls in (() if self.args.quiet_observers else (studio.RenderJob,studio.PreparePreviewJob)):
            original_run=cls.run
            def run(job, original_run=original_run, name=cls.__name__):
                start=time.monotonic(); self.emit('worker_start',job=id(job),name=name, generation=getattr(job,'settings_generation',getattr(job,'generation',None)),time_seconds=getattr(job,'time_seconds',None),frames=getattr(job,'frames',None),size=job.size)
                prof=cProfile.Profile() if self.args.profile else None
                if prof: prof.enable()
                try: return original_run(job)
                finally:
                    if prof:
                        prof.disable(); prof.dump_stats(str(self.folder/f'worker-{start:.9f}-{id(job)}.prof'))
                    end=time.monotonic()
                    item={'job':id(job),'name':name,'start':start,'end':end,'cancelled':job.cancel.event.is_set()}
                    self.jobs.append(item); self.emit('worker_end',**item)
            cls.run=run
        if not self.args.quiet_observers:
            original_start=studio.QThreadPool.start
            def submit(pool,job,*args,**kwargs):
                if isinstance(job,(studio.RenderJob,studio.PreparePreviewJob)):
                    self.emit('worker_submit',job=id(job),name=type(job).__name__)
                return original_start(pool,job,*args,**kwargs)
            studio.QThreadPool.start=submit
            for method,attribute in (('cancel_foreground_render','render_job'),('_obsolete_preparation','prepare_job')):
                original=getattr(studio.SynthStudio,method)
                def cancel(w,*args,original=original,attribute=attribute,**kwargs):
                    job=getattr(w,attribute,None)
                    if job is not None and not job.cancel.event.is_set():self.emit('cancel_request',job=id(job),name=type(job).__name__)
                    return original(w,*args,**kwargs)
                setattr(studio.SynthStudio,method,cancel)
        if self.args.detail:
            targets=[(studio.RenderJob,'__init__'),(studio.PreparePreviewJob,'__init__')] + [(studio.SynthStudio,n) for n in ('capture_preview_validity','invalidate','request_frame','refresh_effect_explanations','refresh_soundtrack','refresh_composition','rebuild_modules')]
            from synth_composer_ui import CompositionPanel
            targets += [(CompositionPanel,n) for n in ('refresh','commit')]
            for cls,name in targets:
                original=getattr(cls,name)
                def timed(obj,*a,original=original,name=name,**kw):
                    start=time.monotonic()
                    try:return original(obj,*a,**kw)
                    finally:self.emit('span',name=name,start=start,end=time.monotonic(),thread=threading.get_ident())
                setattr(cls,name,timed)
    def monitor(self):
        # One ps snapshot each second: own RSS + descendants, background CPU, no dependencies.
        while not self.stop.is_set():
            try:
                rows=[]
                for line in command('ps','-Ao','pid=,ppid=,rss=,%cpu=,comm=').splitlines():
                    a=line.split(None,4)
                    if len(a)==5: rows.append((int(a[0]),int(a[1]),int(a[2]),float(a[3]),a[4]))
                own=os.getpid(); children=set(); parents={own}
                while True:
                    new={p for p,pp,*_ in rows if pp in parents}-parents
                    if not new:break
                    parents|=new; children|=new
                self.emit('memory',rss_kib=sum(r for p,pp,r,c,n in rows if p==own),children_rss_kib=sum(r for p,pp,r,c,n in rows if p in children and Path(n).name!='ps'),observer_ps_rss_kib=sum(r for p,pp,r,c,n in rows if p in children and Path(n).name=='ps'),children=[{'pid':p,'rss_kib':r,'cpu':c,'command':n} for p,pp,r,c,n in rows if p in children and Path(n).name!='ps'],own_cpu=sum(c for p,pp,r,c,n in rows if p==own),background_cpu=[{'pid':p,'cpu':c,'command':n} for p,pp,r,c,n in rows if p not in parents and c>10])
            except Exception as e:self.emit('monitor_error',error=str(e))
            self.stop.wait(1)
    def tick(self):
        now=time.monotonic(); self.emit('event_loop',gap_ms=(now-self.last_tick)*1000); self.last_tick=now
        if hasattr(self,'window'):
            c=self.window.preview_frames
            self.emit('cache',bytes=c.bytes,reserved=c.reserved,budget=c.budget,frames=len(c.items))
            if c.bytes+c.reserved>c.budget:self.observer_error=AssertionError((c.bytes,c.reserved,c.budget))
    async def wait(self,predicate,timeout=900):
        deadline=time.monotonic()+timeout
        while not predicate():
            if self.observer_error:raise self.observer_error
            if time.monotonic()>deadline:
                raise TimeoutError(self.window.preview_status.text()+' '+self.window.status.text())
            await self.pause(5)
    async def pause(self,milliseconds):
        class Delay:
            def __await__(self):
                yield max(1,milliseconds)
        await Delay()
        if self.observer_error:raise self.observer_error
    async def settled(self):
        w=self.window
        await self.wait(lambda:not w.pending_jobs and not w.preview_debounce.isActive() and not w.render_queued)
    def painted_after(self,start,frame=None):
        d=self.display
        return bool(d and d['receipt']>=start and (frame is None or abs(d['time']-frame/self.window.preview_fps())<1e-6) and self.painted and self.painted[0]==d['packet'] and self.painted[1]>=d['return'])
    def assert_monitor(self):
        width,height=(self.case_canvas[k] for k in ('width','height'))
        scale=1. if self.args.quality=='full' else min(1.,720/max(width,height))
        expected=tuple(max(1,round(v*scale)) for v in (width,height))
        assert self.window.quality.currentIndex()==(2 if self.args.quality=='full' else 1)
        assert tuple(self.window.viewer.packet[0])==expected==self.window.preview_size()
    async def measure(self,scenario,action,frame=None,**extra):
        self.active=scenario; began=time.monotonic()
        action(); sync_end=time.monotonic()
        expected_effect=self.window.discovery_dialog.selected_effect_id() if scenario in ('candidate_select','add_project_effect_open') else None
        expected_side='a' if scenario=='before_switch' else 'b' if scenario in ('preview_switch','candidate_select','add_project_effect_open') else None
        def correct():
            d=self.display
            if not self.painted_after(began,frame) or d['generation']!=self.window.settings_generation:return False
            if expected_side is not None and (d['side']!=expected_side or not self.window.comparison or d['owner']!=id(self.window.comparison['token'])):return False
            if expected_effect is not None and (d['effect']!=expected_effect or not self.window.discovery_session.ready):return False
            return True
        await self.wait(correct)
        end=self.painted[1]; d=self.display
        self.assert_monitor()
        record={'case':self.args.case,'quality':self.args.quality,'scenario':scenario,'n':self.sequence,'start':began,'sync_ms':(sync_end-began)*1000,'receipt_ms':(d['receipt']-began)*1000,'paint_ms':(end-began)*1000,'delivery_to_paint_ms':(end-d['receipt'])*1000,'cached':d['cached'],'frame':round(d['time']*self.window.preview_fps()),'size':self.window.viewer.packet[0],**extra}
        record['rgb_sha256']=hashlib.sha256(self.window.viewer.packet[1]).hexdigest()
        self.sequence+=1; self.records.append(record); self.emit('sample',**record)
        dump(self.folder/'samples.json',self.records)
        return record
    def reference(self,name):
        from PIL import Image
        self.assert_monitor()
        size,raw=self.window.viewer.packet
        path=self.folder/f'{name}.png'; Image.frombytes('RGB',size,raw).save(path)
        self.emit('reference',name=name,frame=self.window.timeline.value(),size=size,rgb_sha256=hashlib.sha256(raw).hexdigest(),png_sha256=digest(path))
    def clear_frames(self):
        self.window.preview_frames.clear()
        self.window.preview_frames.switch(self.window.current_preview_context())

    def show_edit_control(self):
        composer=self.window.composer;effect,path=EDIT_PATHS[self.args.case]
        if effect=='bloom':
            composer.look_tabs.setCurrentWidget(composer.effects_panel)
            editor=composer.effects_panel;editor.inspect_effect(effect);editor.reveal_control(path)
        else:
            composer.open_object_details(effect,False)
            editor=composer.object_panel if effect=='text' else composer.object_editor
            editor.reveal_control(path)
        self.edit_control=editor.controls[path]
        assert self.edit_control.input.isEnabled()

    def edit_parameter(self,value):
        self.edit_control.input.setValue(value)

    async def session(self,frames):
        w=self.window
        start=time.monotonic();iteration=0;self.emit('session_start',duration_s=self.args.session)
        while time.monotonic()-start<self.args.session:
            next_time=start+iteration*5
            if time.monotonic()<next_time:
                await self.pause(min(100,round((next_time-time.monotonic())*1000)));continue
            operation=iteration%8
            if operation in (0,3):w.timeline.setValue(frames[(iteration//8)%len(frames)])
            elif operation==1:
                self.show_edit_control();self.edit_parameter(.90+(iteration%2)*.01)
            elif operation==2:w.undo_composition()
            elif operation==4:w.open_effect_discovery('separation')
            elif operation==5 and w.discovery_session:w.discovery_dialog.switch_side('a')
            elif operation==6 and w.discovery_session:w.discovery_dialog.switch_side('b')
            elif w.discovery_session:w.discovery_dialog.reject()
            self.emit('session_action',index=iteration,operation=operation);iteration+=1
        if w.discovery_session:w.discovery_dialog.reject()
        w.auto_prepare.setChecked(False);w.cancel_preparation();await self.settled()
        await self.pause(3000);self.emit('session_end',elapsed_s=time.monotonic()-start,actions=iteration)

    def run(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        self.app=QApplication([]);self.app.setQuitOnLastWindowClosed(False)
        errors=[];coroutine=self.execute()
        # Every wait returns to the OUTER native Qt event loop. Nested loops can
        # defer Cocoa drawing transactions; QTest polling can starve the GIL.
        def advance():
            try:delay=coroutine.send(None)
            except StopIteration:self.app.quit();return
            except BaseException as exc:
                self.stop.set();errors.append(exc);self.app.quit();return
            QTimer.singleShot(delay,advance)
        QTimer.singleShot(0,advance);self.app.exec()
        if errors:raise errors[0]

    async def execute(self):
        from PySide6.QtCore import QTimer, QSettings, Qt
        from PySide6.QtWidgets import QApplication
        import synth_studio as studio
        from studio_theme import apply_theme
        manifest=json.loads((OUT/'manifest.json').read_text())
        app=self.app; apply_theme(app)
        self.instrument()
        timer=QTimer(); timer.setInterval(20); timer.timeout.connect(self.tick)
        if not self.args.quiet_observers:timer.start()
        self.monitor_thread=None
        if not self.args.quiet_observers:
            self.monitor_thread=threading.Thread(target=self.monitor,daemon=True);self.monitor_thread.start()
        self.emit('run_config',wall_time_epoch_s=time.time(),args=vars(self.args),tool_sha256=digest(Path(__file__)),pid=os.getpid(),state_dir=os.environ['NEBULA_STATE_DIR'],git_commit=command('git','-C',str(ROOT),'rev-parse','HEAD'))
        importing_video=self.args.case=='video' and (self.args.import_video or 'video' not in manifest['cases'])
        project_case='text-dye-transfer' if importing_video else self.args.case
        project=json.loads(Path(manifest['cases'][project_case]['path']).read_text())
        self.case_canvas=manifest['cases'][project_case]['canvas']
        # Settings supplies Full canvas before the constructor's first request.
        settings=QSettings(str(Path(os.environ['NEBULA_STATE_DIR'])/'settings.ini'),QSettings.Format.IniFormat)
        settings.setValue('preview/quality',2 if self.args.quality=='full' else 1)
        settings.setValue('preview/auto_prepare',False)
        construction_profile=cProfile.Profile() if self.args.profile else None
        if construction_profile:construction_profile.enable()
        began=time.monotonic(); w=studio.SynthStudio(composition=project,settings=settings); self.window=w
        w.auto_prepare.setChecked(False); w.quality.setCurrentIndex(2 if self.args.quality=='full' else 1); w.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True); w.show();w.raise_();w.activateWindow()
        if construction_profile:
            construction_profile.disable();construction_profile.dump_stats(str(self.folder/'construction.prof'))
            # Stay enabled across outer-loop turns so timer/deferred callbacks
            # (candidate compilation and delivery) are included, not just input.
            self.ui_profile=cProfile.Profile();self.ui_profile.enable()
        await self.wait(lambda:self.painted_after(began,0)); record={'case':self.args.case,'quality':self.args.quality,'scenario':'fixture_bootstrap_construct' if importing_video else 'fresh_construct_open','paint_ms':(self.painted[1]-began)*1000,'size':w.viewer.packet[0]}
        self.records.append(record);self.emit('sample',**record)
        if 'NEBULA_AUDIT_LAUNCH_MONOTONIC' in os.environ:
            record={'case':self.args.case,'quality':self.args.quality,'scenario':'fixture_bootstrap_process' if importing_video else 'fresh_process_open','paint_ms':(self.painted[1]-float(os.environ['NEBULA_AUDIT_LAUNCH_MONOTONIC']))*1000,'size':w.viewer.packet[0]}
            self.records.append(record);self.emit('sample',**record)
        await self.settled()
        if importing_video:
            import_start=time.monotonic(); w.mark_document_clean(); w.start_video_import(manifest['video']['path'])
            await self.wait(lambda:w.import_job is None and 'footage' in w.composition)
            self.emit('video_import',elapsed_s=time.monotonic()-import_start,footage=w.composition['footage'])
            await self.settled()
            doc=copy.deepcopy(w.composition); doc['effects']={'film_emulsion':{'mode':'on','params':{'film_emulsion.effect_intensity':50.0}},'bloom':{'mode':'on','params':{'bloom.strength':.3}}}
            w.composer.commit(doc,'audit-video-treatments'); await self.settled()
            path=OUT/'fixtures/video.nebula.json';dump(path,w.composition)
            seq=w.sequence;manifest['cases']['video']={'path':str(path),'sha256':digest(path),'canvas':w.composition['canvas'],'fps':seq['fps'],'duration':seq['duration'],'sections':len(w.composition['sections']),'effects':w.composition['effects'],'frames':[0,1,29,30,59,60,89],'prepare_frames':[0,1,29,30]};dump(OUT/'manifest.json',manifest)
            self.case_canvas=manifest['cases']['video']['canvas']
            assert (self.case_canvas['width'],self.case_canvas['height'])==(1920,1080)
        assert w.preview_size()==tuple(w.viewer.packet[0])
        self.reference('baseline-frame-0')
        base=copy.deepcopy(w.composition)
        frames=[int(x) for x in self.args.frames.split(',')] if self.args.frames else manifest['cases'][self.args.case]['frames']
        assert frames and all(0<=f<=w.timeline.maximum() for f in frames)
        if not self.args.scaling_only and not self.args.open_only:
            await self.measure('reopen_loaded_resources',lambda:w.set_composition(base,guard=False),0)
            await self.settled()
        if self.args.open_only:
            await self.close();return
        if self.args.prepare_only:
            await self.prepare(tuple(manifest['cases'][self.args.case]['prepare_frames']))
            await self.finish(base);return
        if self.args.drag_only:
            from PySide6.QtTest import QTest
            from PySide6.QtCore import QPoint, Qt
            from PySide6.QtWidgets import QStyle, QStyleOptionSlider
            w.composer.change_scope(0)
            panel=w.composer.effects_panel;w.composer.look_tabs.setCurrentWidget(panel)
            panel.inspect_effect('bloom');panel.reveal_control('bloom.strength')
            control=panel.controls['bloom.strength'];slider=control.slider
            await self.pause(30)
            assert slider.isVisible() and not slider.hasTracking()
            for i in range(self.args.samples):
                option=QStyleOptionSlider();slider.initStyleOption(option)
                handle=slider.style().subControlRect(QStyle.ComplexControl.CC_Slider,option,QStyle.SubControl.SC_SliderHandle,slider)
                pos=handle.center();pressed=time.monotonic();generation=w.settings_generation
                QTest.mousePress(slider,Qt.MouseButton.LeftButton,pos=pos);moves=[]
                target=round(slider.width()*(.15 if i%2 else .18))
                for step in range(1,9):
                    QTest.mouseMove(slider,QPoint(round(pos.x()+(target-pos.x())*step/8),pos.y()),15)
                    moves.append(time.monotonic())
                assert w.settings_generation==generation
                await self.measure('physical_slider_release',lambda:QTest.mouseRelease(slider,Qt.MouseButton.LeftButton,pos=QPoint(target,pos.y())),press_time=pressed,move_times=moves,slider_target_x=target)
            await self.finish(base);return
        if self.args.session_only:
            w.auto_prepare.setChecked(True)
            await self.session(frames)
            await self.finish(base)
            return
        for i in range(0 if self.args.scaling_only else self.args.samples):
            frame=frames[i%len(frames)] if i%4<2 else frames[-(i%len(frames))-1]
            def navigate():
                if w.timeline.value()==frame:w.request_frame()
                else:w.timeline.setValue(frame)
            await self.measure('scrub_navigation',navigate,frame)
        for i in range(self.args.samples):
            frame=frames[i%len(frames)]
            def seek():
                self.clear_frames()
                if w.timeline.value()==frame:w.request_frame()
                else:w.timeline.setValue(frame)
            await self.measure('scrub_uncached',seek,frame)
            if frame not in self.saved_frames:
                self.reference(f'frame-{frame}');self.saved_frames.add(frame)
            await self.measure('scrub_cached',w.request_frame,frame)
        if self.args.scaling_only:
            await self.finish(base)
            return
        # Actual editor callbacks retain all normal compilation/history/UI work.
        w.timeline.setValue(0); await self.settled()
        for scope in (1,0):
            if not scope:
                w.set_composition(base,guard=False);await self.settled()
            w.composer.change_scope(scope);self.show_edit_control()
            await self.pause(30)
            for i in range(self.args.samples):
                await self.measure('clip_parameter' if scope else 'project_parameter',lambda i=i:self.edit_parameter(.90+(i%2)*.01))
        for i in range(self.args.samples):
            from PySide6.QtCore import QTimer
            # 8 committed slider values 15ms apart; physical drag only commits on release.
            times=[]; final={}
            for j in range(8):
                def edit(j=j):
                    times.append(time.monotonic()); self.edit_parameter(.90+j*.01+(i%2)*.01)
                    if j==7:final['time']=times[-1]
                QTimer.singleShot(j*15,edit)
            await self.wait(lambda:'time' in final)
            await self.wait(lambda:self.painted_after(final['time']))
            await self.settled()
            record={'case':self.args.case,'quality':self.args.quality,'scenario':'rapid_committed_slider','paint_ms':(self.painted[1]-final['time'])*1000,'n':i,'input_times':times,'first_input_to_paint_ms':(self.painted[1]-times[0])*1000,'rgb_sha256':hashlib.sha256(w.viewer.packet[1]).hexdigest(),'actual_input_offsets_ms':[(t-times[0])*1000 for t in times]}
            self.records.append(record); self.emit('sample',**record)
        w.set_composition(base,guard=False); await self.settled(); w.composer.change_scope(0)
        w.composer.look_tabs.setCurrentWidget(w.composer.effects_panel);await self.pause(30)
        # Unlocked browser is the same Add Project Effect path as the UI button.
        from PySide6.QtCore import Qt
        def candidate(identifier):
            d=w.discovery_dialog
            for row in range(d.table.rowCount()):
                if d.table.item(row,0).data(Qt.ItemDataRole.UserRole)==identifier:
                    d.table.selectRow(row); return
            raise ValueError('candidate absent: '+identifier)
        def open_candidate():
            w.open_effect_discovery(); candidate('separation')
        await self.measure('add_project_effect_open',open_candidate)
        d=w.discovery_dialog
        identifiers=[d.table.item(row,0).data(Qt.ItemDataRole.UserRole) for row in range(d.table.rowCount())]
        candidates=[x for x in ('raster','separation','tape','bloom') if x in identifiers and x not in d.applied_ids]
        if len(candidates)<2:raise ValueError(('need 2 candidates',candidates))
        for i in range(self.args.samples):
            await self.measure('candidate_select',lambda i=i:candidate(candidates[i%2]))
            await self.measure('before_switch',lambda:d.switch_side('a'))
            await self.measure('preview_switch',lambda:d.switch_side('b'))
        assert w.preview_size()==tuple(w.viewer.packet[0])
        self.reference('candidate');d.reject();await self.settled()
        fixed=tuple(manifest['cases'][self.args.case]['prepare_frames'])
        await self.prepare(fixed)
        await self.finish(base)

    async def prepare(self,fixed):
        w=self.window
        # Fixed absolute frame list, normal 4-frame batching and reservations.
        for explicit in (() if self.args.no_prepare else (False,True)):
            w.cancel_preparation();self.clear_frames();start=time.monotonic()
            w.preparation_target=fixed;w.preparation_explicit=explicit;w._start_warm_batch()
            await self.wait(lambda:all(f in w.preview_frames.items for f in fixed) and w.warming_job is None)
            self.emit('preparation',mode='explicit' if explicit else 'automatic',frames=fixed,elapsed_s=time.monotonic()-start,bytes=w.preview_frames.bytes,reserved=w.preview_frames.reserved)
            w.cancel_preparation()
        # Public scheduling entry points, separately from controlled fixed-list batch.
        for explicit in (() if self.args.survey or self.args.no_prepare else (False,True)):
            self.clear_frames();start=time.monotonic()
            w.auto_prepare.setChecked(not explicit)
            if explicit:w.prepare_playback()
            else:w.schedule_auto_preparation()
            await self.wait(lambda:bool(w.preparation_target))
            target=w.preparation_target
            await self.wait(lambda:all(f in w.preview_frames.items for f in target) and w.warming_job is None)
            self.emit('public_preparation',mode='explicit' if explicit else 'automatic',frames=target,elapsed_s=time.monotonic()-start)
            w.auto_prepare.setChecked(False);w.cancel_preparation()

    async def finish(self,base):
        w=self.window
        from PySide6.QtWidgets import QApplication
        if w.composition != base:
            w.set_composition(base,guard=False);await self.settled()
        await self.measure('restore_reference',lambda:(w.timeline.setValue(0),w.request_frame()),0);self.reference('repeat-frame-0')
        await self.close()

    async def close(self):
        w=self.window
        from PySide6.QtWidgets import QApplication
        await self.settled(); w.viewer.grab().save(str(self.folder/'native-viewer.png'))
        dump(self.folder/'samples.json',self.records)
        if self.ui_profile:
            self.ui_profile.disable();self.ui_profile.dump_stats(str(self.folder/'ui-event-loop.prof'))
        self.stop.set();w.mark_document_clean();w.close();w.jobs.waitForDone(30000)
        if self.monitor_thread:self.monitor_thread.join(3)
        self.emit('done',pid=os.getpid(),platform=QApplication.instance().platformName());self.log.close()
        print(self.args.label,'DONE',len(self.records),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--import-video',action='store_true');p.add_argument('--open-only',action='store_true');p.add_argument('--frames',help='comma-separated absolute frame subset');p.add_argument('--prepare-only',action='store_true');p.add_argument('--drag-only',action='store_true');p.add_argument('--quiet-observers',action='store_true');p.add_argument('--scaling-only',action='store_true');p.add_argument('--session-only',action='store_true');p.add_argument('--no-prepare',action='store_true');p.add_argument('--survey',action='store_true');p.add_argument('--freeze',action='store_true');p.add_argument('--case',choices=CASES,default='guerrilla');p.add_argument('--quality',choices=('full','720'),default='full');p.add_argument('--samples',type=int,default=20);p.add_argument('--label',default='trial');p.add_argument('--profile',action='store_true');p.add_argument('--detail',action='store_true');p.add_argument('--session',type=int,default=0)
    args=p.parse_args()
    if args.samples < 0 or args.session < 0:p.error('samples and session must be nonnegative')
    if Path(args.label).name != args.label or args.label in ('.','..'):p.error('label must be a single directory name')
    if args.session_only and args.session <= 0:p.error('session-only requires --session seconds')
    if not args.freeze and 'NEBULA_AUDIT_LAUNCH_MONOTONIC' not in os.environ:
        environment=dict(os.environ,NEBULA_AUDIT_LAUNCH_MONOTONIC=str(time.monotonic()))
        raise SystemExit(subprocess.run([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]],env=environment).returncode)
    OUT.mkdir(parents=True,exist_ok=True)
    os.environ['NEBULA_STATE_DIR']=str(OUT/'state'/args.label)
    Path(os.environ['NEBULA_STATE_DIR']).mkdir(parents=True,exist_ok=True)
    if args.freeze:freeze()
    else:Audit(args).run()
if __name__=='__main__':main()
