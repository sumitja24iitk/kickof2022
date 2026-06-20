"""
analytics/progression.py — progressive pass / carry filters.

A ball movement is "progressive" (StatsBomb-style, per the blueprint) when it
brings the ball at least 25% closer to the centre of the opponent's goal AND
does not originate inside the opponent's penalty box (so we don't count tap-ins
and goalmouth scrambles as progression).

Functions take an events DataFrame and return tidy rows with start/end coords,
a `completed` flag (opacity in the viz) and the metres-gained `advance`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import transforms

GOAL = (120.0, 40.0)
PROGRESS_FRACTION = 0.25  # must close >=25% of the distance to goal

# opponent penalty box (attacking): x in [102, 120], y in [18, 62]
BOX_X_MIN, BOX_Y_MIN, BOX_Y_MAX = 102.0, 18.0, 62.0


def _dist_to_goal(x: pd.Series, y: pd.Series) -> pd.Series:
    return np.hypot(GOAL[0] - x, GOAL[1] - y)


def _originates_in_box(x: pd.Series, y: pd.Series) -> pd.Series:
    return (x >= BOX_X_MIN) & (y.between(BOX_Y_MIN, BOX_Y_MAX))


def _flag_progressive(df: pd.DataFrame) -> pd.DataFrame:
    """Add dist_start / dist_end / advance / is_progressive to a coords table."""
    if df.empty:
        return df
    df = df.dropna(subset=["x", "y", "end_x", "end_y"]).copy()
    df["dist_start"] = _dist_to_goal(df["x"], df["y"])
    df["dist_end"] = _dist_to_goal(df["end_x"], df["end_y"])
    df["advance"] = df["dist_start"] - df["dist_end"]
    df["is_progressive"] = (
        (df["dist_start"] > 0)
        & (df["dist_end"] <= (1 - PROGRESS_FRACTION) * df["dist_start"])
        & (~_originates_in_box(df["x"], df["y"]))
    )
    return df


def progressive_passes(events: pd.DataFrame) -> pd.DataFrame:
    """Progressive passes from an events frame (keeps the `completed` flag)."""
    passes = transforms.get_passes(events)
    if passes.empty:
        return passes
    flagged = _flag_progressive(passes)
    out = flagged[flagged["is_progressive"]].copy()
    out["kind"] = "pass"
    return out.reset_index(drop=True)


def progressive_carries(events: pd.DataFrame) -> pd.DataFrame:
    """Progressive carries from an events frame (carries are always 'completed')."""
    carries = transforms.get_carries(events)
    if carries.empty:
        return carries
    flagged = _flag_progressive(carries)
    out = flagged[flagged["is_progressive"]].copy()
    out["completed"] = True
    out["kind"] = "carry"
    return out.reset_index(drop=True)
