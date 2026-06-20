"""
viz/pitch.py — one reusable StatsBomb pitch as a Plotly figure background.

The single most-reused asset in the project: 7 of the 12 visuals start with
`fig = get_pitch_figure()` and then add their own traces on top. Pitch geometry
is defined exactly once here so it is never redrawn seven different ways.

Coordinate system (StatsBomb, see SCHEMA.md):
  - 120 (length, x) x 80 (width, y), in yards.
  - attacking goal at x=120, defending goal at x=0, goal mouth y in [36, 44].
  - origin (0, 0) at a corner; y increases top -> bottom.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from utils.styling import PALETTE

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0


def _line(x0, y0, x1, y1, color, width=2):
    return dict(type="line", x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(color=color, width=width), layer="below")


def _rect(x0, y0, x1, y1, color, width=2):
    return dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(color=color, width=width), fillcolor="rgba(0,0,0,0)",
                layer="below")


def _arc_path(cx, cy, r, t0, t1, color, width=2, n=40):
    """A circular arc (centre cx,cy, radius r, angles t0->t1 in radians) as a
    many-segment path shape — Plotly paths don't support SVG 'A', so we sample."""
    ts = np.linspace(t0, t1, n)
    pts = [f"{'M' if i == 0 else 'L'} {cx + r*np.cos(t):.3f} {cy + r*np.sin(t):.3f}"
           for i, t in enumerate(ts)]
    return dict(type="path", path=" ".join(pts),
                line=dict(color=color, width=width), layer="below")


def _pitch_shapes(line_color: str) -> list[dict]:
    L, W = PITCH_LENGTH, PITCH_WIDTH
    shapes = [
        _rect(0, 0, L, W, line_color),               # outer boundary
        _line(L / 2, 0, L / 2, W, line_color),        # halfway line
        # penalty areas (18 yd deep, 44 wide -> y 18..62)
        _rect(0, 18, 18, 62, line_color),
        _rect(L - 18, 18, L, 62, line_color),
        # six-yard boxes (6 deep, 20 wide -> y 30..50)
        _rect(0, 30, 6, 50, line_color),
        _rect(L - 6, 30, L, 50, line_color),
        # goals (drawn just outside the byline)
        _rect(-2, 36, 0, 44, line_color),
        _rect(L, 36, L + 2, 44, line_color),
        # centre circle (radius 10) + centre spot
        dict(type="circle", x0=L/2 - 10, y0=W/2 - 10, x1=L/2 + 10, y1=W/2 + 10,
             line=dict(color=line_color, width=2), layer="below"),
        dict(type="circle", x0=L/2 - 0.4, y0=W/2 - 0.4, x1=L/2 + 0.4, y1=W/2 + 0.4,
             line=dict(color=line_color, width=1), fillcolor=line_color, layer="below"),
        # penalty spots
        dict(type="circle", x0=12 - 0.4, y0=40 - 0.4, x1=12 + 0.4, y1=40 + 0.4,
             line=dict(color=line_color, width=1), fillcolor=line_color, layer="below"),
        dict(type="circle", x0=L-12 - 0.4, y0=40 - 0.4, x1=L-12 + 0.4, y1=40 + 0.4,
             line=dict(color=line_color, width=1), fillcolor=line_color, layer="below"),
    ]
    # penalty arcs (the "D"): the part of the 10-yd circle around each penalty
    # spot that sits outside the box. x=18 boundary -> cos = 6/10 = 0.6.
    a = np.arccos(0.6)
    shapes.append(_arc_path(12, 40, 10, -a, a, line_color))                 # left D
    shapes.append(_arc_path(L - 12, 40, 10, np.pi - a, np.pi + a, line_color))  # right D
    return shapes


def get_pitch_figure(
    fig: go.Figure | None = None,
    *,
    half: bool = False,
    pitch_color: str | None = None,
    line_color: str | None = None,
    height: int = 540,
) -> go.Figure:
    """
    Return a Plotly figure with a StatsBomb pitch drawn as background shapes.

    Pass an existing `fig` to draw the pitch onto it; otherwise a new one is made.
    `half=True` shows the attacking half (x 60..120) for shot maps.
    Add your data traces after calling this — they render above the pitch lines.
    """
    fig = fig or go.Figure()
    pitch_color = pitch_color or PALETTE["pitch"]
    line_color = line_color or PALETTE["pitch_line"]

    fig.update_layout(shapes=_pitch_shapes(line_color))

    x_min = PITCH_LENGTH / 2 if half else 0
    fig.update_xaxes(range=[x_min - 3, PITCH_LENGTH + 3], visible=False,
                     constrain="domain")
    # y reversed so origin is top-left, matching StatsBomb; keep aspect 120:80
    fig.update_yaxes(range=[PITCH_WIDTH + 3, -3], visible=False,
                     scaleanchor="x", scaleratio=1)

    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor=pitch_color,
        paper_bgcolor=PALETTE["bg"],
        showlegend=False,
    )
    return fig
