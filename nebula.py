#!/usr/bin/env python3
"""
nebula.py — analog degradation pipeline TUI
"""

import argparse
import json
import math
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from rich_pixels import Pixels
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, RichLog, Rule, Static

sys.path.insert(0, str(Path(__file__).parent))
from analog_wobble import (
    add_blur, add_paper_texture, add_warm_toning,
    add_chromatic_aberration, add_scan_bands,
    add_scanlines, add_bloom, add_curvature,
    add_vignette, add_luminous_grain, add_dust, add_brightness, wobble,
)
from grade import apply_contrast, apply_shadow_crush, apply_highlight_boost, apply_split_toning

# ── paths ─────────────────────────────────────────────────────────────────────

PREVIEW   = Path("tune_preview.png")
SRC_FRAME = Path("tune_source.png")

_preview_opened = False

# ── params ────────────────────────────────────────────────────────────────────

DEFAULTS: dict = {
    "blur":         (3.0, 7.0),
    "texture":      0.7,
    "warm":         0.8,
    "aberration":   3.0,
    "bands":        0.45,
    "vignette":     0.75,
    "grain":        (0.7, 1.1),
    "dust":         0.6,
    "dust_opacity": 1.0,
    "scanlines":    0.0,
    "bloom":        0.0,
    "curvature":    0.0,
    "brightness":   1.0,
    "px":           (2.0, 5.0),
    "deg":          (0.2, 0.6),
    "fps":          12.0,
    "seed":         42,
    "contrast":     0.4,
    "shadows":      0.15,
    "highlights":   0.05,
    "toning":       0.4,
    "grade":        1,
    "drift":        0.0,
}

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
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"fps={fps},select=eq(n\\,{index})",
        "-vframes", "1", str(SRC_FRAME),
    ], check=True, capture_output=True)


def _render(params: dict, blur_r: float, grain_sigma: float,
            px: float, deg: float) -> Image.Image:
    seed = params.get("seed")
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed))

    img = Image.open(SRC_FRAME).convert("RGB")
    img = add_blur(img, blur_r)
    img = add_paper_texture(img, params["texture"])
    img = add_warm_toning(img, params["warm"])
    img = add_chromatic_aberration(img, params["aberration"])
    img = add_scan_bands(img, params["bands"])
    img = add_scanlines(img, params["scanlines"])
    img = add_bloom(img, params["bloom"])
    img = add_curvature(img, params["curvature"])
    img = add_vignette(img, params["vignette"])
    img = add_luminous_grain(img, grain_sigma)
    img = add_dust(img, params["dust"], params["dust_opacity"])
    img = add_brightness(img, params["brightness"])

    if params.get("grade", 1):
        arr = np.asarray(img, dtype=np.float32)
        arr = apply_contrast(arr, params["contrast"])
        arr = apply_shadow_crush(arr, params["shadows"])
        arr = apply_highlight_boost(arr, params["highlights"])
        arr = apply_split_toning(arr, params["toning"])
        img = Image.fromarray(arr.astype(np.uint8))

    theta = random.uniform(0, 2 * math.pi)
    dx    = int(px * math.cos(theta))
    dy    = int(px * math.sin(theta))
    rot   = deg * random.choice((-1, 1))
    return wobble(img, dx, dy, rot)


def apply_and_save(params: dict) -> None:
    blur_lo,  blur_hi  = params["blur"]
    grain_lo, grain_hi = params["grain"]
    px_lo,    px_hi    = params["px"]
    deg_lo,   deg_hi   = params["deg"]

    panels = []
    for blur_r, grain_s, px, deg in [
        (blur_lo,                  grain_lo * 25,                  px_lo, deg_lo),
        ((blur_lo + blur_hi) / 2, (grain_lo + grain_hi) / 2 * 25, (px_lo + px_hi) / 2, (deg_lo + deg_hi) / 2),
        (blur_hi,                  grain_hi * 25,                  px_hi, deg_hi),
    ]:
        panels.append(_render(params, blur_r, grain_s, px, deg))

    w, h  = panels[0].size
    sep   = 2
    sheet = Image.new("RGB", (w * 3 + sep * 2, h), (0, 0, 0))
    for i, panel in enumerate(panels):
        sheet.paste(panel, (i * (w + sep), 0))

    global _preview_opened
    sheet.save(PREVIEW)
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

    #preview-img {
        height: auto;
    }

    #preview-status {
        height: 1;
        color: #3a3a3a;
        margin-bottom: 1;
    }

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
        saved           = load_params(project)
        self._params    = {**DEFAULTS, **saved} if saved else dict(DEFAULTS)

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield DataTable(id="params-table", show_header=False, cursor_type="row")
            with Vertical(id="right"):
                yield Static("", id="preview-img")
                yield Static("● rendering…", id="preview-status")
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

        img = Image.open(PREVIEW).convert("RGB")
        panel_w = max(40, self.app.size.width - 36)
        panel_h = panel_w * img.height // img.width
        pixels = Pixels.from_image(img, resize=(panel_w, panel_h))

        ts = datetime.now().strftime("%H:%M:%S")
        self.call_from_thread(self.query_one("#preview-img",     Static).update, pixels)
        self.call_from_thread(self.query_one("#preview-status",  Static).update,
                              f"[dim]● {ts}  {PREVIEW}[/]")

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
        cmd = build_pipeline_args(self._video, self._project, self._params)
        with self.suspend():
            subprocess.run(cmd)

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
