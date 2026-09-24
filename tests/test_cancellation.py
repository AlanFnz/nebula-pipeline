import threading
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor

from media import Cancellation, Cancelled, decode_frames, probe


def test_stop_decoder_mid_stream_does_not_deadlock(tmp_path):
    path = tmp_path / 'video.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=720x1280:rate=30:duration=2', '-c:v', 'libx264', str(path)], check=True)
    info = probe(path)
    token = Cancellation()
    ready = threading.Event()
    def job():
        try:
            for i, source in decode_frames(info, 12, 0, 24, 480, token):
                ready.set()
                time.sleep(.1)
        except Cancelled:
            return 'cancelled'
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(job)
        assert ready.wait(5)
        token.cancel()
        assert future.result(timeout=5) == 'cancelled'
