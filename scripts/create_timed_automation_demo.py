"""Create an independent ten-second picture with one 4–5s tape pull.

Run with the repository Python environment. No personal study or app state is
read or modified. Generated review media goes under .validation by default.
"""
from pathlib import Path
import argparse
import copy
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from synth import default_synth_preset
from synth_composition import blank_composition, compile_composition, save_composition
from synth_effects import effect_preset
from synth_media import export_synth_video
from synth_sequence import render_sequence_frame, save_sequence
from synth_subject import select_subject


def demo_composition():
    project = select_subject(blank_composition(), 'silhouette')
    project.update(name='Timed tape pull / 4–5 seconds', fps=15)
    project['canvas'].update(width=720, height=480)
    project['sections'][0]['duration'] = 10.
    project['phrases']['custom']['name'] = 'One uninterrupted portrait'
    project['effects']['edge_phosphor'] = effect_preset('edge_phosphor')
    project['effects']['edge_phosphor']['params'].update({'edge_phosphor.backlight': .8, 'edge_phosphor.grain': .22})
    project['effects']['crt_capture'] = effect_preset('crt_capture')
    project['effects']['tape'] = effect_preset('tape', 3)
    project['sections'][0]['automations'] = [dict(id='demo-pull', path='tape.pull', amount=.6,
        enabled=True, easing='smooth', start_fraction=.4, attack_fraction=.015,
        hold_fraction=0., recovery_fraction=.085)]
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'.validation'/'timed-effect-automation')
    parser.add_argument('--skip-export', action='store_true')
    args=parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    project=demo_composition(); sequence=compile_composition(project)
    baseline=copy.deepcopy(sequence); baseline.pop('automations')
    save_composition(args.output/'timed-tape-pull.nebula.json',project)
    save_sequence(args.output/'timed-tape-pull.sequence.json',sequence)
    for time in (0.,3.9,4.,4.15,4.4,4.9,5.,7.73,9.9):
        for size in (None,(360,240)):
            automated=render_sequence_frame(sequence,time,size)
            plain=render_sequence_frame(baseline,time,size)
            if time<=4 or time>=5: assert np.array_equal(automated,plain), (time,size)
            elif time in (4.15,4.4): assert not np.array_equal(automated,plain), (time,size)
        render_sequence_frame(sequence,time,(360,240)).save(args.output/f'frame-{time:.2f}.png')
    if not args.skip_export:
        export_synth_video(default_synth_preset(),args.output/'timed-tape-pull.mp4',sequence=sequence)
    print(args.output)


if __name__ == '__main__': main()
