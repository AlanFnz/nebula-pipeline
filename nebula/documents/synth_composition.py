"""Musical-scale composition above the deterministic sequence renderer.

Documents keep a snapshot of their source material. Sections arrange reusable
phrases and macro controls compile to ordinary sequence states and cues.
"""
from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path

from nebula.render.synth import MODULE_BY_ID, SHAPES, _seed, curated_presets
from nebula.documents.synth_sequence import normalize_sequence, reference_sequence, color_continuation_cue
from nebula.effects.synth_effects import apply_effects, merge_effects, normalize_effects
from nebula.core.synth_canvas import normalize_canvas
from nebula.core.synth_shared_timing import apply_shared_timing, normalize_shared_timing
from nebula.effects.synth_master import normalize_master
from nebula.documents.synth_compat import render_version
from nebula.documents.synth_automation import normalize_automations, absolute_event, section_event, compiled_id, MAX_SEQUENCE_EVENTS, STAGES

MAX_SECTIONS = 256
FORMAT = "nebula-composition"
MACROS = {
    "rhythm": ("Rhythm", .25, 2., "Slower holds / faster changes within each section."),
    "width": ("Width", .5, 1.8, "Scale the luminous forms and ray apertures together."),
    "motion": ("Instability", 0., 2., "Registration, edge flutter, deformation and missing fragments."),
    "texture": ("Texture", 0., 2., "Horizontal grain, granular ghosts and the surrounding signal cloud."),
    "glow": ("Brightness", .25, 1.6, "Core intensity and bloom, preserving the color relationships."),
    "flashes": ("Flares", 0., 1.8, "Strength of exposure bursts and sweeps."),
    "color": ("Magenta", 0., 1.8, "Violet-magenta edges and the blue falloff in dim forms."),
}
PATHS = {
    "width": ("slab.width", "blinds.aperture", "ink_bloom.size", "ink_bloom.spread"),
    "motion": ("slab.frame_jitter", "slab.edge_ripple", "slab.jitter", "slab.notch", "blinds.curvature", "blinds.row_drift", "blinds.irregularity", "warp.amount", "flare.bend", "flare.asymmetry", "ink_bloom.tumble", "print_surface.registration", "print_surface.rotation_jitter"),
    "texture": ("raster.grain", "raster.chroma", "raster.line_noise", "slab.ghost_grain", "slab.cloud_strength", "slab.cloud_detail", "print_surface.paper_grain", "print_surface.ink_grain", "print_surface.ink_wear"),
    "glow": ("slab.intensity", "blinds.intensity", "bloom.strength"),
    "flashes": ("flare.strength",),
    "color": ("slab.fill_magenta", "slab.vertical_tint", "slab.magenta", "blinds.magenta", "flare.fringe"),
}


def neutral_macros():
    return dict.fromkeys(MACROS, 1.)


def default_geometry(section=False):
    return {"shape": "inherit" if section else "original", "height": 1., "diameter": .6, "sides": 6, "rotation": 0., "position_x": 0., "position_y": 0.}


def effective_geometry(project, section):
    global_geometry = project["geometry"]
    local_geometry = section["geometry"]
    result = copy.deepcopy(global_geometry if local_geometry["shape"] == "inherit" else local_geometry)
    result["height"] = global_geometry["height"] * local_geometry["height"]
    for axis in ("x", "y"):
        result[f"position_{axis}"] = global_geometry[f"position_{axis}"] + local_geometry[f"position_{axis}"]
    return result


def reference_composition(refined=False):
    from nebula.documents.study_library import library_directory
    initial = "initial-refined.json" if refined else "initial-approved.json"
    path = library_directory() / initial
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    from nebula.documents.synth_starting_points import new_piece
    return new_piece("shape")


def composition_from_sequence(sequence):
    """An imported detailed sequence remains intact as one reusable phrase."""
    source = normalize_sequence(sequence)
    result = {"format": FORMAT, "schema_version": 1, "macros": neutral_macros(),
              "geometry": default_geometry(), "effects": {}, "ink_timing": {},
              "variation": 0, "locks": []}
    result.update(name=source["name"], source=source, fps=source["fps"], seed=source["seed"], render_version=source["render_version"])
    result["canvas"] = normalize_canvas(source.get("canvas"))
    result["master"] = normalize_master(source.get("master"))
    result["phrases"] = {"custom": {"name": source["name"], "start": 0., "end": source["duration"]}}
    result["sections"] = [{"id": "section-1", "phrase": "custom", "duration": source["duration"], "loops": 1, "macros": neutral_macros(), "geometry": default_geometry(section=True), "effects": {}, "variation": 0, "locks": []}]
    if source.get('automations'):
        result['sections'][0]['automations'] = [section_event(event, source['duration']) for event in source['automations']]
        result['source'].pop('automations')
    if 'footage' in source:
        result.update(schema_version=2, render_version=2, footage=copy.deepcopy(source['footage']))
    promoted_audio = False
    for key, schema in (('soundtrack', 4), ('audio_reactivity', 5), ('generated_sound', 6), ('visual_performance', 7)):
        if key in source:
            result[key] = copy.deepcopy(source.pop(key))
            result['schema_version'] = schema
            promoted_audio = True
    if promoted_audio:
        result['source'] = normalize_sequence(source)
    return result


def blank_composition():
    """A single clean section to build from reusable effects."""
    source = normalize_sequence({
        "schema_version": 1, "name": "Free composition", "duration": 15., "fps": 25, "seed": 2409,
        "states": {"blank": {"preset": "Reference blinds", "enabled": [], "overrides": {"slab.ghost_opacity": 0., "slab.cloud_strength": 0., "slab.cloud_detail": 0.}}},
        "cues": [{"time": 0., "state": "blank", "transition": "cut"}],
    })
    return composition_from_sequence(source)


def _number(value, label, low, high, integer=False):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    if integer and not float(value).is_integer():
        raise ValueError(f"{label} must be an integer")
    return int(value) if integer else float(value)


def _controls(raw):
    if not isinstance(raw, dict):
        raise ValueError("Macro controls must be an object")
    result = {}
    for key, (_label, low, high, _hint) in MACROS.items():
        result[key] = _number(raw.get(key, 1.), key, low, high)
    return result


def _geometry(raw, section=False):
    if not isinstance(raw, dict):
        raise ValueError("Geometry must be an object")
    result = default_geometry(section)
    result.update({key: raw[key] for key in result if key in raw})
    shapes = {"original", *(label.lower() for label in SHAPES)}
    if section:
        shapes.add("inherit")
    if not isinstance(result["shape"], str) or result["shape"] not in shapes:
        raise ValueError("Unknown geometry shape")
    for key, low, high in (("height", .25, 2.), ("diameter", .05, 1.5), ("sides", 3, 32), ("rotation", -180, 180), ("position_x", -4096, 4096), ("position_y", -4096, 4096)):
        if key.startswith("position_") and isinstance(result[key], bool):
            raise ValueError(f"{key} must be a number")
        result[key] = _number(result[key], key, low, high, key == "sides")
    return result


def normalize_composition(raw):
    if not isinstance(raw, dict) or raw.get("format") != FORMAT or raw.get("schema_version") not in (1, 2, 3, 4, 5, 6, 7):
        raise ValueError("Unsupported composition document")
    snapshots = None
    if 'snapshots' in raw:
        from nebula.documents.synth_exploration import normalize_snapshots
        snapshots = normalize_snapshots(raw['snapshots'])
    result = copy.deepcopy(raw)
    from nebula.documents.synth_live_set import LIVE_SET, normalize_live_set
    if raw.get(LIVE_SET) is not None: result[LIVE_SET] = normalize_live_set(raw[LIVE_SET])
    else: result.pop(LIVE_SET, None)
    if raw.get('schema_version') in (4, 5, 6, 7):
        result['schema_version'] = 1
    if raw.get('soundtrack') is not None:
        from nebula.audio.synth_soundtrack import normalize_soundtrack
        result['soundtrack'] = normalize_soundtrack(raw['soundtrack'])
    else:
        result.pop('soundtrack', None)
    if raw.get('schema_version') in (2, 3) or 'footage' in raw:
        from nebula.sources.synth_video import normalize_footage
        result['footage'] = normalize_footage(raw.get('footage'))
        result['schema_version'] = 2
    if not isinstance(raw.get("source"), dict):
        raise ValueError("A composition must contain its source recipe")
    result["source"] = normalize_sequence(raw.get("source"))
    result['render_version'] = render_version(raw if 'render_version' in raw else result['source'])
    result["canvas"] = normalize_canvas(raw.get("canvas", result["source"].get("canvas")))
    result["master"] = normalize_master(raw.get("master", result['source'].get('master')))
    result["name"] = str(raw.get("name", "Untitled composition"))
    result["fps"] = _number(raw.get("fps", 25), "FPS", 1, 120, True)
    result["seed"] = _number(raw.get("seed", 0), "Seed", 0, 2**31 - 1, True)
    result["macros"] = _controls(raw.get("macros", {}))
    result["geometry"] = _geometry(raw.get("geometry", {}))
    result["effects"] = normalize_effects(raw.get("effects", {}))
    if 'effect_order' in raw:
        from nebula.effects.synth_effect_order import normalize_order
        result['effect_order'] = normalize_order(raw['effect_order'])
    result["variation"] = _number(raw.get("variation", 0), "Variation", 0, 2**31 - 1, True)
    result["locks"] = [key for key in raw.get("locks", []) if key in MACROS]
    phrases = result.get("phrases")
    if not isinstance(phrases, dict) or not phrases:
        raise ValueError("The composition needs reusable phrases")
    for phrase in phrases.values():
        if not isinstance(phrase, dict):
            raise ValueError("Invalid phrase")
        phrase["start"] = _number(phrase.get("start"), "Phrase start", 0, result["source"]["duration"])
        phrase["end"] = _number(phrase.get("end"), "Phrase end", 0, result["source"]["duration"])
        if phrase["end"] <= phrase["start"]:
            raise ValueError("A phrase must have a positive duration")
        phrase["name"] = str(phrase.get("name", "Phrase"))
    sections = result.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= MAX_SECTIONS:
        raise ValueError(f"Use between 1 and {MAX_SECTIONS} clips")
    ids = set()
    authored_event_count = 0
    for section in sections:
        if not isinstance(section, dict) or section.get("phrase") not in phrases:
            raise ValueError("Unknown clip phrase")
        identifier = section.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("Clip identifiers must be unique")
        ids.add(identifier)
        duration = _number(section.get("duration"), "Clip duration", 1 / result["fps"], 300)
        section["duration"] = max(1, round(duration * result["fps"])) / result["fps"]
        if 'authored_duration' in section:
            authored = _number(section['authored_duration'], 'Authored duration', 0., 300.)
            authored_frames = max(1, round(authored * result['fps']))
            if authored_frames < round(section['duration'] * result['fps']):
                section['authored_duration'] = authored_frames / result['fps']
            else:
                section.pop('authored_duration')
        for key in ('effects_rate', 'video_rate'):
            if key in section:
                if isinstance(section[key], bool): raise ValueError(f'Invalid {key}')
                section[key] = _number(section[key], key, 1e-6, 1e6)
                if math.isclose(section[key], 1., rel_tol=1e-12): section.pop(key)
        section["loops"] = _number(section.get("loops", 1), "Clip loops", 1, 32, True)
        section["macros"] = _controls(section.get("macros", {}))
        section["geometry"] = _geometry(section.get("geometry", {}), section=True)
        section["effects"] = normalize_effects(section.get("effects", {}))
        if 'footage' in section:
            if 'footage' not in result: raise ValueError('Section footage needs a video composition')
            from nebula.sources.synth_video import normalize_footage
            section['footage'] = normalize_footage(section['footage'])
            result['schema_version'] = 3
        if "automations" in section:
            events = normalize_automations(section["automations"])
            authored_event_count += len(events)
            if authored_event_count > MAX_SEQUENCE_EVENTS:
                raise ValueError("Composition contains too many automation events")
            if events: section["automations"] = events
            else: section.pop("automations")
        section["variation"] = _number(section.get("variation", 0), "Variation", 0, 2**31 - 1, True)
        section["locks"] = [key for key in section.get("locks", []) if key in MACROS]
    if 'timeline_loops' in result:
        groups = result['timeline_loops']
        if not isinstance(groups, list) or len(groups) > MAX_SECTIONS:
            raise ValueError('Invalid timeline loop groups')
        positions = {section['id']: index for index, section in enumerate(sections)}
        used = set(); normalized_groups = []
        for group in groups:
            if not isinstance(group, dict): raise ValueError('Invalid timeline loop group')
            members = group.get('sections')
            if (not isinstance(members, list) or not members or
                not all(isinstance(key, str) and key in positions for key in members) or
                len(set(members)) != len(members) or used.intersection(members)):
                raise ValueError('Timeline loop groups need distinct known clips without overlaps')
            loops = _number(group.get('loops'), 'Timeline loop count', 1, 32, True)
            if isinstance(group.get('loops'), bool): raise ValueError('Invalid timeline loop count')
            if loops > 1:
                used.update(members)
                normalized_groups.append({'sections': sorted(members, key=positions.get), 'loops': loops})
        if normalized_groups: result['timeline_loops'] = normalized_groups
        else: result.pop('timeline_loops')
    if section_placements(result)[-1][2] > 3600:
        raise ValueError("Composition is longer than one hour")
    normalize_shared_timing(result)
    if result['source'].get('video_segments'): result['schema_version'] = 3
    scopes = [result, *result['sections']]
    if 'footage' in result:
        from nebula.sources.synth_video import VIDEO_EFFECTS
        for scope in scopes:
            from nebula.render.synth_instances import base_id
            if {base_id(key) for key in scope['effects']} - set(VIDEO_EFFECTS):
                raise ValueError('Video compositions support image treatments; object generators need a generated study')
    elif any(scope['effects'].get('subject_cutout', {}).get('mode') == 'on' for scope in scopes):
        raise ValueError('Subject cutout needs imported video')
    if any(scope['effects'].get('edge_phosphor', {}).get('params', {}).get('edge_phosphor.fade_mode', 0) or
           scope['effects'].get('silhouette', {}).get('params', {}).get('silhouette.definition', 0) for scope in scopes):
        result['render_version'] = 2
    if snapshots is not None:
        if snapshots: result['snapshots'] = snapshots
        else: result.pop('snapshots', None)
    if 'soundtrack' in result:
        result['schema_version'] = 4
    if raw.get('audio_reactivity') is not None:
        from nebula.audio.synth_audio_reactivity import normalize_reactivity
        result['audio_reactivity'] = normalize_reactivity(raw['audio_reactivity'], result.get('soundtrack'))
        result['schema_version'] = 5
    else:
        result.pop('audio_reactivity', None)
    if raw.get('generated_sound') is not None:
        from nebula.audio.synth_visual_sound import normalize_sound
        result['generated_sound'] = normalize_sound(raw['generated_sound'])
        result['schema_version'] = 6
    else:
        result.pop('generated_sound', None)
    if raw.get('visual_performance') is not None:
        from nebula.documents.synth_performance import normalize_performance
        result['visual_performance'] = normalize_performance(raw['visual_performance'])
        result['schema_version'] = 7
    else:
        result.pop('visual_performance', None)
    return result


def section_placements(composition):
    """Expanded timeline occurrences: (section index, start, end, group pass).

    Repetitions reuse their original section and states rather than copying the
    source or changing its seed. Selected sequences repeat after their last
    member, in timeline order. Footage and procedural clocks remain continuous.
    """
    fps = composition["fps"]
    cursor = 0
    result = []
    positions = {section['id']: index for index, section in enumerate(composition['sections'])}
    endings = {}
    for group in composition.get('timeline_loops', []):
        indices = sorted(positions[key] for key in group['sections'])
        endings[indices[-1]] = (indices, group['loops'])

    def append(index, repetition=1):
        nonlocal cursor
        section = composition['sections'][index]
        frames = max(1, round(section["duration"] * fps))
        frames *= int(section.get("loops", 1))
        result.append((index, cursor / fps, (cursor + frames) / fps, repetition))
        cursor += frames

    for index in range(len(composition['sections'])):
        append(index)
        if index in endings:
            indices, loops = endings[index]
            for repetition in range(2, loops + 1):
                for member in indices: append(member, repetition)
    return result


def proportional_section_durations(composition, identifiers, factor):
    """Scale selected base durations together, respecting frame and loop limits.

    This also accepts the timeline's lightweight document for drag previews.
    A common scale stops at the shortest section's one-frame minimum, the
    longest section's 300-second maximum, or the arrangement's one-hour limit.
    """
    if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not math.isfinite(factor):
        raise ValueError('Clip stretch factor must be finite')
    if isinstance(identifiers, str): raise ValueError('Select clips to resize')
    selected = set(identifiers)
    fps = composition['fps']
    original = {section['id']: max(1, round(section['duration'] * fps))
                for section in composition['sections'] if section['id'] in selected}
    if not selected or len(original) != len(selected): raise ValueError('Unknown clips to resize')
    placements = section_placements(composition)
    plays = {identifier: 0 for identifier in original}
    for index, *_ in placements:
        section = composition['sections'][index]
        if section['id'] in plays: plays[section['id']] += int(section.get('loops', 1))
    selected_frames = sum(original[key] * plays[key] for key in original)
    other_frames = round(placements[-1][2] * fps) - selected_frames
    budget = 3600 * fps - other_frames
    lower = 1 / min(original.values())
    upper = min(300 * fps / max(original.values()), budget / selected_frames)
    scale = max(lower, min(upper, factor))

    def frames_at(value):
        return {key: max(1, round(frames * value)) for key, frames in original.items()}

    frames = frames_at(scale)
    # Independent frame rounding can push a heavily repeated selection over
    # the arrangement limit. Find the nearest feasible common scale instead
    # of shortening only one section and changing the selection's proportions.
    if sum(frames[key] * plays[key] for key in frames) > budget:
        low, high = lower, scale
        frames = frames_at(low)
        for _ in range(52):
            midpoint = (low + high) / 2
            candidate = frames_at(midpoint)
            if sum(candidate[key] * plays[key] for key in candidate) <= budget:
                low, frames = midpoint, candidate
            else:
                high = midpoint
    return {key: frames[key] / fps for key in frames}


def _resize_section_frames(section, frames, fps, mode, *, footage=False):
    """Resize one normalized clip. Smart growth preserves its authored frame times."""
    old_frames = round(section['duration'] * fps)
    if frames == old_frames:
        return
    duration = frames / fps
    factor = old_frames / frames
    authored = section.get('authored_duration', section['duration'])
    events = section.get('automations', ())
    # Removing an extension can restore the original exactly. If the user has
    # since written gestures in the tail, retime them instead of losing them.
    keep_timing = mode == 'smart' and duration >= authored and (
        frames > old_frames or all(sum(event[key + '_fraction'] for key in STAGES) * factor <= 1 + 1e-12
                                  for event in events))
    if keep_timing:
        section['authored_duration'] = authored
        for event in events:
            for key in STAGES:
                event[key + '_fraction'] *= factor
    else:
        section['effects_rate'] = section.get('effects_rate', 1.) * factor
        if mode == 'video' and footage:
            section['video_rate'] = section.get('video_rate', 1.) * factor
        if 'authored_duration' in section:
            section['authored_duration'] = authored / factor
    section['duration'] = duration


def _finish_resize(project, previous_duration, mode):
    # Perform is recorded on the composition timeline. Preserve those absolute
    # times on extension (and when removing a tail with no recording in it).
    tracks = project.get('visual_performance', {}).get('tracks', {})
    if mode == 'smart' and tracks:
        ratio = previous_duration / section_placements(project)[-1][2]
        for points in tracks.values():
            if points and points[-1][0] * ratio <= 1 + 1e-12:
                for point in points:
                    point[0] = min(1., point[0] * ratio)
    return normalize_composition(project)


def resize_total_duration(raw, duration, mode):
    """Distribute a total edit across clips on the output frame grid."""
    project = normalize_composition(raw)
    placements = section_placements(project)
    previous_duration = placements[-1][2]
    if project.get('timeline_loops'):
        return stretch_sections(project, [s['id'] for s in project['sections']],
                                duration / previous_duration, mode)
    fps = project['fps']
    plays = [s['loops'] for s in project['sections']]
    frames = max(sum(plays), round(duration * fps))
    cursor = 0
    for index, section in enumerate(project['sections']):
        remaining = sum(plays[index + 1:])
        boundary = round(placements[index][2] / previous_duration * frames)
        boundary = min(frames - remaining, max(cursor + plays[index], boundary))
        clip_frames = max(1, round((boundary - cursor) / plays[index]))
        _resize_section_frames(section, clip_frames, fps, mode, footage='footage' in project)
        cursor += clip_frames * plays[index]
    return _finish_resize(project, previous_duration, mode)


def stretch_sections(raw, identifiers, factor, mode='effects'):
    """One proportional ripple edit, with each selected section's own clocks."""
    if mode not in ('smart', 'effects', 'video'):
        raise ValueError('Unknown clip resize mode')
    result = normalize_composition(raw)
    previous_duration = section_placements(result)[-1][2]
    durations = proportional_section_durations(result, identifiers, factor)
    for section in result['sections']:
        if section['id'] in durations:
            _resize_section_frames(section, round(durations[section['id']] * result['fps']), result['fps'],
                                  mode, footage='footage' in result)
    return _finish_resize(result, previous_duration, mode)


def stretch_section(raw, identifier, duration, mode='effects'):
    """Frame-snapped ripple stretch; untouched section clocks retain their phase."""
    if mode not in ('smart', 'effects', 'video'):
        raise ValueError('Unknown clip resize mode')
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration):
        raise ValueError('Clip duration must be finite')
    result = normalize_composition(raw)
    section = next((item for item in result['sections'] if item['id'] == identifier), None)
    if section is None: raise ValueError('Unknown clip to resize')
    fps = result['fps']
    placements = section_placements(result)
    index = result['sections'].index(section)
    plays = sum(section['loops'] for i, *_ in placements if i == index)
    old_frames = round(section['duration'] * fps)
    other_frames = round(placements[-1][2] * fps) - old_frames * plays
    maximum = min(300 * fps, (3600 * fps - other_frames) // plays)
    frames = max(1, min(maximum, round(duration * fps)))
    if frames == old_frames: return result
    _resize_section_frames(section, frames, fps, mode, footage='footage' in result)
    return _finish_resize(result, placements[-1][2], mode)


def section_ranges(composition):
    """First-play edit anchors; the last group member includes its repeat tail."""
    result = [None] * len(composition['sections'])
    for index, start, end, repetition in section_placements(composition):
        if repetition == 1: result[index] = (start, end)
        else:
            group = next(group for group in composition['timeline_loops']
                         if composition['sections'][index]['id'] in group['sections'])
            last = next(i for i, section in enumerate(composition['sections']) if section['id'] == group['sections'][-1])
            result[last] = (result[last][0], end)
    return result


def _adjust_state(state, macros, seed_offset, geometry):
    result = copy.deepcopy(state)
    presets = curated_presets()[state["preset"]]
    defaults = {f"{entry['id']}.{key}": value for entry in presets["modules"] for key, value in entry["params"].items()}
    overrides = result.setdefault("overrides", {})
    for axis in ("x", "y"):
        if geometry[f"position_{axis}"]:
            path = f"object_{axis}"
            overrides[path] = overrides.get(path, 0.) + geometry[f"position_{axis}"]
    for module_id, height_key in (("slab", "height"), ("blinds", "aperture_height")):
        if geometry["shape"] != "original":
            overrides[f"{module_id}.shape"] = [label.lower() for label in SHAPES].index(geometry["shape"])
            for key in ("diameter", "sides", "rotation"):
                overrides[f"{module_id}.{key}"] = geometry[key]
        if geometry["height"] != 1:
            path = f"{module_id}.{height_key}"
            spec = next(spec for spec in MODULE_BY_ID[module_id].params if spec.key == height_key)
            overrides[path] = max(spec.minimum, min(spec.maximum, overrides.get(path, defaults[path]) * geometry["height"]))
    for macro, paths in PATHS.items():
        if macros[macro] == 1:
            continue  # Neutral macros preserve the approved settings verbatim.
        for path in paths:
            module_id, key = path.split(".")
            spec = next(spec for spec in MODULE_BY_ID[module_id].params if spec.key == key)
            value = overrides.get(path, defaults[path]) * macros[macro]
            overrides[path] = max(spec.minimum, min(spec.maximum, value))
    if seed_offset:
        overrides["seed"] = (int(overrides.get("seed", presets["seed"])) + seed_offset) % (2**31 - 1)
    return result


def phrase_events(project, section):
    phrase = project["phrases"][section["phrase"]]
    first, last = phrase["start"], phrase["end"]
    cues = project["source"]["cues"]
    active = next((cue for cue in reversed(cues) if cue["time"] <= first), cues[0])
    events = [copy.deepcopy(cue) for cue in cues if first <= cue["time"] < last]
    if not events or events[0]["time"] > first:
        events.insert(0, dict(active, time=first, transition="cut", duration=0.))
    return events


def compile_composition(raw, *, base_states=None, project_states=None, project_base_states=None):
    """Compile ordinary sequence states; optionally collect inspector base states.

    Base states exclude creative adjustments and bypass, retaining fixed edits.
    Project collectors omit clip overrides; project_base_states also omits bypass
    and creative adjustments. All collectors leave the exported sequence unchanged.
    The editor's snapshot library is excluded from rendering and base collection.
    """
    project = normalize_composition({key: value for key, value in raw.items() if key != 'snapshots'} if isinstance(raw, dict) else raw)
    if base_states is not None: base_states.clear()
    if project_states is not None: project_states.clear()
    if project_base_states is not None: project_base_states.clear()
    result = copy.deepcopy(project["source"])
    if 'effect_order' in project:
        result['effect_order'] = list(project['effect_order'])
    result.pop("soundtrack", None)
    result.pop('visual_performance', None)
    if 'visual_performance' in project:
        result['visual_performance'] = copy.deepcopy(project['visual_performance'])
    result.pop("generated_sound", None)
    if "generated_sound" in project:
        result["generated_sound"] = copy.deepcopy(project["generated_sound"])
    result.pop("audio_reactivity", None)
    if "audio_reactivity" in project:
        result["audio_reactivity"] = copy.deepcopy(project["audio_reactivity"])
    if "soundtrack" in project:
        result["soundtrack"] = copy.deepcopy(project["soundtrack"])
    result['render_version'] = project['render_version']
    result.update(name=project["name"], fps=project["fps"], seed=project["seed"], states={}, cues=[])
    result["canvas"] = copy.deepcopy(project["canvas"])
    result['master'] = copy.deepcopy(project['master'])
    if 'footage' in project:
        result.update(schema_version=2, footage=copy.deepcopy(project['footage']))
    fps = project["fps"]
    placements = section_placements(project)
    result["duration"] = placements[-1][2]
    from nebula.documents.synth_retime import compose_time_maps
    clocks = []
    compiled_automations = []
    # Imported detailed sequences use section-owned gestures. Reject an ambiguous
    # hand-authored embedded sequence instead of silently losing its automation.
    if project["source"].get("automations"):
        raise ValueError("Import automated sequences with composition_from_sequence before arranging clips")
    effects_time = video_time = 0.
    for occurrence, (index, start, end, _repetition) in enumerate(placements):
        section = project['sections'][index]
        phrase = project["phrases"][section["phrase"]]
        first, last = phrase["start"], phrase["end"]
        events = phrase_events(project, section)
        effects = merge_effects(project["effects"], section["effects"])
        macros = {key: project["macros"][key] * section["macros"][key] for key in MACROS}
        effects_rate = section.get('effects_rate', 1.)
        video_rate = section.get('video_rate', 1.)
        clocks.append(dict(start=start, end=end, effects_start=effects_time,
                           effects_rate=effects_rate, video_start=video_time, video_rate=video_rate))
        effects_time += (end - start) * effects_rate
        video_time += (end - start) * video_rate
        rate = macros["rhythm"] * effects_rate
        cycle = (last - first) / rate
        variant = (project["variation"], section["variation"])
        offset = _seed(project["seed"], section["id"], *variant) % (2**31 - 1) if any(variant) else 0
        loop_frames = max(1, round(section["duration"] * fps))
        authored_frames = round(section.get("authored_duration", section["duration"]) * fps)
        loop_end = (round(start * fps) + authored_frames) / fps
        if len(compiled_automations) + section["loops"] * len(section.get("automations", ())) > MAX_SEQUENCE_EVENTS:
            raise ValueError("Arrangement contains too many automation occurrences")
        for loop in range(section["loops"]):
            for event in section.get("automations", ()):
                compiled_automations.append(absolute_event(event, section["duration"], start + loop * section["duration"],
                    compiled_id(section["id"], event["id"], occurrence, loop)))
        cues_by_frame = {}
        # Compile one edited section, then repeat its frame-aligned cues. Extending
        # the source phrase here would run past a trimmed section's loop boundary.
        for repetition in range(math.ceil((loop_end - start) / cycle)):
            for cue in events:
                frame = round((start + repetition * cycle + (cue["time"] - first) / rate) * fps)
                if frame >= round(loop_end * fps):
                    break
                state_name = f"{section['id']}:{cue['state']}"
                if state_name not in result["states"]:
                    # Optional inspector data excludes clip overrides without a
                    # second compilation or any change to the rendered states.
                    if project_states is not None or project_base_states is not None:
                        shared = _adjust_state(project['source']['states'][cue['state']], project['macros'], 0, project['geometry'])
                        shared, shared_base = apply_effects(shared, project['effects'], include_base=True)
                        if project_states is not None: project_states[state_name] = apply_shared_timing(shared, project['ink_timing'])
                        if project_base_states is not None: project_base_states[state_name] = apply_shared_timing(shared_base, project['ink_timing'])
                    state = _adjust_state(project["source"]["states"][cue["state"]], macros, offset, effective_geometry(project, section))
                    if base_states is None:
                        treated = apply_effects(state, effects)
                    else:
                        treated, base = apply_effects(state, effects, include_base=True)
                        base_states[state_name] = apply_shared_timing(base, project['ink_timing'])
                    result["states"][state_name] = apply_shared_timing(treated, project['ink_timing'])
                    if 'footage' in project:
                        result['states'][state_name].setdefault('overrides', {})['treatment_fps'] = section.get('footage', project['footage'])['treatment_fps']
                item = dict(cue, time=frame / fps, state=state_name)
                item["duration"] = min(float(cue.get("duration", 0)) / rate, loop_end - frame / fps)
                if cue.get("transition") in {"flash", "sweep"}:
                    item["intensity"] = min(3., cue.get("intensity", .6) * macros["flashes"])
                cues_by_frame[frame] = item
        if authored_frames < loop_frames:
            continuation = color_continuation_cue(result, list(cues_by_frame.values()), loop_end)
            if continuation:
                cues_by_frame[round(loop_end * fps)] = continuation
        for loop in range(section["loops"]):
            result["cues"].extend(
                dict(cues_by_frame[frame], time=(frame + loop * loop_frames) / fps)
                for frame in sorted(cues_by_frame)
            )
    result.pop('automations', None)
    if compiled_automations: result['automations'] = compiled_automations
    if project['source'].get('time_map') or any(s.get('effects_rate', 1.) != 1 or s.get('video_rate', 1.) != 1 for s in project['sections']):
        result['time_map'] = compose_time_maps(clocks, project['source'].get('time_map'))
    if 'footage' in project:
        from nebula.documents.synth_section_sources import compile_video_segments
        segments = compile_video_segments(project, placements, clocks, result.get('time_map'))
        if segments: result['video_segments'] = segments
    return normalize_sequence(result)


def vary_composition(raw, section_index=None):
    result = normalize_composition(raw)
    target = result if section_index is None else result["sections"][section_index]
    target["variation"] += 1
    if 'footage' in result:
        return result
    rng = random.Random(_seed(result["seed"], "composition-take", target.get("id", "whole"), target["variation"]))
    for key, (_name, low, high, _hint) in MACROS.items():
        if key in target["locks"]:
            continue
        target["macros"][key] = round(max(low, min(high, target["macros"][key] + rng.uniform(-.15, .15))), 2)
    return result


def save_composition(path, composition):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize_composition(composition), indent=2) + "\n")


def load_composition(path):
    raw = json.loads(Path(path).read_text())
    from nebula.documents.synth_section_sources import resolve_media_paths
    resolve_media_paths(raw, Path(path).resolve().parent)
    return normalize_composition(raw)
