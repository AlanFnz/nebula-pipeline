"""Source explanations use the same clocks and end behavior as playback."""
import copy

import pytest

from synth_section_sources import video_source_at
from synth_video_summary import section_playback_summary


def sequence(end_mode='hold', rate=1.):
    return dict(duration=30., footage=dict(path='/clips/portrait.mp4',
        **{'in': 0., 'out': 10., 'end_mode': end_mode}),
        time_map=[dict(start=0., end=30., video_start=0., video_rate=rate)])


@pytest.mark.parametrize('start,duration,rate,mode,expected', [
    (0., 7., 1., 'hold', 'Plays source 00:00.00 → 00:07.00.'),
    (7., 7., 1., 'hold', 'Plays source 00:07.00 → 00:10.00, then holds the last frame for 4.00s.'),
    (0., 7., 2., 'hold', 'Plays source 00:00.00 → 00:10.00, then holds the last frame for 2.00s.'),
    (12., 7., 1., 'hold', 'Holds the last frame for 7.00s.'),
    (7., 7., 1., 'loop', 'then repeats the source range; ends at 00:04.00.'),
    (0., 20., 1., 'loop', 'then repeats the source range; ends at 00:10.00.'),
])
def test_actual_source_offsets_speed_hold_and_loop(start, duration, rate, mode, expected):
    seq = sequence(mode, rate); before = copy.deepcopy(seq)
    text, details = section_playback_summary(seq, start, duration)
    assert f'Clip length: {duration:.2f}s · Speed: {rate:.2f}×' in text
    assert expected in text and expected in details
    assert video_source_at(seq, start)[1] == start * rate
    assert seq == before


def test_trim_in_is_added_to_source_clock_and_repeats_are_explicit():
    seq = sequence(); seq['footage'].update({'in': 3., 'out': 13.})
    text, _ = section_playback_summary(seq, 2., 7., repeated=True)
    assert 'first play' in text and 'Plays source 00:05.00 → 00:12.00.' in text


def test_detailed_import_retains_clock_boundaries_in_explanation():
    seq = sequence(); seq['footage']['out'] = 30.
    seq['time_map'] = [dict(start=0., end=5., video_start=0., video_rate=2.),
                       dict(start=5., end=30., video_start=10., video_rate=.5)]
    text, _ = section_playback_summary(seq, 4., 4.)
    assert 'Speed: varies' in text
    assert '00:08.00 → 00:10.00' in text and '00:10.00 → 00:11.50' in text
    assert video_source_at(seq, 4.)[1] == 8.
    assert video_source_at(seq, 7.)[1] == 11.


def test_multiple_sources_and_long_imports_are_bounded():
    seq = sequence()
    seq['video_segments'] = [dict(start=float(i), end=float(i+1), video_start=0., video_rate=1.,
        footage=dict(seq['footage'], path=f'/clips/source-{i}.mp4')) for i in range(30)]
    text, tooltip = section_playback_summary(seq, 0., 30.)
    assert 'source-0.mp4: Plays source' in text
    assert '27 more source intervals' in text and '18 further source intervals' in tooltip
    assert 'source-29.mp4:' not in tooltip
