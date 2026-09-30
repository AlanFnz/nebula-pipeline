"""Explicit, one-time baseline capture. Never update expectations during tests.

Run from the recorded baseline checkout with .venv/bin/python. Generated review
images stay in output; the manifest and resolved recipes are small JSON assets.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synth import curated_presets, default_synth_preset
from synth_canvas import CANVAS_FORMATS, format_canvas, preview_size, resize_canvas
from synth_composition import compile_composition, section_ranges
from synth_sequence import render_sequence_frame
from synth_starters import STARTERS


def cases(project):
    sequence = compile_composition(project)
    count = round(sequence['duration'] * sequence['fps'])
    yield 'native-cycle', sequence, preview_size(sequence['canvas'], 96), list(range(count))
    # Section boundaries plus evenly spread samples catch both transitions and
    # procedural motion without multiplying the full-cycle suite by seven.
    frames = sorted({0, count - 1, *(round(i * (count - 1) / 5) for i in range(6)),
                     *(max(0, min(count - 1, round(start * sequence['fps']) + delta))
                       for start, _end in section_ranges(project) for delta in (-1, 0, 1))})
    for key, _label, _w, _h in CANVAS_FORMATS:
        resized = dict(sequence, canvas=resize_canvas(sequence['canvas'], format_canvas(key)))
        yield key, resized, preview_size(resized['canvas'], 120), frames
    yield 'preview', sequence, preview_size(sequence['canvas'], 360), frames
    yield 'full', sequence, None, [count // 3]
    low = json.loads(json.dumps(project))
    low['effects']['low_res'] = {'mode': 'on', 'params': {'low_res.resolution': 180}}
    yield 'low-res', compile_composition(low), preview_size(sequence['canvas'], 360), frames


def main():
    destination = ROOT / 'presets' / 'compat-v1.json'
    manifest_path = ROOT / 'tests' / 'fixtures' / 'synth-baseline-v1.json'
    if destination.exists() or manifest_path.exists():
        raise SystemExit('Baseline already exists. Capture a new revision explicitly; never overwrite v1.')
    starters = {key: factory() for key, _label, factory in STARTERS}
    snapshot = {'revision': 1, 'default': default_synth_preset(),
                'presets': curated_presets(), 'starters': starters}
    destination.write_text(json.dumps(snapshot, separators=(',', ':')) + '\n')
    manifest = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'python': platform.python_version(),
                'dependencies': {p: importlib.metadata.version(p) for p in ('numpy', 'Pillow', 'PySide6')},
                'assets': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted((ROOT / 'assets' / 'models').glob('*.npz'))},
                'cases': []}
    review = ROOT / 'output' / 'compat-baseline'
    review.mkdir(parents=True, exist_ok=True)
    for key, project in starters.items():
        for name, sequence, size, frames in cases(project):
            digest = hashlib.sha256()
            for frame in frames:
                image = render_sequence_frame(sequence, frame / sequence['fps'], size)
                digest.update(image.tobytes())
                if name == 'preview' and frame == frames[len(frames) // 2]:
                    image.save(review / f'{key}.png')
            manifest['cases'].append({'starter': key, 'case': name, 'size': size, 'frames': frames,
                                      'sha256': digest.hexdigest()})
            print(key, name, len(frames), flush=True)
    manifest_path.parent.mkdir(exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
