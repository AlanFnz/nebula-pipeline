"""Authored optical-print montage. Renderers remain independent of these cues."""
import copy
import numpy as np
from synth import MODULE_BY_ID
from synth_composition import composition_from_sequence, normalize_composition
from synth_sequence import normalize_sequence


def reading_print_composition():
    """One editable phrase; semantic timing adapts to replacement wording."""
    enabled = ('text', 'print_collage', 'film_burn')
    settings = {'speed': 1., 'depth': 0., 'treatment_fps': 12}
    for module in enabled:
        settings.update({f'{module}.{spec.key}': spec.default for spec in MODULE_BY_ID[module].params})
    settings.update({
        'text.content': 'REVOLUTION IS NOW', 'text.font': 5, 'text.weight': 700,
        'text.reveal': 4, 'text.reading_duration': 7., 'text.reading_final': 2.,
        'text.reading_transition': .25, 'text.reading_breakup': .85,
        'text.size': .36, 'text.fit_width': .88, 'text.tracking': .015,
        'text.saturation': 0., 'text.back_brightness': 0.,
        'print_collage.reading_layout': 1., 'print_collage.width': .9,
        'print_collage.poster': .65, 'print_collage.poster_scale': 2.8,
        'print_collage.echo': .65, 'print_collage.bars': .75,
        'print_collage.x': .12, 'print_collage.y': -.06,
        'print_collage.weave': .006,
        'film_burn.reading_clarity': 1., 'film_burn.print_mix': 1.,
        'film_burn.paper_hue': .985, 'film_burn.paper_light': .94,
        'film_burn.ink_hue': .63, 'film_burn.ink_light': .06,
        'film_burn.exposure': 1.3, 'film_burn.drift': .25,
        'film_burn.reversal': 1.1, 'film_burn.halo': 1.15,
        'film_burn.halo_width': 13., 'film_burn.softness': 3.2,
        'film_burn.ink_spread': 4.5, 'film_burn.damage': .5,
        'film_burn.melt': 3.8, 'film_burn.color_spread': .35,
        'film_burn.grain': .075, 'film_burn.dust': .45,
    })
    source = normalize_sequence(dict(schema_version=1, render_version=2,
        name='Text / reading print', duration=7., fps=12, seed=231026,
        canvas={'width': 956, 'height': 720, 'framing': 'native'},
        states={'reading': {'preset': 'Reference blinds', 'enabled': list(enabled), 'overrides': settings}},
        cues=[{'time': 0., 'state': 'reading', 'transition': 'cut'}]))
    project = composition_from_sequence(source)
    project['phrases']['custom']['name'] = 'Words / interruptions / final phrase'
    return normalize_composition(project)


def film_print_composition():
    enabled=('text','print_collage','film_burn')
    common={'speed':1.,'depth':0.,'treatment_fps':12,'object_x':0.,'object_y':0.}
    for module in enabled:
        common.update({f'{module}.{s.key}':s.default for s in MODULE_BY_ID[module].params})
    common.update({'text.content':'HAÇIENDA','text.font':5,'text.weight':700,
        'text.size':.22,'text.tracking':.035,'text.fit_width':.9,
        'text.brightness':1.,'text.saturation':0.,'text.back_brightness':0.,
        'print_collage.width':.91,'print_collage.height':1.1, 'print_collage.y':.035,
        'film_burn.print_mix':1.,'film_burn.drift':0.,'film_burn.rate':1.,
        'film_burn.grain':.075,'film_burn.dust':.6,'film_burn.roughness':1.,'film_burn.melt':3.8,
        'film_burn.halo':1.15,'film_burn.paper_hue':.985,
        'film_burn.ink_light':.30, 'film_burn.ink_spread':4.5, 'film_burn.color_spread':.35, 'film_burn.damage':.5, 'film_burn.paper_light':.94,'film_burn.softness':3.2})
    def track(points, frame):
        return float(np.interp(frame,[p[0] for p in points],[p[1] for p in points]))
    # Unequal holds and hard cuts are intentional, following the print montage.
    layouts=[
        (0, 'label'),(2,'empty'),(4,'label'),(8,'giant'),(10,'prefix'),
        (12,'single'),(14,'triple'),(18,'single'),(20,'tiny'),(22,'stairs'),
        (23,'tiny'),(25,'poster'),(26,'empty'),(29,'stairs'),(35,'word'),
        (48,'word_echo'),(51,'poster'),(55,'word'),(57,'single_echo'),
        (58,'single'),(61,'empty'),(62,'mixed'),(66,'mixed_poster'),
        (70,'mixed'),(71,'mixed_poster'),(72,'mixed'),(76,'single'),
        (79,'prefix'),(87,'prefix_echo'),(91,'tiny'),(92,'word'),
        (93,'poster'),(94,'word'),(97,'empty'),(98,'stairs'),(104,'poster'),
        (105,'empty'),(108,'giant'),(109,'stairs'),(110,'label'),(111,'word'),
        (117,'word_echo'),(118,'tiny'),(120,'label'),(121,'tiny'),(122,'empty')]
    opening=[(0,.72),(1,.45),(2,.12),(3,.06),(4,.65),(5,.9),(7,1.2),
        (8,1.5),(14,1.3),(16,.8),(21,.9),(22,.9),(25,.67),(26,.35),(27,.06),(28,.18),
        (29,.75),(32,.68),(34,.9),(35,1.6),(38,1.1),(42,.86),(43,1.6),
        (54,1.4),(56,.86),(60,.85),(61,.07),(62,1.6),(70,1.15),(75,.87),
        (78,.8),(79,1.15),(85,1.6),(94,1.25),(97,.8),(98,1.6),(104,1.4),
        (105,.62),(106,.05),(107,.02),(108,.95),(110,.6),(111,1.6),(118,1.6),(121,1.4),(122,.08)]
    exposure=[(0,1.1),(2,.3),(4,1.6),(7,1.4),(8,.8),(12,.95),(16,1.5),(22,1.3),(27,.2),
        (29,1.5),(32,.15),(35,1.4),(38,1.65),(39,.75),(42,.1),(43,.02),(46,.1),
        (47,1.5),(50,1.45),(51,.04),(52,.08),(53,1.7),(56,1.7),(57,1.25),
        (61,.1),(62,.85),(65,.9),(66,.55),(67,.6),(68,1.5),(73,1.6),(76,1.1),
        (79,1.5),(82,1.7),(85,1.25),(90,1.25),(91,1.),(92,1.7),(97,.15),
        (98,.5),(103,.4),(104,.6),(107,.1),(108,1.6),(109,1.2),(110,.25),
        (111,1.6),(115,1.8),(117,1.1),(118,.1),(121,.15),(122,.05)]
    position=[(0,.4),(8,.8),(12,.8),(22,.62),(35,.78),(36,.47),(38,.45),(43,.45),
        (47,.02),(50,.06),(53,.35),(56,.45),(60,.4),(62,.8),(65,.8),(68,.7),
        (72,.5),(78,.35),(81,.4),(85,.85),(90,.85),(92,.3),(96,.5),
        (98,.7),(103,.3),(108,.55),(111,.5),(115,.45),(118,.2),(122,.5)]
    states={}; cues=[]
    for frame in range(123):
        settings=copy.deepcopy(common)
        layout=next(value for start,value in reversed(layouts) if frame>=start)
        settings.update({'film_burn.opening':track(opening,frame),
            'film_burn.exposure':track(exposure,frame),'film_burn.leak_x':track(position,frame),
            'film_burn.leak_hue':.12 if 8<=frame<14 or 47<=frame<=50 or 85<=frame<=90 else .88,
            'film_burn.leak_width':.24 if 8<=frame<14 or 47<=frame<=50 or 85<=frame<=90 else .20,
            'film_burn.halo_width':13.,
            'film_burn.reversal': .02 if 8<=frame<=13 or 43<=frame<=52 or 62<=frame<=67 or 85<=frame<=90 or 98<=frame<=104 or 118<=frame else 1.10,
            'film_burn.halo': .02 if 8<=frame<=13 or 43<=frame<=52 or 62<=frame<=67 or 85<=frame<=90 or 98<=frame<=104 or frame>=118 else 1.15,
            'film_burn.gate_x':.46+.02*np.sin(frame*.55),
            'film_burn.ink_hue':.43 if 43<=frame<=52 or 62<=frame<=67 or 85<=frame<=90 else .63,
            'film_burn.paper_hue':.998 if frame<43 or frame>=47 else .956})
        aperture=settings['film_burn.opening']
        if .3<aperture<1.: settings['film_burn.gate_x']=aperture/2+.015
        if frame==122: settings['film_burn.opening']=0.
        if layout.startswith('mixed'):
            settings.update({'text.content':'Haçienda','print_collage.width':.66,'print_collage.height':1.2})
        if layout.startswith('prefix'):
            settings.update({'text.content':'Haçienda','print_collage.end':.39,'print_collage.width':.40,'print_collage.x':.04,'print_collage.height':.9})
        if layout.startswith('single') or layout=='triple' or layout=='tiny':
            settings.update({'print_collage.start':.275,'print_collage.end':.4,'print_collage.width':.14,
                'print_collage.x':-.14 if frame>56 else .05,'print_collage.height':1.})
            if layout=='triple': settings.update({'print_collage.copies':3,'print_collage.width':.11,'print_collage.x':.12,'print_collage.gap':.01})
            if layout=='tiny':settings.update({'print_collage.width':.04,'print_collage.x':.28,'print_collage.y':.12})
        if layout in ('label','stairs'):
            settings.update({'print_collage.width':.48 if layout=='label' else .36,
                'print_collage.y':0. if layout=='label' else -.13,
                'print_collage.x':-.05,'print_collage.echo':.7,
                'print_collage.echo_y':.24,'print_collage.echo_x':.2})
        if layout=='stairs':settings['text.content']='THE\nHAÇIENDA'
        if layout=='stairs':settings.update({'print_collage.bars':.85,'print_collage.bar_angle':-35.,'print_collage.bar_count':7,'print_collage.y':.04,'print_collage.x':0.,'film_burn.leak_hue':.12,'film_burn.ink_hue':.43,'film_burn.ink_light':.4,'film_burn.exposure':.9})
        if 35<=frame<=38: settings.update({'film_burn.reversal':1.25,'film_burn.ink_hue':.0,'film_burn.ink_light':.6,'film_burn.halo':.75, 'film_burn.softness':3.5})
        if 43<=frame<=46: settings.update({'film_burn.color_spread':.9,'film_burn.ink_hue':.03,'film_burn.ink_light':.32,'film_burn.melt':7.})
        if frame==48: settings.update({'print_collage.echo':0.,'text.content':'HAÇIENDA'})
        if frame in (18,19): settings.update({'print_collage.width':.44,'print_collage.x':-.03,'film_burn.opening':1.4,'film_burn.reversal':.1,'film_burn.exposure':.9,'film_burn.leak_x':.82,'film_burn.leak_hue':.12,'film_burn.ink_hue':.96,'film_burn.ink_light':.12,'film_burn.halo':.5,'film_burn.halo_width':18.,'print_collage.height':1.1})
        if 111<=frame<=117: settings.update({'film_burn.leak_width':.35, 'film_burn.leak_height':.6, 'film_burn.leak_y':.85, 'film_burn.exposure':1.25, 'film_burn.reversal':.35,'film_burn.ink_hue':.08,'film_burn.ink_light':.9,'film_burn.leak_hue':.88,'film_burn.halo_width':20.,'film_burn.halo':1.45,'film_burn.softness':4.,'film_burn.ink_spread':6.5,'film_burn.damage':.05,'film_burn.color_spread':.8})
        if 79<=frame<=84: settings.update({'film_burn.leak_width':.40,'film_burn.softness':3.2,'film_burn.reversal':1.2,'film_burn.exposure':1.7})
        if layout=='empty':settings['text.opacity']=0.
        if layout=='giant':settings.update({'print_collage.width':2.5,'print_collage.x':.8,'print_collage.height':1.1})
        if 'poster' in layout:
            settings.update({'print_collage.poster':.85,'print_collage.poster_scale':3.3,'print_collage.poster_y':.03,'print_collage.height':1.25,'print_collage.echo':.8,'print_collage.bars':.8})
        if 'echo' in layout:settings['print_collage.echo']=.8
        if frame in (0,25,71,104):
            settings.update({'print_collage.poster':.85,'print_collage.poster_start':.15,
                'print_collage.poster_end':.275,'print_collage.poster_scale':1.5,
                'print_collage.poster_y':.63,'print_collage.height':1.})
        key=f'print-{frame:03d}'
        states[key]={'preset':'Reference blinds','enabled':list(enabled),'overrides':settings}
        cues.append(dict(time=frame/12,state=key,transition='cut'))
    source=normalize_sequence(dict(schema_version=1,render_version=2,name='Text / burning print',
        duration=10.25,fps=12,seed=231026,canvas={'width':956,'height':720,'framing':'native'},states=states,cues=cues))
    project=composition_from_sequence(source)
    project['phrases']['custom']['name']='Type / exposure / print cuts'
    return normalize_composition(project)
