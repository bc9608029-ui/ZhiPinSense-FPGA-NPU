#!/usr/bin/env python3
"""Read-only structural audit for binary STL files; no third-party modules."""

from __future__ import annotations

import argparse
import math
import struct
from collections import Counter, defaultdict
from pathlib import Path


def _audit_triangles(path: Path, triangles: list[list[tuple[float, float, float]]]) -> dict[str, object]:
    facets = len(triangles)
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    zero_area = 0
    zero_area_examples: list[list[tuple[float, float, float]]] = []
    nonfinite = 0
    edges: Counter[tuple[tuple[float, float, float], tuple[float, float, float]]] = Counter()
    adjacency: dict[tuple[float, float, float], set[tuple[float, float, float]]] = defaultdict(set)
    for vertices in triangles:
        if not all(math.isfinite(v) for vertex in vertices for v in vertex):
            nonfinite += 1
            continue
        for vertex in vertices:
            for axis, value in enumerate(vertex):
                lo[axis] = min(lo[axis], value)
                hi[axis] = max(hi[axis], value)
        a, b, c = vertices
        ab = tuple(b[i] - a[i] for i in range(3))
        ac = tuple(c[i] - a[i] for i in range(3))
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        if sum(value * value for value in cross) <= 1e-18:
            zero_area += 1
            if len(zero_area_examples) < 10:
                zero_area_examples.append(vertices)
        for p, q in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((p, q)))] += 1
            adjacency[p].add(q)
            adjacency[q].add(p)
    edge_hist = Counter(edges.values())
    unseen = set(adjacency)
    components = 0
    while unseen:
        components += 1
        stack = [unseen.pop()]
        while stack:
            for neighbor in adjacency[stack.pop()]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
    return {
        "file": path.name,
        "facets": facets,
        "bbox_mm": [round(hi[i] - lo[i], 6) for i in range(3)],
        "zero_area": zero_area,
        "zero_area_examples": zero_area_examples,
        "nonfinite": nonfinite,
        "boundary_edges": edge_hist.get(1, 0),
        "nonmanifold_edges": sum(count for uses, count in edge_hist.items() if uses > 2),
        "connected_components": components,
        "watertight_edge_check": edge_hist.get(1, 0) == 0 and all(uses == 2 for uses in edge_hist),
    }


def audit(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("file is shorter than a binary STL header")
    if data.lstrip().startswith(b"solid"):
        vertices: list[tuple[float, float, float]] = []
        for line in data.decode("ascii", errors="strict").splitlines():
            words = line.split()
            if len(words) == 4 and words[0] == "vertex":
                vertices.append(tuple(float(value) for value in words[1:4]))
        if len(vertices) % 3:
            raise ValueError("ASCII STL vertex count is not divisible by three")
        triangles = [vertices[i:i + 3] for i in range(0, len(vertices), 3)]
        return _audit_triangles(path, triangles)
    facets = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + facets * 50
    if len(data) != expected:
        raise ValueError(f"size mismatch: expected {expected}, got {len(data)}")

    triangles = []
    for index in range(facets):
        values = struct.unpack_from("<12fH", data, 84 + index * 50)
        triangles.append([tuple(values[3 + i * 3:6 + i * 3]) for i in range(3)])
    return _audit_triangles(path, triangles)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        print(audit(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
