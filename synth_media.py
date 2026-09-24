"""Atomic FFmpeg export for source-free synth presets."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from media import Cancellation, Cancelled
from synth import normalize_synth, render_synth_frame


def export_synth_video(preset, output, start=0, count=None, cancel=None, progress=None, size=None):
    """Render a deterministic synth loop to MP4.

    ``time_seconds`` is derived from the export FPS, while all stochastic
    treatment state is derived from that time and ``treatment_fps``. Changing
    export FPS therefore changes cadence without changing the animation clock.
    """
    p = normalize_synth(preset)
    cancel = cancel or Cancellation()
    output = Path(output)
    width, height = size or (p["width"], p["height"])
    export_fps = int(p["export_fps"])
    total = max(1, round(float(p["loop_seconds"]) * export_fps))
    start = int(start)
    count = total - start if count is None else int(count)
    if start < 0 or count < 1 or start + count > total:
        raise ValueError("Empty or out-of-range synth export")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".nebula-synth-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    temp = Path(name)
    proc = None
    try:
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "rawvideo",
                 "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(export_fps),
                 "-i", "pipe:0", "-an", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                 "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", str(temp)], stdin=subprocess.PIPE, stderr=errors)
            cancel.attach(proc)
            for index in range(start, start + count):
                cancel.check()
                time_seconds = index / export_fps
                treatment_frame = round(time_seconds * p["treatment_fps"])
                image = render_synth_frame(p, frame=treatment_frame, time_seconds=time_seconds, size=(width, height))
                proc.stdin.write(image.tobytes())
                if progress:
                    progress(index - start + 1, count)
            proc.stdin.close()
            code = proc.wait()
            cancel.check()
            if code:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors="replace")[-2000:] or "FFmpeg could not encode synth")
        os.replace(temp, output)
        return output
    except (BrokenPipeError, Cancelled):
        cancel.check()
        raise ValueError("Synth export cancelled") from None
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
