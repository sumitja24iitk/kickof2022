"""
data/transforms.py — pure-pandas derivations on the flat events table.

These functions take an events DataFrame (from loader.load_events /
load_all_events) and return tidy, plot-ready tables. No Streamlit, no caching,
no I/O — so they are trivial to unit-test and to prototype in a notebook.

Schema reminders (see SCHEMA.md):
  - location / *_end_location are numpy arrays [x, y] (or [x, y, z] for aerial
    shot_end_location). Use helpers below to split them into scalar columns.
  - pass_outcome is NULL for completed passes, non-null for incomplete ones.
  - every Shot row has shot_statsbomb_xg (100% coverage).
  - pitch is 120 x 80; attacking goal at x=120, goal mouth y in [36, 44].
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GOAL_X = 120.0
GOAL_Y = 40.0


def _coord(series: pd.Series, idx: int) -> pd.Series:
    """
    Pull component `idx` (0=x, 1=y, 2=z) out of a column of [x, y(, z)] arrays.

    Returns NaN where the value is missing or too short (e.g. z on a 2D point),
    so the result is always a clean float Series.
    """
    def get(v):
        if v is None:
            return np.nan
        try:
            if len(v) > idx:
                return float(v[idx])
        except TypeError:
            return np.nan
        return np.nan

    return series.apply(get).astype("float64")


def get_shots(events: pd.DataFrame) -> pd.DataFrame:
    """
    One row per shot with flattened coordinates and the fields every shot visual
    needs (xG, outcome, body part, situation, goal flag, goalmouth y/z).
    """
    shots = events[events["type"] == "Shot"].copy()
    if shots.empty:
        return shots

    shots["x"] = _coord(shots["location"], 0)
    shots["y"] = _coord(shots["location"], 1)
    shots["end_x"] = _coord(shots["shot_end_location"], 0)
    shots["end_y"] = _coord(shots["shot_end_location"], 1)
    shots["end_z"] = _coord(shots["shot_end_location"], 2)  # height; NaN if grounded

    shots["xg"] = shots.get("shot_statsbomb_xg", np.nan).astype("float64")
    shots["is_goal"] = shots.get("shot_outcome", pd.Series(index=shots.index)) == "Goal"

    # straight-line distance to the centre of the attacking goal
    shots["distance"] = np.hypot(GOAL_X - shots["x"], GOAL_Y - shots["y"])

    keep = [
        "id", "match_id", "minute", "second", "period", "team", "player",
        "position", "play_pattern", "x", "y", "end_x", "end_y", "end_z",
        "xg", "is_goal", "shot_outcome", "shot_body_part", "shot_technique",
        "shot_type", "shot_one_on_one", "shot_first_time",
    ]
    keep = [c for c in keep if c in shots.columns]
    return shots[keep].reset_index(drop=True)


def get_passes(events: pd.DataFrame, completed_only: bool = False) -> pd.DataFrame:
    """
    One row per pass with start/end coordinates, passer, recipient and a boolean
    `completed` flag (pass_outcome is null == completed).

    Set completed_only=True for passing-network / progression use cases.
    """
    passes = events[events["type"] == "Pass"].copy()
    if passes.empty:
        return passes

    passes["x"] = _coord(passes["location"], 0)
    passes["y"] = _coord(passes["location"], 1)
    passes["end_x"] = _coord(passes["pass_end_location"], 0)
    passes["end_y"] = _coord(passes["pass_end_location"], 1)

    # null outcome == completed pass
    outcome = passes.get("pass_outcome", pd.Series(index=passes.index, dtype=object))
    passes["completed"] = outcome.isna()

    keep = [
        "id", "match_id", "minute", "second", "period", "team", "player",
        "position", "pass_recipient", "pass_recipient_id", "x", "y",
        "end_x", "end_y", "pass_length", "pass_angle", "pass_height",
        "pass_type", "completed", "possession",
    ]
    keep = [c for c in keep if c in passes.columns]
    out = passes[keep]
    if completed_only:
        out = out[out["completed"]]
    return out.reset_index(drop=True)


def get_carries(events: pd.DataFrame) -> pd.DataFrame:
    """One row per carry with start (x, y) and end (end_x, end_y) coordinates."""
    carries = events[events["type"] == "Carry"].copy()
    if carries.empty:
        return carries

    carries["x"] = _coord(carries["location"], 0)
    carries["y"] = _coord(carries["location"], 1)
    carries["end_x"] = _coord(carries["carry_end_location"], 0)
    carries["end_y"] = _coord(carries["carry_end_location"], 1)

    keep = [
        "id", "match_id", "minute", "second", "period", "team", "player",
        "position", "x", "y", "end_x", "end_y", "possession",
    ]
    keep = [c for c in keep if c in carries.columns]
    return carries[keep].reset_index(drop=True)


def get_possessions(events: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse the event stream into one row per possession sequence.

    StatsBomb tags every event with a `possession` number and `possession_team`.
    The result feeds the xT model and the 4.2 possession-replay: each row carries
    the ordered list of (x, y) ball locations plus shot/goal end flags.
    """
    if events.empty or "possession" not in events.columns:
        return pd.DataFrame()

    ev = events.copy()
    ev["x"] = _coord(ev["location"], 0)
    ev["y"] = _coord(ev["location"], 1)

    rows = []
    group_cols = ["match_id", "possession"] if "match_id" in ev.columns else ["possession"]
    for keys, g in ev.groupby(group_cols, sort=True):
        g = g.sort_values("index") if "index" in g.columns else g
        coords = [
            (float(x), float(y))
            for x, y in zip(g["x"], g["y"])
            if pd.notna(x) and pd.notna(y)
        ]
        if not coords:
            continue
        keys = keys if isinstance(keys, tuple) else (keys,)
        rec = dict(zip(group_cols, keys))
        rec.update(
            {
                "possession_team": g["possession_team"].iloc[0]
                if "possession_team" in g.columns else None,
                "start_minute": int(g["minute"].iloc[0]) if "minute" in g.columns else None,
                "n_events": len(g),
                "ends_in_shot": bool((g["type"] == "Shot").any()),
                "ends_in_goal": bool((g.get("shot_outcome") == "Goal").any())
                if "shot_outcome" in g.columns else False,
                "coords": coords,
            }
        )
        rows.append(rec)

    return pd.DataFrame(rows)


def get_player_events(events: pd.DataFrame, player: str) -> pd.DataFrame:
    """All events performed by `player`, with x/y split out. Feeds Tab 3 heatmaps."""
    pe = events[events["player"] == player].copy()
    if pe.empty:
        return pe
    pe["x"] = _coord(pe["location"], 0)
    pe["y"] = _coord(pe["location"], 1)
    return pe.reset_index(drop=True)
