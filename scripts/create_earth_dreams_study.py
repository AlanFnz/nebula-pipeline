#!/usr/bin/env python3
"""Editable 7.6-second dye-print study; no reference footage is used to render."""
from pathlib import Path
import argparse, copy, json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition, save_composition
from synth_sequence import normalize_sequence
FPS=30
FRAMES=228

def composition(calibration=False):
    common={'speed':1.,'depth':0.,'treatment_fps':30,'object_x':0.,'object_y':0.}
    for mod in ('text','dye_transfer'):
        common.update({f'{mod}.{p.key}':p.default for p in MODULE_BY_ID[mod].params})
    common.update({'text.font':1,'text.content':'','text.saturation':0.,'text.brightness':1.,
      'text.back_brightness':0.,'text.fit':2,'text.leading':1.05,'text.tracking':.008,
      'text.reveal':0,'text.motion':0,'text.badge':0,'text.align':1,
      'text.press_height':.025,'text.press_width':.018,'text.press_angle':.75,
      'text.press_baseline':.003,'text.press_seed':19,'text.press_rate':3.,
      'dye_transfer.cadence':15.,'dye_transfer.emulsion':.40,
      'dye_transfer.streaks':.18,'dye_transfer.edge_bloom':.14,
      'dye_transfer.registration':.22,'dye_transfer.focus_flutter':.18,
      'dye_transfer.grain':.013,'dye_transfer.warp':.6,'dye_transfer.wash':.10,
      'dye_transfer.drag':.015,'dye_transfer.drag_mix':.06,
      'dye_transfer.choke':0.,'dye_transfer.erosion':.025,
      'dye_transfer.softness':.25,'dye_transfer.dust':.08,'dye_transfer.weave':.0012,
      'dye_transfer.tooth':.65,'dye_transfer.ink_density':.04,
      'dye_transfer.dye':.14,'dye_transfer.opening':1.2,
      'dye_transfer.edge_leak_hue':.015,'dye_transfer.edge_leak_width':.052,
      'dye_transfer.edge_leak_x':.005})
    palettes={
      'ivory':dict(paper_hue=.965,paper_saturation=.022,paper_light=.98,
        ink_hue=.96,ink_saturation=.16,ink_light=.09,edge_leak=0.),
      'pink':dict(paper_hue=.886,paper_saturation=.675,paper_light=1.05,
        ink_hue=.06,ink_saturation=.86,ink_light=.14,edge_leak=.9,
        ink_veil=.28,ink_veil_x=.26,ink_veil_width=.26),
      'red':dict(paper_hue=.025,paper_saturation=.992,paper_light=1.03,
        ink_hue=.015,ink_saturation=.85,ink_light=.055,edge_leak=0.),
      'red-negative':dict(paper_hue=.994,paper_saturation=.90,paper_light=.12,
        ink_hue=.022,ink_saturation=.97,ink_light=.93,edge_leak=0.,ink_density=.04),
      'pink-negative':dict(paper_hue=.094,paper_saturation=.79,paper_light=.12,
        ink_hue=.94,ink_saturation=.76,ink_light=1.,edge_leak=0.,ink_density=0.),
      'negative':dict(paper_hue=.01,paper_saturation=.10,paper_light=.18,
        ink_hue=.08,ink_saturation=.025,ink_light=.88,edge_leak=0.)}
    if calibration:
        first,earth,dreams,through,heading,sub='I','NEED','BELIEVE IN','& YOU KNOW','SOMEONE','TO BELIEVE IN'
    else:
        first,earth,dreams,through,heading,sub='THE','EARTH','DREAMS','THROUGH US','THE EARTH','DREAMS THROUGH US'
    dream_width = .73 if calibration else .56
    shots=[]
    def shot(frame,text,palette,*,size=.38,width=.73,x=0.,y=0.,font=1,source=None,**finish):
        p=dict(common)
        p.update({'text.content':text,'text.size':size,'text.block_width':width,'text.font':font,
          'dye_transfer.x':x,'dye_transfer.y':y})
        p.update({f'dye_transfer.{k}':v for k,v in palettes[palette].items()})
        p.update({f'dye_transfer.{k}':v for k,v in finish.items()})
        if source:p.update({'text.'+k:v for k,v in source.items()})
        shots.append(dict(frame=frame,text=text,palette=palette,values=p))
    def title(frame,title,subtitle,palette,subtitle_width=1.,**finish):
        shot(frame,title,palette,size=.91,width=.96,source={
          'badge':1,'badge_shape':5,'badge_border':0.,'badge_padding_x':0.,'badge_padding_y':0.,
          'badge_gap':5.,'badge_subtitle':subtitle,'badge_show_subtitle':1,
          'badge_subtitle_scale':.59,'badge_subtitle_width':subtitle_width,
          'align':0,'press_height':.045,'press_angle':1.25,'press_width':.025,
          'press_baseline':.006,'press_seed':23,'press_rate':2.},**finish)
    irregular={'press_height':.24,'press_angle':6.,'press_width':.08,'press_baseline':.06,'press_seed':71,'press_rate':10.,'tracking':.13}
    # Keep the reference's opening flashes, but start the new phrase at THE.
    shot(0,'KNOW' if calibration else first,'pink',size=.96,width=.98 if calibration else .62,edge_leak=.2,
         ink_veil=.70,ink_veil_x=.26,ink_veil_width=.28)
    if calibration:
        shot(2,'SOMEONE TO\nBELIEVE','ivory',size=.34,width=1.65,x=-.50,font=0)
    else:
        shot(2,first,'ivory',size=.72,width=.45,x=-.10)
    shot(5,first,'negative',size=.79,width=.085 if calibration else .27,source=irregular,
         softness=.9,shutter=-.28,streaks=.4,drag=.25,drag_mix=.32)
    shot(11,first,'ivory',size=.70,width=.11 if calibration else .30,x=-.27,source=irregular,softness=.6)
    shot(14,earth,'ivory',size=.78,width=.79,source=irregular)
    shot(20,earth,'ivory',size=.91,width=.89,source=irregular)
    # Oversized, unstable impressions before the first reading hold.
    for frame,txt,size,width,x,y in [
      (26,'SOMEONE' if calibration else earth,.47,1.38,.10,.22),
      (29,'SOMEONE TO' if calibration else earth,.46,1.72,-.29,-.20),
      (38,'SOMEONE TO' if calibration else dreams,.47,1.75,-.25,.51),
      (47,'SOMEONE\nTO BELIEVE' if calibration else dreams,.50,1.34,.10,-.12)]:
        shot(frame,txt,'pink',size=size,width=width,x=x,y=y,font=0,
          source={'press_angle':2.5,'press_height':.055,'press_rate':15.},
          warp=17. if frame>=38 else 2.,registration=.85 if frame>=38 else .25,
          softness=.75,shutter=-.58 if frame>=38 else -.18,
          drag=.32,drag_mix=.42,streaks=.28,edge_leak=.92,edge_leak_width=.1)
    for frame,palette in ((53,'pink'),(59,'ivory'),(61,'pink'),(65,'ivory'),(67,'pink')):
        shot(frame,dreams,palette,size=.38,width=dream_width,y=-.05 if frame==53 else 0.,
          opening=1.17,gate_x=.55,gate_softness=.012,edge_leak=.9 if palette=='pink' else 0.)
    shot(80,dreams,'pink',size=.35,width=dream_width+.01,warp=12.,registration=.8,
      source={'press_height':.08,'press_angle':3.5,'press_rate':15.},shutter=-.28,softness=.8,
      opening=1.10,gate_x=.55)
    shot(84,dreams,'pink',size=.36,width=dream_width+.01,x=.01,y=.02,warp=25.,registration=1.,shutter=-.65,
      source={'press_height':.10,'press_angle':4.,'press_rate':15.},softness=1.1,erosion=.10,drag=.3,drag_mix=.42)
    shot(90,dreams,'pink',size=.35,width=dream_width+.07,x=.13,y=-.02,warp=25.,registration=1.,shutter=.42,
      source={'press_height':.10,'press_angle':4.,'press_rate':15.},softness=1.4,erosion=.13,edge_leak_width=.12)
    shot(92,dreams,'ivory',size=.35,width=dream_width+.04,x=.12,y=-.02,warp=28.,registration=1.,shutter=-.65,
      softness=1.4,erosion=.10,opening=1.04,gate_x=.62,gate_softness=.025)
    # Small left-anchored build, then the same phrase held in full.
    prefix='&' if calibration else 'THROUGH'
    shot(95,prefix,'ivory',size=.55,width=.085 if calibration else .62,x=-.445 if calibration else -.17)
    if calibration:shot(101,'& YOU','ivory',size=.55,width=.45,x=-.265)
    else:shot(101,through,'ivory',size=.55,width=.94)
    shot(104,through,'ivory',size=.55,width=.95)
    shot(113,through,'ivory',size=.56,width=.95,warp=22.,registration=1.,erosion=.11,softness=1.1,shutter=.32)
    shot(117,through,'ivory',size=.55,width=1.05,x=.06,y=.42,warp=28.,registration=1.,erosion=.12,softness=1.9,shutter=-.75)
    # The poster reprise also begins at the beginning of the sentence.
    shot(119,earth if calibration else first,'red',size=.90,width=.95 if calibration else .52,source=irregular,softness=.5)
    # Progressive two-level poster: keep the finished line positions anchored.
    shot(128,'SOME' if calibration else 'THE','red-negative',size=.50,width=.52 if calibration else .29,x=-.22 if calibration else -.325,y=-.225,
      source={'press_height':.045,'press_angle':1.25,'press_seed':23,'press_rate':2.})
    shot(134,heading,'red-negative',size=.50,width=.94,y=-.225,
      source={'press_height':.045,'press_angle':1.25,'press_seed':23,'press_rate':2.})
    title(143,heading,'TO' if calibration else 'DREAMS','red-negative',.14 if calibration else .34)
    title(155,heading,'TO' if calibration else 'DREAMS','red-negative',.14 if calibration else .34,
      warp=14.,registration=.8,shutter=-.20,softness=.9)
    title(158,heading,'TO BELIEVE' if calibration else 'DREAMS THROUGH','red-negative',.75 if calibration else .83)
    title(164,heading,sub,'red-negative')
    title(167,heading,sub,'pink',edge_leak=.25,ink_veil=.36,ink_veil_x=.12)
    # A tiny push into the complete phrase, with irregular printed registration.
    title(178,heading,sub,'pink',scale=1.015,edge_leak=.25,ink_veil=.32,ink_veil_x=.16)
    title(190,heading,sub,'pink',scale=1.025,edge_leak=.20,ink_veil=.38,ink_veil_x=.20)
    title(198,heading,sub,'pink',scale=1.035,edge_leak=.20,ink_veil=.34,ink_veil_x=.23)
    # Return to the last words in positive pink before the shutter exits.
    shot(203,'&' if calibration else 'THROUGH','pink-negative',size=.54,width=.09 if calibration else .61,x=-.44 if calibration else -.17)
    if calibration:shot(209,'& YOU','pink-negative',size=.54,width=.46,x=-.26)
    else:shot(209,through,'pink-negative',size=.54,width=.93)
    shot(212,through,'pink-negative',size=.54,width=.94)
    shot(221,through,'pink-negative',size=.55,width=.94,warp=22.,registration=1.,erosion=.06,softness=1.3,shutter=.35)
    shot(224,through,'pink-negative',size=.85,width=1.65,x=.05,y=.65,warp=30.,registration=1.,softness=2.3,shutter=-.9,drag=.5,drag_mix=.55)
    assert all(a['frame']<b['frame'] for a,b in zip(shots,shots[1:]))
    name='Text / Earth dreams — dye impressions'
    seq=normalize_sequence(dict(schema_version=1,render_version=2,name=name,fps=FPS,seed=291026,
      duration=FRAMES/FPS,canvas=dict(width=720,height=406,framing='native'),
      states={f'shot-{i+1:02}':dict(preset='Reference blinds',enabled=['text','dye_transfer'],overrides=s['values']) for i,s in enumerate(shots)},
      cues=[dict(time=s['frame']/FPS,state=f'shot-{i+1:02}',transition='cut') for i,s in enumerate(shots)]))
    project=composition_from_sequence(seq);template=project['sections'][0]
    project.update(phrases={},sections=[],effect_order=['dye_transfer'],timeline_view='shots')
    for i,s in enumerate(shots):
        key=f'shot-{i+1:02}';end=shots[i+1]['frame'] if i+1<len(shots) else FRAMES
        label=' '.join((s['text']+' '+s['values'].get('text.badge_subtitle','')).split())
        project['phrases'][key]=dict(name=label,start=s['frame']/FPS,end=end/FPS)
        project['sections'].append(dict(copy.deepcopy(template),id=key,phrase=key,duration=(end-s['frame'])/FPS))
    return normalize_composition(project),shots

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);a.add_argument('--calibration',action='store_true')
    args=a.parse_args();project,shots=composition(args.calibration);save_composition(args.output,project)
    print(f'{len(shots)} editable shots; {FRAMES/FPS:.2f}s; saved {args.output}')
