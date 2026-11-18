"""Pitch and editable sequence contracts, shared by UI and both audio paths."""
import math

DIVISIONS = {'1/4': 1., '1/8': .5, '1/16': .25, '1/8T': 1/3, '1/16T': 1/6}
NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
SOLFEGE = ('Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si')


def note_frequency(note): return 440. * 2 ** ((note - 69) / 12)
def frequency_note(hz): return round(69 + 12 * math.log2(hz / 440.))
def note_name(note): return NOTE_NAMES[note % 12] + str(note // 12 - 1)


def snapped_frequency(hz, low, high):
    note = min(math.floor(69 + 12 * math.log2(high / 440.) + 1e-9),
               max(math.ceil(69 + 12 * math.log2(low / 440.) - 1e-9), frequency_note(hz)))
    return note_frequency(note)


def sequence_defaults():
    motif = (12, 15, 19, 17, 12, 19, 15, 22)
    return dict(arp_mode='visual', sequence_trigger='gesture', bpm=120., subdivision='1/16',
                sequence_length=8, sequence=[dict(enabled=True, semitones=motif[i % 8],
                velocity=.85 if i % 4 == 0 else .65, gate=.7) for i in range(16)])


def normalize_sequence_controls(raw, number):
    out = sequence_defaults()
    for key, allowed in (('arp_mode', ('visual', 'sequence')),
                         ('sequence_trigger', ('gesture', 'loop')),
                         ('subdivision', tuple(DIVISIONS))):
        out[key] = raw.get(key, out[key])
        if out[key] not in allowed: raise ValueError(f'Choose a supported {key}')
    out['bpm'] = number(raw.get('bpm', out['bpm']), 'BPM', 30., 240.)
    out['sequence_length'] = raw.get('sequence_length', out['sequence_length'])
    if type(out['sequence_length']) is not int or not 1 <= out['sequence_length'] <= 16:
        raise ValueError('Sequence length must be 1–16 steps')
    entries = raw.get('sequence', out['sequence'])
    if not isinstance(entries, list) or len(entries) != 16:
        raise ValueError('The sequencer needs 16 stored steps')
    out['sequence'] = []
    for entry in entries:
        if not isinstance(entry, dict) or type(entry.get('enabled')) is not bool:
            raise ValueError('Step enabled must be a checkbox')
        offset = entry.get('semitones')
        if type(offset) is not int or not -12 <= offset <= 24:
            raise ValueError('Step pitch must be -12 to +24 semitones')
        out['sequence'].append(dict(enabled=entry['enabled'], semitones=offset,
            velocity=number(entry.get('velocity'), 'step velocity', 0., 1.),
            gate=number(entry.get('gate'), 'step gate', .1, 1.)))
    return out


def step_seconds(config): return 60. / config['bpm'] * DIVISIONS[config['subdivision']]


def sequence_phrase(config, start, motion, phrase, end, include_rests=False):
    step = step_seconds(config)
    notes = []
    for j, entry in enumerate(config['sequence'][:config['sequence_length']]):
        time = start + j * step
        if time >= end: break
        if not include_rests and (not entry['enabled'] or not entry['velocity']): continue
        notes.append(dict(time=float(time), semitones=entry['semitones'],
                          duration=step * entry['gate'], velocity=entry['velocity'] * (.85 + .15 * motion),
                          pan=-.22 if (j + phrase) % 2 == 0 else .22, step=j))
    return notes
