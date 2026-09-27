"""One-time extension of the visual contract for the two v2 profile starters."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.capture_synth_baseline import cases
from synth_starters import starter_composition
from synth_sequence import render_sequence_frame


def main():
    snapshot = ROOT / 'presets/compat-profiles-v2.json'
    manifest = ROOT / 'tests/fixtures/synth-baseline-profiles-v2.json'
    if snapshot.exists() or manifest.exists():
        raise SystemExit('Profile baseline already exists; never overwrite a visual contract.')
    projects = {key: starter_composition(key) for key in ('profile-clear', 'profile-doryphoros')}
    data = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'assets': {'assets/models/doryphoros-head.npz': hashlib.sha256((ROOT / 'assets/models/doryphoros-head.npz').read_bytes()).hexdigest()}, 'cases': []}
    snapshot.write_text(json.dumps(projects, separators=(',', ':')) + '\n')
    for key, project in projects.items():
        for name, sequence, size, frames in cases(project):
            digest = hashlib.sha256()
            for frame in frames:
                digest.update(render_sequence_frame(sequence, frame / sequence['fps'], size).tobytes())
            data['cases'].append({'starter': key, 'case': name, 'size': size, 'frames': frames, 'sha256': digest.hexdigest()})
            print(key, name, len(frames), flush=True)
    manifest.write_text(json.dumps(data, indent=2) + '\n')

if __name__ == '__main__':
    main()
