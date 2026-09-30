"""Reusable effect definitions shared by the composer, inspector and compiler.

An empty rack follows the embedded recipe. Explicit parameter values are
absolute overrides; untouched parameters retain their authored animation.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from synth import MODULE_BY_ID, Param, curated_presets
from synth_artwork import validate_artwork
from synth_text import validate_text
from synth_ink_timing import stage_durations


@dataclass(frozen=True)
class Effect:
    id: str
    label: str
    description: str
    paths: tuple[str, ...]
    modules: tuple[str, ...]
    off: tuple[tuple[str, float], ...] = ()
    looks: tuple[tuple[str, dict], ...] = ()
    primary: int = 6


def paths(module, keys=None):
    return tuple(f"{module}.{key}" for key in (keys.split() if keys else [p.key for p in MODULE_BY_ID[module].params]))


EFFECTS = (
    Effect('scan_modulation', 'Scan modulation', 'Interrupt source rows with coupled oscillators, color-lock failures and bright points. Apply to the whole picture, highlights or a color range; Selection view helps tune the key. Works with footage, text and generated objects.', paths('scan_modulation'), ('scan_modulation',)),
    Effect('crt_capture', 'CRT capture', 'Film the signal through curved phosphor interference, lens softness, focus breathing and emitted-light noise. Covers the entire canvas.', paths('crt_capture'), ('crt_capture',)),
    Effect('text', 'Text', 'Editable wording, typeface, spacing and color. Select Text in Object to replace another source while retaining its treatments. Position uses the shared Object controls.', paths('text'), ('text',), primary=10),
    Effect('stretch_echo', 'Stretch echo', 'Stretch luminous contours behind the source. Adjustable shape, timing and color; follows the shared Object position. Applies before finishing to text, objects and footage.', paths('stretch_echo'), ('stretch_echo',)),
    Effect('signal_etch', 'Signal etch', 'Erode highlights with fresh horizontal grain and pulsing scattered light. The texture follows the image rather than adding an independent noise layer.', paths('signal_etch'), ('signal_etch',)),
    Effect('chroma_print', 'Chroma print', 'Color-map source tones with luminous mids, pale highlights and an optional warm accent. Works on text, objects and footage before finishing.', paths('chroma_print'), ('chroma_print',)),
    Effect('slice_echo', 'Slice echo', 'Displaced strips or broken patches of the source, with adjustable width, stepped edges, negative exposure, tint and motion.', paths('slice_echo'), ('slice_echo',)),
    Effect('screen_mesh', 'Screen mesh', 'Tilted phosphor columns, RGB subpixels and fine scan rows. Covers the canvas and preserves black.', paths('screen_mesh'), ('screen_mesh',)),
    Effect('broadcast', 'Broadcast wear', 'Colored shadow drift, static interruptions, rolling signal loss, polarity reversals and curved CRT edges. Applies to lettering, generated artwork and imported footage.', paths('broadcast'), ('broadcast',), primary=8),
    Effect("subject_cutout", "Subject cutout", "Isolate the foreground locally before applying image treatments. Crowd recovers smaller figures using individual detection regions. Mask continuity fills brief gaps where neighboring source frames agree. First use is cached locally. Available with imported video on macOS.", paths("subject_cutout"), ("subject_cutout",), primary=8),
    Effect("photocopy", "Photocopy", "Crushed black ink, fresh toner grain, cold highlights and screened dots. Exposure pulses, uneven illumination and print cadence can all be adjusted independently. Applies to videos and generated artwork.", paths("photocopy"), ("photocopy",),
           looks=(("Cold copy / pulses", {}), ("Clean monochrome", {"photocopy.tint": 0., "photocopy.blackout": 0., "photocopy.light_depth": 0., "photocopy.flutter": 0.}), ("Screen print", {"photocopy.halftone": .8, "photocopy.grain": .4, "photocopy.blackout": 0.})), primary=8),
    Effect("signal_background", "Signal background", "Refined signal's green-black field, fine grain and horizontal noise in the deepest shadows. Bright artwork stays intact; the texture covers the whole canvas.", paths("signal_background"), ("signal_background",),
           looks=(("Refined signal black", {}), ("Quiet charcoal", {"signal_background.tint": 0., "signal_background.grain": .035}))),
    Effect("silhouette", "Model silhouette", "Fixed solid projection of the existing human head mesh. Combine with Edge phosphor and Scan drag.", paths("silhouette"), ("silhouette",), primary=5),
    Effect("edge_phosphor", "Edge phosphor", "Darken a source into a silhouette with a noisy backlight, colored contour and faint echo. Works on heads, forms, stamps and dense particles.", paths("edge_phosphor"), ("edge_phosphor",),
           looks=(("Green / magenta contour", {}), ("Red / blue contour", {"edge_phosphor.hue": 0., "edge_phosphor.fringe_hue": .64, "edge_phosphor.grain": .5}))),
    Effect("scan_drag", "Scan drag", "Pull bright source colors into horizontal streaks and overload bursts. No luminous shapes are added to an empty signal.", paths("scan_drag"), ("scan_drag",),
           looks=(("Fine signal streaks", {}), ("Overloaded scan", {"scan_drag.overload": 1., "scan_drag.height": .16, "scan_drag.density": .35}), ("Full canvas", {"scan_drag.window": 1.})), primary=8),
    Effect("ink_bloom", "Ink bloom", "Overlapping stamps unfold, turn and gather again. Look sets the silhouette and inks. Timing sets unfold/fold durations, holds and gesture speed. Frame jitter controls the small positional shakes separately.",
           tuple(path for path in paths("ink_bloom") if path not in {'ink_bloom.clock_mode', 'ink_bloom.clock_scale'}), ("ink_bloom",),
           looks=(("CMY unfolding cluster", {}),
                  ("Single rough stamp", {"ink_bloom.count": 1, "ink_bloom.cycle": 0., "ink_bloom.revolutions": 0., "ink_bloom.tumble": 0.}),
                  ("Warm paper flowers", {"ink_bloom.palette": 1, "ink_bloom.points": 8, "ink_bloom.point_depth": .3}),
                  ("Monochrome rosette", {"ink_bloom.palette": 2, "ink_bloom.count": 9})), primary=8),
    Effect("forms", "Luminous forms", "Solid or hollow sources. Combine with ghosts, rays and signal effects.",
           paths("slab", "shape width height count position_x position_y diameter sides rotation spacing edge_hardness hollow intensity fill_magenta fill_gradient vertical_tint edge_softness magenta cyan jitter frame_jitter edge_ripple notch"), ("slab",),
           looks=(("Solid rectangle", {"slab.shape": 0, "slab.hollow": 0, "slab.width": .24}),
                  ("Hollow frame", {"slab.shape": 0, "slab.hollow": 1, "slab.width": .4}),
                  ("Polygon", {"slab.shape": 3, "slab.diameter": .5, "slab.sides": 6}))),
    Effect("rays", "Rays / Venetian blinds", "Thin rays or thick, uneven blinds. Both use the same adjustable aperture.",
           paths("blinds", "rows thickness swelling curvature orientation irregularity aperture aperture_height aperture_vertical taper asymmetry phase offset aperture_position edge_softness row_drift magenta intensity tail_spread edge_bias shape diameter sides rotation"), ("blinds",),
           looks=(("Thin rays", {"blinds.rows": 9, "blinds.thickness": .006, "blinds.swelling": .15}),
                  ("Venetian blinds", {"blinds.rows": 12, "blinds.thickness": .035, "blinds.swelling": .85}),
                  ("Broken fan", {"blinds.rows": 7, "blinds.curvature": .6, "blinds.irregularity": .7, "blinds.orientation": .2}))),
    Effect("particles", "Particle attractor", "Dots follow an invisible 3D target. Impulse gives short, peaked expansions with long holds; Surges adds uneven arrivals and rebound. Release chooses a floor band or outward orbit. Set Assembly cycle to 0 for manual Assembly.",
           paths("particles"), ("particles",),
           looks=(("Human signal surges", {"particles.attractor": 3, "particles.motion": 1, "particles.release": 0, "particles.period": 5., "particles.collapse": .97}),
                  ("Expand / orbit", {"particles.attractor": 3, "particles.motion": 1, "particles.release": 1, "particles.period": 3.8, "particles.orbit_speed": 24., "particles.orbit_start": .7, "particles.dispersion": .9, "particles.scale": .8, "particles.released_brightness": .65}),
                  ("Two impulses / 15s", {"particles.orbit_handoff": 1, "particles.rotation_speed": 18., "particles.turn_scope": 1, "particles.axis_mode": 1, "particles.neck_fade": .42, "particles.yaw": -35., "particles.attractor": 4, "particles.occlusion": 1., "particles.xray": 0., "particles.motion": 2, "particles.release": 1, "particles.period": 7.5, "particles.phase": 0., "particles.expand_seconds": .75, "particles.gather_seconds": 1., "particles.motion_peak": .8, "particles.chaos": .35, "particles.orbit_speed": 24., "particles.dispersion": .9, "particles.scale": .8, "particles.released_brightness": .45, "particles.hue": .70, "particles.saturation": .42, "particles.color_spread": .09, "particles.color_drift": .001}),
                  ("Assemble / disperse", {"particles.release": 0, "particles.collapse": 0.}),
                  ("Held portrait", {"particles.breathing": 0., "particles.assembly": 1., "particles.rotation_speed": 0., "particles.turbulence": .06}),
                  ("Signal fountain", {"particles.release": 0, "particles.collapse": .95, "particles.color_spread": 1.5, "particles.turbulence": .3}),
                  ("Orbiting ring", {"particles.attractor": 2, "particles.pitch": 35., "particles.xray": .4})), primary=9),
    Effect("ghosts", "Ghosts / trails", "Shifted copies of the whole image, plus a companion ghost when a luminous form is present.",
           paths("smear") + paths("slab", "ghost_opacity ghost_offset ghost_width ghost_grain"), ("smear",), (("slab.ghost_opacity", 0.),),
           (("Soft echoes", {"smear.amount": .16, "smear.ghosts": 4, "slab.ghost_opacity": .34}),
            ("Long trail", {"smear.amount": .4, "smear.ghosts": 8, "slab.ghost_opacity": .15}))),
    Effect("breakup", "Signal breakup", "Horizontal tearing and missing bands applied to the combined image.",
           paths("breakup"), ("breakup",),
           looks=(("Tracking loss", {}), ("Hard cuts", {"breakup.amount": .24, "breakup.bands": 9, "breakup.dropout": .35, "breakup.rate": 5., "breakup.mix": 1.}))),
    Effect("tape", "Tape damage", "Faults in the recorded image: tracking slips, scanline loss, color lag and bleed. Adds no bars or independent shapes.", paths("tape"), ("tape",),
           looks=(("Worn tape", {}), ("Tracking slip", {"tape.tracking": .11, "tape.dropouts": .5, "tape.mix": 1.}),
                  ("Color bleed", {"tape.tracking": .01, "tape.chroma_delay": .015, "tape.bleed": .03}))),
    Effect("drift", "Signal drift", "Continuous waves displace the combined image in two dimensions.", paths("warp"), ("warp",)),
    Effect("cloud", "Granular halo", "A noisy halo around luminous forms. Requires Luminous forms in the same section.",
           paths("slab", "cloud_strength cloud_detail cloud_tint cloud_position"), (), (("slab.cloud_strength", 0.), ("slab.cloud_detail", 0.)),
           (("Violet cloud", {"slab.cloud_strength": .6, "slab.cloud_detail": .75}),)),
    Effect("flare", "Exposure flare", "An exposure crest over the sources. Timeline flashes and sweeps remain separate transitions.", paths("flare"), ("flare",),
           looks=(("Exposure sweep", {"flare.strength": .8, "flare.spread": .25}),)),
    Effect("separation", "Color separation", "Displace RGB channels around the sources.", paths("separation"), ("separation",)),
    Effect("interference", "Signal interference", "Moving chromatic exposure bands and bent vertical strings. Processes particles, forms and rays before bloom and grain.", paths("interference"), ("interference",)),
    Effect("frame_jitter", "Frame jitter", "Reposition the artwork slightly on every held frame. Horizontal/vertical motion, rotation and scale vary independently. Print background and finishing grain keep their own clocks.",
           paths("frame_jitter"), ("frame_jitter",),
           looks=(("Hand-positioned paper", {}),
                  ("Subtle scan", {"frame_jitter.x": 2., "frame_jitter.y": 1.5, "frame_jitter.rotation": .10, "frame_jitter.scale": .05}),
                  ("Loose cut-paper", {"frame_jitter.x": 9., "frame_jitter.y": 7., "frame_jitter.rotation": .6, "frame_jitter.scale": .3}))),
    Effect("bloom", "Bloom", "Spread light from the brightest parts of the image.", paths("bloom"), ("bloom",)),
    Effect("raster", "Raster / grain", "Soften the signal and add scan lines, luminance grain and chroma noise.", paths("raster"), ("raster",)),
    Effect("print_surface", "Print surface", "Worn ink on charcoal stock. Frame noise renews the background every scan while preserving the ink treatment; Original paper retains the moving sheet. Applied after signal treatments.",
           paths("print_surface"), ("print_surface",),
           looks=(("Gritty charcoal stock", {}),
                  ("Rough photocopy", {"print_surface.ink_wear": .7, "print_surface.edge_wear": .9, "print_surface.grain_size": 2.8}),
                  ("Quiet paper", {"print_surface.paper_motion": 0., "print_surface.boil": .08, "print_surface.registration": .0005}),
                  ("Chaotic background", {"print_surface.background_mode": 1}))),
    Effect("low_res", "Low-res finish", "Keep the low-resolution preview texture in a full-size export. The whole image, including grain, background and transitions, renders at Working resolution (longest edge), then scales to your canvas. Preview quality still controls the monitor size.",
           paths("low_res"), ("low_res",),
           looks=(("360 px preview feel", {}),
                  ("Chunky / 180 px", {"low_res.resolution": 180}),
                  ("Fine / 720 px", {"low_res.resolution": 720}),
                  ("Crisp pixels / 240 px", {"low_res.resolution": 240, "low_res.sampling": 1}))),
)
EFFECT_BY_ID = {effect.id: effect for effect in EFFECTS}


def parameter(path) -> Param:
    module, key = path.split(".")
    return next(spec for spec in MODULE_BY_ID[module].params if spec.key == key)


def effect_preset(effect_id, look=0):
    effect = EFFECT_BY_ID[effect_id]
    values = {path: parameter(path).default for path in effect.paths}
    if effect.looks:
        values.update(effect.looks[look][1])
    return {"mode": "on", "params": values}


def normalize_effects(raw):
    if not isinstance(raw, dict):
        raise ValueError("Effects must be an object")
    result = {}
    for key, entry in raw.items():
        if key not in EFFECT_BY_ID or not isinstance(entry, dict):
            raise ValueError(f"Unknown effect: {key}")
        mode = entry.get("mode", "recipe")
        if mode not in {"recipe", "on", "off"}:
            raise ValueError(f"Invalid mode for {key}")
        params = entry.get("params", {})
        if not isinstance(params, dict):
            raise ValueError(f"{key} parameters must be an object")
        values = {}
        for path, value in params.items():
            if path not in EFFECT_BY_ID[key].paths:
                raise ValueError(f"Unknown {key} parameter: {path}")
            spec = parameter(path)
            if spec.kind == 'text':
                values[path] = validate_text(value)
                continue
            if spec.kind == "artwork":
                values[path] = validate_artwork(value)
                continue
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not spec.minimum <= value <= spec.maximum:
                raise ValueError(f"{path} must be between {spec.minimum} and {spec.maximum}")
            if spec.kind == "int" and not float(value).is_integer():
                raise ValueError(f"{path} must be an integer")
            values[path] = int(value) if spec.kind == "int" else float(value)
        result[key] = {"mode": mode, "params": values}
    return result


def merge_effects(global_effects, local_effects):
    result = copy.deepcopy(global_effects)
    for key, entry in local_effects.items():
        target = result.setdefault(key, {"mode": "recipe", "params": {}})
        if entry["mode"] != "recipe":
            target["mode"] = entry["mode"]
        target["params"].update(entry["params"])
    return result


def state_values(state):
    preset = curated_presets()[state["preset"]]
    values = {f"{item['id']}.{key}": value for item in preset["modules"] for key, value in item["params"].items()}
    values.update(state.get("overrides", {}))
    enabled = set(state.get("enabled", [item["id"] for item in preset["modules"] if item["enabled"]]))
    return values, enabled


def apply_effects(state, effects):
    if not effects:
        return state
    result = copy.deepcopy(state)
    _, enabled = state_values(state)
    overrides = result.setdefault("overrides", {})
    for effect in EFFECTS:
        entry = effects.get(effect.id)
        if not entry:
            continue
        overrides.update(entry["params"])
        if entry["mode"] == "on":
            enabled.update(effect.modules)
        elif entry["mode"] == "off":
            enabled.difference_update(effect.modules)
            overrides.update(effect.off)
    result["enabled"] = [module for module in MODULE_BY_ID if module in enabled]
    return result


def effect_active(effect, values, enabled):
    if effect.id == "ghosts":
        return ("smear" in enabled and values["smear.amount"] > 0) or ("slab" in enabled and values["slab.ghost_opacity"] > 0)
    if effect.id == "cloud":
        return "slab" in enabled and values["slab.cloud_strength"] > 0
    return any(module in enabled for module in effect.modules)


def describe_effects(states):
    """Inspect real recipe values, including ranges across animated states."""
    resolved = []
    # Display effective seconds, not the internal negative "follow recipe"
    # value. Resolve each state separately to retain per-section differences.
    for state in states:
        values, enabled = state_values(state)
        if 'ink_bloom' in enabled:
            ink = {key.removeprefix('ink_bloom.'): value for key, value in values.items() if key.startswith('ink_bloom.')}
            durations = stage_durations(ink)
            values.update({f'ink_bloom.{key}': value for key, value in durations.items()})
            base_speed = ink['clock_scale'] if ink['clock_mode'] else (values['speed'] if 'speed' in values else curated_presets()[state['preset']]['speed'])
            speed = ink['motion_speed'] * base_speed
            values['_ink_loop'] = sum(durations.values()) / speed if speed > 0 else float('inf')
        resolved.append((values, enabled))
    result = {}
    for effect in EFFECTS:
        active = [(values, enabled) for values, enabled in resolved if effect_active(effect, values, enabled)]
        ranges = {}
        for path in effect.paths:
            module = path.split(".")[0]
            values = [values[path] for values, enabled in active if module in enabled]
            ranges[path] = (min(values), max(values)) if values else (parameter(path).default,) * 2
        if effect.id == 'ink_bloom' and not active:
            defaults = {spec.key: spec.default for spec in MODULE_BY_ID['ink_bloom'].params}
            for key, value in stage_durations(defaults).items():
                ranges[f'ink_bloom.{key}'] = (value, value)
        result[effect.id] = {"active": bool(active), "intermittent": 0 < len(active) < len(resolved), "ranges": ranges}
        if effect.id == 'ink_bloom':
            loops = [values['_ink_loop'] for values, _ in active]
            result[effect.id]['loop_seconds'] = (min(loops), max(loops)) if loops else None
    return result
