#!/usr/bin/env python3
"""Summarize completed audit runs without combining diagnostic and normal samples."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import pstats
import statistics


def stats(values):
    """Nearest-rank p95; retain individual observations separately."""
    values = sorted(values)
    if not values:
        return {'n': 0}
    return {'n': len(values), 'median': statistics.median(values),
            'p95': values[max(0, math.ceil(.95 * len(values)) - 1)],
            'min': values[0], 'max': values[-1]}


def summarize(folder):
    events = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
    complete = bool(events and events[-1]['kind'] == 'done')
    samples_path = folder / 'samples.json'
    samples = json.loads(samples_path.read_text()) if samples_path.exists() else []
    groups = defaultdict(list)
    for sample in samples:
        if 'paint_ms' in sample:
            groups[sample['scenario']].append(sample)
    result = {'completed': complete,
              'config': next((e for e in events if e['kind'] == 'run_config'), None),
              'scenarios': {name: {'paint_ms': stats([s['paint_ms'] for s in group]),
                                   'sync_ms': stats([s['sync_ms'] for s in group if 'sync_ms' in s]),
                                   'samples': group} for name, group in groups.items()},
              'preparation': [e for e in events if e['kind'] in ('preparation', 'public_preparation', 'video_import')],
              'references': [e for e in events if e['kind'] == 'reference'],
              'session': [e for e in events if e['kind'] in ('session_start', 'session_end', 'session_action')]}
    memories = [e for e in events if e['kind'] == 'memory']
    if memories:
        result['memory_kib'] = {'first': memories[0], 'last': memories[-1],
                                'own_peak': max(e['rss_kib'] for e in memories),
                                'children_peak': max(e['children_rss_kib'] for e in memories)}
    pulses = [e for e in events if e['kind'] == 'event_loop']
    result['event_loop_gap_ms'] = stats([e['gap_ms'] for e in pulses])
    session_start = next((e['t'] for e in events if e['kind'] == 'session_start'), None)
    session_end = next((e['t'] for e in events if e['kind'] == 'session_end'), None)
    if session_start is not None and session_end is not None:
        result['session_gap_ms'] = stats([e['gap_ms'] for e in pulses if session_start <= e['t'] <= session_end])
        result['session_memory'] = [e for e in memories if session_start <= e['t'] <= session_end]
    caches = [e for e in events if e['kind'] == 'cache']
    result['cache'] = {'peak_with_reservations': max((e['bytes'] + e['reserved'] for e in caches), default=0),
                       'violations': [e for e in caches if e['bytes'] + e['reserved'] > e['budget']]}
    workers = [e for e in events if e['kind'] == 'worker_end']
    result['workers'] = {name: stats([(e['end']-e['start'])*1000 for e in workers if e['name'] == name])
                         for name in ('RenderJob', 'PreparePreviewJob')}
    result['cancelled_workers'] = [e for e in workers if e['cancelled']]
    if (folder / 'run.prof').exists():
        result['profile_note'] = 'Nested cumulative costs overlap; do not sum.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, nargs='?', default=Path(__file__).resolve().parents[1] / 'output/preview-performance-audit')
    args = parser.parse_args()
    excluded_path=args.root/'excluded-runs.json'
    excluded=json.loads(excluded_path.read_text()) if excluded_path.exists() else {}
    result = {}
    for folder in sorted(args.root.iterdir()):
        if folder.is_dir() and (folder / 'events.jsonl').exists():
            result[folder.name] = summarize(folder)
            result[folder.name]['excluded_reason']=excluded.get(folder.name)
            result[folder.name]['valid_baseline']=result[folder.name]['completed'] and folder.name not in excluded
            print(folder.name, 'complete' if result[folder.name]['completed'] else 'INCOMPLETE',
                  {k: round(v['paint_ms']['median'], 1) for k, v in result[folder.name]['scenarios'].items()})
    (args.root / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    for folder in sorted(args.root.iterdir()):
        profiles = list(folder.glob('*.prof')) if folder.is_dir() else []
        if not profiles:
            continue
        with (folder / 'profiles.txt').open('w') as stream:
            for path in sorted(profiles):
                print('\n', path.name, file=stream)
                pstats.Stats(str(path), stream=stream).strip_dirs().sort_stats('cumulative').print_stats(35)
                pstats.Stats(str(path), stream=stream).strip_dirs().sort_stats('tottime').print_stats(20)


if __name__ == '__main__':
    main()
