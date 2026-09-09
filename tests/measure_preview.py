"""Manual representative QA: python tests/measure_preview.py /path/ref5.mp4."""
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from engine import render_frame
from media import decode_frames
from parameters import save
from studio import Studio, STYLE


def wait(predicate, limit=40):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(.005)
    raise RuntimeError(f"Timed out: {window.status.text()}")


app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
window = Studio()
window.show()
results = {}
phase = "cold_open"
started = time.perf_counter()

def event(generation, kind, data):
    if generation != window.generation:
        return
    if kind == "frame" and data[0] == window.timeline.value():
        results.setdefault(phase, {}).setdefault("current_seconds", time.perf_counter() - started)
    if kind == "done":
        results.setdefault(phase, {})["loop_seconds"] = time.perf_counter() - started

window.events.message.connect(event)
window.open_clip(sys.argv[1])
wait(lambda: window.info and len(window.frames) == 24 and window.preview_future.done())
results["clip"] = window.info
results["proxy"] = window.viewer.packet[0]
phase = "cached_source_edit"
started = time.perf_counter()
window.controls["blur"].spins[0].setValue(2.5)
wait(lambda: not window.debounce.isActive() and window.preview_future.done() and len(window.frames) == 24)
phase = "rapid_edit_scrub_ab"
started = time.perf_counter()
for i in range(20):
    window.controls["blur"].spins[0].setValue(i * .1)
    window.timeline.setValue(i)
    QApplication.processEvents()
window.timeline.setValue(12)
window.capture_a()
window.stage_checks["print"].setChecked(False)
wait(lambda: not window.debounce.isActive() and window.preview_future.done() and len(window.frames) == 24)
packet = window.frames[12]
source = next(decode_frames(window.info, window.params["fps"], 12, 1, window.quality.currentData()))[1]
scale = source.width / window.info["width"]
assert packet[1] == render_frame(source, window.params, 12, scale=scale).tobytes()
assert packet[2] == render_frame(source, window.snapshot, 12, scale=scale).tobytes()
phase = "full_size_ab_still"
started = time.perf_counter()
window.full_still()
wait(lambda: window.preview_future.done() and window.viewer.packet[0] == (window.info["width"], window.info["height"]))
# A full-size still is also checked against the engine's reference output.
source = next(decode_frames(window.info, window.params["fps"], 12, 1))[1]
assert window.viewer.packet[1] == render_frame(source, window.params, 12).tobytes()
# Return to proxy for the delivered UI screenshot and reference launch preset.
phase = "screenshot"
started = time.perf_counter()
window.stage_checks["print"].setChecked(True)
window.controls["vignette"].spins[0].setValue(.3)
window.controls["bloom"].spins[0].setValue(.4)
window.controls["brightness"].spins[0].setValue(1.2)
wait(lambda: not window.debounce.isActive() and window.preview_future.done() and len(window.frames) == 24)
Path(".validation").mkdir(exist_ok=True)
window.grab().save(".validation/studio.png")
save(".validation/qa-preset.json", window.params)
Path(".validation/timings.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
window.close()
wait(lambda: not window.isVisible())
