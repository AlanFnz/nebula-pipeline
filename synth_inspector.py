"""Presentation-only grouping. Parameter names and saved values stay unchanged."""


def control_group(path):
    module, key = path.split('.')
    if module == 'chroma_print':
        if key in ('detail', 'detail_radius', 'softness'): return 'Texture & detail'
        if key != 'mix': return 'Color & light'
    if module == 'slice_echo':
        if key in ('shift_x', 'shift_y', 'travel', 'activity'): return 'Motion & timing'
        if key in ('exposure', 'highlight_protect', 'negative'): return 'Color & light'
        if key in ('angle','width','edge_breakup'): return 'Shape & layout'
        if key == 'envelope': return 'Motion & timing'
        if key == 'luma_mask': return 'Output & blending'
        if key == 'screen': return 'Output & blending'
    if module == 'screen_mesh':
        if key == 'exposure': return 'Color & light'
        if key == 'angle': return 'Shape & layout'
    if module == 'broadcast' and key == 'roll': return 'Motion & timing'
    if module == 'tape' and key == 'tracking': return 'Texture & detail'
    if key in ('content', 'font', 'artwork'): return 'Wording & source' if module == 'text' else 'Source'
    if key in ('copies', 'copy_gap', 'copy_floor'): return 'Repetitions'
    if any(word in key for word in ('hue', 'saturation', 'brightness', 'tint', 'magenta', 'cyan', 'palette', 'color', 'black', 'white')):
        return 'Color & light'
    if any(word in key for word in ('seconds', 'period', 'phase', 'speed', 'rate', 'cadence', 'reveal', 'motion', 'ease', 'zoom_', 'cycle', 'revolutions')):
        return 'Motion & timing'
    if any(word in key for word in ('shape', 'width', 'height', 'size', 'scale', 'stretch', 'spacing', 'tracking', 'leading', 'align', 'fit', 'wrap', 'rotation', 'position', 'yaw', 'pitch', 'roll', 'diameter', 'sides', 'aperture', 'count', 'attractor', 'model')):
        return 'Shape & layout'
    if key in ('mix', 'opacity', 'sampling', 'resolution', 'canvas_coverage', 'strength'): return 'Output & blending'
    return 'Texture & detail'


def grouped_paths(paths):
    groups = {}
    for path in paths: groups.setdefault(control_group(path), []).append(path)
    return groups.items()
