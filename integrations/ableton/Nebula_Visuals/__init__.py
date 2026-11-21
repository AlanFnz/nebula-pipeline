"""Optional Ableton control surface: recover held Nebula notes after a swap."""


def create_instance(c_instance):
    from .surface import NebulaVisuals
    return NebulaVisuals(c_instance)
