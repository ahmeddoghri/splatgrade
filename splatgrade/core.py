from __future__ import annotations

import math
import statistics
from pathlib import Path


def _demo_gaussians() -> list[dict]:
    points = []
    for row in range(5):
        for column in range(5):
            points.append({"x": (column - 2) * 0.4, "y": (row - 2) * 0.4, "z": ((row + column) % 3 - 1) * 0.08, "scale": [0.1, 0.08, 0.09], "opacity": 0.82})
    points.extend({**points[index]} for index in range(3))
    points.extend([
        {"x": -0.35, "y": 0.2, "z": 0.0, "scale": [1.4, 1.2, 1.0], "opacity": 0.75},
        {"x": 0.45, "y": -0.1, "z": 0.05, "scale": [1.1, 1.3, 1.0], "opacity": 0.7},
    ])
    for index in range(4):
        points.append({"x": -0.6 + index * 0.4, "y": 1.3, "z": 0.0, "scale": [0.1, 0.1, 0.1], "opacity": 0.01})
    points.extend([
        {"x": 8.0, "y": 7.5, "z": 6.0, "scale": [0.12, 0.1, 0.11], "opacity": 0.8},
        {"x": -9.0, "y": 7.0, "z": -6.5, "scale": [0.1, 0.12, 0.1], "opacity": 0.8},
    ])
    return points


DEMO = {"gaussians": _demo_gaussians(), "duplicate_epsilon": 1e-6, "low_opacity": 0.02, "giant_factor": 5.0}


def parse_ply(path: str | Path) -> list[dict]:
    lines = Path(path).read_text().splitlines()
    if not lines or lines[0].strip() != "ply":
        raise ValueError("not a PLY file")
    if "format ascii 1.0" not in lines[:5]:
        raise ValueError("only ASCII PLY is supported")
    properties = []
    vertex_count = None
    end_header = None
    in_vertex = False
    for index, line in enumerate(lines[1:], start=1):
        parts = line.split()
        if parts[:2] == ["element", "vertex"]:
            vertex_count = int(parts[2])
            in_vertex = True
        elif parts and parts[0] == "element" and parts[1] != "vertex":
            in_vertex = False
        elif in_vertex and parts and parts[0] == "property":
            properties.append(parts[-1])
        elif line.strip() == "end_header":
            end_header = index
            break
    if vertex_count is None or end_header is None:
        raise ValueError("PLY vertex header is incomplete")
    required = {"x", "y", "z"}
    if not required.issubset(properties):
        raise ValueError("PLY must contain x, y, and z properties")
    result = []
    for line in lines[end_header + 1 : end_header + 1 + vertex_count]:
        values = [float(value) for value in line.split()]
        record = dict(zip(properties, values))
        if {"scale_0", "scale_1", "scale_2"}.issubset(record):
            scale = [math.exp(record[f"scale_{axis}"]) for axis in range(3)]
        else:
            scale = [float(record.get("scale", 0.1))] * 3
        opacity_raw = float(record.get("opacity", 1.0))
        opacity = 1 / (1 + math.exp(-opacity_raw)) if opacity_raw < 0 or opacity_raw > 1 else opacity_raw
        result.append({"x": record["x"], "y": record["y"], "z": record["z"], "scale": scale, "opacity": opacity})
    if len(result) != vertex_count:
        raise ValueError("PLY contains fewer vertices than declared")
    return result


def analyze(payload: dict) -> dict:
    gaussians = list(payload["gaussians"])
    if not gaussians:
        raise ValueError("gaussians must not be empty")
    epsilon = float(payload.get("duplicate_epsilon", 1e-6))
    low_threshold = float(payload.get("low_opacity", 0.02))
    giant_factor = float(payload.get("giant_factor", 5.0))
    normalized = []
    invalid = []
    for index, item in enumerate(gaussians):
        position = [float(item[axis]) for axis in ("x", "y", "z")]
        scale = [float(value) for value in item["scale"]]
        opacity = float(item["opacity"])
        invalid_position = any(not math.isfinite(value) for value in position)
        invalid_scale = len(scale) != 3 or any(not math.isfinite(value) or value <= 0 for value in scale)
        invalid_opacity = not math.isfinite(opacity) or not 0 <= opacity <= 1
        if invalid_position or invalid_scale or invalid_opacity:
            invalid.append(index)
        normalized.append({"index": index, "position": position, "scale": scale, "opacity": opacity, "max_scale": max(scale)})
    valid = [item for item in normalized if item["index"] not in invalid]
    median_scale = statistics.median(item["max_scale"] for item in valid) if valid else 0
    giant = [item["index"] for item in valid if item["max_scale"] > median_scale * giant_factor]
    low_opacity = [item["index"] for item in valid if item["opacity"] < low_threshold]
    duplicate_pairs = []
    for left_index, left in enumerate(valid):
        for right in valid[left_index + 1 :]:
            distance = math.dist(left["position"], right["position"])
            if distance <= epsilon:
                duplicate_pairs.append([left["index"], right["index"]])
    center = [statistics.median(item["position"][axis] for item in valid) for axis in range(3)]
    distances = [math.dist(item["position"], center) for item in valid]
    median_distance = statistics.median(distances)
    mad = statistics.median(abs(distance - median_distance) for distance in distances) or max(0.01, median_distance * 0.1)
    floater_limit = median_distance + 6 * mad
    floaters = [item["index"] for item, distance in zip(valid, distances) if distance > floater_limit]
    bounds = [[min(item["position"][axis] for item in valid), max(item["position"][axis] for item in valid)] for axis in range(3)] if valid else [[0, 0]] * 3
    score = max(0, 100 - 12 * len(invalid) - 8 * len(giant) - 5 * len(duplicate_pairs) - 2 * len(low_opacity) - 6 * len(floaters))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    flagged = set(invalid + giant + low_opacity + floaters + [index for pair in duplicate_pairs for index in pair])
    return {
        "gaussian_count": len(gaussians),
        "quality_score": score,
        "grade": grade,
        "median_scale": round(median_scale, 6),
        "invalid_gaussians": invalid,
        "giant_splats": giant,
        "duplicate_pairs": duplicate_pairs,
        "low_opacity_splats": low_opacity,
        "floaters": floaters,
        "scene_bounds": [[round(value, 4) for value in pair] for pair in bounds],
        "preview": [{"x": item["position"][0], "y": item["position"][1], "z": item["position"][2], "scale": item["max_scale"], "opacity": item["opacity"], "flagged": item["index"] in flagged} for item in valid],
        "scope": "Primitive-level preflight; perceptual quality still requires rendered multi-view inspection against capture references.",
    }
