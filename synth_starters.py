"""Independent editable copies of the built-in studies."""
from synth_composition import ink_bloom_composition, mixed_media_composition, particle_composition, particle_orbit_composition, reference_composition, profile_signal_composition, profile_echoes_composition
from synth_composition import normalize_composition
from synth_compat import starter_snapshot
from synth_profile_recipes import clear_profile_composition, doryphoros_composition
from synth_text_recipes import text_composition


STARTERS = (
    ("refined", "Refined signal · 15s", lambda: reference_composition(refined=True)),
    ("approved", "Approved signal · 15s", reference_composition),
    ("particle-head", "Particle head · 15s", lambda: particle_composition(refined=True)),
    ("particle-orbit", "Expand / orbit · 15s", particle_orbit_composition),
    ("original-particles", "Original particles · 15s", particle_composition),
    ("ink-bloom", "Ink bloom · 3.5s", ink_bloom_composition),
    ("profile-signal", "Profile / phosphor scan · 4s", profile_signal_composition),
    ("profile-echoes", "Profile / signal echoes · 8s", profile_echoes_composition),
    ("profile-clear", "Profile / clear silhouette · 8s", clear_profile_composition),
    ("profile-doryphoros", "Profile / Doryphoros · 8s", doryphoros_composition),
    ("mixed-media", "Mixed media / two bursts · 7s", mixed_media_composition),
    ('text-phosphor', 'Text / phosphor drift · 6s', lambda: text_composition('phosphor')),
    ('text-pressure', 'Text / pressure · 6s', lambda: text_composition('pressure')),
    ('text-pressure-original', 'Text / pressure (first version) · 6s', lambda: starter_snapshot('text-pressure-original')),
    ('text-transmission', 'Text / lost transmission · 6s', lambda: text_composition('transmission')),
    ('text-night', 'Text / night monitor · 6s', lambda: text_composition('night')),
)


def starter_composition(identifier):
    for key, _label, factory in STARTERS:
        if key == identifier:
            project = starter_snapshot(identifier)
            project['render_version'] = 2
            project['source']['render_version'] = 2
            return normalize_composition(project)
    raise ValueError(f"Unknown starter: {identifier}")
