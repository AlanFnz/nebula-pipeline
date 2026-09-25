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
        points, normals = sample_human_head(random)
    if shape != 0:
        random[:, 15] = 1
    cloud = (random[:, 4:7] * 2 - 1) * np.array((1.65, 1.25, 1.3))
    for array in (points, normals, cloud, random):
        array.setflags(write=False)
    return points, normals, cloud, random


def _ease(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def _surge_motion(p, phase, target, attributes):
    """Uneven charges and damped arrivals, with continuous cycle boundaries."""
    chaos = p["chaos"]
    # Modulate cycle duration continuously; the clock never jumps at a wrap.
    phase += chaos * (.055 * np.sin(phase * math.tau * .73) + .022 * np.sin(phase * math.tau * 1.91))
    delay = chaos * (.12 * attributes[:, 7] + .025 * target[:, 1])
    local = (phase - delay) % 1
    incoming = _ease((local - .10) / .30) ** (1 + 4 * p["acceleration"])
    outgoing = _ease((local - .57) / .24) ** (1 + 3 * p["acceleration"])
    hold = incoming * (1 - outgoing)
    cohesion = p["assembly"] * (1 - p["breathing"] * (1 - hold))
    settle = np.clip((local - .40) / .16, 0, 1)
    ring = np.sin(settle * math.tau * 1.5) * np.sin(settle * math.pi) ** 2 * np.exp(-settle * 2)
    transfer = cohesion + ring * p["overshoot"] * .75 * p["assembly"] * p["breathing"]
    return cohesion, transfer


def particle_field(p, time, seed):
    """Return continuous 3D positions, view normals and persistent attributes."""
    target, normals, cloud, attributes = _population(int(p["attractor"]), int(p["count"]), seed)
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
    loose = cloud * p["dispersion"]
    # Collapse toward a horizontal band, like the reference's compressed field.
    loose[:, 1] = loose[:, 1] * (1 - p["collapse"]) - p["collapse"] * 1.15
    if surges:
        loose[:, 2] *= 1 - p["collapse"]
    points = target * transfer[:, None] + loose * (1 - transfer[:, None])
    if surges:
        # Groups take curved paths into the target instead of a straight lerp.
        bend = np.sin(cohesion * math.pi) * p["chaos"]
        angle = attributes[:, 9] * math.tau + time * .8
        points[:, 0] += bend * np.sin(angle) * .5
        points[:, 2] += bend * np.cos(angle) * .5
    motion_phase = attributes[:, 8:11] * math.tau
    flow_clock = time * p["flow"]
    if surges:
        flow_clock += p["chaos"] * (.7 * np.sin(time * 1.7) + .3 * np.sin(time * 4.1))
    flow = np.sin(target[:, [1, 2, 0]] * 3.4 + motion_phase + flow_clock)
    flow += .4 * np.sin(target[:, [2, 0, 1]] * 6.2 - motion_phase + flow_clock * .63)
    if surges:
        flow[:, 1:] *= (1 - .9 * p["collapse"] * (1 - cohesion))[:, None]
    points += flow * p["turbulence"] * (.12 + .88 * (1 - cohesion[:, None]))
    yaw = math.radians(p["yaw"] + time * p["rotation_speed"])
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
    lighting = .18 + .82 * np.clip(normals @ np.array((-.45, .55, .7)), 0, 1)
    relief = lighting * attributes[:, 15]
    visibility *= 1 - cohesion * p["relief"] * (1 - relief)
    twinkle = 1 - p["shimmer"] * (.5 + .5 * np.sin(attributes[:, 12] * math.tau + clock * (4 + attributes[:, 13] * 9)))
    light = (.35 + attributes[:, 14] * .9) * visibility * twinkle * p["intensity"]
    if p.get("released_brightness", 1.) != 1.:
        light *= p["released_brightness"] + (1 - p["released_brightness"]) * cohesion
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
