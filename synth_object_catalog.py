"""Inspector navigation only. Source parameters and their owners stay unchanged."""
from synth_effects import EFFECT_BY_ID
from synth_subject import SUBJECTS
from synth_ink_timing import TIMING_KEYS
from synth_inspector import grouped_paths


PARAMETER_OWNER = {p: effect for _, effects in SUBJECTS.values()
                   for effect in effects for p in EFFECT_BY_ID[effect].paths}
OBJECT_PATHS = {
    kind: tuple(p for effect in effects for p in EFFECT_BY_ID[effect].paths
                if not (effect == 'ink_bloom' and p.split('.')[1] in TIMING_KEYS))
    for kind, (_, effects) in SUBJECTS.items() if effects
}

# Primary controls are first; the remaining groups stay folded until requested.
# A registry fallback keeps future controls reachable without changing a study.
FAMILY_GROUPS = {
    'memory': (
        ('Memory', 'persistence drift dissolve trail_opacity drift_angle expansion'),
        ('Shape & scale', 'shape size sides rotation'),
        ('Path & travel', 'path travel amplitude_x amplitude_y period variation phase spin'),
        ('Color & background', 'palette color_speed color_shift light background'),
        ('Optical finish', 'softness glow mix')),
    'lattice': (
        ('Shape & layout', 'shape sides spacing size minimum rotation'),
        ('Wave motion', 'wave_shape wavelength direction angle pulse phase'),
        ('Rhythm & timing', 'color_rhythm bpm phrase_bars period color_period color_spread color_phase'),
        ('Color & background', 'palette gradient saturation light background'),
        ('Optical finish', 'rim softness glow glow_radius grain mix')),
    'solid': (
        ('Model & scale', 'shape model_data height_stretch scale corner_radius'),
        ('Pose & camera', 'yaw pitch roll perspective'),
        ('Rotation & motion', 'turn_speed tumble_speed roll_speed variation'),
        ('Material & reflections', 'material roughness specular glass_transmission glass_refraction'),
        ('Die markings', 'pip_size pip_light pip_depth'),
        ('Color & light', 'palette color_phase color_speed wash shading saturation light mix')),
    'prismatic': (
        ('Shape & layout', 'shape sides center_shape size gather opening rotation ribbon'),
        ('Folds & motion', 'fold_depth fold_period fold_phase rotation_speed turn_variation transition_ease turn_settle drift'),
        ('Color & light', 'palette color_phase color_speed wash shading saturation light')),
    'radial': (
        ('Shape & detail', 'expansion petals detail branching'),
        ('Motion & drift', 'flow variation rotation phase center_drift drift_speed'),
        ('Ray vibration', 'vibration vibration_speed vibration_wavelength vibration_irregularity'),
        ('Color & light', 'palette color_phase color_speed light'),
        ('Optical finish', 'softness grain')),
    'silhouette': (
        ('Model & scale', 'model scale definition'),
        ('Pose & framing', 'yaw pitch roll center_x center_y'),
        ('Neck & edges', 'neck_fullness neck_length softness opacity')),
    'ink': (
        ('Stamp & scale', 'shape artwork size shape_width shape_height sides shape_rotation'),
        ('Copies & outline', 'count spread points point_depth irregularity'),
        ('Gesture & pose', 'opening revolutions turn rotation tumble tilt fan center_fold disorder'),
        ('Depth & framing', 'cluster_depth stack_spacing perspective position_x position_y'),
        ('Color & ink', 'palette split_ink back_ink saturation opacity')),
    'particles': (
        ('Model & particles', 'attractor scale count dot_size neck_fade'),
        ('Pose & camera', 'yaw pitch rotation_speed turn_scope axis_mode position_x position_y perspective'),
        ('Assembly & motion', 'motion release assembly breathing period expand_seconds gather_seconds motion_peak'),
        ('Orbit & turbulence', 'orbit_speed orbit_start orbit_handoff acceleration chaos overshoot dispersion turbulence collapse flow phase jitter'),
        ('Depth & visibility', 'xray occlusion relief intensity released_brightness'),
        ('Color & light', 'hue saturation color_spread color_drift shimmer')),
}


def family_groups(kind):
    """Return (page, title, initially open, full parameter paths)."""
    available = OBJECT_PATHS[kind]
    if kind == 'signal':
        return tuple((0, f'{label} · {title}', False, tuple(members))
                     for effect, label in (('forms', 'Form base'), ('rays', 'Ray base'))
                     for title, members in grouped_paths(EFFECT_BY_ID[effect].paths))
    prefix = available[0].split('.')[0]
    groups = [(0, title, index == 0, tuple(f'{prefix}.{key}' for key in keys.split()))
              for index, (title, keys) in enumerate(FAMILY_GROUPS[kind])]
    assigned = {p for _, _, _, members in groups for p in members}
    groups.extend((0, title, False, tuple(members)) for title, members
                  in grouped_paths(p for p in available if p not in assigned))
    return tuple(groups)
