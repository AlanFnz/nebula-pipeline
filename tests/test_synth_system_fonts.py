"""Installed font identity, exact rendering, all text studies and missing faces."""
import copy
import json
from pathlib import Path
import shutil
import sys

import pytest
from synth_fonts import (FONT_ROOT, FontUnavailable, clear_font_catalog, load_font,
                         reference_for_face, system_catalog, validate_font)
from synth_text import glyph_mask
from synth_starters import STARTERS, starter_composition
from synth_composition import compile_composition, load_composition, save_composition
from synth_sequence import render_sequence_frame, _interpolate_presets
from synth_effects import normalize_effects, describe_effects
from synth import default_synth_preset, normalize_synth

TEXT_STUDIES = [key for key, _, _ in STARTERS if key.startswith('text-')]


@pytest.fixture
def external_font(tmp_path):
    path = tmp_path/'External.ttf'; shutil.copyfile(FONT_ROOT/'SpaceMono-Bold.ttf', path)
    row = dict(path=str(path), postscript='SpaceMono-Bold', family='Space Mono', style='Bold')
    return reference_for_face(row)


def test_exact_external_face_matches_bundled_bytes(external_font):
    assert glyph_mask('REVOLUTION\nis NOW', external_font, .02, 1., 1).tobytes() == glyph_mask('REVOLUTION\nis NOW', 2, .02, 1., 1).tobytes()
    assert load_font(external_font, 64).getname() == ('Space Mono', 'Bold')


@pytest.mark.parametrize('value', [True, -1, 6, .5, float('inf'), {}, '', 'Arial', '{}', '{"version":1}', 'x'*17000])
def test_bad_font_references_rejected(value):
    with pytest.raises(ValueError): validate_font(value)
    with pytest.raises(ValueError): normalize_effects({'text':{'params':{'text.font':value}}})


def test_missing_or_changed_file_never_uses_cached_pixels_or_substitution(external_font, monkeypatch):
    monkeypatch.setattr('synth_fonts.system_catalog', lambda: ())
    path = Path(json.loads(external_font)['path']); original = path.read_bytes()
    glyph_mask('NOW',external_font,0.,1.,1)  # Prime both glyph and file caches.
    path.write_bytes((FONT_ROOT/'Anton-Regular.ttf').read_bytes())
    with pytest.raises(FontUnavailable): glyph_mask('NOW',external_font,0.,1.,1)
    path.write_bytes(original); path.unlink()
    with pytest.raises(FontUnavailable): glyph_mask('NOW',external_font,0.,1.,1)


def test_identical_file_can_relocate_but_different_version_cannot(external_font, tmp_path, monkeypatch):
    data=json.loads(external_font); moved=tmp_path/'Moved.ttf'; Path(data['path']).rename(moved)
    monkeypatch.setattr('synth_fonts.system_catalog', lambda: (dict(path=str(moved),postscript=data['postscript']),))
    clear_font_catalog()
    assert load_font(external_font,64).getname()==('Space Mono','Bold')
    moved.write_bytes((FONT_ROOT/'Anton-Regular.ttf').read_bytes())
    with pytest.raises(FontUnavailable): load_font(external_font,64)


def test_named_variable_styles_keep_native_weight():
    def face(style):
        return reference_for_face(dict(path=str(FONT_ROOT/'Fredoka.ttf'),postscript='Fredoka-'+style,family='Fredoka',style=style))
    light,bold=face('Light'),face('Bold')
    a=glyph_mask('NOW',light,0.,1.,1,weight=900)
    b=glyph_mask('NOW',bold,0.,1.,1,weight=400)
    assert a.tobytes()!=b.tobytes()
    assert a.tobytes()==glyph_mask('NOW',light,0.,1.,1,weight=400).tobytes()


@pytest.mark.parametrize('key',TEXT_STUDIES)
def test_every_text_study_accepts_system_fonts_and_round_trips(key,external_font,tmp_path):
    c=starter_composition(key); original=copy.deepcopy(c)
    c['effects']['text']={'mode':'recipe','params':{'text.font':external_font}}
    seq=compile_composition(c)
    summary=describe_effects(seq['states'].values())
    assert summary['text']['ranges']['text.font']==(external_font,external_font)
    frame=render_sequence_frame(seq,seq['duration']*.44,(128,96))
    path=tmp_path/'saved.json';save_composition(path,c)
    assert render_sequence_frame(compile_composition(load_composition(path)),seq['duration']*.44,(128,96)).tobytes()==frame.tobytes()
    assert starter_composition(key)==original


def test_font_transitions_and_mixed_inspector_ranges_are_discrete(external_font):
    a=default_synth_preset();b=copy.deepcopy(a)
    next(m for m in b['modules'] if m['id']=='text')['params']['font']=external_font
    b=normalize_synth(b)
    for amount,expected in ((.49,0),(.51,external_font)):
        result=_interpolate_presets(a,b,amount)
        assert next(m for m in result['modules'] if m['id']=='text')['params']['font']==expected
    c=compile_composition(starter_composition('text-phosphor'))
    states=[dict(next(iter(c['states'].values())),overrides={'text.font':v}) for v in (0,external_font)]
    assert describe_effects(states)['text']['ranges']['text.font']==(0,external_font)


def test_variable_font_rejects_invalid_axis_coordinates():
    value=reference_for_face(dict(path=str(FONT_ROOT/'Fredoka.ttf'),postscript='Fredoka-Bold',family='Fredoka',style='Bold'))
    data=json.loads(value);data['axes']['wght']=1e100
    with pytest.raises(FontUnavailable):load_font(json.dumps(data),64)


@pytest.mark.parametrize('effect,path', [('stretch_echo','stretch_echo.typeface'),('optical_print','optical_print.fragment_typeface')])
def test_secondary_typefaces_accept_system_faces(effect,path,external_font):
    c=starter_composition('text-opium' if effect=='stretch_echo' else 'text-dark-print')
    c['effects'][effect]={'mode':'on','params':{path:external_font}}
    assert render_sequence_frame(compile_composition(c),1.3,(128,96)).getbbox()


@pytest.mark.skipif(sys.platform!='darwin',reason='Core Text native catalog')
def test_native_catalog_maps_ttc_faces_and_styles():
    rows=system_catalog();assert rows
    refs=[reference_for_face(next(r for r in rows if r['family']=='Helvetica Neue' and r['style']==style)) for style in ('Regular','Bold','Italic')]
    assert len({json.loads(r)['index'] for r in refs})==3
    assert len({glyph_mask('Aa NOW',r,0.,1.,1).tobytes() for r in refs})==3
