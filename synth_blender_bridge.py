"""A lazy, serialized Blender worker and atomic, content-addressed frame cache.

No Blender dependency is loaded or process launched until a Blender source is
actually rendered. Every cache key includes the builder, executable identity,
physical settings, pose and exact output resolution. Image treatments are not
part of this cache, so their edits never invalidate the clean 3D render.
"""
from __future__ import annotations
import atexit
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import threading
import time
import uuid

from PIL import Image

SCRIPT = Path(__file__).parent/'assets/blender/scene_worker.py'
CACHE = Path.home()/'Library/Caches/Nebula Studio/blender-v1'
PREFIX = b'NEBULA_FRAME '


def blender_executable():
    custom = os.environ.get('NEBULA_BLENDER')
    candidates = ([custom] if custom else []) + [
        '/Applications/Blender.app/Contents/MacOS/Blender',
        str(Path.home()/'Applications/Blender.app/Contents/MacOS/Blender'),
        shutil.which('blender')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate,os.X_OK):
            return Path(candidate).resolve()
    raise ValueError('This object needs Blender 4.2 or newer. Install Blender in Applications, then prepare the preview again. Existing Nebula studies do not require Blender.')


def cache_key(params, angle, size, executable):
    stat = executable.stat()
    payload = dict(params=params, angle=angle, size=list(size),
                   executable=[str(executable),stat.st_size,stat.st_mtime_ns],
                   builder=hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
    return hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()


class BlenderWorker:
    def __init__(self):
        self.process = None
        self.executable = None
        self.buffer = b''
        self.logs = deque(maxlen=12)
        self.lock = threading.RLock()

    def close(self):
        process, self.process = self.process, None
        if process:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
            if process.stdin: process.stdin.close()
            if process.stdout: process.stdout.close()
        self.buffer = b''

    def receive(self, timeout=180):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            while b'\n' in self.buffer:
                line,self.buffer = self.buffer.split(b'\n',1)
                if line.startswith(PREFIX): return json.loads(line[len(PREFIX):])
                self.logs.append(line.decode(errors='replace'))
            if self.process.poll() is not None:
                raise RuntimeError('Blender stopped while preparing a frame. '+ ' '.join(self.logs)[-1200:])
            ready,_,_ = select.select([self.process.stdout],[],[],min(.5,max(0,deadline-time.monotonic())))
            if ready:
                data = os.read(self.process.stdout.fileno(),65536)
                if data: self.buffer += data
        raise RuntimeError('Blender took too long to prepare this frame. Try a smaller preview resolution.')

    def request(self, payload, executable):
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None or self.executable != executable:
                    self.close(); self.logs.clear(); self.executable = executable
                    self.process = subprocess.Popen([str(executable),'--background','--factory-startup',
                        '--disable-autoexec','--python',str(SCRIPT)],stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
                    response = self.receive()
                    if not response.get('ready'): raise RuntimeError('Blender did not initialize its scene worker.')
                    version = tuple(int(n) for n in response['version'].split('.')[:2])
                    if version < (4,2): raise RuntimeError('This scene needs Blender 4.2 or newer. Update Blender in Applications.')
                self.process.stdin.write(json.dumps(payload,allow_nan=False).encode()+b'\n')
                self.process.stdin.flush()
                response = self.receive()
                if not response.get('ok'): raise RuntimeError('Blender: '+response.get('error','render failed'))
                return response
            except Exception:
                self.close()
                raise


worker = BlenderWorker()
atexit.register(worker.close)


def _read(path, size):
    try:
        with Image.open(path) as image:
            if image.size != tuple(size): return None
            return image.convert('RGB')
    except (OSError, ValueError): return None


def trim_cache(folder=CACHE, limit=3*1024**3):
    files = []
    for path in folder.glob('*.png'):
        try:
            stat=path.stat()
            if '.part.' not in path.name: files.append((stat.st_mtime,stat.st_size,path))
        except FileNotFoundError: pass
    files.sort(reverse=True)
    total = 0
    for _,size,path in files:
        total += size
        if total > limit:
            try: path.unlink()
            except FileNotFoundError: pass


def render_frame(params, angle, size):
    executable = blender_executable()
    key = cache_key(params,angle,size,executable)
    CACHE.mkdir(parents=True,exist_ok=True)
    target = CACHE/(key+'.png')
    cached = _read(target,size)
    if cached is not None: return cached
    with worker.lock:
        cached = _read(target,size)
        if cached is not None: return cached
        temporary = CACHE/(key+'-'+uuid.uuid4().hex+'.part.png')
        try:
            worker.request(dict(params=params,angle=angle,size=list(size),output=str(temporary)),executable)
            image = _read(temporary,size)
            if image is None: raise RuntimeError('Blender did not produce a complete frame at the selected resolution.')
            os.replace(temporary,target)
            if int(key[:2],16) < 4: trim_cache()
            return image
        finally:
            temporary.unlink(missing_ok=True)
