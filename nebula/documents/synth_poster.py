"""Editable poster elements backed by their actual source and printing parameters."""
import copy
import uuid
from dataclasses import dataclass, replace
from math import cos, floor, radians, sin

import numpy as np
from PIL import Image, ImageChops

from nebula.core.synth_canvas import content_size
from nebula.documents.synth_sequence import resolve_sequence_frame
from nebula.effects.synth_dye_transfer import deposited_plate
from nebula.effects.synth_effect_order import resolved_order
from nebula.effects.synth_effects import EFFECT_BY_ID, effect_preset, state_values
from nebula.effects.synth_intensity import amount
from nebula.effects.synth_type_overprint import impression_stamp, plate_ink
from nebula.render.synth import _seed
from nebula.render.synth_instances import MAX_INSTANCES, base_id, document_instance_ids
from nebula.sources.synth_text import placed_text_mask


def normalize_poster(options):
    if not isinstance(options, dict):
        raise ValueError('Poster settings must be an object.')
    footer = options.get('footer', [])
    if not isinstance(footer, list) or len(footer) > 128 or any(
            not isinstance(key, str) or base_id(key) != 'type_overprint' for key in footer):
        raise ValueError('Poster footer must list text impressions.')
    result = {'footer': list(dict.fromkeys(footer))} if footer else {}
    for field in ('order', 'hidden'):
        if field not in options:
            continue
        keys = options[field]
        if not isinstance(keys, list) or len(keys) > MAX_INSTANCES + 2 or any(
                not isinstance(k, str) or (k not in ('text', 'plate') and base_id(k) != 'type_overprint')
                for k in keys):
            raise ValueError('Poster order and visibility must reference artwork layers.')
        if keys:
            result[field] = list(dict.fromkeys(keys))
    if 'plate_name' in options:
        if not isinstance(options['plate_name'], str):
            raise ValueError('Plate name must be text.')
        result['plate_name'] = options['plate_name'][:120]
    return result


@dataclass(frozen=True)
class Layer:
    key: str
    label: str
    kind: str
    owner: str
    group: str = ''


class PosterFrame:
    """The inspected frame. Geometry is evaluated only for canvas interaction."""

    def __init__(self, sequence, seconds, options):
        resolved = resolve_sequence_frame(sequence, seconds, normalized=True)
        self._set_artwork(resolved[-1], resolved[2], options)

    @classmethod
    def from_preset(cls, preset, seconds, options):
        frame = cls.__new__(cls)
        frame._set_artwork(preset, seconds, options)
        return frame

    def _set_artwork(self, preset, seconds, options):
        self.preset = preset
        self.time = seconds
        self.modules = {m['id']: m['params'] for m in self.preset['modules'] if m['enabled']}
        self.canvas = (self.preset['width'], self.preset['height'])
        self.reference = content_size(self.preset, self.canvas)
        self.layers = []
        self.before_print = set()
        self.before_screen = set()
        self.dye = self.modules.get('dye_transfer')
        order = [key for key in resolved_order(self.preset) if key in self.modules]
        if 'text' in self.modules:
            self._text('text', '')
        for key in order:
            if base_id(key) == 'type_overprint':
                if self.modules[key].get('layout') == 2:
                    self.layers.append(Layer(key, 'Ink plate' + (' · ' + key.split('@')[1] if '@' in key else ''),
                                             'plate', key))
                else:
                    self._text(key, 'Footer' if key in options.get('footer', ()) else '')
            elif key == 'dye_transfer':
                self.before_print = {n.key for n in self.layers if n.kind in ('text', 'plate')}
            elif key == 'photocopy' and self.modules[key]['process'] and self.modules[key]['mix']:
                self.before_screen = {n.key for n in self.layers if n.kind == 'text'}
            if base_id(key) != 'type_overprint':
                self.layers.append(Layer('finish/' + key, EFFECT_BY_ID[key].label, 'finish', key, 'Print finish'))
        finishes = [node for node in self.layers if node.kind == 'finish']
        self.layers = [node for node in reversed(self.layers) if node.kind != 'finish']
        if self.dye and self.dye['mask_shape']:
            self.layers.append(Layer('plate', options.get('plate_name') or 'Ink plate', 'plate', 'dye_transfer'))
        self.native_order = [node.key for node in self.layers]  # front to back
        self.hidden = frozenset(options.get('hidden', ()))
        order_keys = list(dict.fromkeys([*options.get('order', ()), *self.native_order]))
        self.layers.sort(key=lambda node: order_keys.index(node.key))
        # Keep the tree a faithful reading of the stack when a footer is interleaved.
        footer_rows = [i for i, n in enumerate(self.layers) if n.group == 'Footer']
        if footer_rows and footer_rows[-1] - footer_rows[0] + 1 != len(footer_rows):
            self.layers = [replace(n, group='') for n in self.layers]
        self.order = [node.key for node in self.layers]
        paper = next((key for key in ('dye_transfer', 'text', 'color_field') if key in self.modules), '')
        self.layers.append(Layer('paper', 'Paper', 'paper', paper))
        screen = self.modules.get('photocopy', {})
        self.screened_paper = bool(screen.get('process') and screen['mix'] and
                                   (not self.dye or order.index('photocopy') < order.index('dye_transfer')))
        self.layers.extend(finishes)
        self.by_key = {node.key: node for node in self.layers}
        self.footer = tuple(node.key for node in self.layers if node.group == 'Footer')
        if self.footer:
            self.by_key['footer'] = Layer('footer', 'Footer', 'group', '')
        self._masks = {}

    def _text(self, key, group):
        label = ' '.join(self.modules[key]['content'].split()) or 'Empty text'
        self.layers.append(Layer(key, label, 'text', key, group))

    def texture_paths(self, key):
        """Local material first, then printing operations shared with other layers."""
        local, shared = [], []
        node = self.by_key.get(key)
        if node is None:
            return (), ()

        def add(paths, owner, *names):
            paths.extend(f'{owner}.{name}' for name in names)

        if node.kind == 'paper':
            if node.owner:
                add(local, node.owner, 'paper_grain', 'paper_grain_size')
            if self.screened_paper:
                add(local, 'photocopy', 'paper_grain', 'paper_tint')
                add(shared, 'photocopy', 'halftone', 'dot_size', 'screen_angle', 'grain_size')
            if self.dye:
                add(shared, 'dye_transfer', 'stock_relief', 'fiber_size', 'grain')
        elif node.kind == 'plate':
            if key != 'plate' or self.dye['mask_target']:
                add(local, node.owner, 'mask_dry_ink', 'mask_grain_size', 'mask_density_ramp')
            add(local, node.owner, 'mask_irregularity', 'mask_softness')
            if key == 'plate' or key in self.before_print:
                add(shared, 'dye_transfer', 'stock_relief', 'fiber_size', 'grain')
        elif node.kind == 'text':
            add(local, node.owner, 'ink_grain', 'ink_pinholes', 'ink_grain_size')
            if key in self.before_screen:
                add(shared, 'photocopy', 'grain', 'pinholes', 'edge_fade', 'edge_width',
                    'edge_wear', 'halftone', 'dot_size', 'screen_angle', 'grain_size')
            if key in self.before_print:
                add(shared, 'dye_transfer', 'dry_ink', 'ink_density', 'tooth', 'erosion',
                    'stock_relief', 'fiber_size', 'grain')
        return tuple(local), tuple(shared)

    def _print_transform(self, size):
        p = self.dye
        w, h = size
        cw, ch = content_size(self.preset, size)
        c, s = cos(radians(p['angle'])) / p['scale'], sin(radians(p['angle'])) / p['scale']
        cx, cy = w / 2 + p['x'] * cw, h / 2 + p['y'] * ch
        return c, s, w / 2 - c * cx - s * cy, -s, c, h / 2 + s * cx - c * cy

    def center(self, key):
        if key == 'footer':
            centers = [self.center(member) for member in self.footer]
            return tuple(sum(axis)/len(centers) for axis in zip(*centers))
        node = self.by_key[key]
        w, h = self.canvas
        cw, ch = self.reference
        if key == 'text':
            x, y = self.preset.get('object_x', 0.), self.preset.get('object_y', 0.)
        else:
            p = self.modules[node.owner]
            if node.kind == 'plate':
                x, y = p['mask_x'] * cw, p['mask_y'] * ch
            else:
                x, y = (p['x'] - .5) * cw, (p['y'] - .5) * ch
        if key in self.before_print:
            p = self.dye
            c, s = cos(radians(p['angle'])) * p['scale'], sin(radians(p['angle'])) * p['scale']
            x, y = c*x - s*y + p['x']*cw, s*x + c*y + p['y']*ch
        return w / 2 + x, h / 2 + y

    def mask(self, key, size, *, material=False):
        cache_key = key, size, material
        if cache_key in self._masks:
            return self._masks[cache_key]
        node = self.by_key[key]
        p = self.modules.get(node.owner, {})
        if node.kind == 'group':
            mask = Image.new('L', size)
            for member in self.footer:
                if member not in self.hidden:
                    mask = ImageChops.lighter(mask, self.mask(member, size))
        elif key == 'plate':
            yy, xx = np.indices((size[1], size[0]), dtype=np.float32)
            tick = floor(max(0., self.time * self.preset['speed']) * p['cadence'] + 1e-7)
            dry = p['mask_dry_ink'] if material and p['mask_target'] else 0.
            alpha, _, _ = deposited_plate(xx, yy, p, content_size(self.preset, size), (0., 0.),
                                          _seed(self.preset['seed'], 'dye-transfer'), tick, dry)
            mask = Image.fromarray(np.uint8(alpha[..., 0] * 255))
        elif node.kind == 'plate':
            alpha, _ = plate_ink(p, self.preset, size, key, self.time, material=material)
            mask = Image.fromarray(np.uint8(alpha[..., 0] * 255))
        elif key == 'text':
            mask = placed_text_mask(p, self.time, self.preset, size)
            if material and (p.get('ink_grain') or p.get('ink_pinholes')):
                mask = ImageChops.darker(mask, placed_text_mask(p, self.time, self.preset, size, print_ink=True))
        elif node.kind == 'text':
            mask = Image.new('L', size)
            stamp, origin = impression_stamp(p, self.preset, size, key, self.time, material=material)
            if stamp is not None:
                mask.paste(stamp, origin)
        else:
            return None
        if key in self.before_print:
            mask = mask.transform(size, Image.Transform.AFFINE, self._print_transform(size), Image.Resampling.BILINEAR)
        if material and node.kind in ('text', 'plate'):
            opacity = amount(p) * (p['opacity'] if key == 'text' or p.get('layout') == 1 else 1.)
            if opacity < 1.:
                mask = mask.point(lambda value: round(value * opacity))
        self._masks[cache_key] = mask
        return mask

    def pick(self, position, size):
        if not all(0 <= value < 1 for value in position):
            return None
        x, y = (int(v * edge) for v, edge in zip(position, size))
        for node in self.layers:
            if node.key in self.hidden:
                continue
            params = self.modules.get(node.owner, {})
            if amount(params) <= 0 or (node.key == 'text' and params['opacity'] == 0):
                continue
            mask = self.mask(node.key, size)
            if mask is not None and mask.getpixel((x, y)) >= 96:
                return node.key
        return 'paper'

    def move(self, target, key, dx, dy):
        """Apply a displacement in native canvas pixels to the chosen editing scope."""
        if key == 'footer':
            for member in self.footer:
                self.move(target, member, dx, dy)
            return
        node = self.by_key[key]
        if node.kind not in ('text', 'plate') or not (dx or dy):
            return
        if key in self.before_print:
            a, b, _, d, e, _ = self._print_transform(self.canvas)
            dx, dy = a * dx + b * dy, d * dx + e * dy
        if key == 'text':
            geometry = target['geometry']
            for axis, delta in zip(('position_x', 'position_y'), (dx, dy)):
                if delta:
                    geometry[axis] = min(4096., max(-4096., geometry[axis] + delta))
            return
        params = self.modules[node.owner]
        entry = target['effects'].setdefault(node.owner, {'mode': 'recipe', 'params': {}})
        plate = node.kind == 'plate'
        for axis, delta, edge in zip(('x', 'y'), (dx, dy), self.reference):
            if not delta:
                continue
            name = ('mask_' if plate else '') + axis
            path = f'{node.owner}.{name}'
            origin = entry['params'].get(path, params[name])
            low, high = (-2., 2.) if plate else (-.5, 1.5)
            entry['params'][path] = min(high, max(low, origin + delta / edge))

    def transform_plate(self, target, key, scale, rotation):
        owner = self.by_key[key].owner
        params = self.modules[owner]
        changes = {}
        if scale != 1.:
            changes['mask_size'] = min(4., max(.01, params['mask_size'] * scale))
        if rotation:
            changes['mask_angle'] = (params['mask_angle'] + rotation + 180.) % 360. - 180.
        overrides = {f'{owner}.{k}': v for k, v in changes.items() if v != params[k]}
        if overrides:
            target['effects'].setdefault(owner, {'mode': 'recipe', 'params': {}})['params'].update(overrides)

    def add_layer(self, document, kind, *, duplicate=None, above=None):
        """Use a real independently editable impression and keep its native print process."""
        reserved = (set(document_instance_ids(document)) | set(self.modules) | set(document['effects'])
                    | set(document.get('effect_order', ())))
        options = document['poster']
        for field in ('order', 'hidden', 'footer'):
            reserved.update(options.get(field, ()))
        for state in document['source']['states'].values():
            reserved.update(state.get('enabled', ()))
            reserved.update(path.split('.')[0] for path in state.get('overrides', ()))
        keys = ['type_overprint', *(f'type_overprint@{i}' for i in range(2, MAX_INSTANCES + 1))]
        key = next((k for k in keys if k not in reserved), None)
        if key is None:
            raise ValueError('This composition already uses all available impressions.')
        params = {'layout': 0, 'content': 'New text', 'height': .14, 'x': .5, 'y': .5}
        owner = self.by_key[duplicate].owner if duplicate else None
        if duplicate:
            source = self.modules[owner]
            if duplicate == 'text':
                cw, ch = self.reference
                params = dict(source, layout=1, light=source['brightness'],
                              x=.5+self.preset.get('object_x', 0.)/cw, y=.5+self.preset.get('object_y', 0.)/ch)
            elif duplicate == 'plate':
                prefix = 'mask_ink_' if source['mask_target'] == 1 else 'mask_paper_'
                params = {k: v for k, v in source.items() if k.startswith('mask_')}
                params.update(layout=2, **{c: source[prefix + c] for c in ('hue', 'saturation', 'light')})
                if not source['mask_target']:
                    params.update(hue=0., saturation=0., light=0., mask_dry_ink=0.)
                elif not params['mask_grain_size']:
                    params['mask_grain_size'] = source['fiber_size']
            else:
                params = dict(source)
        elif kind == 'plate':
            params = dict(layout=2, mask_shape=4, mask_size=.32, mask_aspect=1., hue=.045,
                          saturation=.87, light=.95, mask_softness=.4)
        entry = effect_preset(key)
        defaults = entry['params']
        if owner and base_id(owner) == 'type_overprint':
            self._copy_impression(document, owner, key, defaults)
        else:
            document['effects'][key] = {'mode': 'on', 'params': {
                key + '.' + k: v for k, v in params.items()
                if key + '.' + k in defaults and v != defaults[key + '.' + k]}}
        # Preserve the printing stage of a duplicated word, including shared ink and screening.
        chain = list(document.get('effect_order', ()))
        chain.extend(k for k in resolved_order(self.preset) if k in self.modules and k not in chain)
        insert = chain.index(owner) + 1 if owner in chain else len(chain)
        if duplicate == 'text':
            insert = 0
        chain.insert(insert, key)
        document['effect_order'] = chain
        order = list(dict.fromkeys([*self.order, *options.get('order', ())]))
        order.insert(order.index(above) if above in order else 0, key)
        options['order'] = order
        if duplicate in options.get('footer', ()):
            options['footer'].append(key)
        return key

    @staticmethod
    def _copy_impression(document, owner, key, defaults):
        """Copy authored values at their original scopes, including moving clip bases."""
        from nebula.documents.synth_automation import TARGETS
        from nebula.render.synth_instances import base_path
        def remap(path):
            return key + path[len(owner):]
        for state in document['source']['states'].values():
            values, enabled = state_values(state)
            if owner in enabled:
                state['enabled'] = sorted(enabled | {key})
            overrides = {remap(p): v for p, v in values.items() if p.startswith(owner + '.')
                         and defaults.get(remap(p)) != v}
            if overrides:
                state.setdefault('overrides', {}).update(overrides)
        for target in (document, *document['sections']):
            entry = target['effects'].get(owner)
            if entry:
                clone = copy.deepcopy(entry)
                clone['params'] = {remap(p): v for p, v in entry['params'].items()}
                target['effects'][key] = clone
            events = target.get('automations', [])
            copies = [dict(e, id='gesture-' + uuid.uuid4().hex, path=remap(e['path']))
                      for e in events if e['path'].startswith(owner + '.') and base_path(e['path']) in TARGETS]
            events.extend(copies)


def render_stack(preset, seconds, size, options, render):
    """Move separately printed impressions while preserving their native ink processing.

    Two consecutive native proofs isolate the premultiplied contribution of an
    impression, including print grain. Changing its depth changes only the amount
    of that contribution transmitted by the layers above. Accumulate that change
    against the original proof, keeping at most two native prefixes in memory.
    """
    frame = PosterFrame.from_preset(preset, seconds, options)
    native = [k for k in frame.native_order if k not in frame.hidden]
    desired = [k for k in frame.order if k not in frame.hidden]

    def proof(omitted):
        omitted = frame.hidden.union(omitted)
        if not omitted:
            return render(preset)
        modules = []
        for m in preset['modules']:
            key = m['id']
            if key == 'dye_transfer' and 'plate' in omitted:
                m = dict(m, params=dict(m['params'], mask_opacity=0.))
            elif key == 'text' and key in omitted:
                m = dict(m, params=dict(m['params'], opacity=0.))
            elif key in omitted:
                m = dict(m, enabled=False)
            modules.append(m)
        return render(dict(preset, modules=modules))

    full = proof(())
    if native == desired:
        return full

    def transmission(keys):
        t = np.ones((size[1], size[0]), np.float32)
        for key in keys:
            t *= 1. - np.asarray(frame.mask(key, size, material=True), np.float32) / 255.
        return t

    result = np.array(full, np.float32)
    last_prefix, previous = None, None
    for i in reversed(range(len(native))):
        key = native[i]
        old, new = set(native[:i]), set(desired[:desired.index(key)])
        if old == new:
            continue
        weight = transmission(sorted(new - old)) - transmission(sorted(old - new))
        weight *= transmission(sorted(old & new))
        if not weight.any():
            continue
        if last_prefix != i + 1:
            previous = np.asarray(proof(native[:i + 1]), np.float32)
        current = np.asarray(proof(native[:i]) if i else full, np.float32)
        ink = current - previous * transmission([key])[..., None]
        result += ink * weight[..., None]
        previous, last_prefix = current, i
    return Image.fromarray(np.uint8(np.clip(np.rint(result), 0, 255)))
