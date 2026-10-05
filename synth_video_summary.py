"""Read-only explanations of the compiled footage clocks shown in Source."""
import math
from pathlib import Path


def source_time_label(seconds):
    hundredths = round(max(0., seconds) * 100)
    minutes, remainder = divmod(hundredths, 6000)
    return f'{minutes:02d}:{remainder / 100:05.2f}'


def _interval_text(footage, elapsed, rate, duration):
    first, last = footage['in'], footage['out']
    span = last - first
    end = elapsed + duration * rate
    if footage['end_mode'] == 'hold':
        if elapsed >= span - 1e-9:
            return f'Holds the last frame for {duration:.2f}s.'
        text = f'Plays source {source_time_label(first + elapsed)} → {source_time_label(first + min(end, span))}'
        if end > span + 1e-9:
            text += f', then holds the last frame for {(end - span) / rate:.2f}s'
        return text + '.'
    offset = elapsed % span
    if offset + duration * rate <= span + 1e-9:
        return f'Plays source {source_time_label(first + offset)} → {source_time_label(first + min(offset + duration * rate, span))}.'
    final = end % span
    if math.isclose(final, 0., abs_tol=1e-9) or math.isclose(final, span, abs_tol=1e-9): final = span
    return (f'Plays source {source_time_label(first + offset)} → {source_time_label(last)}, '
            f'then repeats the source range; ends at {source_time_label(first + final)}.')


def section_playback_summary(sequence, start, duration, *, repeated=False):
    """Describe one base play, respecting detailed imports and inherited clocks.

    Endpoints describe the source interval, not the last sampled/held frame.
    Repeated shared clips may have different source offsets on later plays.
    """
    clocks = sequence.get('video_segments') or sequence.get('time_map') or [
        dict(start=0., end=sequence['duration'], video_start=0., video_rate=1.)]
    rows = []; rates = []
    for clock in clocks:
        left, right = max(start, clock['start']), min(start + duration, clock['end'])
        if right <= left + 1e-10: continue
        footage = clock.get('footage', sequence.get('footage'))
        if not footage: continue
        rate = clock['video_rate']
        elapsed = clock['video_start'] + (left - clock['start']) * rate
        rows.append((footage, _interval_text(footage, elapsed, rate, right - left)))
        rates.append(rate)
    speed = f'{rates[0]:.2f}×' if rates and all(math.isclose(rate, rates[0], rel_tol=1e-9) for rate in rates) else 'varies'
    heading = f'Clip length: {duration:.2f}s · Speed: {speed}'
    if repeated: heading += ' · first play'
    # Long imported sequences should not create an enormous inspector label.
    multiple = len(rows) > 1
    descriptions = [(Path(footage['path']).name + ': ' if multiple else '') + text for footage, text in rows]
    visible = descriptions[:3]
    if len(descriptions) > 3: visible.append(f'{len(descriptions) - 3} more source intervals; see tooltip.')
    details = descriptions[:12]
    if len(descriptions) > 12: details.append(f'{len(descriptions) - 12} further source intervals.')
    return heading + '\n' + '\n'.join(visible), '\n'.join(details)
