"""Reference 13: original wording and optical cuts, with a shorter dark interlude.

The renderer contains no montage. These authored, editable source states carry
all wording, palettes, framing and cuts. Reference 1.5–16.5s becomes 3 seconds;
the remainder keeps its original cadence (30 fps, 15 fps film texture).
"""
import math

from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def _frame_lettering(content, size, width, angle, x, y):
    """Author complete lettering with room for this study's optical movement.

    This runs only when building the recipe, not when rendering user edits.
    Include blank lines so the progressive word builds keep their anchors.
    Rotate the Text source itself: a later effect cannot recover glyphs that
    were clipped while drawing the unrotated source into the canvas.
    """
    if not content.strip():
        return size, width, x, y
    w, h, margin = 720, 406, 24
    source_w = width * w
    source_h = size * (content.count('\n') + 1) * h
    a = math.radians(angle)
    c, s = abs(math.cos(a)), abs(math.sin(a))
    rotated_w = source_w * c + source_h * s
    rotated_h = source_w * s + source_h * c
    fit = min(1., (w - 2 * margin) / rotated_w, (h - 2 * margin) / rotated_h)
    limit_x = max(0., (w - 2 * margin - rotated_w * fit) / (2 * w))
    limit_y = max(0., (h - 2 * margin - rotated_h * fit) / (2 * h))
    return size * fit, width * fit, max(-limit_x, min(limit_x, x)), max(-limit_y, min(limit_y, y))


def dye_transfer_composition():
    common={'speed':1.,'depth':0.,'treatment_fps':30,'object_x':0.,'object_y':0.}
    for module in ('text','dye_transfer'):
        common.update({f'{module}.{p.key}':p.default for p in MODULE_BY_ID[module].params})
    common.update({'text.font':1,'text.saturation':0.,'text.brightness':1.,
        'text.back_brightness':0.,'text.fit':2,'text.leading':1.2,'text.tracking':-.012,
        'text.badge':0,'text.reveal':0,'text.motion':0,'text.size':.213,
        'text.block_width':.171,'dye_transfer.cadence':15.,
        'dye_transfer.emulsion':.48,'dye_transfer.streaks':.24,
        'dye_transfer.edge_bloom':.22,'dye_transfer.registration':.32,
        'dye_transfer.focus_flutter':.3,'dye_transfer.grain':.009,
        'dye_transfer.warp':.65,'dye_transfer.wash':.22,
        'dye_transfer.drag':.025,'dye_transfer.drag_mix':.12,
        'dye_transfer.choke':.45})
    states={}; cues=[]

    def shot(t, content='', *, size=.213, width=.171, palette='red', font=1,
             leading=1.2, tracking=-.012, x=0., y=0., angle=0., **finish):
        size, width, x, y = _frame_lettering(content, size, width, angle, x, y)
        values=dict(common)
        values.update({'text.content':content,'text.size':min(1.5,size),'text.stretch_y':max(1.,size/1.5),'text.block_width':max(.05,width),
                       'text.font':font,'text.leading':leading,'text.tracking':tracking,
                       'text.stretch_x':min(1.,width/.05),'text.rotation':angle,
                       'dye_transfer.x':x,'dye_transfer.y':y,'dye_transfer.angle':0.})
        colors={
            'red':dict(paper_hue=.026,paper_saturation=1.,paper_light=1.08,ink_light=.13,ink_saturation=.95),
            'pink':dict(paper_hue=.905,paper_saturation=.77,paper_light=1.08,ink_light=.23,ink_saturation=.95),
            'white':dict(paper_hue=.96,paper_saturation=.025,paper_light=.98,ink_light=.16,ink_saturation=0.,wash=.18,dye=.08,edge_bloom=.72),
            'black':dict(paper_light=.012,ink_light=.9,ink_saturation=.025,grain=.006,wash=.1,dye=0.,emulsion=.28,edge_bloom=.05,erosion=.025),
            'grey':dict(paper_hue=.94,paper_saturation=.055,paper_light=.61,
                        ink_light=.018,ink_saturation=0.,wash=.045,dye=0.,
                        grain=.008,emulsion=.16,streaks=.035,edge_bloom=0.,
                        registration=.12,focus_flutter=.15,erosion=.015),
        }
        values.update({f'dye_transfer.{k}':v for k,v in colors[palette].items()})
        values.update({f'dye_transfer.{k}':v for k,v in finish.items()})
        frame=round(t*30); name=f'impression-{frame:03}'
        states[name]={'preset':'Reference blinds','enabled':['text','dye_transfer'],'overrides':values}
        # Last authored state wins when two events snap to the same output frame.
        cues[:]=[c for c in cues if round(c['time']*30)!=frame]
        cues.append(dict(time=frame/30,state=name,transition='cut'))

    # Four-line opening, with unequal pink/negative exposure switches and focus loss.
    for t,palette,softness in ((0,'pink',.6),(.5,'white',.9),(.6,'pink',1.5),
        (.8,'white',2.8),(.9,'pink',3.8),(1.,'white',4.6),(1.3,'white',5.2)):
        shot(t,'JUST\nONE\nMORE\nTRY',palette=palette,softness=softness,
             drag=.12 if palette=='white' else .015,drag_mix=.25 if palette=='white' else .08,
             registration=.16,edge_bloom=.42 if palette=='white' else .08,
             streaks=.34 if palette=='white' else .16,emulsion=.55,focus_flutter=.2)

    # Keep the character of the long interruption, with fewer dark frames.
    shot(1.5,palette='black')
    shot(1.7,'SOMEONE',size=.75,width=1.6,palette='white',x=-.4,y=-.2,softness=3.)
    shot(1.83,palette='black')
    shot(2.03,'&',size=1.2,width=.7,palette='white',angle=-29.,warp=9.,softness=3.)
    shot(2.17,palette='black')
    # The reference's short wedge/disc/neck flashes, condensed within the
    # existing interruption. Text remains a complete, separately editable source.
    shot(2.27,'JUST ONE\n\n\n\n\nMORE TRY',size=.25,width=.47,palette='grey',
         angle=90.,leading=1.2,softness=2.8,mask_shape=2,mask_size=2.6,
         mask_aspect=.75,mask_y=.15,mask_softness=3.)
    shot(2.37,'JUST ONE\n\n\n\n\nMORE TRY',size=.25,width=.47,palette='grey',
         angle=90.,leading=1.2,softness=2.8,mask_shape=1,mask_size=1.16,
         mask_x=.008,mask_y=.01,mask_softness=3.4)
    shot(2.47,palette='black')
    shot(2.57,palette='grey',mask_shape=3,mask_size=1.18,
         mask_x=.006,mask_y=.04,mask_softness=3.2)
    shot(2.63,palette='grey',mask_shape=1,mask_size=1.16,
         mask_x=.008,mask_y=.01,mask_softness=3.4)
    shot(2.7,'BELIEVE\n& YOU KNOW',size=.7,width=1.2,palette='white',angle=90.,x=.2,softness=2.7)
    shot(2.83,palette='black')
    shot(3.03,'&',size=.18,width=.09,palette='black',x=.18,y=-.2,softness=3.)
    shot(3.17,palette='white',paper_light=.84)
    shot(3.27,palette='grey',paper_light=.38,mask_shape=1,mask_size=.68,
         mask_aspect=1.1,mask_x=.035,mask_y=.03,mask_softness=70.,mask_opacity=.68,
         emulsion=.06,wash=.06)
    shot(3.37,palette='black')
    shot(3.6,'KNOW',size=.9,width=1.4,palette='white',x=-.5,softness=4.)
    shot(3.73,palette='black')
    shot(4.03,'&\nYOU\nKNOW',size=.65,width=.57,angle=90.,y=.1,softness=.9)
    shot(4.17,palette='black')
    shot(4.37,'I',size=.9,width=.065,palette='black',drag=.5,drag_mix=.95,softness=3.,ink_light=.01,halo=2.)

    # Reference closing sequence, shifted twelve seconds earlier.
    def original(t,*args,**kwargs): shot(t-12,*args,**kwargs)
    original(16.5,'I',size=.9,width=.065,palette='black',drag=.5,drag_mix=.95,softness=2.5,ink_light=.01,halo=2.)
    original(16.6,'&\nYOU\nKNOW',size=.65,width=.6,angle=90.,y=.15)
    original(16.77,'I',size=.9,width=.065,palette='black',drag=.5,drag_mix=1.,softness=3.,ink_light=.01,halo=2.)
    original(16.9,'I',size=.19,width=.025,palette='white',font=0,tracking=.12)
    original(17.,'NEED',size=.19,width=.62,palette='white',font=0,tracking=.15)
    original(17.1,'SOMEONE',size=.21,width=.37,y=-.57,drag=.2,drag_mix=.5)
    original(17.27,'SOMEONE\n\n\n',size=.238,width=.355,leading=1.15)
    original(17.5,'SOMEONE\nTO\n\n',size=.238,width=.355,leading=1.15)
    original(17.9,'SOMEONE\nTO\nBELIEVE\n',size=.238,width=.355,leading=1.15)
    original(18.43,'SOMEONE\nTO\nBELIEVE\nIN',size=.238,width=.355,leading=1.15)
    # A few exposed registration slips; avoid perfectly stationary holds.
    original(18.57,'SOMEONE\nTO\nBELIEVE\nIN',size=.238,width=.355,leading=1.15,warp=9.,erosion=.25,softness=1.1,shutter=-.08,registration=.7)
    original(18.67,'SOMEONE\nTO\nBELIEVE\nIN',size=.238,width=.355,leading=1.15)
    original(19.5,'&',size=.55,width=.10,palette='black',x=-.44)
    original(19.67,'& YOU',size=.55,width=.48,palette='black',x=-.25)
    original(19.9,'& YOU KNOW',size=.55,width=.98,palette='black')
    original(20.07,'& YOU KNOW',size=.55,width=.98,palette='black',warp=12.,erosion=.04,shutter=.22,registration=.8)
    original(20.3,'& YOU KNOW',size=.38,width=1.5,font=0,x=-.32,drag=.3,shutter=-.4,streaks=.7)
    original(20.5,'I\n\n',size=.27,width=.025,font=0,x=-.21,leading=1.7)
    original(20.6,'I NEED\n\n',size=.25,width=.445,font=0,leading=1.7,tracking=.14,y=-.025,choke=1.5)
    original(20.83,'I NEED\nSOMEONE\n',size=.27,width=.65,font=0,leading=1.7,tracking=.1,x=-.1,softness=1.6)
    original(21.,'I NEED\nSOMEONE TO\n',size=.25,width=.82,font=0,leading=1.7,tracking=.14,y=-.025,choke=1.5)
    original(21.4,'I NEED\nSOMEONE TO\nBELIEVE',size=.25,width=.82,font=0,leading=1.7,tracking=.14,y=-.025,choke=1.5)
    original(22.,'I NEED\nSOMEONE TO\nBELIEVE IN',size=.25,width=.82,font=0,leading=1.7,tracking=.14,y=-.025,choke=1.5)
    original(23.07,'TO',size=.27,width=.30,font=0,tracking=.28,x=-.36)
    original(23.3,'&\nYOU\nKNOW',size=.6,width=.6,angle=90.,x=-.2,y=.5)
    original(23.5,'YOU',size=.30,width=.7,font=0,tracking=.2,palette='pink',drag=.2,drag_mix=.45,warp=3.,wash=.38,erosion=.12,shutter=-.8,streaks=.85,registration=.4,emulsion=.65)
    original(23.7,'KNOW',size=.9,width=.98,palette='pink',warp=6.,dye=.7)
    original(23.9,'SOMEONE\nTO',size=.55,width=.95,y=.2,dye=.8)
    original(24.1,'I NEED',size=.24,width=.44,x=.18,palette='white',drag=.45,drag_mix=.7,wash=.32,shutter=.25,streaks=.9,registration=.2,edge_bloom=.25)
    original(24.5,'S',size=.55,width=.14,x=-.44)
    original(24.6,'SO',size=.55,width=.27,x=-.37)
    original(24.7,'SOM',size=.55,width=.47,x=-.27)
    original(24.83,'SOME',size=.55,width=.60,x=-.2)
    original(24.93,'SOMEONE',size=.55,width=.98)
    original(25.1,'TO',size=.25,width=.32,font=0,tracking=.3,erosion=.5,warp=5.)
    original(25.3,'BELIEVE',size=.58,width=1.1,paper_light=.06,ink_light=1.,ink_hue=.025,ink_saturation=1.,softness=1.8,drag_mix=.5)
    original(25.47,'MORE',size=1.6,width=1.5,x=-.2)
    original(25.57,'YOU',size=.85,width=1.5,x=.55,y=.16,font=0,tracking=.2,erosion=.3,warp=7.,drag=.5,drag_mix=.6,wash=.6,shutter=-.8,streaks=.65,registration=1.,softness=2.6,emulsion=.8)
    original(25.73,'BELIEVE',size=1.05,width=1.55,x=-.12,paper_light=.04,ink_light=1.,ink_hue=.025,ink_saturation=1.)
    original(25.93,'IN',size=.2,width=.13,font=0)
    original(26.47,'IN',size=.18,width=.12,font=0,warp=12.,erosion=.8,y=.07,x=.15)
    original(26.67,'IN',size=.2,width=.16,font=0,angle=-22.,warp=10.,erosion=.7,x=.32,y=.35,palette='white',paper_hue=.025,paper_saturation=1.)
    original(26.87,'&\n\n',size=.31,width=.24,leading=1.12,palette='white')
    original(27.07,'&\nYOU\n',size=.31,width=.24,leading=1.12,palette='white')
    original(27.4,'&\nYOU\nKNOW',size=.31,width=.29,leading=1.12,palette='white')
    seq=normalize_sequence(dict(schema_version=1,render_version=2,name='Text / one more try',
        duration=473/30,fps=30,seed=261027,canvas={'width':720,'height':406,'framing':'native'},
        states=states,cues=sorted(cues,key=lambda c:c['time'])))
    project=composition_from_sequence(seq)
    project['phrases']['custom']['name']='One more try / dye-transfer montage'
    project['effect_order']=['dye_transfer']
    return normalize_composition(project)
