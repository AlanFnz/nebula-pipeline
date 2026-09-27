"""Explicit, cancellable audio assembly for treated footage exports."""
from pathlib import Path
import tempfile
from synth_video import check_source, run_ffmpeg


def mux_source_audio(video, destination, footage, start, duration, cancel):
    """Repeat only the trimmed range, or pad its end with silence for Hold."""
    check_source(footage)
    span = footage['out'] - footage['in']
    with tempfile.TemporaryDirectory(prefix='.nebula-audio-', dir=Path(video).parent) as folder:
        trimmed = Path(folder) / 'trim.wav'
        run_ffmpeg(['-i', footage['path'], '-map', '0:a:0', '-vn',
            '-af', f"atrim=start={footage['in']}:end={footage['out']},asetpts=PTS-STARTPTS,aresample=48000,apad",
            '-t', str(span), '-c:a', 'pcm_s16le', str(trimmed)], cancel)
        args = ['-i', str(video)]
        if footage['end_mode'] == 'loop':
            args += ['-stream_loop', '-1', '-i', str(trimmed)]
            # A full-cycle offset is equivalent and avoids decoding hours of
            # repeated audio when exporting a range late in the timeline.
            offset = start % span
        else:
            args += ['-i', str(trimmed)]
            offset = start
        args += ['-map', '0:v:0', '-map', '1:a:0', '-af',
            f'apad,atrim=start={offset}:duration={duration},asetpts=PTS-STARTPTS',
            '-t', str(duration), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', str(destination)]
        run_ffmpeg(args, cancel)
