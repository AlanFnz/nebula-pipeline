import subprocess

from PIL import Image
import pytest

from _pipeline import extract_frames
from media import probe, decode_frames, export_video, Cancellation, Cancelled
from parameters import DEFAULTS


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=96x80:rate=24:duration=1", "-c:v", "libx264", str(path)], check=True)
    return probe(path)


def test_decode_grid_matches_legacy_extraction(clip, tmp_path):
    folder = tmp_path / "raw"
    extract_frames(clip["path"], folder, 12)
    actual = list(decode_frames(clip, 12, 3, 5))
    assert len(actual) == 5
    for index, image in actual:
        assert image.tobytes() == Image.open(folder / f"frame_{index+1:05}.png").convert("RGB").tobytes()


def test_export_uses_absolute_frame_and_shared_renderer(clip, tmp_path, monkeypatch):
    import media
    from engine import render_frame
    rendered = []
    def observed(source, params, frame):
        image = render_frame(source, params, frame)
        rendered.append((frame, image.tobytes()))
        return image
    monkeypatch.setattr(media, "render_frame", observed)
    output = tmp_path / "result.mp4"
    export_video(clip, DEFAULTS, output, start=3, count=4)
    assert [i for i, _ in rendered] == [3, 4, 5, 6]
    for (i, raw), (j, source) in zip(rendered, decode_frames(clip, 12, 3, 4)):
        assert i == j
        assert raw == render_frame(source, DEFAULTS, i).tobytes()
    assert abs(probe(output)["duration"] - 4/12) < .02


def test_cancel_preserves_destination_and_source(clip, tmp_path):
    dest = tmp_path / "existing.mp4"
    dest.write_bytes(b"original")
    cancel = Cancellation()
    cancel.cancel()
    with pytest.raises(Cancelled):
        export_video(clip, DEFAULTS, dest, cancel=cancel)
    assert dest.read_bytes() == b"original"
    assert not list(tmp_path.glob(".nebula-*.mp4"))
    with pytest.raises(ValueError):
        export_video(clip, DEFAULTS, clip["path"])


def test_mid_export_cancellation_preserves_existing_file(clip, tmp_path):
    dest = tmp_path / "existing.mp4"
    dest.write_bytes(b"keep this output")
    cancel = Cancellation()
    def progress(done, total):
        if done == 2:
            cancel.cancel()
    with pytest.raises(Cancelled):
        export_video(clip, DEFAULTS, dest, cancel=cancel, progress=progress)
    assert dest.read_bytes() == b"keep this output"
    assert not list(tmp_path.glob(".nebula-*.mp4"))
