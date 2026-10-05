"""Create the editable Temporal fragments Study from local footage.

Media stays local. Use --save-study to add an independent copy to the library.
The output contains a composition and an optional ten-second MP4 (shorter if
less footage is available). No existing composition or Study is overwritten.
"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from synth import default_synth_preset
from synth_composition import compile_composition, save_composition
from synth_media import export_synth_video
from synth_repetition_recipes import temporal_fragments_composition
from synth_studies import save_study, study_composition
from synth_video import inspect_video, normalize_footage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--start',type=float,default=0.)
    parser.add_argument('--output',type=Path,default=ROOT/'.validation'/'temporal-fragments-delivery')
    parser.add_argument('--save-study',action='store_true')
    parser.add_argument('--skip-export',action='store_true')
    args=parser.parse_args()
    footage=inspect_video(args.source)
    footage['in']=args.start
    footage=normalize_footage(footage)
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Choose an empty output folder to preserve previous renders.')
    args.output.mkdir(parents=True,exist_ok=True)
    project=temporal_fragments_composition(footage)
    if args.save_study:
        identifier=save_study(project,project['name'])
        project=study_composition(identifier)
        print('Saved Study:',identifier,flush=True)
    save_composition(args.output/'temporal-fragments.nebula.json',project)
    if not args.skip_export:
        def progress(done,total):
            if done % 25==0 or done==total: print(f'{done}/{total} frames',flush=True)
        export_synth_video(default_synth_preset(),args.output/'temporal-fragments-10s.mp4',
                           sequence=compile_composition(project),progress=progress)
    print(args.output,flush=True)


if __name__=='__main__': main()
