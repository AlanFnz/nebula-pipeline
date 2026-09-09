"""FFmpeg decoding and atomic export, shared by preview jobs and tests."""
import json
import math
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from PIL import Image

from engine import render_frame
from parameters import normalize


class Cancelled(Exception):
    pass


class Cancellation:
    def __init__(self):
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.processes = set()

    def check(self):
        if self.event.is_set():
            raise Cancelled()

    def attach(self, process):
        with self.lock:
            self.processes.add(process)
            if self.event.is_set() and process.poll() is None:
                process.terminate()

    def detach(self, process):
        with self.lock:
            self.processes.discard(process)

    def cancel(self):
        self.event.set()
        with self.lock:
            for process in self.processes:
                if process.poll() is None:
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
         "-show_format", "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Cannot read this clip")
    data = json.loads(result.stdout)
    if not data.get("streams"):
        raise ValueError("No video stream found")
    stream = data["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    rotation = next((s.get("rotation", 0) for s in stream.get("side_data_list", [])
                     if "rotation" in s), float(stream.get("tags", {}).get("rotate", 0)))
    if round(rotation) % 180:
        width, height = height, width
    duration = float(stream.get("duration") or data.get("format", {}).get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("This first version needs a clip with a known duration")
    return dict(path=str(Path(path).resolve()), width=width, height=height, duration=duration)


def dimensions(info, edge=None):
    scale = min(1, edge / max(info["width"], info["height"])) if edge else 1
    return max(1, round(info["width"] * scale)), max(1, round(info["height"] * scale))


def frame_count(info, fps):
    # FFmpeg fps filter rounds the final timestamp to the output time base.
    return max(1, math.floor(info["duration"] * fps + 0.5))


def decode_frames(info, fps, start, count, edge=None, cancel=None):
    """Always use the same fps filter and absolute frame grid as legacy export.

    Decode from the beginning for exact seeking, including variable-rate clips.
    This trades late-clip seek speed for reliable frame identity.
    """
    cancel = cancel or Cancellation()
    cancel.check()
    w, h = dimensions(info, edge)
    vf = f"fps={fps},select=gte(n\\,{start})"
    if edge:
        vf += f",scale={w}:{h}:flags=lanczos"
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-nostdin", "-i", info["path"],
             "-map", "0:v:0", "-vf", vf, "-frames:v", str(count),
             "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            stdout=subprocess.PIPE, stderr=errors)
        cancel.attach(proc)
        try:
            for index in range(start, start + count):
                cancel.check()
                raw = proc.stdout.read(w * h * 3)
                cancel.check()
                if not raw:
                    break
                if len(raw) != w * h * 3:
                    raise ValueError("FFmpeg returned an incomplete frame")
                yield index, Image.frombytes("RGB", (w, h), raw)
            proc.stdout.close()
            code = proc.wait()
            cancel.check()
            if code:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors="replace")[-2000:])
        finally:
            if proc.poll() is None:
                proc.terminate()
            proc.stdout.close()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            cancel.detach(proc)


def export_video(info, params, output, start=0, count=None, cancel=None, progress=None):
    """Render full-size frames into MP4; only replace destination on success.

    Audio is intentionally omitted. Frame indices remain absolute for a range
    export, so loop exports have exactly the preview's temporal realization.
    """
    p = normalize(params)
    cancel = cancel or Cancellation()
    output = Path(output)
    if output.resolve() == Path(info["path"]).resolve():
        raise ValueError("Choose an output different from the source clip")
    count = count or frame_count(info, p["fps"]) - start
    if start < 0 or count < 1:
        raise ValueError("Empty export range")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".nebula-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    temp = Path(name)
    proc = None
    try:
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "rawvideo",
                 "-pix_fmt", "rgb24", "-s", f'{info["width"]}x{info["height"]}',
                 "-r", str(p["fps"]), "-i", "pipe:0", "-an",
                 "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264",
                 "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temp)],
                stdin=subprocess.PIPE, stderr=errors)
            cancel.attach(proc)
            rendered = 0
            for index, source in decode_frames(info, p["fps"], start, count, cancel=cancel):
                image = render_frame(source, p, index)
                cancel.check()
                proc.stdin.write(image.tobytes())
                rendered += 1
                if progress:
                    progress(rendered, count)
            proc.stdin.close()
            code = proc.wait()
            cancel.check()
            if code or not rendered:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors="replace")[-2000:] or "No frames exported")
        os.replace(temp, output)
        return output
    except BrokenPipeError:
        cancel.check()
        raise ValueError("FFmpeg could not encode this clip") from None
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if proc.stdin and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except BrokenPipeError:
                    pass
            cancel.detach(proc)
        temp.unlink(missing_ok=True)
