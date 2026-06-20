"""
analytics/xt_model.py — Expected Threat (xT), Karun Singh's Markov-chain model.

The pitch is split into a GRID_X x GRID_Y grid. Each cell's xT value is the
probability that possession starting there eventually leads to a goal, solved by
value iteration:

    xT(c) = shoot%(c) * goal%(c)
          + move%(c) * Σ_c' T(c, c') * xT(c')

where for each cell:
  shoot% / move% = share of actions there that are shots vs successful moves,
  goal%          = P(goal | shot) from there,
  T(c, c')       = where successful moves from c end up.

Fitted on all tournament events. ~one matrix solve; cheap and cached upstream.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GRID_X, GRID_Y = 12, 8
CELL_W, CELL_H = 120 / GRID_X, 80 / GRID_Y


def cell_index(x: float, y: float) -> int | None:
    """Flat cell index (0 .. GRID_X*GRID_Y-1) for a pitch location, or None."""
    if x is None or y is None or np.isnan(x) or np.isnan(y):
        return None
    xi = min(int(x // CELL_W), GRID_X - 1)
    yi = min(int(y // CELL_H), GRID_Y - 1)
    return yi * GRID_X + xi


def _xy(loc):
    if loc is None:
        return (np.nan, np.nan)
    return (float(loc[0]), float(loc[1]))


def fit_xt(events: pd.DataFrame, n_iter: int = 60) -> np.ndarray:
    """Return the fitted xT surface as a (GRID_Y, GRID_X) array."""
    n_cells = GRID_X * GRID_Y
    shots = np.zeros(n_cells)
    goals = np.zeros(n_cells)
    moves = np.zeros(n_cells)
    trans = np.zeros((n_cells, n_cells))

    is_shot = events["type"] == "Shot"
    for r in events[is_shot].itertuples():
        x, y = _xy(getattr(r, "location"))
        c = cell_index(x, y)
        if c is None:
            continue
        shots[c] += 1
        if getattr(r, "shot_outcome", None) == "Goal":
            goals[c] += 1

    # successful moves: completed passes + carries
    passes = events[(events["type"] == "Pass") & (events["pass_outcome"].isna())]
    for r in passes.itertuples():
        c0 = cell_index(*_xy(getattr(r, "location")))
        c1 = cell_index(*_xy(getattr(r, "pass_end_location")))
        if c0 is None or c1 is None:
            continue
        moves[c0] += 1
        trans[c0, c1] += 1

    carries = events[events["type"] == "Carry"]
    for r in carries.itertuples():
        c0 = cell_index(*_xy(getattr(r, "location")))
        c1 = cell_index(*_xy(getattr(r, "carry_end_location")))
        if c0 is None or c1 is None:
            continue
        moves[c0] += 1
        trans[c0, c1] += 1

    total = shots + moves
    with np.errstate(divide="ignore", invalid="ignore"):
        shoot_p = np.where(total > 0, shots / total, 0.0)
        move_p = np.where(total > 0, moves / total, 0.0)
        goal_p = np.where(shots > 0, goals / shots, 0.0)
        row_sum = trans.sum(axis=1, keepdims=True)
        T = np.where(row_sum > 0, trans / row_sum, 0.0)

    xt = np.zeros(n_cells)
    for _ in range(n_iter):
        xt = shoot_p * goal_p + move_p * (T @ xt)

    return xt.reshape(GRID_Y, GRID_X)


def xt_at(surface: np.ndarray, x: float, y: float) -> float:
    """Look up the xT value of the cell containing (x, y)."""
    c = cell_index(x, y)
    if c is None:
        return 0.0
    return float(surface.reshape(-1)[c])
