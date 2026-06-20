"""
utils/state.py — session_state plumbing that links the four tabs.

Per the blueprint, cross-tab interactions flow through a small, fixed set of
session_state keys so that a click in one tab is read by another:

  selected_match_id  bracket (1.1) click -> Tab 2 reads this match
  selected_team      xG scatter (1.2) click -> Tab 3 filters to this squad
  selected_player    Tab 3 player picker
  time_range         momentum brush (2.1) -> filters 2.3 / 2.4  (minute lo, hi)

Visuals are built standalone first (Phase 2); the actual wiring of these keys is
finalised in Phase 3. This module just gives everyone one agreed vocabulary.
"""

from __future__ import annotations

import streamlit as st

from data import loader

# Default values for every cross-tab key. None == "no selection yet".
_DEFAULTS: dict[str, object] = {
    "selected_match_id": None,
    "selected_team": None,
    "selected_player": None,
    "time_range": None,        # (min_minute, max_minute) or None for whole match
    "active_tab": "Tournament",
}


def init_state() -> None:
    """Seed any missing session_state keys. Safe to call on every rerun."""
    for key, default in _DEFAULTS.items():
        st.session_state.setdefault(key, default)


# --- typed convenience accessors -------------------------------------------

def get_match_id() -> int | None:
    return st.session_state.get("selected_match_id")


def set_match_id(match_id: int | None) -> None:
    st.session_state["selected_match_id"] = int(match_id) if match_id is not None else None


def get_team() -> str | None:
    return st.session_state.get("selected_team")


def set_team(team: str | None) -> None:
    st.session_state["selected_team"] = team


def get_player() -> str | None:
    return st.session_state.get("selected_player")


def set_player(player: str | None) -> None:
    st.session_state["selected_player"] = player


def get_time_range() -> tuple[int, int] | None:
    return st.session_state.get("time_range")


def set_time_range(time_range: tuple[int, int] | None) -> None:
    st.session_state["time_range"] = time_range


# --- the cross-tab filter ---------------------------------------------------

def get_filtered_events(match_id: int | None = None):
    """
    Return the events for the active match, narrowed by the current global
    filters (time_range, selected_team).

    `match_id` overrides the session selection when provided. Returns an empty
    DataFrame if no match is selected yet, so callers can guard with `.empty`.
    """
    import pandas as pd

    mid = match_id if match_id is not None else get_match_id()
    if mid is None:
        return pd.DataFrame()

    events = loader.load_events(int(mid))

    time_range = get_time_range()
    if time_range and "minute" in events.columns:
        lo, hi = time_range
        events = events[events["minute"].between(lo, hi)]

    team = get_team()
    if team and "team" in events.columns:
        events = events[events["team"] == team]

    return events.reset_index(drop=True)
