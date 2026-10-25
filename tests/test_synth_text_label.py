"""Label geometry, optional outlines and compatibility with the FAC51 layout."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from synth import MODULE_BY_ID
from synth_composition import compile_composition, load_composition, save_composition
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_text import badge_mask, glyph_mask


@pytest.mark.parametrize('subtitle', ['', 'THE HAÇIENDA'])
@pytest.mark.parametrize('border', [0., .009, .022])
def test_label_defaults_match_original_mask(subtitle, border):
    main = glyph_mask('FAC51', 5, .065, 1., 1, weight=500)
    expected = Image.new('L', (1000, 460))
    if border:
        ImageDraw.Draw(expected).rounded_rectangle((10,10,990,450), radius=7,
                                                   outline=255, width=max(1,round(border*1000)))
    expected.paste(main.resize((800,200), Image.Resampling.LANCZOS), (100,91))
    if subtitle:
        sub = glyph_mask(subtitle,5,.12,1.,1,weight=650)
        expected.paste(sub.resize((780,60), Image.Resampling.LANCZOS), (110,326))
    assert badge_mask(main,subtitle,5,500,border).tobytes() == expected.tobytes()


def test_none_hides_only_frame_and_padding_axes_are_independent():
    main = Image.new('L',(800,200),255)
    bare = badge_mask(main,'',0,400,0.)
    none = badge_mask(main,'',0,400,.022,shape=5)
    assert none.tobytes() == bare.tobytes()
    wide = badge_mask(main,'',0,400,0.,padding_x=140.)
    tall = badge_mask(main,'',0,400,0.,padding_y=122.5)
    assert wide.size == (bare.width+100,bare.height)
    assert tall.size == (bare.width,bare.height+100)
    assert wide.getbbox() == tuple(v+d for v,d in zip(bare.getbbox(),(50,0,50,0)))
    assert tall.getbbox() == tuple(v+d for v,d in zip(bare.getbbox(),(0,50,0,50)))


@pytest.mark.parametrize('shape',range(6))
def test_multiline_label_stays_bounded_for_all_shapes(shape):
    wording='\n'.join(['REVOLUTION']*8)
    main=glyph_mask(wording,0,0.,1.,1)
    label=badge_mask(main,wording,0,400,.08,shape=shape,main_lines=8,
                     padding_x=300.,padding_y=300.,gap=200.,subtitle_scale=.6)
    assert max(label.size)<=4096 and label.getbbox()
    if shape in (2,3,4): assert label.width==label.height


def test_natural_label_preserves_type_proportions_and_omits_empty_subtitle_space():
    main=Image.new('L',(20,100),255)
    label=badge_mask(main,'',0,400,0.,keep_proportions=True)
    x0,y0,x1,y1=label.getbbox()
    assert (x1-x0,y1-y0)==(40,200)
    assert label.height==365  # main + padding + outer safety margin, no lower line
    with_subtitle=badge_mask(main,'TWO\nLINES',0,400,0.,keep_proportions=True)
    assert with_subtitle.height>label.height


def test_shape_outline_geometry_and_zero_border():
    blank=Image.new('L',(800,200))
    for shape in (1,2,3,4):
        label=badge_mask(blank,'',0,400,.022,shape=shape)
        assert np.asarray(label).max()==255
        assert not badge_mask(blank,'',0,400,0.,shape=shape).getbbox()
    circle=badge_mask(blank,'',0,400,.022,shape=2)
    assert circle.getpixel((circle.width//2,10))==255
    assert circle.getpixel((10,10))==0


def test_new_label_controls_survive_document_reload(tmp_path):
    p=starter_composition('text-contact-film')
    p['effects']['text']={'mode':'recipe','params':{
        'text.content':'REVOLUTION\nIS NOW', 'text.badge_subtitle':'TWO\nLINES',
        'text.badge_shape':2, 'text.badge_padding_x':35., 'text.badge_padding_y':25.,
        'text.badge_type_fit':1, 'text.badge_gap':20., 'text.badge_subtitle_scale':.2}}
    original=render_sequence_frame(compile_composition(p),2.08,(192,144))
    save_composition(tmp_path/'circle.json',p)
    loaded=load_composition(tmp_path/'circle.json')
    assert render_sequence_frame(compile_composition(loaded),2.08,(192,144)).tobytes()==original.tobytes()
    assert all(key.split('.')[1] in {spec.key for spec in MODULE_BY_ID['text'].params}
               for key in loaded['effects']['text']['params'])
