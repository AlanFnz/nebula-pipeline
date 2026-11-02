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
from PySide6.QtCore import QObject, QTimer, Signal

from synth_visual_sound import RATE
from synth_visual_sound_instrument import InstrumentVoice

BLOCK = 480
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

    def update(self, config):
        self.pending=copy.deepcopy(config)

    def render(self, length=BLOCK):
        if self.old is None and self.pending is not None:
            config,self.pending=self.pending,None
            if config != self.voice.config:
                self.old=self.voice;self.voice=self.make_voice(config,warm=False)
                self.voice.states=list(self.old.states);self.fade=0
        output=self.voice.render(self.position,length)
        if self.old is not None:
            old=self.old.render(self.position,length)
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
    """One worker, four 10-ms packets, one latest configuration; never Qt work."""
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

    def stop(self):
        with self.condition:
            self.epoch+=1;self.command=None;self.queue.clear();self.condition.notify_all()

    def pop(self):
        with self.condition:
            value=self.queue.popleft() if self.queue else None
            self.condition.notify_all()
            return value

    def run(self):
        epoch=-1;engine=None;previous=None
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.closed or (self.command is not None and len(self.queue)<4))
                if self.closed: return
                command=self.command;current_epoch=self.epoch
            seq,signals,config,start=command
            try:
                if current_epoch!=epoch:
                    engine=LiveInstrument(seq,signals,config,start);epoch=current_epoch;previous=config
                elif config!=previous:
                    engine.update(config);previous=config
                packet=engine.render().tobytes()
            except Exception as exc:
                with self.condition:
                    valid=current_epoch==self.epoch
                    if valid: self.command=None;self.queue.clear()
                if valid: self.error(str(exc))
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


class LiveSoundMonitor(QObject):
    statusChanged=Signal(str)
    failed=Signal(str)

    def __init__(self,parent=None,*,backend_factory=QtLiveOutput,clock=time.monotonic):
        super().__init__(parent);self.factory=backend_factory;self.clock=clock
        self.backend=None;self.producer=AudioProducer(self.failed.emit);self.failed.connect(self.fail)
        self.sequence=None;self.signals=None;self.config=None;self.playing=False;self.closed=False;self.unavailable=False
        self.level=.7;self.muted=False;self.pending=b'';self.anchor=0.;self.seconds=0.
        self.timer=QTimer(self);self.timer.setInterval(5);self.timer.timeout.connect(self.pump)

    def set_source(self,sequence,signals,config):
        self.stop();self.unavailable=False;self.sequence=sequence;self.signals=signals;self.config=copy.deepcopy(config)

    def set_config(self,config):
        self.config=copy.deepcopy(config);self.producer.update(config)

    def set_monitor(self,level,muted):
        self.level=level;self.muted=muted
        if self.backend: self.backend.volume(0. if muted else level)

    def sync(self,seconds,playing,force=False):
        if self.closed or self.unavailable or self.sequence is None: return
        if not playing:
            self.stop();return
        now=self.clock()
        expected=self.seconds+(now-self.anchor if self.playing else 0.)
        # Repeated UI refreshes with force=True must not restart the audio stream.
        if not self.playing or abs(seconds-expected)>.12:
            try:
                if self.backend is None: self.backend=self.factory(self)
                self.backend.start();self.backend.volume(0. if self.muted else self.level)
                # Device initialization can take time on first use; start at the
                # video's current time rather than retaining that startup lag.
                ready=self.clock();target=max(0.,seconds+ready-now)
                self.pending=b'';self.producer.start(self.sequence,self.signals,self.config,target)
                self.seconds=target;self.anchor=ready;self.playing=True;self.timer.start()
                self.statusChanged.emit('Live · turn the knobs while the video plays. Apply saves the sound.')
            except Exception as exc: self.fail(str(exc))

    def pump(self):
        if not self.playing or not self.backend: return
        try:
            # Never synthesize on the GUI thread or buffer a whole soundtrack.
            for _ in range(4):
                if not self.pending: self.pending=self.producer.pop() or b''
                if not self.pending: break
                written=self.backend.write(self.pending)
                if written<0: raise RuntimeError('The audio output could not accept live sound.')
                self.pending=self.pending[written:]
                if self.pending: break
        except Exception as exc: self.fail(str(exc))

    def stop(self):
        self.timer.stop();self.producer.stop();self.pending=b'';self.playing=False
        if self.backend: self.backend.stop()

    def fail(self,message):
        self.unavailable=True;self.stop();self.statusChanged.emit('Live sound: '+message)

    def close(self):
        if self.closed: return
        self.closed=True;self.stop();self.producer.close()
        if self.backend: self.backend.close();self.backend=None
