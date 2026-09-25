"""Seeded 3D point attractors, evaluated directly at any time.

The procedural surfaces are sampling targets only; no mesh is drawn. Particle
identities persist through assembly and dispersion, so seeking needs no warmup.
"""
from functools import lru_cache
import math

import numpy as np

from synth_particle_mesh import sample_human_head


def _head_surface(y, angle):
    radius = np.sqrt(np.maximum(0, 1 - y * y))
    jaw = 1 - .22 * np.clip(-y, 0, 1)
    x = .68 * radius * np.sin(angle) * jaw
    z = .64 * radius * np.cos(angle)
    front = np.clip(np.cos(angle), 0, 1) ** 6

    def bump(cx, cy, sx, sy):
        return np.exp(-((x - cx) / sx) ** 2 - ((y - cy) / sy) ** 2)

    # Brow, recessed eye sockets, cheekbones, nose bridge/tip, lips and chin.
    relief = .08 * (bump(-.25, .33, .22, .09) + bump(.25, .33, .22, .09))
    relief -= .14 * (bump(-.25, .18, .16, .105) + bump(.25, .18, .16, .105))
    relief += .085 * (bump(-.34, -.08, .19, .18) + bump(.34, -.08, .19, .18))
    relief += .22 * bump(0, .04, .085, .29) + .27 * bump(0, -.13, .12, .11)
    relief -= .055 * (bump(-.1, -.19, .055, .035) + bump(.1, -.19, .055, .035))
    relief += .065 * bump(0, -.36, .21, .075) + .045 * bump(0, -.45, .19, .055)
    relief -= .06 * bump(0, -.405, .22, .026)
    relief += .09 * bump(0, -.68, .25, .18)
    return np.column_stack((x, y, z + front * relief))


@lru_cache(maxsize=8)
def _population(shape, count, seed):
    rng = np.random.default_rng(seed)
    # One random row per identity: increasing count retains the existing dots.
    random = rng.random((count, 16))
    y, angle = random[:, 0] * 2 - 1, random[:, 1] * math.tau
    radius = np.sqrt(1 - y * y)
    if shape == 0:
        points = _head_surface(y, angle)
        tangent_y = _head_surface(np.clip(y + .001, -.99999, .99999), angle) - _head_surface(np.clip(y - .001, -.99999, .99999), angle)
        tangent_a = _head_surface(y, angle + .001) - _head_surface(y, angle - .001)
        normals = np.cross(tangent_a, tangent_y)
        normals /= np.maximum(1e-8, np.linalg.norm(normals, axis=1, keepdims=True))
        # A short neck and two ears make the guide legible in three-quarter view.
        neck = random[:, 2] < .09
        points[neck] = np.column_stack((.27 * np.sin(angle[neck]), -1.28 + random[neck, 0] * .55, .1 + .30 * np.cos(angle[neck])))
        normals[neck] = np.column_stack((np.sin(angle[neck]), np.zeros(neck.sum()), np.cos(angle[neck])))
        ears = (random[:, 2] >= .09) & (random[:, 2] < .13)
        sign = np.where(random[ears, 3] < .5, -1, 1)
        points[ears] = np.column_stack((sign * (.64 + .09 * radius[ears] * np.cos(angle[ears])), y[ears] * .21 - .02, -.01 + .13 * radius[ears] * np.sin(angle[ears])))
        normals[ears] = np.column_stack((sign * radius[ears] * np.cos(angle[ears]), y[ears], radius[ears] * np.sin(angle[ears])))
        x = points[:, 0]
        sockets = np.exp(-((np.abs(x) - .25) / .135) ** 2 - ((y - .18) / .075) ** 2)
        mouth = np.exp(-(x / .2) ** 4 - ((y + .405) / .035) ** 2)
        front = np.clip(np.cos(angle), 0, 1) ** 8
        random[:, 15] = 1 - front * np.maximum(sockets * .88, mouth * .8)
        random[neck | ears, 15] = 1
    elif shape == 1:
        points = np.column_stack((radius * np.sin(angle), y, radius * np.cos(angle))) * .85
        normals = points / .85
    elif shape == 2:
        tube = random[:, 0] * math.tau
        radial = .66 + .25 * np.cos(tube)
        points = np.column_stack((radial * np.sin(angle), .25 * np.sin(tube), radial * np.cos(angle)))
        normals = np.column_stack((np.cos(tube) * np.sin(angle), np.sin(tube), np.cos(tube) * np.cos(angle)))
    else:
        points, normals = sample_human_head(random, portrait=shape == 4)
    if shape != 0:
        random[:, 15] = 1
    if shape == 4:
        # A subdued iris in the new eye surfaces; eyelids and face occlude it.
        iris = np.exp(-((np.abs(points[:, 0]) - .2647) / .04) ** 4 - ((points[:, 1] + .0136) / .043) ** 4)
        random[:, 15] -= iris * .75 * _ease((points[:, 2] - .74) / .05)
    cloud = (random[:, 4:7] * 2 - 1) * np.array((1.65, 1.25, 1.3))
    for array in (points, normals, cloud, random):
        array.setflags(write=False)
    return points, normals, cloud, random


def _ease(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def _surge_phase(p, phase, target, attributes):
    chaos = p["chaos"]
    # Modulate cycle duration continuously; the clock never jumps at a wrap.
    phase += chaos * (.055 * np.sin(phase * math.tau * .73) + .022 * np.sin(phase * math.tau * 1.91))
    delay = chaos * (.12 * attributes[:, 7] + .025 * target[:, 1])
    return phase - delay


def _surge_motion(p, phase, target, attributes):
    """Uneven charges and damped arrivals, with continuous cycle boundaries."""
    local = _surge_phase(p, phase, target, attributes) % 1
    incoming = _ease((local - .10) / .30) ** (1 + 4 * p["acceleration"])
    outgoing = _ease((local - .57) / .24) ** (1 + 3 * p["acceleration"])
    hold = incoming * (1 - outgoing)
    cohesion = p["assembly"] * (1 - p["breathing"] * (1 - hold))
    settle = np.clip((local - .40) / .16, 0, 1)
    ring = np.sin(settle * math.tau * 1.5) * np.sin(settle * math.pi) ** 2 * np.exp(-settle * 2)
    transfer = cohesion + ring * p["overshoot"] * .75 * p["assembly"] * p["breathing"]
    return cohesion, transfer


def _impulse_ease(value, peak):
    value = np.clip(value, 0., 1.)
    power = 1 + 4 * peak
    forward, backward = value ** power, (1 - value) ** power
    return forward / (forward + backward)


def _impulse_phase(p, phase, target, attributes):
    # Keep the authored cycle count exact. Disorder staggers groups by a few
    # milliseconds rather than stretching a short burst across the whole cycle.
    delay = p["chaos"] * (.07 * attributes[:, 7] + .015 * target[:, 1])
    return phase - delay / p["period"]


def _impulse_hold(phase, period, expand_seconds, gather_seconds, peak):
    outward = _impulse_ease((phase - .28) / min(.25, expand_seconds / period), peak)
    inward = _impulse_ease((phase - .76) / min(.20, gather_seconds / period), peak)
    return 1 - outward + inward


@lru_cache(maxsize=32)
def _orbit_integral(motion, assembly, breathing, acceleration, start,
                    period=12., expand_seconds=.75, gather_seconds=1., peak=.8):
    """Integral of the release gate over one cycle, in cycle units.

    Integrating angular velocity keeps rotation continuous across cycle wraps
    and long seeks. Multiplying absolute time by a release weight would rewind
    the cloud at every gathering, with speed increasing as the clip gets longer.
    """
    phase = np.linspace(0., 1., 2049)
    if motion == 2:
        hold = _impulse_hold(phase, period, expand_seconds, gather_seconds, peak)
    elif motion == 1:
        incoming = _ease((phase - .10) / .30) ** (1 + 4 * acceleration)
        outgoing = _ease((phase - .57) / .24) ** (1 + 3 * acceleration)
        hold = incoming * (1 - outgoing)
    else:
        hold = _ease((.5 - .5 * np.cos(phase * math.tau)) * 1.6)
    cohesion = assembly * (1 - breathing * (1 - hold))
    gate = _ease(((1 - cohesion) - start) / (1 - start))
    integral = np.concatenate(([0.], np.cumsum((gate[:-1] + gate[1:]) * .5 / (len(phase) - 1))))
    integral.setflags(write=False)
    return integral


def _outward_direction(target, attributes):
    direction = target / np.array((.8, 1.1, .8)) + (attributes[:, 4:7] - .5) * 1.4
    direction /= np.maximum(1e-8, np.linalg.norm(direction, axis=1, keepdims=True))
    return direction * (.6 + attributes[:, 6] * .8)[:, None]


@lru_cache(maxsize=8)
def _axis_reference(shape, seed):
    # A fixed population keeps the pivot independent of the displayed count.
    # Remove the target's offset and the radial distribution's own bias before
    # rotating; otherwise the whole cloud travels around the origin.
    target, _, _, attributes = _population(shape, 32768, seed)
    pivot = target.mean(axis=0)
    pivot[1] = 0.
    drift = _outward_direction(target - pivot, attributes).mean(axis=0)
    pivot.setflags(write=False); drift.setflags(write=False)
    return pivot, drift


def _assembled_turn_time(p, time):
    """Integrate the assembled gate, so a released cloud keeps its own speed."""
    integral = _orbit_integral(p.get("motion", 0), p["assembly"], p["breathing"], p["acceleration"], 0.,
                               p["period"], p.get("expand_seconds", .75), p.get("gather_seconds", 1.), p.get("motion_peak", .8))
    phase = np.array((p["phase"], time / p["period"] + p["phase"]))
    released = (np.floor(phase) * integral[-1] + np.interp(phase % 1, np.linspace(0., 1., len(integral)), integral)) * p["period"]
    return time - (released[1] - released[0])


def _orbit_time(p, phase):
    integral = _orbit_integral(p.get("motion", 0), p["assembly"], p["breathing"], p["acceleration"], p["orbit_start"],
                               p["period"], p.get("expand_seconds", .75), p.get("gather_seconds", 1.), p.get("motion_peak", .8))
    return (np.floor(phase) * integral[-1] + np.interp(phase % 1, np.linspace(0., 1., len(integral)), integral)) * p["period"]


def _carried_orbit_time(p, time):
    # One orientation for both volumes, retained after every gathering. An
    # independent clock per point would deform the face as it reassembles.
    phase = np.array((p["phase"], time / p["period"] + p["phase"]))
    if p.get("motion", 0) == 1:
        phase += p["chaos"] * (.055 * np.sin(phase * math.tau * .73) + .022 * np.sin(phase * math.tau * 1.91))
    clock = _orbit_time(p, phase)
    return clock[1] - clock[0]


def _orbit_cloud(p, time, target, attributes, drift=None, rotate=True):
    # A rounded, irregular volume, distributed outward from each surface point.
    # Its radius does not taper with height, so it never forms a funnel.
    direction = target / np.array((.8, 1.1, .8)) + (attributes[:, 4:7] - .5) * 1.4
    direction /= np.maximum(1e-8, np.linalg.norm(direction, axis=1, keepdims=True))
    cloud = target + direction * (p["dispersion"] * (.6 + attributes[:, 6] * .8))[:, None]
    if drift is not None:
        cloud -= p["dispersion"] * drift
    if not rotate:
        return cloud
    phase = time / p["period"] + p["phase"]
    if p.get("motion", 0) == 1:
        phase = _surge_phase(p, phase, target, attributes)
    elif p.get("motion", 0) == 2:
        phase = _impulse_phase(p, phase, target, attributes)
    # Each group keeps its staggered release, including its delayed spin-up.
    clock = _orbit_time(p, phase)
    angle = np.deg2rad(p["orbit_speed"]) * clock
    cosine, sine = np.cos(angle), np.sin(angle)
    x, z = cloud[:, 0].copy(), cloud[:, 2].copy()
    cloud[:, 0], cloud[:, 2] = x * cosine + z * sine, -x * sine + z * cosine
    return cloud


def particle_field(p, time, seed):
    """Return continuous 3D positions, view normals and persistent attributes."""
    target, normals, cloud, attributes = _population(int(p["attractor"]), int(p["count"]), seed)
    drift = None
    if p.get("axis_mode", 0) == 1:
        pivot, drift = _axis_reference(int(p["attractor"]), seed)
        target = target - pivot
    phase = time / p["period"] + p["phase"]
    wave = .5 - .5 * math.cos(phase * math.tau)
    hold = np.clip(wave * 1.6, 0, 1)
    hold = hold * hold * (3 - 2 * hold)
    assembly = p["assembly"] * (1 - p["breathing"] * (1 - hold))
    # A spatially staggered release avoids all points switching at once.
    cohesion = np.clip(assembly * 1.2 - attributes[:, 7] * .2, 0, 1)
    cohesion = cohesion * cohesion * (3 - 2 * cohesion)
    transfer = cohesion
    surges = p.get("motion", 0) == 1
    if surges:
        cohesion, transfer = _surge_motion(p, phase, target, attributes)
    impulse = p.get("motion", 0) == 2
    if impulse:
        local = _impulse_phase(p, phase, target, attributes) % 1
        hold = _impulse_hold(local, p["period"], p["expand_seconds"], p["gather_seconds"], p["motion_peak"])
        cohesion = p["assembly"] * (1 - p["breathing"] * (1 - hold))
        transfer = cohesion
    orbit = p.get("release", 0) == 1
    carry = orbit and p.get("orbit_handoff", 0) == 1
    if orbit:
        loose = _orbit_cloud(p, time, target, attributes, drift, rotate=not carry)
    else:
        loose = cloud * p["dispersion"]
        # Collapse toward a horizontal band, like the reference's compressed field.
        loose[:, 1] = loose[:, 1] * (1 - p["collapse"]) - p["collapse"] * 1.15
        if surges or impulse:
            loose[:, 2] *= 1 - p["collapse"]
    points = target * transfer[:, None] + loose * (1 - transfer[:, None])
    if surges or impulse:
        # Groups take curved paths into the target instead of a straight lerp.
        bend = np.sin(cohesion * math.pi) * p["chaos"]
        angle = attributes[:, 9] * math.tau + time * .8
        points[:, 0] += bend * np.sin(angle) * .5
        points[:, 2] += bend * np.cos(angle) * .5
    motion_phase = attributes[:, 8:11] * math.tau
    flow_clock = time * p["flow"]
    if surges or impulse:
        flow_clock += p["chaos"] * (.7 * np.sin(time * 1.7) + .3 * np.sin(time * 4.1))
    flow = np.sin(target[:, [1, 2, 0]] * 3.4 + motion_phase + flow_clock)
    flow += .4 * np.sin(target[:, [2, 0, 1]] * 6.2 - motion_phase + flow_clock * .63)
    if (surges or impulse) and not orbit:
        flow[:, 1:] *= (1 - .9 * p["collapse"] * (1 - cohesion))[:, None]
    points += flow * p["turbulence"] * (.12 + .88 * (1 - cohesion[:, None]))
    turn_time = _assembled_turn_time(p, time) if p.get("turn_scope", 0) == 1 else time
    yaw = math.radians(p["yaw"] + turn_time * p["rotation_speed"])
    if carry:
        # Blend the two shapes in one rotating frame. Blending an orbiting
        # cloud back toward an unrotated target makes the return unwind.
        yaw += math.radians(_carried_orbit_time(p, time) * p["orbit_speed"])
    pitch = math.radians(p["pitch"])
    yaw_matrix = np.array(((math.cos(yaw), 0, math.sin(yaw)), (0, 1, 0), (-math.sin(yaw), 0, math.cos(yaw))))
    pitch_matrix = np.array(((1, 0, 0), (0, math.cos(pitch), -math.sin(pitch)), (0, math.sin(pitch), math.cos(pitch))))
    rotation = pitch_matrix @ yaw_matrix
    return points @ rotation.T, normals @ rotation.T, attributes, cohesion


def render_particles(arr, p, time, preset, seed):
    if p["intensity"] == 0:
        return arr
    h, w = arr.shape[:2]
    clock = time * preset["speed"]
    points, normals, attributes, cohesion = particle_field(p, clock, seed)
    perspective = 3.8 / np.maximum(.5, 3.8 - points[:, 2] * p["perspective"])
    scale = h * .35 * p["scale"]
    x = w * (.5 + p["position_x"] * .5) + points[:, 0] * scale * perspective
    y = h * (.5 - p["position_y"] * .5) - (points[:, 1] + .1) * scale * perspective
    # Irregular scan registration is separate from the smooth particle paths.
    frame = round(time * preset["treatment_fps"])
    x += p["jitter"] * w * np.sin(np.floor(y / max(1, h / 144)) * 1.73 + frame * 2.39)
    hue = p["hue"] + points[:, 1] * p["color_spread"] * .35 + attributes[:, 11] * .12 + clock * p["color_drift"]
    rgb = np.clip(np.abs((hue[:, None] + np.array((0, 2 / 3, 1 / 3))) % 1 * 6 - 3) - 1, 0, 1)
    rgb = 1 - p["saturation"] + rgb * p["saturation"]
    facing = np.clip(normals[:, 2] * .85 + .2, 0, 1)
    visibility = (1 - cohesion) + cohesion * (p["xray"] + (1 - p["xray"]) * facing)
    if p.get("occlusion", 0.) > 0:
        # A fixed proxy grid gives preview/export the same depth decisions.
        # Only point depths are used; no solid guide surface enters the image.
        visibility *= _surface_visibility(points, x / w, y / h, cohesion, w / h, p["occlusion"])
    lighting = .18 + .82 * np.clip(normals @ np.array((-.45, .55, .7)), 0, 1)
    relief = lighting * attributes[:, 15]
    visibility *= 1 - cohesion * p["relief"] * (1 - relief)
    twinkle = 1 - p["shimmer"] * (.5 + .5 * np.sin(attributes[:, 12] * math.tau + clock * (4 + attributes[:, 13] * 9)))
    light = (.35 + attributes[:, 14] * .9) * visibility * twinkle * p["intensity"]
    if p.get("released_brightness", 1.) != 1.:
        light *= p["released_brightness"] + (1 - p["released_brightness"]) * cohesion
    if p.get("neck_fade", 0.) > 0 and int(p["attractor"]) in (0, 3, 4):
        target = _population(int(p["attractor"]), int(p["count"]), seed)[0]
        # Fade in model space so the soft edge turns with the head. Restore
        # those dots during release, retaining the complete expanded cloud.
        light *= _neck_visibility(target[:, 1], attributes[:, 3], cohesion, p["neck_fade"])
    colors = rgb * light[:, None]
    layer = np.zeros_like(arr)
    # Subpixel splats avoid pixel snapping; fixed reference sizes keep dots
    # consistent between preview and export. Off-screen particles never wrap.
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - ix, y - iy
    energy = (h / 576) ** 2 * (1 + p["dot_size"] ** 1.5)
    for dx, dy, weight in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xx, yy = ix + dx, iy + dy
        inside = (xx >= 0) & (xx < w) & (yy >= 0) & (yy < h)
        np.add.at(layer, (yy[inside], xx[inside]), colors[inside] * (weight[inside] * energy)[:, None])
    radius = max(0, p["dot_size"] - .5) * h / 576 * .65
    if radius > .05:
        # Float convolution retains additive energy in dense, glowing clusters.
        reach = math.ceil(radius * 3)
        kernel = np.exp(-.5 * (np.arange(-reach, reach + 1) / radius) ** 2)
        kernel /= kernel.sum()
        for axis in (0, 1):
            padding = [(0, 0), (0, 0), (0, 0)]
            padding[axis] = (reach, reach)
            padded = np.pad(layer, padding)
            layer = np.zeros_like(layer)
            for offset, weight in enumerate(kernel):
                slices = [slice(None)] * 3
                slices[axis] = slice(offset, offset + arr.shape[axis])
                layer += padded[tuple(slices)] * weight
    return arr + layer


def _neck_visibility(height, variation, cohesion, width):
    if width <= 0:
        return np.ones_like(height)
    # All head guides end near -1.25. The feather begins just above the lowest
    # mesh edge; seeded variation prevents a new ruler-straight boundary.
    feather = _ease((height + 1.18 - (variation - .5) * width * .18) / width)
    return 1 - (1 - feather) * cohesion ** 2


def _surface_visibility(points, x, y, cohesion, aspect, strength):
    height, width = 192, round(192 * aspect)
    ix = np.clip((x * width).astype(int), 0, width - 1)
    iy = np.clip((y * height).astype(int), 0, height - 1)
    depth = np.full((height, width), -np.inf)
    eligible = (x >= 0) & (x < 1) & (y >= 0) & (y < 1) & (cohesion > .8)
    np.maximum.at(depth, (iy[eligible], ix[eligible]), points[eligible, 2])
    # Close small sampling gaps; the soft depth tolerance protects silhouette.
    pad = np.pad(depth, 1, constant_values=-np.inf)
    front = np.maximum.reduce([pad[dy:dy + height, dx:dx + width] for dy in range(3) for dx in range(3)])
    gap = np.maximum(0., front[iy, ix] - points[:, 2] - .035)
    hidden = 1 - np.exp(-gap * 28)
    return 1 - hidden * strength * cohesion ** 4
