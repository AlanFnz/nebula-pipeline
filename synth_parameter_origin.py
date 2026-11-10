"""Read-only explanations of the renderer's resolved parameter values.

Accept the inspector's existing resolved frame: no compilation, media analysis,
rendering, or mutation belongs in this presentation layer.
"""
from synth_automation import envelope
from synth_effects import EFFECT_BY_ID
from synth_instances import base_id, base_path
from synth_performance import CONTROLS, SURFACES


VALUE_SOURCES_HELP = (
    'Study → project base → clip base → Creative adjustments → clip automation → Perform surface. '
    'Audio responses follow these values; Perform can also change the visual clock and finished image.\n'
    'Use fixed value replaces the study animation only in the editing scope. '
    'Clip automation and Perform are kept. Restore removes only the local base override.\n'
    'Monitor values are read-only. They follow the displayed clip, which may differ from the clip being edited. '
    'A fixed speed or rate can still generate motion.'
)


def performance_summary(config):
    if not config: return '', ''
    active = [c for key, c in CONTROLS.items()
              if config.get('tracks', {}).get(key) or config.get('values', {}).get(key, c.default) != c.default]
    if not active: return '', ''
    recorded = [c.title for c in active if config.get('tracks', {}).get(c.key)]
    fixed = [c.title for c in active if not config.get('tracks', {}).get(c.key)]
    if not config.get('enabled', True):
        title = 'Perform bypassed · saved adjustments kept'
    else:
        parts = []
        if recorded: parts.append(f'{len(recorded)} recorded')
        if fixed: parts.append(f'{len(fixed)} fixed')
        title = 'Perform · ' + ' · '.join(parts)
    detail = ('Recorded: ' + ', '.join(recorded) + '. ' if recorded else '')
    detail += ('Fixed: ' + ', '.join(fixed) + '. ' if fixed else '')
    detail += ('These project-wide controls are separate from the base editors. '
               'Frame/Finish alter the finished image; Motion can retime it; Surface adjusts object parameters. '
               'Editing a recorded knob with Record off replaces that knob’s recording. Undo restores it.')
    return title, detail


class FrameOrigins:
    def __init__(self, document, sequence, seconds, resolved):
        self.document = document
        self.seconds = seconds
        self.source_seconds = resolved[1]
        self.transition = resolved[5] != 'cut' and resolved[6] < 1
        self.modules = {m['id']: m for m in resolved[-1]['modules']}
        self.values = {f"{m['id']}.{key}": value for m in self.modules.values()
                       for key, value in m['params'].items()}
        self.section = None
        self.clip_label = 'Monitor'
        # Cue names preserve the owning section even with repeated placements.
        owners = [(i, s) for i, s in enumerate(document['sections'])
                  if resolved[4]['state'].startswith(s['id'] + ':')]
        if owners:
            index, self.section = max(owners, key=lambda item: len(item[1]['id']))
            self.clip_label = f'Clip {index + 1}'
        self.owners = {path: key for key, effect in EFFECT_BY_ID.items() for path in effect.paths}
        self.events = {}
        for event in sequence.get('automations', ()):
            if event['amount'] and envelope(event, self.source_seconds):
                self.events.setdefault(event['path'], []).append(event)
        self.performance = sequence.get('visual_performance') or {}
        self.audio_paths = set()
        reactivity = sequence.get('audio_reactivity') or {}
        if reactivity.get('enabled', True):
            self.audio_paths = {m['path'] for m in reactivity.get('mappings', ())
                                if m.get('enabled', True) and m['amount'] and m['sensitivity']}

    def describe(self, path, *, animated=False, automation_count=0, selected_id=None):
        from synth_effect_parameter_ui import format_value
        if path not in self.values: return None
        if selected_id and (not self.section or self.section['id'] != selected_id):
            return (f'Monitor is outside this clip · {self.clip_label}',
                    'The base editor still applies to the selected clip. Move the playhead into it to inspect its animated value.')
        effect_id = self.owners.get(path, path.split('.')[0])
        project = self.document['effects'].get(effect_id, {})
        local = (self.section or {}).get('effects', {}).get(effect_id, {})
        overrides = path in local.get('params', {})
        origin = self.clip_label + ' base' if overrides else 'Project base' if path in project.get('params', {}) else 'Study'
        stages = [origin]
        module = self.modules[path.split('.')[0]]
        enabled = module['enabled']
        # Ghost intensity can act on the luminous companion without Smear.
        if path == 'smear.effect_intensity':
            slab = self.modules.get('slab', {})
            enabled |= bool(slab.get('enabled') and slab.get('params', {}).get('ghost_opacity'))
        from synth_creative import CREATIVE_CONTROLS
        adjustments = dict(project.get('creative', {}).get('values', {}))
        adjustments.update(local.get('creative', {}).get('values', {}))
        creative = [c.label for c in CREATIVE_CONTROLS.get(base_id(effect_id), ())
                    if base_path(path) in c.paths and adjustments.get(c.key, c.neutral) != c.neutral]
        if creative: stages.append('Creative: ' + ', '.join(creative))
        active_event = bool(self.events.get(path))
        if active_event: stages.append('Clip automation' if enabled else 'Clip automation (effect off)')
        elif automation_count:
            local_events = [e for e in (self.section or {}).get('automations', ()) if e['path'] == path]
            stages.append('Automation on other clips' if not local_events else
                          'Clip automation disabled' if not any(e.get('enabled', True) for e in local_events) else
                          'Clip automation idle')
        surface = []
        if self.performance.get('enabled', True):
            for control, mappings in SURFACES.get(base_id(module['id']), ()):
                if path.split('.')[1] not in {key for key, _, _ in mappings}: continue
                recorded = bool(self.performance.get('tracks', {}).get(control.key))
                fixed = self.performance.get('values', {}).get(control.key, control.default) != control.default
                if recorded or fixed:
                    surface.append('Perform ' + control.title + (' (recorded)' if recorded else ' (fixed)'))
        if surface: stages.extend(surface)
        if not (animated or automation_count or active_event or surface or creative or
                (overrides and not selected_id) or path in self.audio_paths): return None
        label = f'Monitor {self.seconds:.2f}s · {self.clip_label} · '
        label += format_value(path, self.values[path])
        if not enabled: label += ' · effect off'
        elif path in self.audio_paths: label += ' (before audio response)'
        if stages != ['Study']: label += '\n' + ' → '.join(stages)
        detail = f'{self.clip_label} at monitor time {self.seconds:.2f}s (visual source {self.source_seconds:.2f}s). '
        detail += 'Value sources: ' + ' → '.join(stages) + '. '
        if self.transition: detail += 'During a study transition, both source states may contribute. '
        detail += 'This read-only value includes resolved base edits, Creative, clip automation and Perform surface. '
        if path in self.audio_paths: detail += 'An audio response is applied afterwards; its result is not sampled here. '
        if not enabled: detail += 'This module is disabled or bypassed, so the shown parameter does not contribute. '
        detail += 'Editing or restoring the base keeps clip automation and Perform. Finished-image controls remain separate.'
        return label, detail
