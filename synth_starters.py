"""Independent editable copies of the built-in studies."""
from synth_composition import ink_bloom_composition, particle_composition, particle_orbit_composition, reference_composition


STARTERS = (
    ("refined", "Refined signal · 15s", lambda: reference_composition(refined=True)),
    ("approved", "Approved signal · 15s", reference_composition),
    ("particle-head", "Particle head · 15s", lambda: particle_composition(refined=True)),
    ("particle-orbit", "Expand / orbit · 15s", particle_orbit_composition),
    ("original-particles", "Original particles · 15s", particle_composition),
    ("ink-bloom", "Ink bloom · 3.5s", ink_bloom_composition),
)


def starter_composition(identifier):
    for key, _label, factory in STARTERS:
        if key == identifier:
            return factory()
    raise ValueError(f"Unknown starter: {identifier}")
