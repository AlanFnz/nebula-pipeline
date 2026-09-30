"""New profile variations built from an immutable, already approved recipe."""
from synth_compat import starter_snapshot
from synth_composition import normalize_composition


def clear_profile_composition():
    project = starter_snapshot('profile-echoes')
    project.update(name='Profile / clear silhouette', render_version=2)
    project['source'].update(name=project['name'], render_version=2)
    for state in project['source']['states'].values():
        p = state['overrides']
        p.update({
            'silhouette.definition': .65, 'silhouette.scale': .44,
            'silhouette.center_y': .45, 'silhouette.yaw': -94., 'silhouette.softness': .2,
            'edge_phosphor.rim_width': .004, 'edge_phosphor.glow': .005,
            'edge_phosphor.separation': .007,
            # The same neck blend, now an explicit reusable object region.
            'edge_phosphor.fade_mode': 1, 'edge_phosphor.fade_anchor': 1,
            'edge_phosphor.fade_strength': 1., 'edge_phosphor.fade_start': .9,
            'edge_phosphor.fade_width': .38, 'edge_phosphor.fade_angle': 0.,
            'edge_phosphor.fade_x': 0., 'edge_phosphor.fade_y': 0.,
            'edge_phosphor.fade_curve': 1, 'edge_phosphor.fade_softness': .065,
        })
        p['edge_phosphor.fringe'] *= .7
        if p.get('scan_drag.overload', 0.) < .1:
            # Quieter holds make the nose/mouth legible between full-strength
            # authored overloads; the eight-second choreography stays intact.
            p['scan_drag.amount'] *= .6
            p['scan_drag.jitter'] *= .5
    return normalize_composition(project)


def doryphoros_composition():
    project = clear_profile_composition()
    project['name'] = project['source']['name'] = 'Profile / Doryphoros'
    for state in project['source']['states'].values():
        state['overrides'].update({
            'silhouette.model': 2, 'silhouette.definition': 0.,
            'silhouette.yaw': -90., 'silhouette.neck_fullness': 0.,
        })
    return normalize_composition(project)
