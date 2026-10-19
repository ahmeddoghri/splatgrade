from __future__ import annotations

import math
import struct
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


# PLY scalar types, mapped to struct format characters and byte widths.
_PLY_TYPES = {
    "char": ("b", 1), "int8": ("b", 1),
    "uchar": ("B", 1), "uint8": ("B", 1),
    "short": ("h", 2), "int16": ("h", 2),
    "ushort": ("H", 2), "uint16": ("H", 2),
    "int": ("i", 4), "int32": ("i", 4),
    "uint": ("I", 4), "uint32": ("I", 4),
    "float": ("f", 4), "float32": ("f", 4),
    "double": ("d", 8), "float64": ("d", 8),
}


def _gaussian_from(record: dict) -> dict:
    if {"scale_0", "scale_1", "scale_2"}.issubset(record):
        scale = [math.exp(record[f"scale_{axis}"]) for axis in range(3)]
    else:
        scale = [float(record.get("scale", 0.1))] * 3
    opacity_raw = float(record.get("opacity", 1.0))
    opacity = 1 / (1 + math.exp(-opacity_raw)) if opacity_raw < 0 or opacity_raw > 1 else opacity_raw
    return {"x": record["x"], "y": record["y"], "z": record["z"], "scale": scale, "opacity": opacity}


def _parse_header(data: bytes) -> tuple[str, list[tuple[str, str]], int, int]:
    """Return (format, [(type, name)], vertex_count, offset after end_header)."""
    marker = b"end_header"
    position = data.find(marker)
    if not data.startswith(b"ply") or position == -1:
        raise ValueError("not a PLY file")
    newline = data.find(b"\n", position)
    header = data[:position].decode("ascii", errors="replace").splitlines()
    ply_format = None
    properties: list[tuple[str, str]] = []
    vertex_count = None
    in_vertex = False
    for line in header[1:]:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "format":
            if len(parts) < 2:
                raise ValueError("PLY header has a malformed format line")
            ply_format = parts[1]
        elif parts[0] == "element":
            if len(parts) < 3:
                raise ValueError("PLY header has a malformed element line")
            in_vertex = parts[1] == "vertex"
            if in_vertex:
                vertex_count = int(parts[2])
        elif parts[0] == "property" and in_vertex:
            if parts[1] == "list":
                raise ValueError("list properties are not supported on vertex elements")
            if len(parts) < 3:
                raise ValueError("PLY header has a malformed property line")
            properties.append((parts[1], parts[-1]))
        elif parts[0] not in ("comment", "obj_info"):
            raise ValueError(f"unrecognized PLY header line: {line.strip()}")
    if ply_format is None or vertex_count is None:
        raise ValueError("PLY vertex header is incomplete")
    if not {"x", "y", "z"}.issubset({name for _, name in properties}):
        raise ValueError("PLY must contain x, y, and z properties")
    return ply_format, properties, vertex_count, newline + 1


def parse_ply(path: str | Path) -> list[dict]:
    data = Path(path).read_bytes()
    ply_format, properties, vertex_count, body = _parse_header(data)
    names = [name for _, name in properties]

    if ply_format == "ascii":
        lines = data[body:].decode("utf-8", errors="replace").splitlines()
        result = []
        for line in lines[:vertex_count]:
            values = [float(value) for value in line.split()]
            if len(values) < len(names):
                raise ValueError("PLY vertex row has fewer fields than declared properties")
            result.append(_gaussian_from(dict(zip(names, values))))
        if len(result) != vertex_count:
            raise ValueError("PLY contains fewer vertices than declared")
        return result

    # Real 3DGS exporters (Inria, nerfstudio, and the viewers that read them)
    # write binary little-endian, so ASCII-only support meant this gate could
    # not open a single scene produced by an actual splatting pipeline.
    if ply_format not in ("binary_little_endian", "binary_big_endian"):
        raise ValueError(f"unsupported PLY format: {ply_format}")
    endian = "<" if ply_format == "binary_little_endian" else ">"
    try:
        layout = "".join(_PLY_TYPES[kind][0] for kind, _ in properties)
    except KeyError as error:
        raise ValueError(f"unsupported PLY property type: {error.args[0]}") from None
    stride = sum(_PLY_TYPES[kind][1] for kind, _ in properties)
    needed = stride * vertex_count
    available = len(data) - body
    if available < needed:
        raise ValueError(
            f"PLY body is truncated: {available} bytes for {vertex_count} vertices of {stride} bytes"
        )
    unpack = struct.Struct(endian + layout).unpack_from
    result = []
    for index in range(vertex_count):
        values = unpack(data, body + index * stride)
        result.append(_gaussian_from(dict(zip(names, (float(value) for value in values)))))
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
