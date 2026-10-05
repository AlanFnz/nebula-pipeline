"""Presentation-only grouping. Parameter names and saved values stay unchanged."""


def control_group(path):
    from synth_instances import base_path
    path = base_path(path)
    module, key = path.split('.')
    if module == 'particles' and key in ('assembly', 'breathing', 'motion', 'release', 'turn_scope', 'orbit_start', 'orbit_handoff'):
        return 'Motion & timing'
    if module == 'signal_repetition':
        if key in ('input', 'region', 'show_key') or key.startswith('key_'): return 'Signal selection'
        if key in ('spacing', 'sample_width', 'sample_center', 'contour', 'row_height', 'row_breakup', 'row_lines', 'edge_echo', 'edge_distance'): return 'Repetitions'
        if key in ('wave', 'drift', 'instability', 'rate', 'cadence', 'outline_warp'): return 'Motion & timing'
        if key.startswith('outside_'): return 'Outside selection'
        if key in ('relief', 'detail', 'fringe', 'edge_width', 'exposure'): return 'Color & light'
    if module == 'scan_modulation':
        if key in ('input', 'region', 'show_key') or key.startswith('key_'): return 'Signal selection'
        if key.startswith('fade'): return 'Selection fade'
        if key.startswith('spark') or key == 'sparks': return 'Bright points'
        if key in ('row_pitch', 'irregularity', 'wave', 'tear', 'streak', 'depth', 'dropout'): return 'Scan structure'
        if key in ('black', 'white', 'exposure', 'fragment_width'): return 'Color & light'
    if module == 'crt_capture':
        if key in ('pitch', 'phosphor', 'moire', 'moire_pitch', 'angle', 'curvature', 'weave', 'field', 'bend', 'drift'): return 'Screen interference'
        if key in ('softness', 'focus_drift', 'halation', 'threshold', 'radius'): return 'Lens & light spill'
        if key in ('exposure', 'flicker'): return 'Color & light'
    if module == 'chroma_print':
        if key in ('detail', 'detail_radius', 'softness'): return 'Texture & detail'
        if key != 'mix': return 'Color & light'
    if module == 'slice_echo':
        if key.startswith('flash_'): return 'Fragment flashes'
        if key in ('shift_x', 'shift_y', 'travel', 'activity', 'timing_scatter', 'motion_chaos'): return 'Motion & timing'
        if key in ('exposure', 'highlight_protect', 'negative'): return 'Color & light'
        if key in ('angle','width','edge_breakup'): return 'Shape & layout'
        if key == 'envelope': return 'Motion & timing'
        if key == 'luma_mask': return 'Output & blending'
        if key == 'screen': return 'Output & blending'
    if module == 'screen_mesh':
        if key == 'exposure': return 'Color & light'
        if key == 'angle': return 'Shape & layout'
    if module == 'broadcast' and key == 'roll': return 'Motion & timing'
    if module == 'tape' and key in ('pull', 'pull_edges'): return 'Motion & timing'
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
