"""Deterministic, source-free visual synthesizer for Nebula Studio.

The renderer is intentionally stateless: a frame is a pure function of a
versioned preset, continuous time and output size.  That makes scrubbing,
variation generation and export agree without a temporal feedback buffer.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass
from numbers import Real
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from synth_particles import render_particles
from synth_tape import render_tape_damage
from synth_instances import InstanceRegistry, instance_base, base_id
from synth_photocopy import render_photocopy
from synth_text import FONTS, validate_text, render_text
from synth_broadcast import render_broadcast, render_broadcast_exposure
from synth_echo import render_stretch_echo, render_signal_etch
from synth_chroma import render_chroma_print, render_slice_echo, render_screen_mesh
from synth_modulation import render_scan_modulation, render_crt_capture
from synth_modulation_controls import modules as modulation_modules
from synth_canvas import content_size, normalize_canvas, source_framing, object_offset
from synth_print import render_ink_bloom, render_print_surface
from synth_profile import render_silhouette, render_edge_phosphor, render_scan_drag
from synth_profile_v1 import render_edge_phosphor as render_edge_phosphor_v1
from synth_compat import CURRENT_RENDER_VERSION, frozen_data, frozen_defaults, render_version
from synth_artwork import validate_artwork
from synth_jitter import render_frame_jitter
from synth_resolution import finish_resolution, render_resolution

SYNTH_SCHEMA_VERSION = 1
SYNTH_PRESETS_DIR = Path.home() / ".nebula_pipeline" / "synth_presets"


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    default: float | int | str
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float = 0.01
    kind: str = "float"
    hint: str = ""
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Module:
    id: str
    label: str
    description: str
    params: tuple[Param, ...]


def P(key, label, default, minimum=0, maximum=1, step=.01, hint="", kind=None, choices=()):
    if kind is None:
        integer_bounds = float(minimum).is_integer() and float(maximum).is_integer()
        kind = "int" if isinstance(default, int) and not isinstance(default, bool) and step == 1 and integer_bounds else "float"
    if kind == "int":
        step = 1
    return Param(key, label, default, minimum, maximum, step, kind=kind, hint=hint, choices=choices)


SHAPES = ("Rectangle", "Ellipse", "Circle", "Polygon")


def geometry_params():
    return (
        P("shape", "Shape", 0, 0, 3, 1, "Geometry of the luminous source or ray aperture.", choices=SHAPES),
        P("diameter", "Diameter", .6, .05, 1.5, .01, "Circle / polygon diameter as a fraction of image height."),
        P("sides", "Polygon sides", 6, 3, 32, 1, "Number of sides of the regular polygon."),
        P("rotation", "Rotation", 0.0, -180, 180, 1, "Rotation in degrees around the source centre."),
    )


MODULES = (
    Module("slab", "Luminous slabs", "Vertical luminous sources with white cores and colored edges.", (
        *geometry_params(),
        P("count", "Slab count", 1, 1, 5, 1, "Number of vertical sources."),
        P("width", "Core width", .18, .02, .8, .01, "Width of the bright central aperture."),
        P("spacing", "Spacing", .22, .02, 1, .01, "Distance between slab centers."),
        P("height", "Height", .62, .08, 1, .01, "Finite vertical extent of the slab."),
        P("position_x", "Horizontal position", .2, -1, 1, .01, "Moves the slab across the frame."),
        P("position_y", "Vertical position", 0, -1, 1, .01, "Moves the slab up or down."),
        P("edge_hardness", "Edge hardness", .82, 0, 1, .01, "Hard rectangular edge versus soft glow."),
        P("hollow", "Hollow centre", 0, 0, 1, .01, "Cuts a dark channel through the luminous core."),
        P("notch", "Missing chunks", .08, 0, 1, .01, "Adds deterministic interruptions to the block."),
        P("intensity", "Core intensity", 1.0, .1, 1.5, .01, "Brightness of the white slab body."),
        P("fill_magenta", "Magenta fill", 0.0, 0, 1, .01, "Moves the slab body from neutral white toward violet-magenta."),
        P("fill_gradient", "Split fill", 0.0, 0, 1, .01, "Concentrates the magenta fill on the left, leaving a white right core."),
        P("vertical_tint", "Blue falloff", 0.0, 0, 1, .01, "Fades a warm upper core into blue-violet at the bottom."),
        P("ghost_width", "Ghost width", .32, .05, 1, .01, "Width of the dimmer right-hand ghost."),
        P("ghost_offset", "Ghost offset", .24, .02, .8, .01, "Distance of the secondary ghost to the right."),
        P("ghost_opacity", "Ghost opacity", .34, 0, 1, .01, "Strength of the secondary ghost."),
        P("edge_softness", "Edge softness", .08, .005, .35, .005, "Soft luminous edge falloff."),
        P("magenta", "Magenta edge", .85, 0, 1, .01, "Purple/magenta channel strength."),
        P("cyan", "Cyan fringe", .42, 0, 1, .01, "Green/cyan channel fringe strength."),
        P("jitter", "Shape irregularity", .12, 0, .5, .01, "Slow shape wobble; does not randomize every frame."),
        P("frame_jitter", "Frame registration", 0.0, 0, .04, .001, "Small independent horizontal registration changes at the treatment rate."),
        P("edge_ripple", "Edge flutter", 0.0, 0, .04, .001, "Uneven horizontal registration across groups of scan lines."),
        P("ghost_grain", "Ghost grain", 0.0, 0, 1, .01, "Breaks the secondary block into fine signal noise."),
        P("cloud_strength", "Signal cloud", 0.0, 0, 1, .01, "Local noisy halo surrounding the block."),
        P("cloud_tint", "Cloud violet", .8, 0, 1, .01, "Blends gray-green signal noise toward violet."),
        P("cloud_position", "Cloud vertical offset", 0.0, -1, 1, .01, "Moves the noisy halo above or below the block."),
        P("cloud_detail", "Cloud granulation", 0.0, 0, 1, .01, "Clumped signal noise that survives softness, including in the ghost."),
    )),
    Module("blinds", "Irregular Venetian blinds", "Horizontal rays that swell into an asymmetric central aperture.", (
        *geometry_params(),
        P("rows", "Ray count", 9, 1, 32, 1, "Number of horizontal rays", kind="int"),
        P("thickness", "Ray thickness", .012, .002, .12, .001, "Thickness of the thin outer rays."),
        P("aperture", "Aperture width", .34, .03, .95, .01, "Width of the thick central region."),
        P("aperture_height", "Aperture height", .64, .10, 1, .01, "Vertical window for thickening the rays."),
        P("aperture_vertical", "Aperture vertical", 0.0, -1, 1, .01, "Moves the thickening window up or down."),
        P("swelling", "Central swelling", .9, 0, 1, .01, "How much rays thicken inside the aperture."),
        P("taper", "Pinch / taper", .8, 0, 1, .01, "Asymmetric point-like taper toward the sides."),
        P("asymmetry", "Asymmetry", .22, -1, 1, .01, "Offsets one side of the aperture envelope."),
        P("orientation", "Orientation", 0.0, -1, 1, .01, "Blend from horizontal rays to vertical rays."),
        P("phase", "Phase", 0.0, -1, 1, .01, "Phase offset for the ray pattern."),
        P("offset", "Pattern offset", 0.0, -1, 1, .01, "Slides the ray stack across the frame."),
        P("aperture_position", "Aperture position", 0.0, -1, 1, .01, "Moves the thick central aperture."),
        P("edge_softness", "Edge softness", .06, .005, .4, .005, "Softness of colored ray edges."),
        P("curvature", "Row curvature", .16, -1, 1, .01, "Bends each ray around its aperture."),
        P("row_drift", "Row drift", .08, 0, .5, .01, "Independent smooth drift for each ray."),
        P("irregularity", "Irregularity", .16, 0, 1, .01, "Uneven thickness and ray breaks."),
        P("magenta", "Magenta edge", .9, 0, 1, .01, "Colored edge around white rays."),
        P("intensity", "Ray intensity", 1.0, .1, 1.5, .01, "Brightness of the white rays and their colored edges."),
        P("tail_spread", "Soft ray tails", 0.0, 0, 1, .01, "Broadens the tapered shoulders outside the central aperture."),
        P("edge_bias", "Colored tail balance", 0.0, -1, 1, .01, "Moves the colored ray fringe toward the left or right tail."),
    )),
    Module("particles", "Particle attractor", "Dots assemble around an invisible 3D surface, then disperse.", (
        P("attractor", "Attractor", 0, 0, 5, 1, "Doryphoros uses a classical sculpture scan. Use Surface occlusion to keep the face readable. Only particles are rendered.", choices=("Stylized head", "Sphere", "Ring", "Human head", "Portrait head", "Doryphoros")),
        P("motion", "Motion", 0, 0, 2, 1, "Gentle drifts; Surges adds uneven arrivals and rebound. Impulse separates quick, peaked moves from longer holds.", choices=("Gentle", "Surges", "Impulse")),
        P("release", "Release", 0, 0, 1, 1, "Cloud / band retains the original dispersion. Expand / orbit releases in every direction, then revolves around the vertical axis.", choices=("Cloud / band", "Expand / orbit")),
        P("assembly", "Assembly", 1.0, 0, 1, .01, "0 = dispersed field; 1 = assembled surface. Breathing animates below this ceiling."),
        P("breathing", "Assembly cycle", 1.0, 0, 1, .01, "Depth of automatic assembly / release. Set to 0 to hold Assembly fixed."),
        P("period", "Cycle seconds", 12.0, .5, 120, .5, "One assembly / release cycle at global speed 1."),
        P("expand_seconds", "Expansion seconds", .75, .1, 5, .05, "Impulse: duration of the outward move, independent of Cycle seconds. Capped at a quarter cycle."),
        P("gather_seconds", "Gather seconds", 1.0, .1, 5, .05, "Impulse: duration of the return to the surface. Capped at a fifth of the cycle."),
        P("motion_peak", "Motion peak", .8, 0, 1, .01, "Impulse: 0 is linear; higher values concentrate velocity into a narrow peak, easing into and out of the move."),
        P("orbit_speed", "Orbit degrees / sec", 20.0, -90, 90, .5, "Expand / orbit: speed of the released cloud. Negative values reverse direction; separate from Head turn."),
        P("orbit_start", "Orbit after expansion", .7, 0, .95, .01, "Expand / orbit: fraction of release before rotation eases in. .7 waits until roughly 70% expanded."),
        P("orbit_handoff", "Return rotation", 0, 0, 1, 1, "Carry orbit keeps the accumulated cloud rotation when the head reforms. Both shapes share one orientation, preventing a backward unwind on return.", choices=("Original head angle", "Carry orbit")),
        P("acceleration", "Acceleration", .8, 0, 1, .01, "Surges: particles hesitate, accelerate sharply, then settle."),
        P("chaos", "Arrival disorder", .7, 0, 1, .01, "Bend and stagger particle paths. Surges also varies cycle timing; Impulse keeps the cycle exact with a small stagger."),
        P("overshoot", "Overshoot", .45, 0, 1, .01, "Surges: pass through the target and rebound before settling."),
        P("count", "Particle count", 22000, 200, 60000, 100, "More points create a denser signal field.", kind="int"),
        P("dot_size", "Dot size", 1.2, .5, 6, .1, "Soft dot radius at 576-pixel image height."),
        P("dispersion", "Dispersion", 1.0, 0, 2, .01, "Spread of released particles around the attractor."),
        P("turbulence", "Turbulence", .18, 0, 1, .01, "Continuous wandering, stronger away from the surface."),
        P("collapse", "Collapse to band", .0, 0, 1, .01, "Cloud / band release only: dots compress toward a low horizontal band."),
        P("flow", "Flow speed", .7, 0, 4, .05, "Rate of the continuous turbulent field."),
        P("phase", "Cycle phase", 0.0, 0, 1, .01, "Move the assembly cycle forward. Impulse starts assembled at 0; Gentle / Surges near .5."),
        P("yaw", "Head turn", -20.0, -180, 180, 1, "Starting rotation around the vertical axis."),
        P("pitch", "Tilt", 0.0, -90, 90, 1, "Tilt the entire 3D field."),
        P("rotation_speed", "Turn degrees / sec", 4.0, -90, 90, .5, "Head turn speed at global speed 1; Turn timing controls when it turns. Zero stops this turn while leaving Orbit speed independent."),
        P("turn_scope", "Turn timing", 0, 0, 1, 1, "Assembled only slows the head turn during release, leaving the expanded cloud's speed to Orbit degrees / sec. Follows the nominal assembly cycle.", choices=("Continuous", "Assembled only")),
        P("axis_mode", "Rotation axis", 0, 0, 1, 1, "Centered aligns the head and expanded cloud to one vertical pivot, removing the cloud's sideways orbit around the origin.", choices=("Original origin", "Centered")),
        P("scale", "Scale", 1.0, .2, 2, .01, "Size of the attractor in the image."),
        P("position_x", "Horizontal position", 0.0, -1, 1, .01),
        P("position_y", "Vertical position", 0.0, -1, 1, .01),
        P("perspective", "Perspective", .65, 0, 1, .01, "0 = orthographic; 1 = stronger depth foreshortening."),
        P("xray", "See-through", .08, 0, 1, .01, "Visibility of the back surface through the front dots."),
        P("occlusion", "Surface occlusion", 0.0, 0, 1, .01, "Hide deeper dots behind the assembled face, preventing the mouth interior and back of the head from shining through. Fades away during expansion."),
        P("neck_fade", "Neck feather", 0.0, 0, 1, .01, "Soften the lower edge of head targets in model space. Larger values dissolve more of the neck. Zero retains the mesh edge; released particles remain visible."),
        P("relief", "Surface relief", .85, 0, 1, .01, "Directional point brightness reveals the nose, eyes and mouth; no solid surface is drawn."),
        P("intensity", "Intensity", 1.35, 0, 3, .01),
        P("released_brightness", "Released brightness", 1.0, 0, 1, .01, "Dim loose particles while retaining bright dots on the assembled surface."),
        P("hue", "Hue", .76, 0, 1, .01, "Color of the central band; 0 = red, .33 = green, .67 = blue."),
        P("saturation", "Saturation", .65, 0, 1, .01),
        P("color_spread", "Spectral spread", .85, 0, 2, .01, "Different colors along the vertical volume."),
        P("color_drift", "Color drift", .025, 0, .5, .005, "Slow color circulation per second."),
        P("shimmer", "Shimmer", .45, 0, 1, .01, "Per-dot brightness fluctuation, independent of its trajectory."),
        P("jitter", "Scan registration", .0015, 0, .02, .0005, "Small held shifts across scan lines."),
    )),
    Module("silhouette", "Model silhouette", "A solid projection of a bundled head model, with a fixed pose.", (
        P("model", "Head model", 0, 0, 2, 1, "Doryphoros is a CC0 museum scan of a classical sculpture. Facial definition at 0 preserves its natural profile.", choices=("Portrait head", "Human head", "Doryphoros")),
        P("scale", "Model scale", .4, .1, 1.5, .01, "Uniform model scale relative to the artwork height."),
        P("yaw", "Head angle", -90., -180, 180, 1, "Fixed pose. -90 degrees faces left; no automatic rotation."),
        P("pitch", "Head tilt", 0., -90, 90, 1),
        P("roll", "Head roll", 0., -180, 180, 1),
        P("definition", "Facial definition", 0., 0, 1, .01, "Gently emphasize the nose, lips and chin in the silhouette. Zero keeps the original mesh projection."),
        P("center_x", "Framing X", .60, -.5, 1.5, .01, "Model pivot within the artwork. Object Position moves the complete source group."),
        P("center_y", "Framing Y", .4, -.5, 1.5, .01),
        P("neck_fullness", "Neck fullness", .4, 0, .8, .01, "Shape the front of the neck below the jaw without altering the face."),
        P("neck_length", "Neck extension", .7, 0, 2, .05, "Extend the mesh below its cut edge to keep the neck out of frame."),
        P("softness", "Contour softness", .5, 0, 5, .1),
        P("opacity", "Silhouette opacity", 1., 0, 1, .01),
    )),
    Module("ink_bloom", "Ink bloom", "Printed silhouettes unfold as a rotating three-dimensional cluster.", (
        P("shape", "Stamp shape", 0, 0, 5, 1, "Replace the silhouette while keeping the unfolding motion and ink treatment.", choices=("Original burst", "Square", "Circle", "Triangle", "Polygon", "Custom artwork")),
        Param("artwork", "Custom artwork", "", kind="artwork", hint="Import a transparent PNG or a contrasting silhouette. Its shape is printed with the selected inks and embedded in the composition."),
        P("count", "Stamp count", 7, 1, 13, 1, "One central stamp with satellites arranged around it."),
        P("size", "Stamp size", .15, .02, .4, .005, "Radius relative to the shorter canvas edge; proportions survive format changes."),
        P("spread", "Open spread", .255, 0, .6, .005, "Distance from the center to the surrounding stamps when open."),
        P("period", "Recipe cycle seconds", 53 / 15, .5, 60, .05, "Base cycle for stages that still follow the recipe. Custom stage durations determine the new loop length."),
        P("opening", "Opening", 1., 0, 1, .01, "Maximum opening. Set Automatic cycle to 0 to control the opening manually."),
        P("cadence", "Motion FPS", 15, 1, 60, 1, "How often the geometry updates. Gesture speed changes travel per frame, not this rate. Export FPS can limit the visible rate."),
        P("shape_width", "Shape width", 1., .1, 2, .01, "Horizontal scale of each silhouette before the cluster turns."),
        P("shape_height", "Shape height", 1., .1, 2, .01, "Vertical scale; imported artwork keeps its proportions at width and height 1."),
        P("sides", "Polygon sides", 6, 3, 32, 1, "Used by the Polygon shape."),
        P("shape_rotation", "Shape rotation", 0., -180, 180, 1, "Rotate each silhouette within its own plane."),
        P("points", "Points per stamp", 12, 3, 32, 1),
        P("point_depth", "Point depth", .4, .05, .85, .01),
        P("irregularity", "Ragged shape", .72, 0, 1, .01, "Uneven tip lengths and notches; stable for a given take."),
        P("palette", "Ink palette", 0, 0, 2, 1, choices=("CMY / white", "Warm print", "Monochrome")),
        P("split_ink", "Split ink", 1., 0, 1, .01, "A second ink color on the edge of each impression."),
        P("back_ink", "Reverse-side ink", .9, 0, 1, .01, "Use the first palette ink on reverse faces, revealing the other colors as the cluster turns."),
        P("saturation", "Saturation", 1., 0, 1, .01),
        P("cycle", "Automatic cycle", 1., 0, 1, .01),
        P("phase", "Cycle phase", 0., 0, 1, .01),
        P("open_start", "Open at (%)", 12., 0, 90, 1, "Start opening at this percentage of the cycle."),
        P("open_duration", "Open over (%)", 28., 1, 90, 1, "Duration of the eased opening as a percentage of the cycle."),
        P("close_start", "Close at (%)", 56., 0, 99, 1),
        P("close_duration", "Close over (%)", 27., 1, 90, 1),
        P("revolutions", "Turns per cycle", 1., -3, 3, .1),
        P("turn", "Starting turn", 0., -180, 180, 1),
        P("rotation", "Print rotation", 0., -180, 180, 1),
        P("tumble", "Tumble", .9, 0, 1, .01),
        P("tilt", "Tilt", 12., 0, 80, 1),
        P("fan", "Stamp fanning", 8., 0, 80, 1, "Individual planes open at different angles. Low values retain thin edge-on silhouettes."),
        P("center_fold", "Middle fold", 1., 0, 1, .01, "Fold the central impression across the outer planes during edge-on turns."),
        P("disorder", "Layout disorder", .5, 0, 1, .01),
        P("cluster_depth", "Cluster depth", .6, 0, 1.5, .01, "Depth between alternating stamps. Zero makes a flat rosette."),
        P("stack_spacing", "Closed stack spacing", .045, 0, .3, .005, "Separation between ink planes before they unfold."),
        P("perspective", "Perspective", .25, 0, 1, .01),
        P("position_x", "Horizontal position", 0., -1, 1, .01),
        P("position_y", "Vertical position", 0., -1, 1, .01),
        P("opacity", "Ink opacity", 1., 0, 1, .01),
        P("motion_speed", "Gesture speed", 1., 0, 8, .05, "Scale the whole unfold/hold/fold motion. 2× is twice as fast; 0 freezes it. Motion FPS stays constant. Frame jitter and background noise keep their own clocks."),
        P("clock_mode", "Gesture clock", 0, 0, 1, 1, "Shared composition timing uses an independent clock across all sections.", choices=("Scene", "Independent")),
        P("clock_scale", "Clock scale", 1., 0, 8, .05, "Base clock scale retained when consolidating an existing composition's timing."),
        P("unfold_seconds", "Unfold (s)", -1., -1, 60, .05, "Time to open at speed 1×. Zero opens instantly. Reset to follow the recipe."),
        P("unfolded_seconds", "Stay unfolded (s)", -1., -1, 60, .05, "Time fully open at speed 1×; the turn continues. Reset to follow the recipe."),
        P("fold_seconds", "Fold (s)", -1., -1, 60, .05, "Time to close at speed 1×. Zero closes instantly. Reset to follow the recipe."),
        P("folded_seconds", "Stay folded (s)", -1., -1, 60, .05, "Total closed rest between gestures at speed 1×. Split before and after the gesture like the original recipe. Reset to follow the recipe."),
    )),
    Module("edge_phosphor", "Edge phosphor", "Dark silhouettes against a noisy colored backlight with chromatic contour echoes.", (
        P("hue", "Backlight hue", .295, 0, 1, .005, "0 = red, .33 = green, .67 = blue."),
        P("backlight", "Backlight intensity", .7, 0, 2, .01),
        P("saturation", "Backlight saturation", 1., 0, 1, .01),
        P("edge", "Contour intensity", 1.1, 0, 3, .01),
        P("fringe_hue", "Fringe hue", .83, 0, 1, .005),
        P("fringe", "Fringe strength", 1., 0, 2, .01),
        P("grain", "Phosphor grain", .75, 0, 1.5, .01),
        P("spread", "Backlight reach", .36, .01, 1, .01),
        P("rim_width", "Contour width", .006, .001, .05, .001),
        P("separation", "Contour color gap", .012, 0, .1, .001),
        P("glow", "Contour glow", .009, 0, .1, .001),
        P("echo", "Contour echo", .2, 0, 1, .01),
        P("echo_distance", "Echo distance", .035, 0, .2, .005),
        P("lower_fade", "Lower contour fade", .8, 0, 1, .01),
        P("neck_dissolve", "Neck dissolve", 0., 0, 1, .01, "For Model silhouette: dissolve neck contours into the backlight below the jaw. Follows object position, scale and roll; 0 keeps the original outline."),
        P("fade_mode", "Region space", 0, 0, 2, 1, "Profile preset preserves the original neck blend. Object follows the chosen source's root; Canvas stays fixed in the viewport.", choices=("Profile preset", "Object", "Canvas")),
        P("fade_strength", "Fade strength", 0., 0, 1, .01, "Fade contours, fringe, echoes and fill, and blend their backlight into the region."),
        P("fade_start", "Fade start", 0., -3, 3, .01, "Offset along the fade direction. Object units follow its size; canvas units are half its shortest edge."),
        P("fade_width", "Fade width", .5, .01, 3, .01, "Distance from unchanged to fully faded in region units."),
        P("fade_angle", "Fade direction", 0., -180, 180, 1, "0 fades downward; 90 fades to the right, relative to the anchor."),
        P("fade_softness", "Light blending", .065, 0, .3, .005, "Soften the surrounding backlight inside the region before grain is applied."),
        P("fade_anchor", "Object anchor", 0, 0, 6, 1, "Attach to the root of a source, including compound stamps or particle clouds.", choices=("Primary object", "Model silhouette", "Luminous forms", "Ink stamps", "Particles", "Rays", "Text")),
        P("fade_x", "Region X", 0., -3, 3, .01),
        P("fade_y", "Region Y", 0., -3, 3, .01),
        P("fade_curve", "Fade curve", 1, 0, 1, 1, choices=("Linear", "Smooth")),
        P("body", "Silhouette fill", 0., 0, 1, .01),
        P("side", "Light side", 0, 0, 1, 1, choices=("Left", "Right")),
        P("threshold", "Source threshold", .2, .05, .95, .01),
        P("rate", "Phosphor FPS", 15., 0, 60, 1, "Held texture rate. Zero freezes the texture."),
        P("canvas_coverage", "Canvas coverage", 1, 0, 1, 1, "Extend the backlight into space revealed by a canvas resize; the head keeps its size and pose.", choices=("Artwork bounds", "Extend to canvas")),
        P("mix", "Mix", 1., 0, 1, .01),
    )),
    Module("scan_drag", "Scan drag", "Stretch and tear the source's bright edges into horizontal scan streaks.", (
        P("amount", "Fine streak strength", .55, 0, 1, .01),
        P("density", "Streak density", .025, 0, 1, .01),
        P("length", "Streak reach", .7, 0, 1, .01),
        P("overload", "Overload burst", 0., 0, 1, .01),
        P("center", "Burst height position", .68, 0, 1, .01),
        P("height", "Burst thickness", .12, .002, .5, .005),
        P("gain", "Burst exposure", 1.2, 0, 5, .05),
        P("blocks", "Tracking tears", 3, 0, 12, 1),
        P("block_height", "Tracking tear height", .018, .002, .15, .002),
        P("band_size", "Overload row groups", 7., 1, 16, .5, "Thickness of irregular groups at 270 scanlines."),
        P("tearing", "Horizontal rupture", .12, 0, .3, .002),
        P("jitter", "Line registration", .001, 0, .02, .0005),
        P("chroma", "Scan color slip", .012, 0, .1, .001),
        P("grain", "Streak grain", .12, 0, 1, .01),
        P("glow", "Overload bloom", .25, 0, 2, .01, "Spread overload light around the affected part of the source."),
        P("tint", "Overload color", .8, 0, 1, .01),
        P("softness", "Scan softness", .45, 0, 3, .05),
        P("wander", "Burst instability", .7, 0, 2, .01),
        P("dropout", "Dark line loss", .2, 0, 1, .01),
        P("direction", "Streak direction", 1, 0, 1, 1, choices=("Left", "Right")),
        P("window", "Recording width", .75, .1, 1, .01, "Width of the recorded signal; 1 fills the canvas. Black margins match the reference."),
        P("rate", "Scan FPS", 15., 0, 60, 1, "Held fault rate. Zero freezes the pattern."),
        P("canvas_coverage", "Canvas coverage", 1, 0, 1, 1, "Let scan streaks reach the edges after a canvas resize. Artwork bounds retains the original recording-width crop.", choices=("Artwork bounds", "Extend to canvas")),
        P("mix", "Mix", 1., 0, 1, .01),
    )),
    Module("flare", "Signal flare", "An asymmetric horizontal exposure sweep around the source.", (
        P("strength", "Exposure", 0.0, 0, 3, .01, "Adds a clipped white signal flare."),
        P("position_y", "Vertical position", .5, 0, 1, .01, "Centre of the horizontal sweep."),
        P("position_x", "Horizontal centre", .62, 0, 1, .01, "Strongest part of the exposure."),
        P("spread", "Vertical spread", .25, .02, 2, .01, "From a narrow horizontal burst to full-frame exposure."),
        P("reach", "Horizontal reach", .4, .05, 2, .01, "Width of the flare around its centre."),
        P("fringe", "Violet fringe", .2, 0, 1, .01, "Violet noise around the exposure boundary."),
        P("asymmetry", "Uneven exposure", 0.0, -1, 1, .01, "Different falloff above and below the exposure crest."),
        P("bend", "Exposure bend", 0.0, -1, 1, .01, "Bends the crest away from the brightest part of the source."),
    )),
    Module("warp", "Independent warp", "Displaces rows and columns without temporal feedback.", (
        P("amount", "Warp amount", .035, 0, .25, .001, "Normalized displacement."),
        P("frequency", "Warp frequency", 3.2, .1, 16, .1, "Number of broad waves across the frame."),
        P("direction", "Direction", .35, -1, 1, .01, "Blend between horizontal and vertical displacement."),
        P("speed", "Warp speed", .7, 0, 4, .05, "Animation rate for this module."),
    )),
    Module("separation", "Color separation", "R/G/B registration offsets for a fractured signal edge.", (
        P("amount", "Separation", .018, 0, .15, .001, "Normalized channel displacement."),
        P("angle", "Angle", .15, -1, 1, .01, "Direction of the color split."),
        P("green", "Green restraint", .35, 0, 1, .01, "Keep green closer to the luminance core."),
    )),
    Module("smear", "Horizontal smear", "Stateless luminous trails extending from bright forms.", (
        P("amount", "Trail length", .12, 0, .7, .01, "Normalized horizontal trail length."),
        P("direction", "Direction", .2, -1, 1, .01, "Left/right balance of the trails."),
        P("ghosts", "Ghost count", 4, 1, 10, 1, "Number of shifted translucent copies", kind="int"),
        P("opacity", "Trail brightness", 1., 0, 3, .01, "Brightness of shifted copies. 1 preserves the original trail fading; zero removes these copies."),
    )),
    Module("interference", "Signal interference", "Moving chromatic bands and a bent vertical scan comb across the sources.", (
        P("chroma", "Chromatic bands", .65, 0, 1, .01, "Mix broad moving violet, green and blue interference into the signal."),
        P("bands", "Band count", 7.0, 1, 24, .25),
        P("depth", "Band contrast", .45, 0, 1, .01, "Uneven exposure between horizontal bands."),
        P("bend", "Band bending", .3, 0, 1, .01),
        P("comb", "Vertical comb", .35, 0, 1, .01, "Broken vertical strings within the signal."),
        P("speed", "Signal speed", 1.0, 0, 6, .05),
        P("columns", "Comb columns", 130, 20, 320, 1),
        P("mix", "Mix", 1.0, 0, 1, .01),
    )),
    Module("frame_jitter", "Frame jitter", "Small held shifts, turns and scale changes, like repositioned paper or an unsteady scan.", (
        P("x", "Horizontal jitter", 5., 0, 30, .25, "Maximum displacement in pixels at a 720-pixel short edge; scales with the canvas."),
        P("y", "Vertical jitter", 4., 0, 30, .25, "Maximum vertical displacement in pixels at a 720-pixel short edge."),
        P("rotation", "Rotation jitter", .18, 0, 3, .01, "Maximum held rotation in degrees around the canvas center."),
        P("scale", "Scale jitter (%)", .12, 0, 3, .01, "Tiny changes in magnification, independent of the source's size control."),
        P("rate", "Jitter FPS", 15, 0, 60, 1, "New pose per held frame at global speed 1. Zero freezes the pose."),
        P("strength", "Jitter strength", 1., 0, 2, .01, "Scale all registration movement. Zero bypasses exactly."),
        P("seed", "Jitter seed", 0, 0, 100000, 1, "Change the movement pattern independently of the source and print textures."),
    )),
    Module("bloom", "Bloom", "Soft overexposure around luminous regions.", (
        P("threshold", "Threshold", .42, 0, 1, .01, "Luminance threshold for glow."),
        P("radius", "Radius", 9.0, .5, 40, .5, "Blur radius in output pixels at reference size."),
        P("strength", "Strength", .55, 0, 2, .01, "Glow contribution."),
    )),
    Module("raster", "Raster + grain", "Scan lines, fine grain and restrained color noise.", (
        P("softness", "Signal softness", 0.0, 0, 5, .1, "Softens the signal before grain; radius at 720-pixel width."),
        P("lines", "Scanline depth", .18, 0, .8, .01, "Darkness of alternating rows."),
        P("grain", "Fine grain", .08, 0, .5, .01, "Fine luminance grain."),
        P("chroma", "Chroma noise", .035, 0, .25, .005, "Small colored noise component."),
        P("line_noise", "Horizontal grain", 0.0, 0, .5, .01, "Correlated signal grain along short horizontal streaks."),
    )),
    Module("breakup", "Signal breakup", "Held horizontal tears and dropouts across the combined image.", (
        P("amount", "Horizontal tear", .08, 0, .5, .01, "Maximum horizontal displacement as a fraction of image width."),
        P("bands", "Bands", 18, 1, 96, 1, "Number of independently displaced horizontal bands."),
        P("dropout", "Dropouts", .12, 0, 1, .01, "Probability of a band losing its signal."),
        P("rate", "Changes per second", 8.0, 0, 60, .5, "Hold rate of the tears; zero freezes the pattern."),
        P("mix", "Mix", .75, 0, 1, .01, "Blend the broken signal with the original."),
    )),
    Module("tape", "Tape damage", "Tracking slips, chroma smear and lost scanlines within the existing image.", (
        P("pull", "Horizontal pull", 0., -1, 1, .01, "Broad continuous sideways stretch of the recorded picture. Positive pulls right, negative pulls left; zero preserves the image."),
        P("pull_edges", "Pull edges", 0, 0, 1, 1, "Keep canvas filled anchors both picture edges while stretching the interior. Applies only to Horizontal pull; other tape faults keep their own behavior.", choices=("Allow blanking", "Keep canvas filled")),
        P("tracking", "Tracking slip", .04, 0, .3, .002, "Horizontal displacement of short irregular scan regions."),
        P("jitter", "Line jitter", .001, 0, .02, .0005, "Small independent scanline timing errors."),
        P("dropouts", "Dropouts", .3, 0, 1, .01, "Short missing stretches of the recorded image."),
        P("chroma_delay", "Chroma delay", .006, 0, .08, .001, "Delay color relative to luminance, measured as a fraction of image width."),
        P("bleed", "Color bleed", .008, 0, .12, .001, "Smear the source's own color horizontally."),
        P("head_switch", "Head-switch error", .25, 0, 1, .01, "Distort and darken the bottom edge as the tape head changes."),
        P("rate", "Fault changes / sec", 16.0, 0, 60, .5, "Held fault rate at global speed 1; zero freezes the pattern."),
        P("mix", "Mix", .8, 0, 1, .01, "Blend tape faults with the original signal."),
    )),
    Module("print_surface", "Print surface", "Charcoal paper, ink erosion and held scanner registration across the whole image.", (
        P("background_mode", "Background", 0, 0, 1, 1, "Frame noise generates a new full-canvas field every scan. Original paper retains saved clips.", choices=("Original paper", "Frame noise")),
        P("noise_amount", "Background noise", 1., 0, 2, .01, "Strength of the frame noise, independently of the ink treatment."),
        P("noise_size", "Noise size", 1.3, .7, 8, .1, "Grain size at 720 pixels on the shorter canvas edge."),
        P("noise_clumps", "Noise clumping", .8, 0, 1, .01, "Uneven grain density; each frame gets new patches instead of moving a texture."),
        P("noise_floor", "Background tone", .09, 0, .25, .001, "Brightness of the frame-noise background, independently of the figures."),
        P("cadence", "Scan FPS", 15, 1, 60, 1, "Rate of registration and fresh scan noise, independent of export FPS."),
        P("black_level", "Paper brightness", .077, 0, .25, .001),
        P("paper_grain", "Paper grain", .85, 0, 2, .01),
        P("ink_grain", "Ink grain", .35, 0, 1, .01),
        P("ink_wear", "Ink wear", .20, 0, 1, .01),
        P("edge_wear", "Frayed edges", .65, 0, 1, .01),
        P("registration", "Frame registration", .002, 0, .03, .001, "Small held shifts of the printed artwork."),
        P("grain_size", "Grain size", 1.3, .7, 8, .1, "Paper tooth size at 720 pixels on the shorter edge."),
        P("fibers", "Paper fibers", .75, 0, 2, .01),
        P("mottle", "Uneven stock", .45, 0, 1, .01),
        P("boil", "Texture boil", .25, 0, 1, .01, "Fresh grain within each scan; the underlying sheet remains persistent."),
        P("paper_motion", "Paper movement", .06, 0, .3, .005),
        P("rotation_jitter", "Rotation jitter", .45, 0, 3, .05),
        P("dust", "Dust flecks", .12, 0, 1, .01),
        P("softness", "Scan softness", .8, 0, 3, .05),
        P("mix", "Mix", 1., 0, 1, .01),
    )),
    Module("signal_background", "Signal background", "Fill deep blacks with the green-black grain of Refined signal while preserving bright artwork.", (
        P("level", "Background level", .06, 0, .2, .001, "Brightness of the textured black. Zero restores the original image."),
        P("grain", "Fine grain", .08, 0, .3, .005),
        P("line_noise", "Horizontal grain", .028, 0, .2, .002),
        P("chroma", "Chroma noise", .004, 0, .05, .001),
        P("tint", "Green tint", 1., 0, 2, .05, "0 is neutral charcoal; 1 matches Refined signal's green-black field."),
        P("lines", "Scanline depth", .09, 0, .5, .01),
        P("threshold", "Shadow reach", .18, .02, .5, .01, "Fade the texture out before this signal brightness. Brighter contours remain unchanged."),
        P("rate", "Background FPS", 15., 0, 60, 1, "New grain per held frame at speed 1. Zero freezes the texture."),
        P("mix", "Mix", 1., 0, 1, .01),
    )),
    Module("low_res", "Low-res finish", "Render the complete image at a smaller working resolution, then scale it to the canvas. Includes grain, backgrounds and transitions.", (
        P("resolution", "Working resolution", 360, 64, 2160, 1, "Pixels on the longest edge. 360 preserves the 360 px preview look at every export size. Limited to the saved canvas size."),
        P("sampling", "Enlargement", 0, 0, 1, 1, "Soft matches the smooth preview enlargement. Crisp pixels keeps hard pixel edges.", choices=("Soft", "Crisp pixels")),
    )),
    Module("subject_cutout", "Subject cutout", "Local foreground masking before image treatments. Requires imported video and macOS 14 or later.", (
        P("mode", "Detect", 0, 0, 2, 1, "Foreground isolates prominent objects; People restricts detection to people. Crowd gives smaller figures their own detection region. Crowd is slower on first use; all masks are cached locally.", choices=("Foreground", "People", "Crowd")),
        P("retention", "Mask continuity", 0., 0, 1, .01, "Recover brief detection gaps where the surrounding frames agree. Zero keeps single-frame detection. Does not reconstruct hidden bodies."),
        P("retention_seconds", "Continuity reach", .12, .04, .5, .01, "Seconds before and after the source frame to check. Larger values can bridge longer gaps but are less reliable for fast movement."),
        P("silhouette", "Silhouette", .65, 0, 1, .01, "Darken the extracted subject; zero preserves its original colors."),
        P("paper", "Backdrop brightness", 1., 0, 1, .01),
        P("background_detail", "Original background", 0., 0, 1, .01, "Blend the source surroundings back into the backdrop."),
        P("threshold", "Mask cutoff", .1, 0, .95, .01),
        P("feather", "Edge softness", 1., 0, 20, .1, "Pixels at a 720 px short edge."),
        P("expand", "Expand / shrink edge", 0., -12, 12, .5, "Pixels at a 720 px short edge."),
        P("shadow", "Projected shadow", 0., 0, 1, .01),
        P("shadow_anchor", "Shadow anchor", 1, 0, 1, 1, "Subject base follows the lowest point of the detected mask. Canvas plane uses Shadow ground.", choices=("Canvas plane", "Subject base")),
        P("ground", "Shadow ground", .94, 0, 1, .01, "Ground plane as a fraction of canvas height, when Canvas plane is selected."),
        P("shadow_length", "Shadow depth", .15, .02, 1, .01),
        P("shadow_slant", "Shadow slant", -.65, -2, 2, .05),
        P("invert", "Invert mask", 0, 0, 1, 1, choices=("Subject", "Surroundings")),
        P("mix", "Mix", 1., 0, 1, .01),
    )),
    Module("photocopy", "Photocopy", "Crushed ink, fresh toner grain, halftone screens and uneven copy exposure. Works on any image.", (
        P("threshold", "Ink threshold", .42, 0, 1, .01),
        P("contrast", "Ink contrast", 4., .1, 12, .1),
        P("grain", "Toner grain", .85, 0, 2, .01),
        P("grain_size", "Toner size", 2.2, .5, 12, .1, "Pixels at a 720 px short edge; identical scale in preview and export."),
        P("halftone", "Halftone ink", .25, 0, 1, .01),
        P("tint", "Cold ink", .8, 0, 1, .01),
        P("exposure", "Copy exposure", 0., -4, 3, .05, "Exposure in stops."),
        P("blackout", "Dark exposure pulse", .75, 0, 1, .01, "Brief dark pass within each cycle; zero disables it."),
        P("cadence", "Print FPS", 12., 0, 60, 1, "Fresh toner and exposure flutter per second; zero freezes the grain."),
        P("dot_size", "Screen dot size", 8., 2, 40, .5),
        P("screen_angle", "Screen angle", -22., -90, 90, 1),
        P("light_depth", "Uneven illumination", .7, 0, 1, .01),
        P("light_width", "Light width", .5, .05, 2, .01),
        P("light_x", "Light position", .5, -1, 2, .01),
        P("light_drift", "Light movement", .15, 0, 1, .01),
        P("flutter", "Exposure flutter", .2, 0, 2, .01),
        P("period", "Exposure cycle", 2., .1, 30, .1, "Seconds per illumination, tint and dark-pulse cycle."),
        P("phase", "Cycle offset", 0., 0, 1, .01),
        P("tint_drift", "Cold ink variation", .65, 0, 1, .01),
        P("black", "Ink black", .015, 0, .3, .001),
        P("white", "Paper white", .97, .3, 1, .01),
        P("softness", "Pre-copy blur", .6, 0, 8, .1),
        P("edge_wear", "Frayed ink edges", 1.8, 0, 8, .1),
        P("invert", "Negative", 0., 0, 1, .01),
        P("mix", "Mix", 1., 0, 1, .01),
    )),
)
MODULES += (
    Module('text', 'Text', 'Editable typography rendered before the image treatments. Fonts travel with the Studio.', (
        P('content', 'Wording', 'REVOLUTION IS NOW', kind='text', hint='Up to 512 characters and eight lines. Line breaks are preserved.'),
        P('font', 'Typeface', 0, 0, len(FONTS)-1, 1, choices=FONTS),
        P('size', 'Text size', .14, .01, 1.5, .01, 'Line height relative to the authored canvas height. Canvas resizing preserves the lettering.'),
        P('tracking', 'Letter spacing', 0., -.15, .8, .01, 'Extra spacing as a fraction of the font size.'),
        P('leading', 'Line spacing', 1., .6, 2.5, .05),
        P('align', 'Line alignment', 1, 0, 2, 1, choices=('Left', 'Center', 'Right')),
        P('fit', 'Text fitting', 1, 0, 2, 1, 'Fit long lines keeps proportions. Fill block deliberately stretches the lettering to the authored width and text height; changing the canvas still preserves that shape.', choices=('Off', 'Fit long lines', 'Fill block')),
        P('block_width', 'Block width', .65, .05, 2, .01, 'Authored canvas width occupied by Fill block lettering, before size motion.'),
        P('fit_width', 'Line width limit', .9, .05, 2, .01, 'Maximum width of the whole text group in Fit long lines. Shrinks uniformly only when needed.'),
        P('hue', 'Text hue', .22, 0, 1, .01),
        P('saturation', 'Text saturation', .3, 0, 1, .01),
        P('brightness', 'Text brightness', 1., 0, 3, .05),
        P('opacity', 'Text opacity', 1., 0, 1, .01),
        P('stretch_x', 'Width stretch', 1., .15, 4, .05, 'Intentional typographic stretch, independent of canvas shape.'),
        P('stretch_y', 'Height stretch', 1., .15, 8, .05),
        P('rotation', 'Text rotation', 0., -180, 180, 1),
        P('back_hue', 'Backdrop hue', .6, 0, 1, .01),
        P('back_saturation', 'Backdrop saturation', .75, 0, 1, .01),
        P('back_brightness', 'Backdrop brightness', .045, 0, 1, .005),
        P('reveal', 'Show', 0, 0, 2, 1, choices=('Whole phrase', 'One word at a time', 'Type on')),
        P('word_seconds', 'Word / character interval', .65, .03, 10, .05, 'Seconds between words or characters. Whole phrase ignores this control.'),
        P('motion', 'Size motion', 0, 0, 3, 1, choices=('Still', 'Recede', 'Breathe', 'Perspective pullback')),
        P('zoom_start', 'Starting magnification', 1.7, .05, 8, .05),
        P('zoom_end', 'Ending magnification', .4, .05, 8, .05),
        P('period', 'Motion cycle', 2., .15, 30, .05),
        P('ease', 'Recede acceleration', 2., .2, 8, .1, 'One is linear; larger values travel quickly at the beginning and settle.'),
        P('phase', 'Motion phase', 0., 0, 1, .01),
        P('cadence', 'Text motion FPS', 0., 0, 60, 1, 'Zero uses continuous time. Grain and recording faults keep their own clocks.'),
        P('copies', 'Text copies', 1, 1, 6, 1, 'Repeat the current wording as one movable object. Fit long lines keeps the entire group inside the authored canvas.'),
        P('copy_gap', 'Copy spacing', .3, 0, 3, .05, 'Gap between repetitions, relative to the letter height.'),
        P('wrap_columns', 'Wrap after characters', 0, 0, 80, 1, 'Zero keeps manual line breaks. Otherwise wrap at this width, preferring spaces and splitting long words. Reveals still follow the original wording. Very long text uses wider lines to stay within eight lines.'),
        P('copy_floor', 'Repeat size floor', 0., 0, 1, .05, 'In Fit long lines, reduce the number of copies when fitting would shrink below this fraction of Text size. Zero always keeps all copies. One copy may still shrink to fit.'),
    )),
    Module('broadcast', 'Broadcast wear', 'Color drift in shadows, static interruptions, polarity reversals and curved CRT framing. Works on any source.', (
        P('field', 'Color field', .18, 0, 1, .01, 'Soft color variation in shadows, across the full canvas.'),
        P('hue', 'Field hue', .55, 0, 1, .01),
        P('hue_spread', 'Field color spread', .16, -.5, .5, .01),
        P('drift', 'Field change speed', .7, 0, 5, .05),
        P('static', 'Static intensity', .85, 0, 1, .01),
        P('period', 'Interruption cycle', 3., .15, 30, .05),
        P('duration', 'Interruption duration', .12, 0, 3, .01, 'Seconds of static in each cycle. Zero disables full-screen interruptions.'),
        P('phase', 'Interruption phase', .35, 0, 1, .01),
        P('band', 'Rolling static height', 0., 0, 1, .01, 'Zero disables the moving noise band; one spans the canvas height.'),
        P('roll', 'Static roll speed', .45, -3, 3, .05),
        P('rate', 'Static FPS', 24., 0, 60, 1),
        P('reverse', 'Polarity reversal', 0., 0, 1, .01),
        P('reverse_period', 'Polarity cycle', .8, .06, 10, .01),
        P('reverse_hue', 'Reversal ink hue', .045, 0, 1, .01),
        P('reverse_saturation', 'Reversal ink saturation', .9, 0, 1, .01),
        P('reverse_phase', 'Polarity phase', 0., 0, 1, .01),
        P('reverse_blend', 'Exposure overlap', 0., 0, 1, .01, 'Blend the positive and negative exposures during each reversal.'),
        P('field_spread', 'Field misregistration', 0., 0, .3, .005, 'Different magnification of the overlapping exposures leaves offset contours.'),
        P('reverse_stage', 'Polarity placement', 0, 0, 1, 1, 'Before finishing lets grain, tape damage and chromatic edges treat both polarities.', choices=('Final screen', 'Before finishing')),
        P('edge_fringe', 'Composite fringe', 0., 0, 2, .01, 'Colored edge ringing follows contrast boundaries in any source.'),
        P('edge_width', 'Fringe width', .004, .001, .03, .001, 'Horizontal signal delay as a fraction of canvas width.'),
        P('edge_hue', 'Fringe color', .8, 0, 1, .01, 'The two sides of an edge use complementary hues.'),
        P('curve', 'Screen curvature', .07, 0, .5, .005),
        P('vignette', 'Corner shading', .4, 0, 1, .01),
        P('wash', 'Exposure wash', 0., 0, 1, .01, 'Fresh, uneven color exposures follow Field hue and color spread. Changes at Static FPS.'),
        P('static_style', 'Signal loss texture', 0, 0, 1, 1, choices=('Snow', 'Broken sync')),
        P('static_chroma', 'Static color', .6, 0, 1, .01, 'Color carrier streaks in Broken sync interruptions.'),
        P('outages', 'Random outages', 0., 0, 1, .01, 'Probability of an additional interruption per Static FPS frame. Seeded and repeatable when scrubbing.'),
        P('sync_tear', 'Sync tearing', 0., 0, 1, .01, 'Uneven horizontal displacement during signal loss. Processes the source and its noise together.'),
        P('halo', 'Screen halation', 0., 0, 3, .01, 'Colored light spread from bright content, independent of the source.'),
        P('halo_radius', 'Halation radius', .06, .005, .25, .005, 'Blur radius relative to the shorter canvas edge.'),
        P('halo_hue', 'Halation hue', .61, 0, 1, .01),
        P('halo_threshold', 'Halation threshold', .5, 0, .95, .01, 'Only highlights above this value emit colored light.'),
        P('screen', 'CRT glass', 0., 0, 1, .01, 'Rounded screen aperture, uneven edge wear and a faint reflected rim.'),
        P('screen_inset', 'Glass inset', .045, 0, .2, .005, 'Border relative to each canvas edge. Changes the screen aperture, not the object proportions.'),
        P('screen_wear', 'Glass edge wear', .5, 0, 1, .01),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),
)

MODULES += (
    Module('stretch_echo', 'Stretch echo', 'Animated contours stretched around the source. Works on text, objects and footage before finishing.', (
        P('typeface', 'Echo typeface', 0, 0, len(FONTS), 1, 'Optional alternate typeface when the source is Text. Other sources always use their own pixels.', choices=('Source pixels',) + FONTS),
        P('stretch_y', 'Vertical stretch', 4., .1, 12, .05),
        P('stretch_x', 'Horizontal stretch', 1., .1, 6, .05),
        P('minimum', 'Starting stretch', 1., .1, 12, .05),
        P('motion', 'Animation', 1, 0, 2, 1, choices=('Still', 'Open / reset', 'Breathe')),
        P('period', 'Cycle seconds', 1.5, .1, 30, .05),
        P('ease', 'Opening ease', 2.5, .1, 10, .1),
        P('phase', 'Cycle phase', 0., 0, 1, .01),
        P('cadence', 'Motion FPS', 0., 0, 60, 1, 'Zero gives continuous motion.'),
        P('outline', 'Contour / solid', 1., 0, 1, .01),
        P('stroke', 'Contour width', 1., .25, 8, .25, 'Pixels at a 720-pixel reference edge.'),
        P('threshold', 'Highlight threshold', .2, 0, .95, .01),
        P('copies', 'Echo copies', 1, 1, 6, 1),
        P('position_x', 'Echo center X', 0., -.5, .5, .01, 'Relative to the object center and reference canvas width.'),
        P('position_y', 'Echo center Y', 0., -.5, .5, .01, 'Relative to the object center and reference canvas height.'),
        P('hue', 'Echo hue', 0., 0, 1, .01),
        P('saturation', 'Echo saturation', 0., 0, 1, .01),
        P('opacity', 'Echo brightness', .85, 0, 2, .01),
        P('source', 'Source brightness', 1., 0, 2, .01),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),
    Module('signal_etch', 'Signal etch', 'Horizontal grain, eroded highlights and pulsing light scatter derived from the image itself.', (
        P('grain', 'Grain intensity', .6, 0, 2, .01),
        P('grain_size', 'Grain size', 1., .5, 8, .1),
        P('streak', 'Horizontal grain stretch', 5., 1, 30, .5),
        P('erosion', 'Highlight erosion', .5, 0, 1, .01),
        P('core', 'Solid ink retention', 0., 0, 1, .01, 'Protect the interiors of thick strokes while fine contours and edges remain worn.'),
        P('roughness', 'Edge displacement', 4., 0, 40, .5),
        P('scatter', 'Light scatter', .8, 0, 5, .05),
        P('spread_x', 'Scatter width', 12., 1, 150, 1),
        P('spread_y', 'Scatter height', 8., 1, 150, 1),
        P('pulse', 'Exposure pulse', 3., 0, 12, .1),
        P('period', 'Pulse cycle seconds', 1.5, .1, 30, .05),
        P('pulse_seconds', 'Pulse duration', .14, .01, 3, .01),
        P('pulse_spread', 'Pulse vertical spread', 100., 1, 250, 1, 'Pixels at a 720-pixel reference edge.'),
        P('pulse_stretch', 'Pulse vertical stretch', 1., .25, 6, .05, 'Stretch only the light scattered during the flash.'),
        P('pulse_focus', 'Pulse center focus', .8, 0, 1, .01, 'Concentrate the flash around the horizontal center of the image highlights.'),
        P('phase', 'Pulse phase', 0., 0, 1, .01),
        P('cadence', 'Texture FPS', 24., 0, 60, 1, 'Zero freezes the texture; exposure pulses keep their own clock.'),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),
)

MODULES += (
    Module('chroma_print', 'Chroma print', 'Map source tones to luminous color while retaining texture and optional warm accents.', (
        P('exposure', 'Input exposure', .2, -3, 3, .05),
        P('black', 'Black point', .12, 0, .8, .01),
        P('white', 'White point', .8, .2, 1.5, .01),
        P('gamma', 'Midtone lift', 1.1, .2, 3, .05),
        P('softness', 'Image softness', 0., 0, 8, .1, 'Defocus the source before tone mapping. Later CRT phosphor lines stay crisp.'),
        P('detail', 'Local contrast', 0., 0, 4, .05, 'Recover facial or surface relief from the source before color mapping.'),
        P('detail_radius', 'Detail radius', 35., 2, 150, 1, 'Pixels at a 720-pixel reference edge.'),
        P('mid_hue', 'Midtone hue', .51, 0, 1, .01),
        P('mid_saturation', 'Midtone saturation', .85, 0, 1, .01),
        P('highlight_start', 'Highlight transition', .5, 0, .95, .01),
        P('white_hue', 'Highlight hue', .52, 0, 1, .01),
        P('white_saturation', 'Highlight saturation', .05, 0, 1, .01),
        P('warm_color', 'Warm accent amount', .7, 0, 1, .01, 'Recolor red-dominant source details with a separate accent.'),
        P('warm_threshold', 'Warm accent threshold', .16, 0, .8, .01),
        P('warm_hue', 'Warm accent hue', .94, 0, 1, .01),
        P('warm_saturation', 'Warm accent saturation', .85, 0, 1, .01),
        P('solarize', 'Solarization', 0., 0, 1, .01),
        P('solarize_point', 'Solarization threshold', .8, .1, 1, .01),
        P('solarize_lift', 'Solarized highlight recovery', 0., 0, 1, .01, 'Restore white at the solarization threshold while keeping reversed bright tones. Zero retains the original response.'),
        P('source_color', 'Original color', 0., 0, 1, .01),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),
    Module('slice_echo', 'Slice echo', 'Displaced strips or broken image patches, with colored and negative exposures.', (
        P('count', 'Slice count', 3, 1, 12, 1),
        P('height', 'Slice height', .18, .01, 1, .01),
        P('width', 'Fragment width', 1., .05, 1, .01, 'One keeps full-width strips. Smaller values create bounded patches of the source image.'),
        P('edge_breakup', 'Broken edges', 0., 0, 1, .01, 'Give fragments irregular stepped edges. The pattern reshuffles with each event.'),
        P('shift_x', 'Horizontal displacement', .2, 0, 1, .01),
        P('shift_y', 'Vertical displacement', .18, 0, 1, .01),
        P('scale', 'Magnification variation', .12, 0, .7, .01),
        P('softness', 'Slice edge softness', .003, 0, .2, .001),
        P('angle', 'Slice angle', 0., -90, 90, .5, 'Tilt the slice boundaries without rotating or stretching the source image.'),
        P('period', 'Reshuffle seconds', .6, .05, 10, .05),
        P('timing_scatter', 'Timing scatter', 0., 0, 1, .01, 'Vary the length of each reshuffle interval. The average rhythm stays near Reshuffle seconds; zero keeps regular timing.'),
        P('motion_chaos', 'Travel turbulence', 0., 0, 1, .01, 'Accelerate and reverse each bar within its interval with independent, seeded movement.'),
        P('activity', 'Active intervals', .9, 0, 1, .01),
        P('travel', 'Slice travel', .22, 0, 2, .01),
        P('cadence', 'Slice motion FPS', 12., 0, 60, 1, 'Zero gives continuous travel. The layout reshuffles at Reshuffle seconds.'),
        P('phase', 'Reshuffle phase', 0., 0, 1, .01),
        P('envelope', 'Event fade', 0., 0, .5, .01, 'Fraction of each reshuffle interval used to fade in and out. Zero keeps abrupt cuts; 0.5 fades throughout the interval.'),
        P('hue', 'Slice tint hue', .9, 0, 1, .01),
        P('saturation', 'Slice tint saturation', .8, 0, 1, .01),
        P('color_chance', 'Tinted slices', .65, 0, 1, .01),
        P('color_mix', 'Tint amount', .8, 0, 1, .01),
        P('negative', 'Negative exposure', 0., 0, 1, .01, 'Reverse the tones inside displaced fragments before applying their tint.'),
        P('highlight_protect', 'Keep bright highlights', 0., 0, 1, .01, 'Keep luminous highlights pale while tinting darker parts of each slice.'),
        P('exposure', 'Slice exposure', 0., -2, 2, .05),
        P('screen', 'Exposure overlap', .25, 0, 1, .01, 'Zero replaces source strips; one uses Screen blending for luminous overlapping images.'),
        P('opacity', 'Slice opacity', .85, 0, 1, .01),
        P('luma_mask', 'Image-shaped opacity', 0., 0, 1, .01, 'Let the brightness of each displaced image determine its opacity, so dark fragments reveal the image below.'),
        P('flash_source', 'Flash source', 0, 0, 1, 1, 'Before slices samples the underlying image, keeping earlier color treatment but avoiding already-tinted bars.', choices=('Combined slices', 'Before slices')),
        P('flash_opacity', 'Flash opacity', 0., 0, 1, .01, 'Add brief image patches over the main slices. Zero disables flashes. Tint and displacement follow the main slices.'),
        P('flash_period', 'Flash interval', .2, .05, 10, .01, 'Seconds between new patch layouts, independently of the main bars.'),
        P('flash_scatter', 'Flash timing scatter', 0., 0, 1, .01, 'Vary the flash intervals independently of the main bars.'),
        P('flash_seconds', 'Flash duration', .06, .01, 2, .01, 'Each flash appears immediately and fades out. Limited to the flash interval; very short flashes can fall between frames.'),
        P('flash_count', 'Flash count', 2, 1, 6, 1),
        P('flash_width', 'Flash width', .32, .05, 1, .01),
        P('flash_height', 'Flash height', .24, .01, 1, .01),
        P('flash_breakup', 'Flash broken edges', .2, 0, 1, .01),
        P('flash_negative', 'Flash negative exposure', .35, 0, 1, .01),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),
    Module('screen_mesh', 'Screen mesh', 'Fine tilted phosphor columns, RGB subpixels and scan rows across the complete image.', (
        P('pitch', 'Column spacing', 4., 1, 20, .25, 'Pixels at a 720-pixel reference edge. Subpixel patterns fade out in small previews to prevent aliasing.'),
        P('angle', 'Screen angle', 7., -90, 90, .5),
        P('strength', 'Column depth', .5, 0, 1, .01),
        P('rgb', 'RGB phosphors', .35, 0, 1, .01),
        P('row_pitch', 'Row spacing', 2.5, 1, 20, .25),
        P('rows', 'Row depth', .15, 0, 1, .01),
        P('exposure', 'Screen exposure', .5, -2, 2, .05),
        P('phase', 'Column phase', 0., 0, 1, .01),
        P('jitter', 'Column instability', .03, 0, 1, .01),
        P('bend', 'Column curvature', 0., 0, 12, .1, 'Gently bow phosphor columns. Pixels at a 720-pixel reference edge.'),
        P('wear', 'Phosphor wear', 0., 0, 1, .01, 'Uneven phosphor points and tiny row registration errors. Zero keeps the clean screen pattern.'),
        P('grain', 'Screen grain', .035, 0, .3, .005),
        P('cadence', 'Screen texture FPS', 25., 0, 60, 1, 'Zero freezes grain and column instability.'),
        P('softness', 'Screen softness', .25, 0, 3, .05),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),
)

# Append-only: legacy module indices also determine existing random seeds.
MODULES += modulation_modules(Module, P)
MODULE_BY_ID = InstanceRegistry({module.id: module for module in MODULES})


def _defaults(module: Module):
    return {param.key: param.default for param in module.params}


def default_synth_preset():
    return {
        "schema_version": SYNTH_SCHEMA_VERSION,
        "render_version": CURRENT_RENDER_VERSION,
        "name": "Irregular blinds",
        "width": 720,
        "height": 576,
        "framing": "native",
        "object_x": 0., "object_y": 0.,
        "treatment_fps": 25,
        "export_fps": 25,
        "loop_seconds": 4.0,
        "seed": 2409,
        "speed": .55,
        "depth": .75,
        "variation_mode": "smooth",
        "animation": {
            "targets": {
                "blinds.aperture": {"depth": .18, "rate": .22},
                "blinds.aperture_position": {"depth": .16, "rate": .17},
                "blinds.curvature": {"depth": .22, "rate": .14},
                "slab.width": {"depth": .12, "rate": .12},
                "slab.spacing": {"depth": .08, "rate": .11},
            }
        },
        "modules": [
            {"id": module.id, "enabled": module.id in {"slab", "blinds", "warp", "separation", "smear", "bloom", "raster"}, "params": _defaults(module)}
            for module in MODULES
        ],
    }


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def normalize_synth(raw=None):
    """Validate/upgrade a synth preset while preserving unknown future modules."""
    version = CURRENT_RENDER_VERSION if raw is None else render_version(raw) if isinstance(raw, dict) else 1
    base = default_synth_preset() if version == 2 else frozen_data('default')
    base['render_version'] = version
    if raw is None:
        return base
    if not isinstance(raw, dict):
        raise ValueError("Synth preset must be a JSON object")
    if int(raw.get("schema_version", 1)) != SYNTH_SCHEMA_VERSION:
        raise ValueError(f"Unsupported synth schema version: {raw.get('schema_version')}")
    result = copy.deepcopy(base)
    result.update(normalize_canvas(raw))
    for key in ("name", "variation_mode"):
        if key in raw:
            result[key] = str(raw[key])
    for key, minimum, maximum in (("width", 64, 4096), ("height", 64, 4096), ("treatment_fps", 1, 120), ("export_fps", 1, 120), ("seed", 0, 2**31 - 1), ("speed", 0, 8), ("depth", 0, 1), ("loop_seconds", .1, 3600), ("object_x", -100000, 100000), ("object_y", -100000, 100000)):
        if key in raw:
            value = raw[key]
            if not _finite(value) or not minimum <= float(value) <= maximum:
                raise ValueError(f"{key} is outside the supported range")
            result[key] = int(value) if key in {"width", "height", "treatment_fps", "export_fps", "seed"} else float(value)
    if result["variation_mode"] not in {"smooth", "stepped"}:
        raise ValueError("variation_mode must be smooth or stepped")
    animation = raw.get("animation", result["animation"])
    if not isinstance(animation, dict) or not isinstance(animation.get("targets", {}), dict):
        raise ValueError("animation.targets must be an object")
    result["animation"] = {"targets": {}}
    for key, target in animation.get("targets", {}).items():
        if not isinstance(key, str) or not isinstance(target, dict):
            raise ValueError("Each animation target needs a key and object")
        depth = target.get("depth", 0)
        rate = target.get("rate", 1)
        if not _finite(depth) or not _finite(rate) or float(depth) < 0 or float(rate) < 0:
            raise ValueError(f"Invalid animation target: {key}")
        result["animation"]["targets"][key] = {"depth": float(depth), "rate": float(rate)}
    modules = raw.get("modules", result["modules"])
    if not isinstance(modules, list):
        raise ValueError("modules must be a list")
    result["modules"] = []
    for entry in modules:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Each module needs an id")
        module = MODULE_BY_ID.get(entry["id"])
        if module is None:
            # Unknown modules are retained for forward-compatible save/reload,
            # but skipped by the current renderer.
            result["modules"].append(copy.deepcopy(entry))
            continue
        params = _defaults(module)
        if version == 1:
            params.update(frozen_defaults(module.id))
        incoming = entry.get("params", {})
        if not isinstance(incoming, dict):
            raise ValueError(f"{module.id}.params must be an object")
        for spec in module.params:
            if spec.key not in incoming:
                continue
            value = incoming[spec.key]
            if spec.kind == 'text':
                params[spec.key] = validate_text(value)
                continue
            if spec.kind == "artwork":
                params[spec.key] = validate_artwork(value)
                continue
            if not _finite(value):
                raise ValueError(f"{module.id}.{spec.key} must be finite")
            if spec.kind == "float" and not spec.minimum <= float(value) <= spec.maximum:
                raise ValueError(f"{module.id}.{spec.key} is outside the supported range")
            if spec.kind == "int" and not float(value).is_integer():
                raise ValueError(f"{module.id}.{spec.key} must be an integer")
            if spec.kind == "int" and not int(spec.minimum) <= int(value) <= int(spec.maximum):
                raise ValueError(f"{module.id}.{spec.key} is outside the supported range")
            params[spec.key] = int(value) if spec.kind == "int" else float(value)
        result["modules"].append({"id": module.id, "enabled": bool(entry.get("enabled", True)), "params": params})
    # Selecting a new region explicitly opts the edited copy into v2. Loading
    # an untouched v1 document never upgrades its rendering contract.
    if any((m['id'] == 'edge_phosphor' and m.get('params', {}).get('fade_mode', 0)) or
           (m['id'] == 'silhouette' and m.get('params', {}).get('definition', 0)) for m in result['modules']):
        result['render_version'] = 2
    return result


def load_synth(path):
    return normalize_synth(json.loads(Path(path).read_text()))


def save_synth(path, preset):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize_synth(preset), indent=2) + "\n")


def _seed(seed, name, *parts):
    key = ":".join(map(str, ("nebula-synth-v1", seed, name, *parts))).encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "little")


def _smooth(seed, name, position, mode="smooth"):
    if mode == "stepped":
        position = math.floor(position)
    left = math.floor(position)
    fraction = position - left
    rng_a = random.Random(_seed(seed, name, left))
    a = rng_a.uniform(-1, 1)
    if mode == "stepped":
        return a
    b = random.Random(_seed(seed, name, left + 1)).uniform(-1, 1)
    eased = fraction * fraction * (3 - 2 * fraction)
    return a + (b - a) * eased


def _hsv(hue, saturation=1, value=1):
    h = (hue % 1) * 6
    i = int(h)
    f = h - i
    p, q, t = value * (1 - saturation), value * (1 - saturation * f), value * (1 - saturation * (1 - f))
    return np.array(((value, t, p), (q, value, p), (p, value, t), (p, q, value), (t, p, value), (value, p, q))[i], dtype=np.float32)


def _zero_roll(arr, shift, axis=1):
    out = np.zeros_like(arr)
    if shift == 0:
        return arr.copy()
    if axis == 1:
        if shift > 0:
            out[:, shift:] = arr[:, :-shift]
        else:
            out[:, :shift] = arr[:, -shift:]
    else:
        if shift > 0:
            out[shift:] = arr[:-shift]
        else:
            out[:shift] = arr[-shift:]
    return out


def _add(arr, mask, color):
    arr += mask[..., None] * color[None, None, :]


def _clock(preset, t):
    """Global animation clock: speed and depth both have visible meaning."""
    return float(t) * float(preset["speed"])


def _modulated(preset, module_id, key, value, t, minimum=None, maximum=None):
    target = preset.get("animation", {}).get("targets", {}).get(f"{module_id}.{key}")
    if not target or not preset.get("depth", 0):
        return value
    span = (float(maximum) - float(minimum)) if minimum is not None and maximum is not None else max(abs(float(value)), 1.0)
    noise = _smooth(preset["seed"], f"mod:{module_id}.{key}", _clock(preset, t) * target["rate"], preset["variation_mode"])
    result = float(value) + noise * target["depth"] * span * float(preset["depth"])
    if minimum is not None:
        result = max(float(minimum), result)
    if maximum is not None:
        result = min(float(maximum), result)
    return result


def _signal_noise(seed, name, frame, size, grid):
    """A reference-sized noise field keeps its physical scale in the preview."""
    rng = np.random.default_rng(_seed(seed, name, frame))
    noise = rng.normal(size=(grid[1], grid[0])).astype(np.float32)
    return np.asarray(Image.fromarray(noise).resize(size, Image.Resampling.BILINEAR))


def _shape_distance(dx, dy, rx, ry, shape, sides=6, rotation=0, aspect=1):
    """Signed contour distance; rotate in image pixels before normalizing axes."""
    angle = math.radians(rotation)
    x = dx * aspect
    u = (x * math.cos(angle) + dy * math.sin(angle)) / (rx * aspect)
    v = (-x * math.sin(angle) + dy * math.cos(angle)) / ry
    if shape == 0:
        distance = np.maximum(np.abs(u), np.abs(v)) - 1
    elif shape in (1, 2):
        distance = np.hypot(u, v) - 1
    else:
        sector = math.tau / sides
        angle = (np.arctan2(v, u) + math.pi / 2) % sector - sector / 2
        distance = np.hypot(u, v) * np.cos(angle) - math.cos(math.pi / sides)
    return distance * min(rx, ry), u, v


def _render_slab(arr, p, t, preset, module_index):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    dx, dy = object_offset(preset, (w, h))
    if dx: x = x - dx
    if dy: y = y - dy
    cw, ch = content_size(preset, (w, h))
    xn = ((x - (w - cw) / 2) / max(1, cw - 1)) * 2 - 1
    yn = ((y - (h - ch) / 2) / max(1, ch - 1)) * 2 - 1
    q = p
    clock = _clock(preset, t)
    frame_clock = round(t * preset["treatment_fps"])
    rng = np.random.default_rng(_seed(preset["seed"], "slab-signal", frame_clock))
    registration = p.get("frame_jitter", 0)
    xn = xn + registration * (rng.normal(0, .25) + .12 * rng.normal(size=(h, 1)))
    if p.get("edge_ripple", 0) > 0:
        ripple = _signal_noise(preset["seed"], "slab-edge", round(t * preset["treatment_fps"]), (1, h), (1, 144))
        xn = xn + ripple * p["edge_ripple"]
    wobble = _smooth(preset["seed"], "slab-shape", clock * .6, preset["variation_mode"]) * q["jitter"] * .18 * preset["depth"]
    count = int(q["count"])
    width = _modulated(preset, "slab", "width", q["width"], t, .02, .8)
    spacing = _modulated(preset, "slab", "spacing", q["spacing"], t, .02, 1)
    vertical_center = float(p.get("position_y", 0)) + .08 * _smooth(preset["seed"], "slab-y", clock * .4, preset["variation_mode"]) * preset["depth"]
    half_height = max(.02, float(p.get("height", .62)))
    shape = int(p.get("shape", 0))
    shaped = shape != 0 or p.get("rotation", 0) != 0
    aspect = cw / ch
    if shape in (2, 3):
        half_height = p["diameter"]
        width = 2 * half_height / aspect
    vertical_distance = np.abs(yn - vertical_center)
    vertical_mask = np.clip((half_height - vertical_distance) / max(.004, (1 - p["edge_hardness"]) * .10), 0, 1)
    for index in range(count):
        center = float(p.get("position_x", .2)) + (index - (count - 1) / 2) * spacing + wobble
        dist = np.abs(xn - center)
        frame_clock = round(t * preset["treatment_fps"])
        fast_signal = _smooth(preset["seed"], "slab-fill", frame_clock + index * .17, "stepped")
        fill_flicker = .62 + .36 * (fast_signal + 1) / 2
        core = np.clip((width / 2 - dist) / max(.002, q["edge_softness"]), 0, 1) * vertical_mask
        if shaped:
            distance, u, v = _shape_distance(xn - center, yn - vertical_center, width / 2, half_height, shape, p["sides"], p["rotation"], aspect)
            core = np.clip(-distance / max(.002, q["edge_softness"]), 0, 1)
        notch_center = vertical_center + _smooth(preset["seed"], "slab-notch", index + frame_clock, "stepped") * half_height
        # Rectangular bites remove the right side of the body while leaving a
        # narrow vertical stem, which produces the L/T fragments in the study.
        cut_region = ((xn - center) > -width * .30) & (np.abs(yn - notch_center) < half_height * .65)
        if shaped:
            cut_region = (u > -.6) & (np.abs(v - (notch_center - vertical_center) / half_height) < .65)
        notch_probability = float(p.get("notch", 0))
        cut_active = 1.0 if fast_signal < (2 * notch_probability - 1) else 0.0
        core *= 1 - cut_active * cut_region
        hollow = float(p.get("hollow", 0))
        if shaped:
            core *= 1 - hollow * np.clip((-distance - q["edge_softness"] * 1.5) / max(.002, min(width / 2, half_height) * .12), 0, 1)
        else:
            core *= 1 - hollow * np.exp(-((dist / max(.001, width * .25)) ** 8))
        edge = np.exp(-(((xn - center + width / 2) / max(.002, q["edge_softness"])) ** 2)) * vertical_mask
        if shaped:
            edge = np.exp(-(distance / max(.002, q["edge_softness"])) ** 2) * np.clip(.5 - u * .5, 0, 1)
        fill_magenta = float(p.get("fill_magenta", 0.0))
        color = (1.0 - fill_magenta) * np.array((.95, .965, .94), dtype=np.float32) + fill_magenta * np.array((.76, .26, .91), dtype=np.float32)
        if p.get("fill_gradient", 0) > 0:
            split_fill = np.clip((center + width * .18 - xn) / max(.001, width * .20), 0, 1)
            tint = fill_magenta * ((1 - p["fill_gradient"]) + p["fill_gradient"] * split_fill)
            color = (1 - tint[..., None]) * np.array((.95, .965, .94)) + tint[..., None] * np.array((.90, .32, 1.0))
        if p.get("vertical_tint", 0) > 0:
            gradient = np.clip((yn - vertical_center + half_height) / (2 * half_height), 0, 1)
            warm = np.array((.78, .57, .59)); cool = np.array((.34, .22, .75))
            gradient_color = warm + gradient[..., None] * (cool - warm)
            color = color * (1 - p["vertical_tint"]) + gradient_color * p["vertical_tint"]
        if np.ndim(color) > 1:
            arr += (core * fill_flicker * p["intensity"])[..., None] * color
        else:
            _add(arr, core * fill_flicker * p["intensity"], color)
        edge_color = np.array((.78, .02, .65), dtype=np.float32)
        if p.get("vertical_tint", 0) > 0:
            edge_color = edge_color * (1 - p["vertical_tint"]) + np.array((.95, .38, .12)) * p["vertical_tint"]
        _add(arr, edge * q["magenta"] * p["intensity"], edge_color)
        fringe = np.exp(-(((dist - width * .72) / max(.003, q["edge_softness"] * 1.7)) ** 2)) * vertical_mask
        if shaped:
            fringe = np.exp(-((distance - q["edge_softness"]) / max(.003, q["edge_softness"] * 1.7)) ** 2) * np.clip(.5 + u * .5, 0, 1)
        _add(arr, fringe * q["cyan"], np.array((.02, .55, .45), dtype=np.float32))
        ghost_offset = float(p.get("ghost_offset", .24))
        ghost_width = max(.02, width * float(p.get("ghost_width", .32)))
        ghost_dist = np.abs(xn - center - ghost_offset)
        ghost = np.clip((ghost_width - ghost_dist) / max(.006, q["edge_softness"]), 0, 1) * vertical_mask
        if shaped:
            ghost_distance, _, _ = _shape_distance(xn - center - ghost_offset, yn - vertical_center, ghost_width, half_height, shape, p["sides"], p["rotation"], aspect)
            ghost = np.clip(-ghost_distance / max(.006, q["edge_softness"]), 0, 1)
        ghost *= float(p.get("ghost_opacity", .34)) * (.78 + .22 * _smooth(preset["seed"], "slab-ghost", round(t * preset["treatment_fps"]) + index, preset["variation_mode"]))
        ghost *= 1 - cut_active * .90 * (yn > notch_center)
        ghost *= (1 - p.get("ghost_grain", 0)) + p.get("ghost_grain", 0) * np.clip(rng.normal(.65, .52, (h, w)), 0, 1)
        detail = p.get("cloud_detail", 0)
        if detail > 0:
            signal = _signal_noise(preset["seed"], f"slab-cloud-{index}", frame_clock, (w, h), (360, 288))
            patches = _signal_noise(preset["seed"], f"slab-density-{index}", frame_clock, (w, h), (18, 16))
            granules = np.clip(signal * 1.3 - .12, 0, 1.8)
            density = np.clip(.7 + patches * .35, .4, 1.1)
            ghost *= (1 - detail) + detail * np.clip(.8 + signal * 1.2, 0, 1.5)
        _add(arr, ghost * float(p.get("intensity", 1.0)), np.array((.68, .66, .70), dtype=np.float32))
        if p.get("cloud_strength", 0) > 0:
            # Noise lives around the source, with a broad halo and uneven
            # signal density; it does not lift the whole background uniformly.
            cloud_mask = np.exp(-((xn - center) / (width * 1.4)) ** 2 - ((yn - vertical_center - p.get("cloud_position", 0)) / (half_height * 1.2)) ** 4)
            if shaped:
                cloud_distance, cloud_u, _ = _shape_distance(xn - center, yn - vertical_center - p.get("cloud_position", 0), width / 2, half_height, shape, p["sides"], p["rotation"], aspect)
                cloud_mask = np.exp(-(cloud_distance / max(.01, min(width / 2, half_height) * .5)) ** 2) * np.clip(.65 - cloud_u * .35, .15, 1)
            cloud = np.clip(rng.normal(.14, .30, (h, w)), 0, 1) * cloud_mask
            if detail > 0:
                # Concentrate the granular spill at the left edge and above
                # the block, leaving the right-hand ghost legible.
                halo_y = yn - vertical_center - p.get("cloud_position", 0)
                halo = np.exp(-((xn - center + width * .45) / (width * .55)) ** 2 - (halo_y / (half_height * 1.25)) ** 4)
                cap = np.exp(-((xn - center + width * .1) / (width * .8)) ** 2 - ((halo_y + half_height) / .22) ** 2)
                halo_mask = cloud_mask if shaped else np.maximum(halo, cap)
                cloud = cloud * (1 - detail) + granules * density * halo_mask * detail
            tint = p.get("cloud_tint", .8)
            cloud_color = (1 - tint) * np.array((.72, .82, .69)) + tint * np.array((.60, .08, .95))
            _add(arr, cloud * p["cloud_strength"], cloud_color)


def _render_blinds(arr, p, t, preset, module_index):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    dx, dy = object_offset(preset, (w, h))
    if dx: x = x - dx
    if dy: y = y - dy
    cw, ch = content_size(preset, (w, h))
    xn = ((x - (w - cw) / 2) / max(1, cw - 1)) * 2 - 1
    yn = (y - (h - ch) / 2) / max(1, ch - 1)
    clock = _clock(preset, t)
    base_hue = .76 + .025 * _smooth(preset["seed"], "blind-hue", clock, preset["variation_mode"])
    orientation = float(p.get("orientation", 0))
    theta = orientation * math.pi / 2
    yn2 = yn * 2 - 1
    u = xn * math.cos(theta) + yn2 * math.sin(theta)
    v = -xn * math.sin(theta) + yn2 * math.cos(theta)
    vn = (v + 1) / 2
    shaped_envelope = None
    for row in range(int(p["rows"])):
        row_unit = (row + .5) / p["rows"]
        drift = _smooth(preset["seed"], "blind-row", row + clock * .65, preset["variation_mode"]) * p["row_drift"] * preset["depth"] / max(1, p["rows"])
        cy = row_unit + drift + p.get("offset", 0) * .25
        curvature = _modulated(preset, "blinds", "curvature", p["curvature"], t, -1, 1)
        bend = curvature * (u ** 2) * .18 * math.sin(clock + row * .71 + p.get("phase", 0) * math.pi) * preset["depth"]
        distance = np.abs(vn - cy - bend)
        aperture = _modulated(preset, "blinds", "aperture", p["aperture"], t, .03, .95)
        aperture_pos = _modulated(preset, "blinds", "aperture_position", p.get("aperture_position", 0), t, -1, 1)
        # `aperture` is expressed as a frame-width fraction. Coordinates are
        # in [-1, 1], so its half-width is close to the fraction itself.
        half_aperture = max(.01, aperture * .9)
        asym = p["asymmetry"] * .28 + aperture_pos * .45
        absu = np.abs(u - asym)
        # A shallow plateau creates the broad white patches; the outer ramp
        # preserves the pinched/tapered ends seen in the reference.
        shoulder = max(.01, half_aperture * (.12 + p["taper"] * .24))
        envelope = np.clip((half_aperture - absu) / shoulder, 0, 1)
        envelope = np.power(envelope, .72)
        vertical_center = .5 + float(p.get("aperture_vertical", 0)) * .35
        vertical_half = max(.04, float(p.get("aperture_height", .64)) / 2)
        vertical_window = np.clip((vertical_half - np.abs(vn - vertical_center)) / max(.02, vertical_half * .22), 0, 1)
        vertical_window = np.power(vertical_window, .65)
        envelope *= vertical_window
        shape = int(p.get("shape", 0))
        if shape != 0 or p.get("rotation", 0) != 0:
            if shaped_envelope is None:
                rx, ry = half_aperture, vertical_half * 2
                if shape in (2, 3):
                    rx, ry = p["diameter"] * ch / cw, p["diameter"]
                # Place the aperture in image space so rotating the ray stack
                # cannot stretch a circle on a non-square canvas.
                aperture_y = (vertical_center - .5) * 2
                center_x = asym * math.cos(theta) - aperture_y * math.sin(theta)
                center_y = asym * math.sin(theta) + aperture_y * math.cos(theta)
                aperture_distance, _, _ = _shape_distance(xn - center_x, yn2 - center_y, rx, ry, shape, p["sides"], p["rotation"] + math.degrees(theta), cw / ch)
                shaped_envelope = np.clip(-aperture_distance / max(.005, min(rx, ry) * (.12 + p["taper"] * .24)), 0, 1) ** .72
            envelope = shaped_envelope
        taper = 1 - p["taper"] * (1 - envelope)
        outer = p["thickness"] * .4 + .12 / (p["rows"] ** 2 + 1) * np.exp(-((u - asym) / .96) ** 2)
        if p.get("tail_spread", 0) > 0:
            outer += p["tail_spread"] * .07 / p["rows"] * np.exp(-((u - asym) / .7) ** 2)
        local_thickness = outer * np.clip(taper, .35, 1.2) + p["swelling"] * envelope * .36 / p["rows"]
        irregular = 1 + p["irregularity"] * .18 * _smooth(preset["seed"], "blind-width", row + clock, preset["variation_mode"])
        edge_power = 2 + (1 - np.clip(p.get("edge_softness", .06) / .4, 0, 1)) * 6
        mask = np.exp(-((distance / np.maximum(.001, local_thickness * irregular)) ** edge_power))
        # Thin rays remain visible to the edges while the aperture holds a
        # near-rectangular bright section.
        mask *= .62 + .32 * envelope
        white = np.array((1.0, .985, .98), dtype=np.float32)
        _add(arr, mask * p.get("intensity", 1), white)
        edge = np.exp(-((distance / np.maximum(.001, local_thickness + .002 + p["edge_softness"] * .10)) ** 2)) - mask
        edge *= np.clip(.35 + envelope, 0, 1) * (1 + p.get("edge_softness", .06) * 2)
        edge = np.clip(edge, 0, 1) * p["magenta"]
        if p.get("edge_bias", 0) != 0:
            edge *= 1 + p["edge_bias"] * np.tanh((asym - u) * 5)
        color = _hsv(base_hue + .004 * row, .82, .8)
        _add(arr, edge * p.get("intensity", 1), color)


def _render_flare(arr, p, t, preset, module_index):
    if p["strength"] <= 0:
        return
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    x /= max(1, w - 1); y /= max(1, h - 1)
    distance = y - p["position_y"]
    if p.get("bend", 0) != 0:
        distance = distance - p["bend"] * .24 * ((x - p["position_x"]) / p["reach"]) ** 2
    spread = p["spread"]
    if p.get("asymmetry", 0) != 0:
        spread = spread * (1 + p["asymmetry"] * .75 * np.sign(distance))
    sweep = np.exp(-(distance / spread) ** 2)
    sweep *= .12 + 1.15 * np.exp(-((x - p["position_x"]) / p["reach"]) ** 2)
    rng = np.random.default_rng(_seed(preset["seed"], "flare", round(t * preset["treatment_fps"])))
    boundary = np.exp(-((sweep - .28) / .16) ** 2)
    _add(arr, boundary * np.clip(rng.normal(.2, .3, (h, w)), 0, 1) * p["fringe"], np.array((.8, .08, 1.0)))
    _add(arr, sweep * p["strength"], np.array((.96, .98, .94)))


def _warp(arr, p, t, preset):
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    phase = _clock(preset, t) * p["speed"]
    direction = p["direction"]
    dx = p["amount"] * w * (np.sin(y / max(1, h - 1) * math.tau * p["frequency"] + phase) * (1 - abs(direction)) + direction * np.sin(x / max(1, w - 1) * math.tau * p["frequency"] + phase * .73))
    dy = p["amount"] * h * (.35 * np.sin(x / max(1, w - 1) * math.tau * p["frequency"] + phase * .51))
    xs = np.clip(np.rint(x - dx).astype(int), 0, w - 1)
    ys = np.clip(np.rint(y - dy).astype(int), 0, h - 1)
    return arr[ys, xs]


def _separate(arr, p, t, preset):
    h, w = arr.shape[:2]
    shift = int(p["amount"] * w)
    angle = p["angle"]
    horizontal = int(shift * math.cos(angle * math.pi / 2))
    vertical = int(shift * math.sin(angle * math.pi / 2))
    out = arr.copy()
    out[..., 0] = _zero_roll(arr[..., 0], horizontal, 1)
    out[..., 2] = _zero_roll(arr[..., 2], -horizontal, 1)
    if vertical:
        out[..., 0] = _zero_roll(out[..., 0], vertical, 0)
        out[..., 2] = _zero_roll(out[..., 2], -vertical, 0)
    # Green restraint is a real registration control: at 1 it stays put; at 0
    # it follows the chromatic displacement halfway.
    green_shift = int(horizontal * (1 - p["green"]) * .5)
    out[..., 1] = _zero_roll(arr[..., 1], green_shift, 1)
    return out


def _smear(arr, p):
    if p["amount"] <= 0:
        return arr.copy()
    h, w = arr.shape[:2]
    out = arr.copy()
    ghosts = int(p["ghosts"])
    direction = 1 if p["direction"] >= 0 else -1
    for index in range(1, ghosts + 1):
        shift = direction * int(p["amount"] * w * index / ghosts)
        if shift:
            gain = .22 / index
            if p.get('opacity', 1.) != 1.: gain *= p['opacity']
            out += _zero_roll(arr, shift, 1) * gain
    return out


def _bloom(arr, p):
    image = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")
    lum = np.asarray(image.convert("L"), dtype=np.float32) / 255
    mask = np.clip((lum - p["threshold"]) / max(.001, 1 - p["threshold"]), 0, 1)
    bright = np.asarray(image, dtype=np.float32) * mask[..., None]
    blurred = np.asarray(Image.fromarray(np.clip(bright, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(p["radius"])), dtype=np.float32) / 255
    return arr + blurred * p["strength"]


def _raster(arr, p, seed, treatment_frame):
    h, w = arr.shape[:2]
    result = arr.copy()
    if p.get("softness", 0) > 0:
        signal = Image.fromarray(np.clip(result * 255, 0, 255).astype(np.uint8))
        result = np.asarray(signal.filter(ImageFilter.GaussianBlur(p["softness"] * w / 720)), dtype=np.float32) / 255
    result[::2] *= 1 - p["lines"]
    rng = np.random.default_rng(_seed(seed, "raster", treatment_frame))
    luminance = np.mean(result, axis=2, keepdims=True)
    result += rng.normal(0, p["grain"], result.shape).astype(np.float32) * np.sqrt(np.clip(luminance, 0, 1))
    chroma = rng.normal(0, p["chroma"], (h, w, 1)).astype(np.float32)
    result[..., 0] += chroma[..., 0]
    result[..., 2] -= chroma[..., 0]
    if p.get("line_noise", 0) > 0:
        streaks = _signal_noise(seed, "line-grain", treatment_frame, (w, h), (120, 576))
        result += streaks[..., None] * p["line_noise"] * np.sqrt(np.clip(luminance, 0, 1))
    return result


def _signal_background(arr, p, t, preset):
    if p['mix'] == 0 or p['level'] == 0:
        return arr
    # Reuse the reference's raster process on its lifted green-black field.
    # Apply after source faults so the silhouette and recording margins share
    # the same continuous canvas texture, without adding noise to highlights.
    field = np.empty_like(arr)
    field[:] = (np.array((.055, .067, .055), dtype=np.float32) - .06) * p['tint'] + .06
    field *= p['level'] / .06
    tick = math.floor(t * preset['speed'] * p['rate'] + 1e-9)
    field = np.maximum(0., _raster(field, p, _seed(preset['seed'], 'signal-background'), tick))
    shadows = np.clip(1 - arr.max(axis=2) / p['threshold'], 0, 1)
    shadows = shadows * shadows * (3 - 2 * shadows)
    return arr + field * (shadows * p['mix'])[..., None]


def _interference(arr, p, t, preset):
    if p["mix"] == 0:
        return arr
    h, w = arr.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    y /= max(1, h - 1)
    x /= max(1, w - 1)
    clock = t * preset["speed"] * p["speed"]
    background = np.array((.055, .067, .055), dtype=np.float32)
    signal = np.maximum(arr - background, 0)
    phase = math.tau * (y * p["bands"] - clock * .7 + x * p["bend"])
    phase += p["bend"] * np.sin(y * 17 + clock * 2.3) * 3
    gain = 1 - p["depth"] * (.5 + .5 * np.sin(phase))
    color_phase = y * 9 + x * 3 + np.sin(y * 13 - clock) + clock * .8
    colors = .25 + .75 * (.5 + .5 * np.cos(color_phase[..., None] + np.array((0., 2.1, 4.2))))
    tinted = signal * (1 - p["chroma"]) + signal.mean(axis=2, keepdims=True) * colors * 1.6 * p["chroma"]
    comb = .5 + .5 * np.sin(x * math.tau * p["columns"] + np.sin(y * 27 + clock * 3) * p["bend"] * 5)
    treated = background + tinted * (gain * (1 - p["comb"] * comb))[..., None]
    return arr * (1 - p["mix"]) + treated * p["mix"]


def _breakup(arr, p, t, preset):
    if p["mix"] == 0 or (p["amount"] == 0 and p["dropout"] == 0):
        return arr
    h, w = arr.shape[:2]
    rng = np.random.default_rng(_seed(preset["seed"], "breakup", math.floor(t * p["rate"] + 1e-9)))
    bands = int(p["bands"])
    band = np.minimum(np.arange(h) * bands // h, bands - 1)
    shifts = np.rint(rng.uniform(-1, 1, bands) * p["amount"] * w).astype(int)[band]
    x = np.arange(w)[None, :] - shifts[:, None]
    result = arr[np.arange(h)[:, None], np.clip(x, 0, w - 1)].copy()
    background = np.array((.055, .067, .055), dtype=np.float32)
    result[(x < 0) | (x >= w)] = background
    result[rng.random(bands)[band] < p["dropout"]] = background
    return arr * (1 - p["mix"]) + result * p["mix"]


RENDERERS = {
    'crt_capture': lambda arr, params, t, preset, index: render_crt_capture(arr, params, t, preset['speed'], _seed(preset['seed'], 'crt-capture'), content_size(preset, (arr.shape[1], arr.shape[0]))),
    'screen_mesh': lambda arr, params, t, preset, index: render_screen_mesh(arr, params, t, preset['speed'], _seed(preset['seed'], 'screen-mesh'), content_size(preset, (arr.shape[1], arr.shape[0]))),
    'broadcast': lambda arr, params, t, preset, index: render_broadcast(arr, params, t, preset['speed'], _seed(preset['seed'], 'broadcast')),
    "photocopy": lambda arr, params, t, preset, index: render_photocopy(arr, params, t, _seed(preset["seed"], "photocopy")),
    "signal_background": lambda arr, params, t, preset, index: _signal_background(arr, params, t, preset),
    "silhouette": lambda arr, params, t, preset, index: render_silhouette(arr, params, t, preset, _seed(preset["seed"], "silhouette")),
    "edge_phosphor": lambda arr, params, t, preset, index: render_edge_phosphor(arr, params, t, preset, _seed(preset["seed"], "edge-phosphor")),
    "scan_drag": lambda arr, params, t, preset, index: render_scan_drag(arr, params, t, preset, _seed(preset["seed"], "scan-drag")),
    "frame_jitter": lambda arr, params, t, preset, index: render_frame_jitter(arr, params, t, preset["speed"], _seed(preset["seed"], "frame-jitter"), content_size(preset, (arr.shape[1], arr.shape[0])) if 'reference' in preset else None),
    "ink_bloom": lambda arr, params, t, preset, index: render_ink_bloom(arr, params, t, preset["speed"], _seed(preset["seed"], "ink-bloom"), content_size(preset, (arr.shape[1], arr.shape[0])) if 'reference' in preset else None, object_offset(preset, (arr.shape[1], arr.shape[0]))),
    "print_surface": lambda arr, params, t, preset, index: render_print_surface(arr, params, t, preset["speed"], _seed(preset["seed"], "print-surface")),
    "slab": lambda arr, params, t, preset, index: _render_slab(arr, params, t, preset, index),
    "blinds": lambda arr, params, t, preset, index: _render_blinds(arr, params, t, preset, index),
    "particles": lambda arr, params, t, preset, index: render_particles(arr, params, t, preset, _seed(preset["seed"], "particles")),
    "flare": lambda arr, params, t, preset, index: _render_flare(arr, params, t, preset, index),
    "warp": lambda arr, params, t, preset, index: _warp(arr, params, t, preset),
    "separation": lambda arr, params, t, preset, index: _separate(arr, params, t, preset),
    "smear": lambda arr, params, t, preset, index: _smear(arr, params),
    "interference": lambda arr, params, t, preset, index: _interference(arr, params, t, preset),
    "bloom": lambda arr, params, t, preset, index: _bloom(arr, params),
    "raster": lambda arr, params, t, preset, index: _raster(arr, params, preset["seed"], round(t * preset["treatment_fps"])),
    "breakup": lambda arr, params, t, preset, index: _breakup(arr, params, t, preset),
    "tape": lambda arr, params, t, preset, index: render_tape_damage(arr, params, t, preset["speed"], _seed(preset["seed"], "tape")),
}


def render_synth_frame(preset, frame=0, time_seconds=None, size=None, source_image=None, source_mask=None):
    """Render one frame at continuous time; `frame` is only a default clock."""
    p = normalize_synth(preset)
    output, (width, height), sampling = render_resolution(p, size)
    continuous_time = frame / p["treatment_fps"] if time_seconds is None else float(time_seconds)
    # The scene treatment clock holds geometry as well as grain. Modules with
    # independent clocks opt out below, consistently in preview and export.
    t = math.floor(continuous_time * p["treatment_fps"] + 1e-9) / p["treatment_fps"]
    arr = np.zeros((height, width, 3), dtype=np.float32)
    # The reference has a lifted green-black field rather than zero RGB.
    arr[..., 0] = .055
    arr[..., 1] = .067
    arr[..., 2] = .055
    text_source = next((entry for entry in p['modules'] if entry['id'] == 'text' and entry['enabled']), None)
    if text_source and source_image is None:
        arr = render_text(arr, text_source['params'], continuous_time, p)
    scan = next((entry['params'] for entry in p['modules'] if entry['id'] == 'scan_modulation' and entry['enabled'] and entry['params']['mix']), None)
    untreated = None
    if scan and scan['input'] and source_image is not None:
        untreated = np.asarray(source_image.convert('RGB'), dtype=np.float32)/255
    cutout = next((entry for entry in p['modules'] if entry['id'] == 'subject_cutout' and entry['enabled'] and entry['params']['mix'] > 0), None)
    if cutout:
        if source_image is None or source_mask is None:
            raise ValueError('Subject cutout needs imported video and its foreground mask')
        from synth_cutout import render_cutout
        source_image = render_cutout(source_image, source_mask, cutout['params'])
    if source_image is not None:
        from synth_video import VIDEO_MODULES
        if source_image.size != (width, height):
            raise ValueError('Video source must match the working canvas')
        arr = np.asarray(source_image.convert('RGB'), dtype=np.float32) / 255
    treatment_frame = round(t * p["treatment_fps"])
    broadcast = next((entry['params'] for entry in p['modules'] if entry['id'] == 'broadcast' and entry['enabled']), None)
    # New treatments have a stable stage without inserting modules into old
    # serialized orders (whose indices also determine existing random seeds).
    generators = {'slab', 'blinds', 'particles', 'silhouette', 'ink_bloom', 'flare'}
    source_end = max((i for i, m in enumerate(p['modules']) if m.get('enabled', True) and m['id'] in generators), default=-1) + 1
    source_effects = {entry['id']: entry['params'] for entry in p['modules']
                      if entry['enabled'] and entry['id'] in ('chroma_print', 'slice_echo', 'stretch_echo', 'signal_etch', 'scan_modulation')}
    def treat_source(image):
        reference = content_size(p, (width, height))
        source_pixels = untreated if untreated is not None else image
        if 'chroma_print' in source_effects:
            image = render_chroma_print(image, source_effects['chroma_print'], reference)
        if 'slice_echo' in source_effects:
            image = render_slice_echo(image, source_effects['slice_echo'], continuous_time,
                                      p['speed'], _seed(p['seed'], 'slice-echo'), reference)
        original = image
        if 'stretch_echo' in source_effects:
            dx, dy = object_offset(p, (width, height))
            alternate = None
            echo = source_effects['stretch_echo']
            if echo['typeface'] and text_source and source_image is None:
                # Source-specific typography stays in the adapter. The image
                # effect receives pixels and remains usable with any source.
                alternate = render_text(image, dict(text_source['params'], font=echo['typeface']-1,
                    back_brightness=0.), continuous_time, p)
            image = render_stretch_echo(image, source_effects['stretch_echo'], continuous_time,
                                        p['speed'], (width / 2 + dx, height / 2 + dy), reference, alternate)
        if 'signal_etch' in source_effects:
            image = render_signal_etch(image, source_effects['signal_etch'], continuous_time,
                                       p['speed'], _seed(p['seed'], 'signal-etch'), reference, original)
        if 'scan_modulation' in source_effects:
            image = render_scan_modulation(image, source_effects['scan_modulation'], continuous_time,
                                           p['speed'], _seed(p['seed'], 'scan-modulation'), reference, source_pixels)
        return image
    polarity_index = None
    if broadcast and broadcast['reverse_stage'] and (broadcast['reverse'] or broadcast['edge_fringe']) and broadcast['mix']:
        # Preserve existing module indices/seeds. The optional early reversal
        # follows source generators and precedes the remaining image finishes.
        polarity_index = source_end
    for index, entry in enumerate(p["modules"]):
        if index == polarity_index:
            reversed_signal = render_broadcast_exposure(arr, broadcast, continuous_time, p['speed'])
            arr = arr * (1 - broadcast['mix']) + reversed_signal * broadcast['mix']
        if index == source_end and source_effects:
            arr = treat_source(arr)
        if not entry.get("enabled", True):
            continue
        instance_id = entry.get("id")
        module_id = base_id(instance_id)
        if source_image is not None and module_id not in VIDEO_MODULES:
            if module_id != 'low_res':
                raise ValueError(f'{module_id} requires a generated object, not a video source')
            continue
        renderer = RENDERERS.get(module_id)
        if renderer is None:
            continue
        params = entry.get("params", {})
        cw, ch = content_size(p, (width, height))
        if source_framing(p) == "adaptive" and cw < ch and module_id in {"slab", "blinds"} and int(params.get("shape", 0)) in (2, 3):
            params = dict(params, diameter=params["diameter"] * cw / ch)
        # Shared ink motion owns its hold clock across recipe sections. Other
        # effects retain the scene's speed and treatment cadence.
        module_time = continuous_time if module_id in ('photocopy', 'broadcast', 'screen_mesh', 'crt_capture') or (module_id == 'ink_bloom' and params.get('clock_mode', 0)) else t
        if module_id == 'edge_phosphor':
            if p['render_version'] == 1:
                rendered = render_edge_phosphor_v1(arr, params, module_time, p, _seed(p['seed'], 'edge-phosphor'))
            else:
                rendered = render_edge_phosphor(arr, params, module_time, p, _seed(p['seed'], 'edge-phosphor'), continuous_time)
        elif module_id == "tape" and (params.get("pull", 0) or instance_base(instance_id)):
            rendered = render_tape_damage(arr, params, module_time, p["speed"], _seed(p["seed"], instance_id), pull_time=continuous_time)
        else:
            rendered = renderer(arr, params, module_time, p, index)
        if rendered is not None:
            arr = rendered
    if polarity_index == len(p['modules']):
        reversed_signal = render_broadcast_exposure(arr, broadcast, continuous_time, p['speed'])
        arr = arr * (1 - broadcast['mix']) + reversed_signal * broadcast['mix']
    if source_end == len(p['modules']) and source_effects:
        arr = treat_source(arr)
    image = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")
    return finish_resolution(image, output, sampling)


def curated_presets():
    """Existing named presets use their frozen defaults, including disabled modules."""
    presets = frozen_data('presets')
    for preset in presets.values():
        preset['render_version'] = 1
        # Append opt-in operations so every legacy module keeps its index/seed.
        present = {entry['id'] for entry in preset['modules']}
        for module in MODULES:
            if module.id not in present:
                preset['modules'].append({'id': module.id, 'enabled': False, 'params': _defaults(module)})
        for entry in preset['modules']:
            module = MODULE_BY_ID.get(entry['id'])
            if module:
                entry['params'] = dict(_defaults(module), **entry['params'])
    return presets
