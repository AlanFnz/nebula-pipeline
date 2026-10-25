"""FAC51 contact-print study: 39 authored exposures at 12 fps."""
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def contact_print_composition():
    enabled=('text','contact_print')
    common={'speed':1.,'depth':0.,'treatment_fps':12}
    for module in enabled:
        common.update({f'{module}.{s.key}':s.default for s in MODULE_BY_ID[module].params})
    common.update({'text.content':'FAC51','text.font':5,'text.weight':500,
        'text.size':.322,'text.saturation':0.,'text.back_brightness':0.,
        'text.tracking':.065,'text.badge':1,'text.badge_subtitle':'THE HAÇIENDA',
        'contact_print.grain':.19, 'contact_print.dust':.48, 'contact_print.roughness':.22,
        'contact_print.gate_softness':.07, 'contact_print.softness':1.2})
    # Opening, exposure, light X/Y, positive, erosion, gate X, scale.
    exposures=[
        (.58,.85,.47,.86,1,.88,.49,1.05),(.76,1.02,.58,.66,1,.65,.56,1.08),
        (.8,1.3,.58,.64,1,.45,.55,1.08),(.8,.03,.6,.5,.9,.7,.56,1.04),
        (.75,.02,.6,.5,.8,.5,.52,1.),(.98,1.05,.37,.68,1,.65,.46,.9),
        (.94,.6,.55,.6,1,.5,.56,.9),(.94,.05,.5,.5,1,.15,.56,.9),
        (1.,1.35,.55,.6,1,.2,.50,.9),(1.,1.45,.52,.6,1,.15,.46,.9),
        (1.,1.4,.41,.6,1,.7,.46,.94),(.72,.02,.5,.5,1,.88,.47,1.),
        (.7,.01,.5,.5,1,.87,.47,1.),(.96,.03,.5,.6,0,.0,.47,1.),
        (1.,.03,.5,.6,0,.0,.48,1.),(0,0,.5,.5,0,0,.5,1.),
        (0,0,.5,.5,0,0,.5,1.),(0,0,.5,.5,0,0,.5,1.),
        (0,0,.5,.5,0,0,.5,1.),(.32,1.,.48,.9,0,0,.4,1.),
        (.92,2.1,.35,.68,0,0,.46,1.02),(.7,1.4,.4,.73,0,0,.44,1.),
        (.58,.03,.5,.5,0,.2,.48,1.),(.98,.03,.5,.5,0,0,.48,1.),
        (.98,2.,.53,.95,0,.12,.48,1.02),(1.,2.2,.38,.5,0,.12,.5,1.02),
        (1.,2.3,.38,.54,0,.13,.5,1.02),(1.,1.9,.4,.62,0,.13,.5,1.02),
        (1.,.4,.4,.55,0,.05,.5,1.02),(1.,2.3,.35,.5,0,.1,.5,1.02),
        (1.,2.4,.35,.65,0,.15,.5,1.02),(1.,2.,.4,.65,0,.08,.5,1.02),
        (1.,1.2,.45,.6,0,.07,.5,1.02),(1.,1.1,.44,.65,0,.05,.5,1.02),
        (1.,1.2,.48,.6,0,.1,.5,1.02),(.4,.1,.3,.7,0,.3,.4,1.),
        (0,0,.5,.5,0,0,.5,1.),(.65,.0,.5,.5,0,0,.44,1.),
        (.34,.2,.5,.5,0,0,.42,1.),
    ]
    states={}; cues=[]
    keys=('opening','exposure','leak_x','leak_y','positive','erosion','gate_x','scale')
    for frame,values in enumerate(exposures):
        settings=dict(common)
        settings.update({f'contact_print.{k}':v for k,v in zip(keys,values)})
        settings['contact_print.ink_lift']=.02 if frame<25 else .75
        settings['contact_print.density']=.98 if frame in (0,11,12,19,22,35) else (.4 if frame in (1,2,3,4) else 0.)
        if frame in (0,11,12): settings['contact_print.brightness']=.2
        if frame<13:
            settings['text.badge_border']=.009
            settings['text.badge_subtitle']=''
        if frame==0: settings.update({'text.badge_border':0.,'contact_print.ink_density':.35})
        if frame in (1,2): settings['contact_print.leak_width']=.4
        if frame in (3,4): settings['contact_print.positive']=.3
        if frame in (11,12): settings['contact_print.erosion']=.8
        if frame in (7,8,9): settings['contact_print.erosion']=.1
        if frame>=24:
            settings['contact_print.erosion']=.05
            settings['contact_print.edge_dye']=.85 if frame not in (28,32,33,34) else .15
        if frame in (1,2,8,9,10): settings['contact_print.exposure']*=.8
        if frame==19:
            settings.update({'contact_print.gate_height':.55,'contact_print.gate_y':.78,'contact_print.gate_x':.55})
        if frame in (21,22,35): settings['contact_print.gate_width']=1.4
        if frame==20:
            settings.update({'contact_print.shutter':.1,'contact_print.shutter_x':.43,'contact_print.shutter_angle':19.,'contact_print.light_hue':.12})
        if frame==21:
            settings.update({'contact_print.shutter':.65,'contact_print.shutter_x':.88,'contact_print.shutter_angle':0.,'contact_print.light_hue':.08})
        if frame in (13,14): settings.update({'contact_print.opening':.90,'contact_print.gate_x':.45})
        if frame in (11,12): settings['contact_print.positive']=.45
        settings['contact_print.melt']=2.8 if frame<13 else (.8 if frame>=24 else .6)
        settings['contact_print.leak_height']=.5 if frame in (0,19,24) else 1.2
        settings['contact_print.neighbor']=1. if 1<=frame<=10 else 0.
        if frame in (19,21,22,35): settings['contact_print.gate_angle']=(-18 if frame!=35 else 12)
        if frame>=37:
            settings.update({'text.opacity':0.,'contact_print.gate_height':.35 if frame==37 else 1.5,
                             'contact_print.gate_y':.45,'contact_print.gate_angle':12 if frame==37 else 23})
        name=f'exposure-{frame:02}'
        states[name]={'preset':'Reference blinds','enabled':list(enabled),'overrides':settings}
        cues.append({'time':frame/12,'state':name,'transition':'cut'})
    seq=normalize_sequence(dict(schema_version=1,render_version=2,name='Text / FAC51 contact film',
        duration=3.25,fps=12,seed=251012,canvas={'width':956,'height':720,'framing':'native'},
        states=states,cues=cues))
    project=composition_from_sequence(seq)
    project['phrases']['custom']['name']='FAC51 / positive / blackout / negative'
    return normalize_composition(project)
