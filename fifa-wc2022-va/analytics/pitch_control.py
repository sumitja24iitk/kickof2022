"""
analytics/pitch_control.py — Voronoi pitch-control geometry.

Given player positions from a 360 freeze-frame, partition the pitch into cells,
one per player, where each cell is the region of the pitch closer to that player
than to any other. Cells are clipped to the pitch rectangle so polygons never
spill past the sidelines (a listed project risk).

Returns plain coordinate lists so the viz layer stays free of geometry code.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import MultiPoint, box

PITCH = box(0, 0, 120, 80)
# far "bounding" points so every real player's region comes out finite
_FAR = np.array([[-1000, -1000], [3000, -1000], [3000, 3000], [-1000, 3000]])


def voronoi_cells(points: np.ndarray) -> list[list[tuple[float, float]] | None]:
    """
    points: (n, 2) array of player (x, y) positions.
    Returns a list (len n) of polygon vertex lists (each clipped to the pitch),
    or None for a player whose cell is degenerate. Needs at least 3 players.
    """
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return [None] * len(pts)

    vor = Voronoi(np.vstack([pts, _FAR]))
    cells: list[list[tuple[float, float]] | None] = []
    for i in range(len(pts)):
        region = vor.regions[vor.point_region[i]]
        if not region or -1 in region:
            cells.append(None)
            continue
        verts = [vor.vertices[v] for v in region]
        # convex hull guarantees a valid, correctly-ordered convex polygon
        poly = MultiPoint(verts).convex_hull.intersection(PITCH)
        if poly.is_empty or poly.geom_type != "Polygon":
            cells.append(None)
            continue
        cells.append([(float(x), float(y)) for x, y in poly.exterior.coords])
    return cells


def control_summary(points: np.ndarray, teammate: np.ndarray) -> dict:
    """Area controlled by each side (sum of clipped cell areas), as % of pitch."""
    from shapely.geometry import Polygon

    cells = voronoi_cells(points)
    area = {"teammate": 0.0, "opponent": 0.0}
    for cell, is_mate in zip(cells, teammate):
        if cell is None:
            continue
        a = Polygon(cell).area
        area["teammate" if is_mate else "opponent"] += a
    total = area["teammate"] + area["opponent"]
    if total == 0:
        return {"teammate_pct": 0.0, "opponent_pct": 0.0}
    return {
        "teammate_pct": 100 * area["teammate"] / total,
        "opponent_pct": 100 * area["opponent"] / total,
    }
