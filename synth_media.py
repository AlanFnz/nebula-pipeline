"""Atomic FFmpeg export for source-free synth presets."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from media import Cancellation, Cancelled
from synth import normalize_synth, render_synth_frame


def export_synth_video(preset, output, start=0, count=None, cancel=None, progress=None, size=None, sequence=None):
    """Render a deterministic synth loop to MP4.

    ``time_seconds`` is derived from the export FPS, while all stochastic
    treatment state is derived from that time and ``treatment_fps``. Changing
    export FPS therefore changes cadence without changing the animation clock.
    """
    p = normalize_synth(preset)
    sequence_renderer = None
    sequence_data = None
    if sequence is not None:
        from synth_sequence import normalize_sequence, render_sequence_frame
        sequence_data = normalize_sequence(sequence)
        sequence_renderer = render_sequence_frame
    cancel = cancel or Cancellation()
    output = Path(output)
    footage = sequence_data.get('footage') if sequence_data else None
    provider = None
    if footage:
        from synth_video import VideoFrameProvider, check_source
        from synth_section_sources import footage_references, rendered_footage
        # Protect every authored asset, even when all sections override the
        # shared source. Validate only footage actually used by the export.
        for source in footage_references(sequence_data):
            source_path = Path(source['path'])
            if output.resolve() == source_path.resolve() or (output.exists() and source_path.exists() and os.path.samefile(output, source_path)):
                raise ValueError('Choose an output different from the source clip')
        for source in rendered_footage(sequence_data): check_source(source)
        provider = VideoFrameProvider(cancel=cancel)
    canvas = sequence_data.get("canvas", p) if sequence_data else p
    width, height = size or (canvas["width"], canvas["height"])
    export_fps = int(sequence_data["fps"] if sequence_data else p["export_fps"])
    total = max(1, round(float(sequence_data["duration"] if sequence_data else p["loop_seconds"]) * export_fps))
    start = int(start)
    count = total - start if count is None else int(count)
    if start < 0 or count < 1 or start + count > total:
        raise ValueError("Empty or out-of-range synth export")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".nebula-synth-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    temp = Path(name)
    proc = None
    muxed = None
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
                if sequence_renderer:
                    image = sequence_renderer(sequence_data, time_seconds, size=(width, height), frame_provider=provider) if provider else sequence_renderer(sequence_data, time_seconds, size=(width, height))
                else:
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
        if footage and any(source['audio'] == 'keep' and source['has_audio'] for source in rendered_footage(sequence_data)):
            from synth_video_audio import mux_source_audio, mux_section_audio
            fd, name = tempfile.mkstemp(prefix='.nebula-mux-', suffix='.mp4', dir=output.parent)
            os.close(fd); muxed = Path(name)
            if sequence_data.get('video_segments'):
                mux_section_audio(temp, muxed, sequence_data['video_segments'], start / export_fps, count / export_fps, cancel)
            else:
                mux_source_audio(temp, muxed, footage, start / export_fps, count / export_fps, cancel, time_map=sequence_data.get('time_map'))
            cancel.check()
            os.replace(muxed, output)
        else:
            cancel.check()
            os.replace(temp, output)
        return output
    except Cancelled:
        raise ValueError("Synth export cancelled") from None
    except BrokenPipeError:
        if cancel.event.is_set(): raise ValueError('Synth export cancelled') from None
        raise ValueError('FFmpeg stopped while encoding the export') from None
    finally:
        if provider: provider.close()
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
        if muxed: muxed.unlink(missing_ok=True)
