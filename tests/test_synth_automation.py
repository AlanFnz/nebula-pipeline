import copy
import numpy as np
import pytest
from nebula.documents.synth_automation import normalize_automations, envelope, absolute_event, apply_automations
from nebula.documents.synth_composition import blank_composition, normalize_composition, compile_composition, composition_from_sequence, stretch_section, save_composition, load_composition
from nebula.documents.synth_sequence import normalize_sequence, resolve_sequence_frame, render_sequence_frame, save_sequence, load_sequence

def gesture(**values):
    return dict(id='gesture', path='bloom.strength', amount=0.8, enabled=True, easing='linear', start_fraction=0.4, attack_fraction=0.02, hold_fraction=0.02, recovery_fraction=0.06, **values)

def project():
    p = blank_composition()
    p['sections'][0]['duration'] = 10.0
    p['source']['states']['blank']['enabled'] = ['slab', 'bloom']
    p['sections'][0]['automations'] = [gesture()]
    return p

def value(seq, t, path='bloom.strength'):
    preset = resolve_sequence_frame(seq, t)[-1]
    module, key = path.split('.')
    return next((m for m in preset['modules'] if m['id'] == module))['params'][key]
