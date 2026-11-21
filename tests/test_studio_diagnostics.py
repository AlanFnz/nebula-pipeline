import json
from pathlib import Path

import nebula.core.studio_diagnostics as diagnostics


def test_local_logs_rotate_and_failed_setup_does_not_break_editor(tmp_path):
    try:
        path = diagnostics.configure(tmp_path)
        diagnostics.record('preview.loop_changed', enabled=True, cached=[[0, 72], [180, 220]])
        lines = [json.loads(line) for line in path.read_text().splitlines()]
        assert lines[0]['event'] == 'session.started' and lines[0]['version']
        assert lines[1]['cached'] == [[0, 72], [180, 220]]
        # Exercise the real rotation mechanism at a smaller threshold.
        diagnostics._logger.handlers[0].maxBytes = 512
        for _ in range(20): diagnostics.record('preview.batch_started', frames=list(range(4)))
        assert Path(str(path)+'.1').exists() and Path(str(path)+'.2').exists()
        assert len(list(tmp_path.glob('preview-events.log*'))) == 3
        assert all(p.stat().st_size < 512 for p in tmp_path.glob('preview-events.log*'))
        not_folder = tmp_path/'file'; not_folder.write_text('keep')
        assert diagnostics.configure(not_folder) is None
        assert not diagnostics.enabled()
        diagnostics.record('preview.loop_changed', enabled=False)
        assert not_folder.read_text() == 'keep'
    finally: diagnostics.close()
