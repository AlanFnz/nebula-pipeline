#!/usr/bin/env python3
"""
nebula.py — analog degradation pipeline TUI
"""

import argparse
import json
import subprocess
import sys
import time as _time
from datetime import datetime
from pathlib import Path

from PIL import Image
from rich.text import Text as RichText
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, RichLog, Static

sys.path.insert(0, str(Path(__file__).parent))
from _banner import get_banner_text
from _pipeline import extract_frames, clear_frames, require_ffmpeg
from assemble import assemble_video
from analog_wobble import process as wobble_process
from grade import process as grade_process

# ── paths ─────────────────────────────────────────────────────────────────────

PREVIEW   = Path("tune_preview.png")
SRC_FRAME = Path("tune_source.png")

_preview_opened = False
_preview_frame_index = 0
_preview_video = None
_preview_fps = None

# ── params ────────────────────────────────────────────────────────────────────

from parameters import DEFAULTS

RANGE_PARAMS  = {"blur", "grain", "px", "deg"}
SINGLE_PARAMS = {"aberration", "vignette", "bands", "texture", "warm", "dust", "dust_opacity",
                 "scanlines", "bloom", "curvature", "brightness", "fps", "seed",
                 "contrast", "shadows", "highlights", "toning", "grade", "drift"}

PARAM_GROUPS = [
    ("print pass", ["blur", "texture", "warm"]),
    ("scan pass",  ["aberration", "bands", "scanlines", "bloom", "curvature",
                    "vignette", "grain", "dust", "dust_opacity", "brightness"]),
    ("grade pass", ["grade", "contrast", "shadows", "highlights", "toning"]),
    ("video",      ["px", "deg", "fps"]),
    ("misc",       ["drift", "seed"]),
]

ALL_PARAMS = RANGE_PARAMS | SINGLE_PARAMS

# ── persistence ───────────────────────────────────────────────────────────────

PRESETS_DIR = Path.home() / ".nebula_pipeline" / "presets"


def _restore_tuples(raw: dict) -> dict:
    for k in RANGE_PARAMS:
        if k in raw and isinstance(raw[k], list):
            raw[k] = tuple(raw[k])
    return raw


def params_file(project: Path) -> Path:
    return project / "tune_params.json"


def save_params(params: dict, project: Path) -> None:
    params_file(project).parent.mkdir(parents=True, exist_ok=True)
    params_file(project).write_text(json.dumps(params, indent=2))


def load_params(project: Path) -> dict | None:
    f = params_file(project)
    if not f.exists():
        return None
    try:
        return _restore_tuples(json.loads(f.read_text()))
    except Exception:
        return None


def save_preset(name: str, params: dict) -> None:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    (PRESETS_DIR / f"{name}.json").write_text(json.dumps(params, indent=2))


def load_preset(name: str) -> dict | None:
    f = PRESETS_DIR / f"{name}.json"
    if not f.exists():
        return None
    try:
        return _restore_tuples(json.loads(f.read_text()))
    except Exception:
        return None


def list_presets() -> list[str]:
    if not PRESETS_DIR.exists():
        return []
    return sorted(p.stem for p in PRESETS_DIR.glob("*.json"))


# ── rendering ─────────────────────────────────────────────────────────────────

def extract_frame(video: Path, fps: float, index: int) -> None:
    global _preview_frame_index, _preview_video, _preview_fps
    _preview_frame_index = index
    _preview_video, _preview_fps = video, fps
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"fps={fps},select=eq(n\\,{index})",
        "-vframes", "1", str(SRC_FRAME),
    ], check=True, capture_output=True)


def apply_and_save(params: dict) -> None:
    """Exact selected-frame rendering, using the same order and time as export."""
    from engine import render_frame
    if _preview_video is not None and params["fps"] != _preview_fps:
        extract_frame(_preview_video, params["fps"], _preview_frame_index)
    img = render_frame(Image.open(SRC_FRAME), params, _preview_frame_index)
    global _preview_opened
    img.save(PREVIEW)
    if not _preview_opened:
        subprocess.run(["open", str(PREVIEW)], check=False)
        _preview_opened = True


# ── pipeline ──────────────────────────────────────────────────────────────────

def build_pipeline_args(video: Path, project: Path, params: dict) -> list[str]:
    p = params
    args = [
        sys.executable, "_pipeline.py", str(video), str(project),
        "--fps",          str(p["fps"]),
        "--blur",         str(p["blur"][0]),       str(p["blur"][1]),
        "--texture",      str(p["texture"]),
        "--warm",         str(p["warm"]),
        "--aberration",   str(p["aberration"]),
        "--bands",        str(p["bands"]),
        "--vignette",     str(p["vignette"]),
        "--grain",        str(p["grain"][0]),      str(p["grain"][1]),
        "--dust",         str(p["dust"]),
        "--dust-opacity", str(p["dust_opacity"]),
        "--scanlines",    str(p["scanlines"]),
        "--bloom",        str(p["bloom"]),
        "--curvature",    str(p["curvature"]),
        "--brightness",   str(p["brightness"]),
        "--drift",        str(p["drift"]),
        "--px",           str(p["px"][0]),         str(p["px"][1]),
        "--deg",          str(p["deg"][0]),         str(p["deg"][1]),
    ]
    if p.get("grade", 1):
        args += [
            "--grade",
            "--contrast",   str(p["contrast"]),
            "--shadows",    str(p["shadows"]),
            "--highlights", str(p["highlights"]),
            "--toning",     str(p["toning"]),
        ]
    if p.get("seed") is not None:
        args += ["--seed", str(int(p["seed"]))]
    return args


def parse_and_set(param: str, raw: str, params: dict) -> tuple[bool, str]:
    if param in RANGE_PARAMS:
        parts = raw.split()
        if len(parts) != 2:
            return False, f"{param} needs two values: MIN MAX"
        try:
            params[param] = (float(parts[0]), float(parts[1]))
        except ValueError:
            return False, f"invalid values for {param}"
    elif param in SINGLE_PARAMS:
        try:
            params[param] = int(raw.strip()) if param in ("seed", "grade") else float(raw.strip())
        except ValueError:
            return False, f"invalid value for {param}"
    else:
        return False, f"unknown param '{param}'"
    return True, ""


def _fmt(v) -> str:
    if isinstance(v, tuple):
        return f"{v[0]}  {v[1]}"
    return str(v)


def _fmt_elapsed(secs: float) -> str:
    s = max(0, int(secs))
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"0:{m:02d}:{s:02d}"


def _fmt_remaining(elapsed: float, cur: int, tot: int) -> str:
    if cur <= 0 or cur >= tot or elapsed <= 0:
        return "-:--:--"
    return _fmt_elapsed(elapsed / cur * (tot - cur))


def _make_run_progress(step_order: list, step_data: dict) -> RichText:
    t = RichText()
    now = _time.time()
    for name in step_order:
        d     = step_data[name]
        cur, tot = d["cur"], d["tot"]
        start = d.get("start")
        elapsed = ((d.get("end") or now) - start) if start else 0.0
        filled  = round(cur / tot * 40) if tot > 0 else 0
        t.append(f"  {name:<14}", style="dim")
        t.append("█" * filled,        style="color(214)")
        t.append("░" * (40 - filled), style="color(238)")
        t.append(f"  {cur}/{tot}",             style="")
        t.append("  fr",                       style="dim")
        t.append(f"  {_fmt_elapsed(elapsed)}", style="")
        t.append("  ·  ",                      style="dim")
        t.append(_fmt_remaining(elapsed, cur, tot), style="")
        t.append("\n")
    return t


# ── modals ────────────────────────────────────────────────────────────────────

class EditModal(ModalScreen):
    DEFAULT_CSS = """
    EditModal { align: center middle; }
    #dialog {
        background: #1a1a1a;
        border: solid #ffaf00;
        padding: 1 2;
        width: 52;
        height: auto;
    }
    #title { color: #ffaf00; text-style: bold; margin-bottom: 1; }
    #val   { background: #0d0d0d; color: #ffaf00; border: solid #333333; width: 100%; }
    #hint  { color: #444444; margin-top: 1; height: 1; }
    """

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, param: str, current: str) -> None:
        super().__init__()
        self._param   = param
        self._current = current

    def compose(self) -> ComposeResult:
        hint = "MIN  MAX" if self._param in RANGE_PARAMS else "value"
        with Vertical(id="dialog"):
            yield Label(f"edit  {self._param}  [dim]{self._current}[/]", id="title", markup=True)
            yield Input(value=self._current, placeholder=hint, id="val")
            yield Label("enter to confirm · esc to cancel", id="hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class NameModal(ModalScreen):
    """Generic single-input modal for preset save/load."""

    DEFAULT_CSS = """
    NameModal { align: center middle; }
    #dialog {
        background: #1a1a1a;
        border: solid #d78700;
        padding: 1 2;
        width: 52;
        height: auto;
    }
    #title   { color: #d78700; text-style: bold; margin-bottom: 1; }
    #names   { color: #555555; margin-bottom: 1; height: 1; }
    #val     { background: #0d0d0d; color: #d78700; border: solid #333333; width: 100%; }
    #hint    { color: #444444; margin-top: 1; height: 1; }
    """

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, title: str, names: list[str] | None = None) -> None:
        super().__init__()
        self._title = title
        self._names = names or []

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._title, id="title")
            if self._names:
                yield Label("  ".join(self._names), id="names")
            yield Input(placeholder="name", id="val")
            yield Label("enter to confirm · esc to cancel", id="hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── app ───────────────────────────────────────────────────────────────────────

class NebulaApp(App):
    TITLE     = "nebula"
    SUB_TITLE = "analog degradation"

    CSS = """
    NebulaApp { background: #0d0d0d; }

    Header    { background: #0d0d0d; color: #ffaf00; text-style: bold; }
    Footer    { background: #131313; color: #d78700; }

    #body {
        height: 1fr;
        border: solid #2a2a2a;
    }

    #left {
        width: 30;
        border-right: solid #2a2a2a;
    }

    #params-table {
        height: 1fr;
        background: #0d0d0d;
        color: #c87800;
    }
    DataTable > .datatable--row-highlighted {
        background: #1e1500;
        color: #ffaf00;
    }

    #right {
        width: 1fr;
        padding: 0 1;
    }

    #preview-panel { height: auto; }
    #preview-status {
        height: 1;
        color: #3a3a3a;
        margin-bottom: 1;
    }

    #run-panel   { display: none; height: auto; padding: 1 0; }
    #run-banner  { height: auto; }
    #run-progress { height: auto; margin-top: 1; }

    #log {
        height: 1fr;
        background: #0d0d0d;
        color: #666666;
    }
    """

    BINDINGS = [
        Binding("r",      "run_pipeline", "Run"),
        Binding("s",      "save_preset",  "Save preset"),
        Binding("l",      "load_preset",  "Load preset"),
        Binding("ctrl+z", "reset_params", "Reset"),
        Binding("q",      "quit",         "Quit"),
    ]

    def __init__(self, video: Path, project: Path, frame_idx: int) -> None:
        super().__init__()
        self._video     = video
        self._project   = project
        self._frame_idx = frame_idx
        saved                = load_params(project)
        self._params         = {**DEFAULTS, **saved} if saved else dict(DEFAULTS)
        self._run_step_order: list[str] = []
        self._run_step_data:  dict      = {}

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield DataTable(id="params-table", show_header=False, cursor_type="row")
            with Vertical(id="right"):
                with Vertical(id="preview-panel"):
                    yield Static("● rendering…", id="preview-status")
                with Vertical(id="run-panel"):
                    yield Static(get_banner_text(), id="run-banner")
                    yield Static("", id="run-progress")
                yield RichLog(id="log", markup=True, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self._build_table()
        saved = load_params(self._project)
        self._log(f"[dim]loaded params[/]" if saved else "[dim]using defaults[/]")
        self._render_preview()

    # ── table ─────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        t = self.query_one("#params-table", DataTable)
        t.add_column("", key="k", width=14)
        t.add_column("", key="v", width=14)
        for group, keys in PARAM_GROUPS:
            t.add_row(f" [dim]{group}[/]", "", key=None)
            for k in keys:
                t.add_row(f"  {k}", _fmt(self._params[k]), key=k)

    def _refresh_table(self) -> None:
        t = self.query_one("#params-table", DataTable)
        for k in ALL_PARAMS:
            t.update_cell(k, "v", _fmt(self._params[k]), update_width=False)

    # ── preview ───────────────────────────────────────────────────────────────

    @work(thread=True, exclusive=True)
    def _render_preview(self) -> None:
        apply_and_save(self._params)
        ts = datetime.now().strftime("%H:%M:%S")
        self.call_from_thread(
            self.query_one("#preview-status", Static).update,
            f"[dim]● {ts}  {PREVIEW}[/]",
        )

    # ── row edit ──────────────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key not in ALL_PARAMS:
            return

        def on_result(raw: str | None) -> None:
            if not raw:
                return
            ok, err = parse_and_set(key, raw, self._params)
            if not ok:
                self._log(f"[red]{err}[/]")
                return
            self.query_one("#params-table", DataTable).update_cell(
                key, "v", _fmt(self._params[key]), update_width=False,
            )
            save_params(self._params, self._project)
            self._log(f"  [color(214)]{key}[/] = {_fmt(self._params[key])}")
            self._render_preview()

        self.push_screen(EditModal(key, _fmt(self._params[key])), on_result)

    # ── actions ───────────────────────────────────────────────────────────────

    def action_run_pipeline(self) -> None:
        self._run_pipeline()

    @work(thread=True, exclusive=True)
    def _run_pipeline(self) -> None:
        p = self._params
        frames_raw     = self._project / "frames_raw"
        frames_wobbled = self._project / "frames_wobbled"
        treated        = self._project / "frames_treated"

        def set_step(name: str, cur: int, tot: int) -> None:
            self.call_from_thread(self._update_run_ui, name, cur, tot)

        step_names = ["extracting", "wobbling"]
        if p.get("grade", 1):
            step_names.append("grading")
        step_names.append("assembling")
        self.call_from_thread(self._start_run_display, step_names)

        try:
            try:
                require_ffmpeg()
            except SystemExit as e:
                self.call_from_thread(self._log, f"[red]{e}[/]")
                return

            for folder in (frames_raw, frames_wobbled, treated):
                folder.mkdir(parents=True, exist_ok=True)
                clear_frames(folder)

            set_step("extracting", 0, 1)
            n = extract_frames(self._video, frames_raw, p["fps"])
            set_step("extracting", 1, 1)

            set_step("wobbling", 0, n)
            wobble_process(
                frames_raw, frames_wobbled,
                px_range=p["px"], deg_range=p["deg"],
                grain_range=p["grain"], blur_range=p["blur"],
                aberration=p["aberration"], vignette=p["vignette"],
                bands=p["bands"], texture=p["texture"], warm=p["warm"],
                dust=p["dust"], dust_opacity=p["dust_opacity"],
                scanlines=p["scanlines"], bloom=p["bloom"],
                curvature=p["curvature"], brightness=p["brightness"],
                seed=int(p["seed"]) if p.get("seed") is not None else None,
                drift=p["drift"],
                stages=p.get("_stages"),
                on_progress=lambda cur, tot: set_step("wobbling", cur, tot),
            )

            if p.get("grade", 1):
                set_step("grading", 0, n)
                grade_process(
                    frames_wobbled, treated,
                    contrast=p["contrast"], shadows=p["shadows"],
                    highlights=p["highlights"], toning=p["toning"],
                    on_progress=lambda cur, tot: set_step("grading", cur, tot),
                )
                src_frames = treated
                output = self._project / "output" / "final.mp4"
            else:
                src_frames = frames_wobbled
                output = self._project / "output" / "preview_wobbled.mp4"

            set_step("assembling", 0, 1)
            (self._project / "output").mkdir(parents=True, exist_ok=True)
            assemble_video(src_frames, output, fps=p["fps"])
            set_step("assembling", 1, 1)

            self.call_from_thread(self._log, f"[color(214)]→ {output}[/]")
        except Exception as e:
            self.call_from_thread(self._log, f"[red]error: {e}[/]")
        finally:
            self.call_from_thread(self._end_run_display)

    def _start_run_display(self, step_names: list[str]) -> None:
        self._run_step_order = step_names
        self._run_step_data  = {
            n: {"cur": 0, "tot": 1, "start": None, "end": None}
            for n in step_names
        }
        self.query_one("#run-progress", Static).update(
            _make_run_progress(self._run_step_order, self._run_step_data)
        )
        self.query_one("#run-panel").display     = True
        self.query_one("#preview-panel").display = False

    def _update_run_ui(self, name: str, cur: int, tot: int) -> None:
        now = _time.time()
        d   = self._run_step_data[name]
        if d["start"] is None:
            d["start"] = now
        d["cur"] = cur
        d["tot"] = tot
        if cur >= tot:
            d.setdefault("end", now)
        self.query_one("#run-progress", Static).update(
            _make_run_progress(self._run_step_order, self._run_step_data)
        )

    def _end_run_display(self) -> None:
        self.query_one("#run-panel").display     = False
        self.query_one("#preview-panel").display = True

    def action_save_preset(self) -> None:
        def on_name(name: str | None) -> None:
            if name:
                save_preset(name, self._params)
                self._log(f"[color(214)]saved preset '{name}'[/]")
        self.push_screen(NameModal("save preset"), on_name)

    def action_load_preset(self) -> None:
        names = list_presets()

        def on_name(name: str | None) -> None:
            if not name:
                return
            preset = load_preset(name)
            if preset is None:
                self._log(f"[red]preset '{name}' not found[/]")
                return
            self._params = {**DEFAULTS, **preset}
            save_params(self._params, self._project)
            self._refresh_table()
            self._render_preview()
            self._log(f"[color(214)]loaded preset '{name}'[/]")

        self.push_screen(NameModal("load preset", names), on_name)

    def action_reset_params(self) -> None:
        self._params = dict(DEFAULTS)
        params_file(self._project).unlink(missing_ok=True)
        self._refresh_table()
        self._render_preview()
        self._log("[dim]reset to defaults[/]")

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="nebula — analog degradation pipeline")
    ap.add_argument("video",   type=Path, help="source video")
    ap.add_argument("project", type=Path, nargs="?", default=Path("test_run"),
                    help="project folder (default: test_run)")
    ap.add_argument("--frame", type=int, default=None,
                    help="frame index to preview (default: midpoint)")
    args = ap.parse_args()

    if not args.video.exists():
        raise SystemExit(f"error: video not found: {args.video}")

    args.project.mkdir(parents=True, exist_ok=True)
    saved  = load_params(args.project)
    params = {**DEFAULTS, **saved} if saved else dict(DEFAULTS)

    if args.frame is not None:
        frame_idx = args.frame
    else:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(args.video)],
            capture_output=True, text=True,
        )
        try:
            frame_idx = int(float(result.stdout.strip()) * params["fps"] / 2)
        except (ValueError, TypeError):
            frame_idx = 15

    print(f"extracting frame {frame_idx}…")
    extract_frame(args.video, params["fps"], frame_idx)

    NebulaApp(args.video, args.project, frame_idx).run()


if __name__ == "__main__":
    main()
