"""Exercise the same study loader on an empty install and a local catalogue."""
import json
import os
from pathlib import Path
import subprocess
import sys

from nebula.documents.synth_composition import save_composition
from nebula.documents.synth_starting_points import new_piece


def test_optional_library_round_trip(tmp_path):
    pack = tmp_path / 'library'
    project = new_piece('shape')
    save_composition(pack / 'studies' / 'sample.nebula', project)
    (pack / 'catalog.json').write_text(json.dumps({
        'version': 1, 'studies': [{'id': 'sample', 'name': 'Sample',
                                  'date': '2026-01-01', 'category': 'Other'}]}))
    script = """
import sys
from nebula.documents.synth_studies import study_records, study_composition
from nebula.documents.synth_composition import compile_composition, reference_composition
from nebula.documents.synth_starting_points import new_piece
from pathlib import Path
rows = study_records(Path(sys.argv[1]) / 'personal')
if sys.argv[2] == 'installed':
    assert [row.identifier for row in rows] == ['sample']
    assert study_composition('sample') == new_piece('shape')
else:
    assert not rows
assert compile_composition(reference_composition())['cues']
"""
    for location, status in [(pack, 'installed'), (tmp_path / 'missing', 'standalone')]:
        subprocess.run([sys.executable, '-c', script, str(tmp_path), status], check=True,
                       cwd=Path(__file__).resolve().parents[1],
                       env=dict(os.environ, NEBULA_STUDY_LIBRARY=str(location)))
