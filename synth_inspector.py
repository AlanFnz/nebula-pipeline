"""Presentation-only grouping. Parameter names and saved values stay unchanged."""


def control_group(path):
    module, key = path.split('.')
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
