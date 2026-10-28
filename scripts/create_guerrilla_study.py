#!/usr/bin/env python3
"""Author a local, editable spoken-intro study from the supplied 28 s bounce.

Uses the frozen One more try printing vocabulary, with new portrait framing and
voice-aligned cuts. The soundtrack remains local; this script embeds no audio.
"""
from __future__ import annotations

import argparse
import copy
import csv
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synth_composition import (compile_composition, composition_from_sequence,
                               load_composition, normalize_composition, save_composition)
from synth_sequence import normalize_sequence, render_sequence_frame
from synth_soundtrack import probe_soundtrack

FPS = 30
# First full-band transient: ~9.36 s in the supplied bounce. Frame 281 is
# 9.366667 s: the first frame reserved for the user's separately edited footage.
HANDOFF_FRAME = 281
NAME = 'Text / Guerrilla Radio — spoken intro'


def composition(audio_path):
    original = load_composition(ROOT / 'presets/text-dye-transfer-v7.json')
    common = copy.deepcopy(next(iter(original['source']['states'].values()))['overrides'])
    common.update({
        'text.fit': 2, 'text.stretch_x': 1., 'text.stretch_y': 1.,
        'text.rotation': 0., 'text.tracking': -.012, 'text.leading': 1.16,
        'dye_transfer.scale': 1., 'dye_transfer.x': 0., 'dye_transfer.y': -.05,
        'dye_transfer.angle': 0., 'dye_transfer.mask_shape': 0,
        'dye_transfer.opening': 1.2, 'dye_transfer.warp': .85,
        'dye_transfer.softness': .6, 'dye_transfer.erosion': .018,
        'dye_transfer.grain': .009, 'dye_transfer.dust': .035,
        'dye_transfer.drag': .025, 'dye_transfer.drag_mix': .12,
        'dye_transfer.weave': .0018, 'dye_transfer.emulsion': .34,
        'dye_transfer.streaks': .14, 'dye_transfer.edge_bloom': .12,
        'dye_transfer.registration': .2, 'dye_transfer.focus_flutter': .18,
        'dye_transfer.shutter': 0., 'dye_transfer.cadence': 15.,
    })
    palettes = {
        'pink': dict(paper_hue=.905, paper_saturation=.77, paper_light=1.08,
                     ink_hue=.015, ink_saturation=.9, ink_light=.16, wash=.20, dye=.18),
        'paper': dict(paper_hue=.96, paper_saturation=.025, paper_light=.98,
                      ink_hue=.015, ink_saturation=0., ink_light=.14, wash=.16, dye=.08),
        'orange': dict(paper_hue=.026, paper_saturation=1., paper_light=1.08,
                       ink_hue=.015, ink_saturation=.95, ink_light=.10, wash=.2, dye=.20),
        'negative': dict(paper_hue=.96, paper_saturation=.025, paper_light=.015,
                         ink_hue=.96, ink_saturation=.025, ink_light=.93,
                         wash=.08, dye=0., edge_bloom=.04, erosion=.012, grain=.006),
    }
    shots = []

    def shot(t, text, palette, *, size=.14, width=.76, font=1, x=0., y=-.05,
             angle=0., pulse=0., **finish):
        values = dict(common)
        values.update({'text.content': text, 'text.size': size, 'text.block_width': width,
                       'text.font': font, 'text.rotation': angle,
                       'dye_transfer.x': x, 'dye_transfer.y': y})
        values.update({f'dye_transfer.{key}': value for key, value in palettes[palette].items()})
        values.update({f'dye_transfer.{key}': value for key, value in finish.items()})
        shots.append(dict(frame=round(t * FPS), text=text, palette=palette,
                          values=values, pulse=pulse))

    # Each phrase has its own typographic rhythm. Short exposure changes keep
    # the same wording; there are no random future-word flashes or clipped type.
    shot(0, 'IT HAS TO', 'pink', size=.10, width=.68, y=-.14)
    shot(.70, 'START', 'pink', size=.23, width=.70, y=-.05, pulse=.035)
    shot(.94, 'SOMEWHERE', 'pink', size=.14, width=.82)
    shot(1.34, 'IT HAS TO\nSTART\nSOMEWHERE', 'pink', size=.105, width=.74, pulse=.025)
    shot(1.83, 'IT HAS TO\nSTART\nSOMEWHERE', 'paper', size=.105, width=.74,
         softness=1.2, drag=.09, drag_mix=.22, shutter=.10)
    shot(1.93, 'IT HAS TO\nSTART\nSOMEWHERE', 'pink', size=.105, width=.74)
    shot(2.17, 'SOMEWHERE', 'paper', size=.11, width=.76, angle=-5., y=.03,
         drag=.10, drag_mix=.20, softness=1.3)

    shot(2.29, 'IT HAS TO', 'paper', size=.095, width=.63, y=-.19, angle=-5.)
    shot(2.99, 'START', 'paper', size=.22, width=.65, angle=-5., x=-.03, pulse=.04)
    shot(3.22, 'SOMETIME', 'paper', size=.15, width=.78, angle=-5.)
    shot(3.63, 'IT HAS TO\nSTART\nSOMETIME', 'orange', size=.105, width=.74,
         angle=3., registration=.32, pulse=.03)
    shot(4.07, 'IT HAS TO\nSTART\nSOMETIME', 'paper', size=.105, width=.74,
         angle=3., softness=1.25, drag=.12, drag_mix=.25)
    shot(4.17, 'SOMETIME', 'paper', size=.13, width=.74, y=.03, angle=3.)
    shot(4.40, 'SOMETIME', 'negative', size=.13, width=.74, y=.03, angle=3.)

    shot(4.50, 'WHAT', 'negative', size=.13, width=.50, font=0, y=-.23)
    shot(4.82, 'WHAT\nBETTER', 'negative', size=.13, width=.71, font=0, y=-.16)
    shot(5.17, 'PLACE', 'negative', size=.24, width=.77, font=0, y=-.04, pulse=.025)
    shot(5.50, 'THAN', 'negative', size=.13, width=.54, font=0, y=.07)
    shot(5.78, 'HERE', 'pink', size=.28, width=.78, font=0, y=-.04, pulse=.045)
    shot(6.17, 'HERE', 'negative', size=.28, width=.78, font=0, y=-.04,
         drag=.12, drag_mix=.28, softness=.85)
    shot(6.27, 'HERE', 'pink', size=.28, width=.78, font=0, y=-.04)
    shot(6.47, 'WHAT BETTER\nPLACE\nTHAN HERE?', 'paper', size=.105, width=.73,
         angle=-3., softness=.9)
    shot(6.70, 'WHAT BETTER\nPLACE\nTHAN HERE?', 'negative', size=.105, width=.73,
         angle=-3., shutter=-.16, drag=.08, drag_mix=.20)

    shot(6.77, 'WHAT', 'orange', size=.12, width=.38, y=-.23)
    shot(7.10, 'WHAT\nBETTER', 'orange', size=.12, width=.62, y=-.16)
    shot(7.43, 'TIME', 'orange', size=.25, width=.68, angle=5., pulse=.04)
    shot(7.98, 'THAN', 'paper', size=.13, width=.50, angle=-5., y=.04)
    shot(8.33, 'NOW', 'orange', size=.31, width=.79, y=-.04, pulse=.05)
    shot(8.80, 'NOW', 'paper', size=.31, width=.79, y=-.04,
         softness=1.1, drag=.10, drag_mix=.24, shutter=.16)
    shot(8.90, 'NOW', 'orange', size=.31, width=.79, y=-.04)
    shot(9.13, 'NOW', 'pink', size=.32, width=.81, y=-.04,
         warp=1.4, registration=.35, streaks=.22)
    shot(9.30, 'NOW', 'paper', size=.32, width=.81, y=-.04,
         softness=1.3, drag=.15, drag_mix=.28, shutter=-.28)

    assert len({s['frame'] for s in shots}) == len(shots)
    assert all(a['frame'] < b['frame'] for a, b in zip(shots, shots[1:]))
    source = normalize_sequence(dict(
        schema_version=1, render_version=2, name=NAME, fps=FPS, seed=281026,
        duration=HANDOFF_FRAME / FPS, canvas=dict(width=1080, height=1920, framing='adaptive'),
        states={f'shot-{i+1:02}': dict(preset='Reference blinds', enabled=['text', 'dye_transfer'],
                                     overrides=s['values']) for i, s in enumerate(shots)},
        cues=[dict(time=s['frame']/FPS, state=f'shot-{i+1:02}', transition='cut') for i, s in enumerate(shots)]))
    project = composition_from_sequence(source)
    template = project['sections'][0]
    project.update(phrases={}, sections=[], effect_order=['dye_transfer'], timeline_view='shots')
    for i, s in enumerate(shots):
        name = f'shot-{i+1:02}'
        end = shots[i+1]['frame'] if i+1 < len(shots) else HANDOFF_FRAME
        start = s['frame']
        project['phrases'][name] = dict(name=' '.join(s['text'].split()), start=start/FPS, end=end/FPS)
        clip = dict(copy.deepcopy(template), id=name, phrase=name, duration=(end-start)/FPS)
        if s['pulse']:
            clip['automations'] = [dict(id=f'press-{i+1}', path='dye_transfer.scale',
                amount=s['pulse'], enabled=True, easing='smooth', start_fraction=0.,
                attack_fraction=.22, hold_fraction=.08, recovery_fraction=.70)]
        project['sections'].append(clip)
    track = probe_soundtrack(audio_path)
    if track['duration'] < HANDOFF_FRAME/FPS:
        raise ValueError('The bounce must include the whole spoken intro and band entrance.')
    project.update(schema_version=4, soundtrack=track)
    return normalize_composition(project), shots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--save-study', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Keep the editable document independent of Ableton's temporary session.
    media = args.output / 'media'
    media.mkdir(exist_ok=True)
    copied_audio = media / ('Guerrilla-Radio-guide' + args.audio.suffix.lower())
    if args.audio.resolve() != copied_audio.resolve():
        shutil.copy2(args.audio, copied_audio)
    project, shots = composition(copied_audio)
    path = args.output / 'Guerrilla-Radio-spoken-intro.nebula.json'
    portable = copy.deepcopy(project)
    portable['soundtrack']['path'] = copied_audio.relative_to(args.output).as_posix()
    save_composition(path, portable)
    assert load_composition(path) == project
    sequence = compile_composition(project)
    assert round(sequence['duration']*FPS) == HANDOFF_FRAME
    with (args.output/'cuts.csv').open('w') as f:
        writer = csv.writer(f); writer.writerow(['clip','start_frame','start_seconds','end_frame','text','palette'])
        for i, s in enumerate(shots):
            end = shots[i+1]['frame'] if i+1 < len(shots) else HANDOFF_FRAME
            writer.writerow([i+1, s['frame'], f"{s['frame']/FPS:.6f}", end, s['text'].replace('\n',' / '), s['palette']])
    from PIL import Image, ImageDraw, ImageFont
    sheet = Image.new('RGB', (6*234, 6*440), '#15181b')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(ROOT/'assets/fonts/SpaceMono-Bold.ttf'), 13)
    for i, s in enumerate(shots):
        frame = render_sequence_frame(sequence, (s['frame']+.5)/FPS, size=(216,384))
        x,y = (i%6)*234+9,(i//6)*440+8
        sheet.paste(frame,(x,y)); draw.text((x,y+390), f"{i+1:02}  {s['frame']/FPS:.2f}s",font=font,fill='white')
    sheet.save(args.output/'contact-sheet.jpg', quality=90)
    if args.render:
        from synth import default_synth_preset
        from synth_media import export_synth_video
        def progress(done, total):
            if done % 30 == 0 or done == total: print(f'{done}/{total} frames', flush=True)
        export_synth_video(default_synth_preset(), args.output/'Guerrilla-Radio-audio-guide.mp4',
                           sequence=sequence, progress=progress)
        import subprocess
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(args.output/'Guerrilla-Radio-audio-guide.mp4'),
                        '-map','0:v:0','-c:v','copy','-an','-movflags','+faststart',
                        str(args.output/'Guerrilla-Radio-silent.mp4')],check=True)
    if args.save_study:
        from synth_studies import save_study
        identifier = save_study(project, NAME)
        (args.output/'library-id.txt').write_text(identifier+'\n')
        print('Saved study:',identifier,flush=True)
    print(path, flush=True)


if __name__ == '__main__':
    main()
