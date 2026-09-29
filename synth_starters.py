"""Independent editable copies of the built-in studies."""
from synth_composition import ink_bloom_composition, mixed_media_composition, particle_composition, particle_orbit_composition, reference_composition, profile_signal_composition, profile_echoes_composition
from synth_composition import normalize_composition
from synth_compat import starter_snapshot
from synth_profile_recipes import clear_profile_composition, doryphoros_composition
from synth_text_recipes import text_composition, opium_composition


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
    ('text-opium', 'Text / opium · 4.5s', opium_composition),
    ('text-phosphor', 'Text / phosphor drift · 6s', lambda: text_composition('phosphor')),
    ('text-phosphor-original', 'Text / phosphor drift (first version) · 6s', lambda: starter_snapshot('text-phosphor-original')),
    ('text-pressure', 'Text / pressure · 6s', lambda: text_composition('pressure')),
    ('text-pressure-original', 'Text / pressure (first version) · 6s', lambda: starter_snapshot('text-pressure-original')),
    ('text-transmission', 'Text / lost transmission · 6s', lambda: text_composition('transmission')),
    ('text-transmission-original', 'Text / lost transmission (first version) · 6s', lambda: starter_snapshot('text-transmission-original')),
    ('text-night', 'Text / night monitor · 6s', lambda: text_composition('night')),
    ('text-night-original', 'Text / night monitor (first version) · 6s', lambda: starter_snapshot('text-night-original')),
)


# First appearance in the repository, retained independently of app builds.
STARTER_DATES = {
    'refined': '2026-09-26', 'approved': '2026-09-26',
    'particle-head': '2026-09-26', 'particle-orbit': '2026-09-26',
    'original-particles': '2026-09-26',
    'ink-bloom': '2026-09-27', 'mixed-media': '2026-09-27',
    'profile-signal': '2026-09-27', 'profile-echoes': '2026-09-27',
    'profile-clear': '2026-09-27', 'profile-doryphoros': '2026-09-27',
    'text-phosphor': '2026-09-28', 'text-phosphor-original': '2026-09-28',
    'text-pressure': '2026-09-28', 'text-pressure-original': '2026-09-28',
    'text-transmission': '2026-09-28', 'text-transmission-original': '2026-09-28',
    'text-night': '2026-09-28', 'text-night-original': '2026-09-28',
    'text-opium': '2026-09-29',
}


def starter_composition(identifier):
    for key, _label, factory in STARTERS:
        if key == identifier:
            project = starter_snapshot(identifier)
            project['render_version'] = 2
            project['source']['render_version'] = 2
            return normalize_composition(project)
    raise ValueError(f"Unknown starter: {identifier}")
