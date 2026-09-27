"""Raw-pixel contracts captured before the reusable-region refactor."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.capture_synth_baseline import cases
from synth_starters import starter_composition

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'tests/fixtures/synth-baseline-v1.json').read_text())


@pytest.mark.parametrize('identifier', tuple(dict.fromkeys(c['starter'] for c in MANIFEST['cases'])))
def test_starter_keeps_baseline_pixels(identifier):
    from synth_sequence import render_sequence_frame
    expected = {c['case']: c for c in MANIFEST['cases'] if c['starter'] == identifier}
    for name, sequence, size, frames in cases(starter_composition(identifier)):
        contract = expected[name]
        assert (list(size) if size else None) == contract['size']
        assert frames == contract['frames']
        digest = hashlib.sha256()
        for frame in frames:
            digest.update(render_sequence_frame(sequence, frame / sequence['fps'], size).tobytes())
        assert digest.hexdigest() == contract['sha256'], (identifier, name)


def test_bundled_model_assets_keep_their_identity():
    for relative, expected in MANIFEST['assets'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
