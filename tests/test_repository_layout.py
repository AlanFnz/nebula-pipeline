"""Source launchers and relocated resources must work outside the checkout cwd."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nebula.resources import RESOURCE_ROOT, PACKAGE_ROOT

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name', ['studio', 'nebula', '_pipeline', 'analog_wobble', 'assemble', 'grade', 'generate'])
def test_existing_cli_commands_still_start(name, tmp_path):
    result = subprocess.run([sys.executable, str(ROOT/(name+'.py')), '--help'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'usage:' in result.stdout


def test_resources_keep_their_root_and_study_data(tmp_path):
    code = '''
import json
from nebula.resources import RESOURCE_ROOT
from nebula.documents.synth_starting_points import new_piece
from nebula.sources.synth_fonts import FONT_ROOT
from nebula.sources.synth_blender_bridge import SCRIPT
assert FONT_ROOT.is_dir() and SCRIPT.is_file()
assert (RESOURCE_ROOT/'assets/help.svg').is_file()
assert (RESOURCE_ROOT/'assets/render-defaults-v1.json').is_file()
print(json.dumps(new_piece('shape')))
'''
    # Simulate an installed source package, with an unrelated working directory.
    import os
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['format'] == 'nebula-composition'


def test_only_entry_points_and_version_remain_at_root():
    assert {p.name for p in ROOT.glob('*.py')} == {
        'studio.py', 'mac_app.py', 'nebula.py', '_pipeline.py',
        'analog_wobble.py', 'assemble.py', 'grade.py', 'generate.py', '_version.py',
    }
    assert PACKAGE_ROOT == ROOT/'nebula'
    assert RESOURCE_ROOT == ROOT
