"""Bounded, interactive audio monitoring; no full-track regeneration on knob edits.

Only the layered instrument opts into this monitor. Its fixed settings share the
export DSP. Live changes crossfade voices over 40 ms; saved exports still render
one deterministic configuration from the start of the timeline.
"""
import copy
import threading
import time
from collections import deque

import numpy as np
from PySide6.QtCore import QObject, QTimer, QThread, QMetaObject, Qt, Signal, Slot

from synth_visual_sound import RATE
from synth_visual_sound_instrument import InstrumentVoice

BLOCK = 480
QUEUED_BLOCKS = 6  # 60 ms of synthesis ahead of the device absorbs visual/UI peaks.
FADE = round(.040 * RATE)


class LiveInstrument:
    def __init__(self, sequence, signals, config, start=0):
        self.sequence=sequence;self.signals=signals;self.position=start
        self.voice=self.make_voice(config);self.old=None;self.fade=0;self.pending=None
        self.start_fade=0 if start else FADE

    def make_voice(self, config, warm=True):
        voice=InstrumentVoice(self.sequence,copy.deepcopy(config),self.signals)
        # Reconstruct a short filter history after a seek or a parameter change.
        history=min(self.position,round(RATE*.08)) if warm else 0
        if history: voice.render(self.position-history,history)
        return voice

    def update(self, config, signals=None, sequence=None):
        if signals is not None:
            self.signals=signals
            self.sequence=sequence or self.sequence
        self.pending=copy.deepcopy(config)

    def render(self, length=BLOCK):
        if self.old is None and self.pending is not None:
            config,self.pending=self.pending,None
            if config != self.voice.config or self.signals is not self.voice.signals:
                self.old=self.voice;self.voice=self.make_voice(config,warm=False)
                self.voice.states=list(self.old.states);self.fade=0
                for key, channel in self.voice.mixer.items():
                    channel.inherit(self.old.mixer[key])
        tones={} if self.old is not None else None
        output=self.voice.render(self.position,length,tone_cache=tones)
        if self.old is not None:
            old=self.old.render(self.position,length,tone_cache=tones)
            blend=np.clip((self.fade+np.arange(length))/FADE,0,1)
            blend=blend*blend*(3-2*blend)
            output=old*(1-blend[:,None])+output*blend[:,None]
            self.fade+=length
            if self.fade>=FADE: self.old=None
        if self.start_fade<FADE:
            blend=np.clip((self.start_fade+np.arange(length))/FADE,0,1)
            output*= (blend*blend*(3-2*blend))[:,None]
            self.start_fade+=length
        self.position+=length
        return output.astype('<f4')


class AudioProducer:
    """One worker, six 10-ms packets, one latest configuration; never Qt work."""
    def __init__(self, error):
        self.condition=threading.Condition();self.queue=deque();self.command=None
        self.epoch=0;self.closed=False;self.error=error
        self.thread=threading.Thread(target=self.run,name='Nebula live synth',daemon=True)
        self.thread.start()

    def start(self,sequence,signals,config,seconds):
        with self.condition:
            self.epoch+=1;self.queue.clear()
            self.command=(sequence,signals,copy.deepcopy(config),round(seconds*RATE))
            self.condition.notify_all()

    def update(self,config):
        with self.condition:
            if self.command:
                seq,signals,_,start=self.command
                self.command=(seq,signals,copy.deepcopy(config),start)
            self.condition.notify_all()

    def update_source(self, sequence, signals, config):
        with self.condition:
            if self.command:
                self.command=(sequence,signals,copy.deepcopy(config),self.command[3])
            self.condition.notify_all()

    def stop(self):
        with self.condition:
            self.epoch+=1;self.command=None;self.queue.clear();self.condition.notify_all()

    def pop(self):
        with self.condition:
            value=self.queue.popleft() if self.queue else None
            self.condition.notify_all()
            return value

    def run(self):
        epoch=-1;engine=None;previous=None;previous_signals=None
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.closed or (self.command is not None and len(self.queue)<QUEUED_BLOCKS))
                if self.closed: return
                command=self.command;current_epoch=self.epoch
            seq,signals,config,start=command
            try:
                if current_epoch!=epoch:
                    engine=LiveInstrument(seq,signals,config,start);epoch=current_epoch;previous=config;previous_signals=signals
                elif config!=previous or signals is not previous_signals:
                    engine.update(config, signals, seq);previous=config;previous_signals=signals
                packet=engine.render().tobytes()
            except Exception as exc:
                with self.condition:
                    valid=current_epoch==self.epoch
                    if valid: self.command=None;self.queue.clear()
                if valid: self.error(current_epoch,str(exc))
                continue
            with self.condition:
                if current_epoch==self.epoch and self.command is not None: self.queue.append(packet)

    def close(self):
        with self.condition:
            self.closed=True;self.command=None;self.queue.clear();self.condition.notify_all()
        self.thread.join(timeout=2)


class QtLiveOutput:
    def __init__(self,parent):
        from PySide6.QtMultimedia import QAudioFormat,QAudioSink,QMediaDevices
        device=QMediaDevices.defaultAudioOutput()
        if device.isNull(): raise RuntimeError('Connect an audio output device to listen live.')
        fmt=QAudioFormat();fmt.setSampleRate(RATE);fmt.setChannelCount(2);fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
        if not device.isFormatSupported(fmt): raise RuntimeError('This audio device does not support 48 kHz stereo live monitoring. Choose another output or use Apply & prepare.')
        self.sink=QAudioSink(device,fmt,parent);self.sink.setBufferSize(round(RATE*.04)*8);self.io=None

    def start(self):
        self.sink.reset();self.io=self.sink.start()
        if self.io is None: raise RuntimeError('The audio output could not start.')

    def write(self,packet):
        if self.io is None: return 0
        from PySide6.QtMultimedia import QAudio
        if self.sink.error().value not in (QAudio.Error.NoError.value,QAudio.Error.UnderrunError.value):
            raise RuntimeError('Live audio output stopped. Check the output device and reopen the sound panel.')
        capacity=self.sink.bytesFree()//8*8
        return self.io.write(packet[:capacity]) if capacity else 0

    def volume(self,value): self.sink.setVolume(value)
    def stop(self): self.sink.reset();self.io=None
    def close(self): self.stop();self.sink.deleteLater()


class AudioOutputWorker(QObject):
    """Own the device and its pump on an event loop independent of the GUI."""
    ready=Signal(int,float,float)
    failed=Signal(int,str)

    def __init__(self,producer,factory,clock):
        super().__init__();self.producer=producer;self.factory=factory;self.clock=clock
        self.backend=None;self.pending=b'';self.playing=False;self.epoch=0
        self.level=.7;self.muted=False
        self.timer=QTimer(self);self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(5);self.timer.timeout.connect(self.pump)

    @Slot(object)
    def start(self,request):
        epoch,sequence,signals,config,seconds,requested=request
        self.stop();self.epoch=epoch
        try:
            if self.backend is None: self.backend=self.factory(self)
            self.backend.start();self.backend.volume(0. if self.muted else self.level)
            ready=self.clock();target=max(0.,seconds+ready-requested)
            self.producer.start(sequence,signals,config,target)
            self.playing=True;self.timer.start();self.ready.emit(epoch,target,ready)
        except Exception as exc: self.fail(str(exc))

    @Slot(object)
    def configure(self,config): self.producer.update(config)

    @Slot(int,str)
    def producer_failed(self,epoch,message):
        # A queued failure from before a seek/pause cannot stop the new stream.
        if self.playing and epoch==self.producer.epoch: self.fail(message)

    @Slot(float,bool)
    def monitor(self,level,muted):
        self.level=level;self.muted=muted
        try:
            if self.backend: self.backend.volume(0. if muted else level)
        except Exception as exc: self.fail(str(exc))

    @Slot()
    def pump(self):
        if not self.playing or not self.backend: return
        try:
            for _ in range(4):
                if not self.pending: self.pending=self.producer.pop() or b''
                if not self.pending: break
                written=self.backend.write(self.pending)
                if written<0: raise RuntimeError('The audio output could not accept live sound.')
                self.pending=self.pending[written:]
                if self.pending: break
        except Exception as exc: self.fail(str(exc))

    @Slot()
    def stop(self):
        self.timer.stop();self.producer.stop();self.pending=b'';self.playing=False
        if self.backend: self.backend.stop()

    def fail(self,message):
        self.stop();self.failed.emit(self.epoch,message)

    @Slot()
    def shutdown(self):
        self.stop()
        if self.backend: self.backend.close();self.backend=None


class LiveSoundMonitor(QObject):
    statusChanged=Signal(str)
    failed=Signal(str)
    startRequested=Signal(object)
    stopRequested=Signal()
    configRequested=Signal(object)
    monitorRequested=Signal(float,bool)
    producerFailed=Signal(int,str)

    def __init__(self,parent=None,*,backend_factory=QtLiveOutput,clock=time.monotonic):
        super().__init__(parent);self.clock=clock
        self.producer=AudioProducer(self.producerFailed.emit);self.failed.connect(self.fail)
        self.sequence=None;self.signals=None;self.config=None;self.playing=False;self.closed=False;self.unavailable=False
        self.level=.7;self.muted=False;self.anchor=0.;self.seconds=0.;self.epoch=0
        self.output_thread=QThread(self);self.output_thread.setObjectName('Nebula live audio output')
        if hasattr(QThread,'QualityOfService'):
            self.output_thread.setServiceLevel(QThread.QualityOfService.High)
        self.output=AudioOutputWorker(self.producer,backend_factory,clock)
        self.output.moveToThread(self.output_thread)
        self.output_thread.finished.connect(self.output.deleteLater)
        self.startRequested.connect(self.output.start)
        self.stopRequested.connect(self.output.stop)
        self.configRequested.connect(self.output.configure)
        self.monitorRequested.connect(self.output.monitor)
        self.producerFailed.connect(self.output.producer_failed)
        self.output.ready.connect(self.output_ready)
        self.output.failed.connect(self.output_failed)
        self.output_thread.start(QThread.Priority.HighPriority)

    @property
    def backend(self): return self.output.backend

    def set_source(self,sequence,signals,config):
        self.stop();self.unavailable=False;self.sequence=sequence;self.signals=signals;self.config=copy.deepcopy(config)

    def update_source(self,sequence,signals,config):
        # Producer uses immutable snapshots; updating does not reset sink or clock.
        self.sequence=sequence;self.signals=signals;self.config=copy.deepcopy(config)
        if not self.closed: self.producer.update_source(sequence,signals,config)

    def set_config(self,config):
        self.config=copy.deepcopy(config)
        if not self.closed: self.configRequested.emit(self.config)

    def set_monitor(self,level,muted):
        self.level=level;self.muted=muted
        if not self.closed: self.monitorRequested.emit(level,muted)

    def sync(self,seconds,playing,force=False):
        if self.closed or self.unavailable or self.sequence is None: return
        if not playing:
            if self.playing: self.stop()
            return
        now=self.clock()
        expected=self.seconds+(now-self.anchor if self.playing else 0.)
        # Repeated UI refreshes with force=True must not restart the audio stream.
        if not self.playing or abs(seconds-expected)>.12:
            self.epoch+=1;self.seconds=max(0.,seconds);self.anchor=now;self.playing=True
            self.startRequested.emit((self.epoch,self.sequence,self.signals,self.config,self.seconds,now))

    @Slot(int,float,float)
    def output_ready(self,epoch,seconds,anchor):
        if epoch!=self.epoch or not self.playing or self.closed: return
        self.seconds=seconds;self.anchor=anchor
        self.statusChanged.emit('Live · turn the knobs while the video plays. Apply saves the sound.')

    @Slot(int,str)
    def output_failed(self,epoch,message):
        if epoch==self.epoch and not self.closed: self.fail(message)

    def stop(self):
        self.epoch+=1;self.playing=False
        if not self.closed: self.stopRequested.emit()

    def fail(self,message):
        self.unavailable=True;self.stop();self.statusChanged.emit('Live sound: '+message)

    def close(self):
        if self.closed: return
        self.stop();self.closed=True
        # Close every Qt audio object on its owner thread before joining it.
        QMetaObject.invokeMethod(self.output,'shutdown',Qt.ConnectionType.BlockingQueuedConnection)
        self.output_thread.quit();self.output_thread.wait()
        self.producer.close()
