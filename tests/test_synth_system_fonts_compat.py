"""Representative pixels of every shipped text study before system fonts."""
import hashlib
import json
from pathlib import Path
from synth_starters import starter_composition
from synth_composition import compile_composition
from synth_sequence import render_sequence_frame


def test_all_text_study_snapshots_match_0363_pixels():
    rows=json.loads((Path(__file__).parent/'fixtures/system-typefaces-v0363-hashes.json').read_text())
    sequences={key:compile_composition(starter_composition(key)) for key in {row[0] for row in rows}}
    for key,time,expected in rows:
        frame=render_sequence_frame(sequences[key],time,(128,96))
        assert hashlib.sha256(frame.tobytes()).hexdigest()==expected,(key,time)
