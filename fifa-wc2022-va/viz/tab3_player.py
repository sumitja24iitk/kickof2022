"""
viz/tab3_player.py — Tab 3 (Player Spotlight) visuals.

Visual 3.1 — Action Density Heatmap:
  a glowing 2D-histogram of every action by the selected player over the pitch,
  revealing their operating zones. Reads selected_player from session_state;
  in-tab toggles pick the action type and the scope (this match vs tournament).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import progression
from data import loader, transforms
from utils import state, styling
from viz.pitch import get_pitch_figure, PITCH_LENGTH, PITCH_WIDTH

# action-type filter -> set of StatsBomb event types ('all' means any located event)
ACTION_TYPES: dict[str, set[str] | None] = {
    "All actions": None,
    "Passes": {"Pass"},
    "Carries": {"Carry"},
    "Shots": {"Shot"},
    "Defensive": {
        "Pressure", "Ball Recovery", "Interception", "Block",
        "Clearance", "Duel", "50/50", "Foul Committed",
    },
}


@st.cache_data(show_spinner=False)
def _slim_all_events() -> pd.DataFrame:
    """Tournament-wide events, only the columns the heatmap needs (cached once)."""
    return loader.load_all_events(columns=["player", "type", "location", "match_id"])


def get_action_points(player: str, match_id: int | None, action: str) -> pd.DataFrame:
    """x/y coordinates of `player`'s actions, optionally scoped to one match."""
    if match_id is not None:
        ev = loader.load_events(int(match_id))
        ev = ev[ev["player"] == player]
    else:
        allev = _slim_all_events()
        ev = allev[allev["player"] == player]

    types = ACTION_TYPES.get(action)
    if types is not None:
        ev = ev[ev["type"].isin(types)]

    pts = transforms.get_player_events(ev, player) if "x" not in ev.columns else ev
    pts = pts.dropna(subset=["x", "y"]) if {"x", "y"}.issubset(pts.columns) else pts
    return pts


def build_heatmap(pts: pd.DataFrame) -> go.Figure:
    """Density heatmap of action locations layered over the pitch."""
    fig = get_pitch_figure(height=560)
    if pts.empty:
        return fig

    fig.add_trace(
        go.Histogram2d(
            x=pts["x"], y=pts["y"],
            xbins=dict(start=0, end=PITCH_LENGTH, size=6),
            ybins=dict(start=0, end=PITCH_WIDTH, size=6),
            colorscale="Inferno", zsmooth="best", opacity=0.82,
            showscale=True, colorbar=dict(title="Actions", thickness=12),
            hovertemplate="x %{x:.0f}, y %{y:.0f}<br>%{z} actions<extra></extra>",
        )
    )
    return fig


def render_heatmap() -> None:
    """Visual 3.1 — Action Density Heatmap."""
    st.subheader("Action Density Heatmap")
    player = state.get_player()

    if not player:
        st.info("Pick a **match** then a **player** in the sidebar to see their action map.")
        st.caption("Glowing heatmap of every action by the selected player — reveals their operating zones.")
        return

    c1, c2 = st.columns(2)
    with c1:
        action = st.radio("Action type", list(ACTION_TYPES), horizontal=True, key="heat_action")
    with c2:
        scope = st.radio("Scope", ["This match", "Whole tournament"], horizontal=True, key="heat_scope")

    match_id = state.get_match_id() if scope == "This match" else None
    pts = get_action_points(player, match_id, action)

    if pts.empty:
        st.warning(f"No **{action.lower()}** found for {player} in this scope.")
    else:
        st.plotly_chart(build_heatmap(pts), width="stretch", key="heat_fig")

    scope_txt = "this match" if match_id is not None else "the whole tournament"
    st.caption(
        f"Density of {player}'s {action.lower()} across {scope_txt} "
        f"({len(pts)} located actions) — brighter zones are where they operate most."
    )


# --- 3.2 Progressive Pass & Carry Map --------------------------------------

# columns progression needs (kept slim so the tournament-wide load stays cheap)
_PROG_COLS = [
    "player", "team", "type", "location", "pass_end_location", "carry_end_location",
    "pass_outcome", "pass_recipient", "minute", "match_id", "period",
]


@st.cache_data(show_spinner=False)
def _prog_all_events() -> pd.DataFrame:
    return loader.load_all_events(columns=_PROG_COLS)


def get_progression(player: str, match_id: int | None) -> pd.DataFrame:
    """Progressive passes + carries for `player`, scoped to a match or tournament."""
    if match_id is not None:
        ev = loader.load_events(int(match_id))
    else:
        ev = _prog_all_events()
    ev = ev[ev["player"] == player]

    passes = progression.progressive_passes(ev)
    carries = progression.progressive_carries(ev)
    cols = ["x", "y", "end_x", "end_y", "kind", "completed", "advance", "minute",
            "pass_recipient", "match_id"]
    frames = [d.reindex(columns=cols) for d in (passes, carries) if not d.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)


def build_progression_figure(prog: pd.DataFrame, kinds: set[str]) -> go.Figure:
    """Arrows for progressive passes/carries; colour = kind, opacity = success."""
    fig = get_pitch_figure(height=560)
    color = {"pass": styling.PALETTE["accent"], "carry": styling.PALETTE["accent2"]}

    for _, r in prog.iterrows():
        if r["kind"] not in kinds:
            continue
        fig.add_annotation(
            x=r["end_x"], y=r["end_y"], ax=r["x"], ay=r["y"],
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=1.1, arrowwidth=2,
            arrowcolor=color[r["kind"]],
            opacity=1.0 if bool(r.get("completed", True)) else 0.35,
        )

    # invisible end-point markers carry the hover detail
    shown = prog[prog["kind"].isin(kinds)]
    if not shown.empty:
        recipient = shown["pass_recipient"].fillna("—")
        fig.add_trace(
            go.Scatter(
                x=shown["end_x"], y=shown["end_y"], mode="markers",
                marker=dict(size=7, color=[color[k] for k in shown["kind"]], opacity=0.6),
                customdata=np.stack([shown["kind"], recipient, shown["minute"].fillna(-1),
                                     shown["advance"]], axis=-1),
                hovertemplate=("%{customdata[0]} → %{customdata[1]}<br>"
                               "min %{customdata[2]:.0f} · +%{customdata[3]:.0f} yd to goal<extra></extra>"),
            )
        )
    return fig


def render_progression() -> None:
    """Visual 3.2 — Progressive Pass & Carry Map."""
    st.subheader("Progressive Pass & Carry Map")
    player = state.get_player()
    if not player:
        st.info("Pick a **match** then a **player** in the sidebar to map their progressions.")
        st.caption("Arrows for passes and carries that moved the ball ≥25% closer to goal.")
        return

    c1, c2 = st.columns(2)
    with c1:
        show = st.radio("Show", ["Both", "Passes", "Carries"], horizontal=True, key="prog_show")
    with c2:
        scope = st.radio("Scope", ["This match", "Whole tournament"], horizontal=True, key="prog_scope")

    kinds = {"Passes": {"pass"}, "Carries": {"carry"}}.get(show, {"pass", "carry"})
    match_id = state.get_match_id() if scope == "This match" else None
    prog = get_progression(player, match_id)
    shown = prog[prog["kind"].isin(kinds)]

    if shown.empty:
        st.warning(f"No progressive {show.lower()} for {player} in this scope.")
    else:
        st.plotly_chart(build_progression_figure(prog, kinds), width="stretch", key="prog_fig")

    scope_txt = "this match" if match_id is not None else "the whole tournament"
    n_pass = int((shown["kind"] == "pass").sum())
    n_carry = int((shown["kind"] == "carry").sum())
    st.caption(
        f"{player}'s ball progressions across {scope_txt}: {n_pass} passes, {n_carry} carries "
        "(≥25% closer to goal, started outside the box). Blue = pass, amber = carry; "
        "faded = incomplete."
    )


def render() -> None:
    """Streamlit entry for Tab 3 — Player Spotlight."""
    render_heatmap()
    st.divider()
    render_progression()
