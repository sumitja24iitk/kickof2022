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


# --- 3.3 3D Shot Trajectories ----------------------------------------------

_SHOT_COLS = [
    "player", "type", "location", "shot_end_location", "shot_statsbomb_xg",
    "shot_outcome", "minute", "match_id", "period",
]


@st.cache_data(show_spinner=False)
def _shots_all_events() -> pd.DataFrame:
    return loader.load_all_events(columns=_SHOT_COLS)


@st.cache_data(show_spinner=False)
def _match_labels() -> dict:
    m = loader.load_matches()
    return {int(r.match_id): f"{r.home_team} v {r.away_team}" for r in m.itertuples()}


def get_player_shots(player: str, match_id: int | None) -> pd.DataFrame:
    """Player's shots with flattened coords incl. end height (z)."""
    if match_id is not None:
        ev = loader.load_events(int(match_id))
    else:
        ev = _shots_all_events()
    ev = ev[ev["player"] == player]
    shots = transforms.get_shots(ev)
    if shots.empty:
        return shots
    return shots[shots["period"] < 5].reset_index(drop=True)


def build_shots3d_figure(shots: pd.DataFrame) -> go.Figure:
    """Parabolic 3D trajectories from shot location to the goal-frame end point."""
    fig = go.Figure()
    labels = _match_labels()

    for s in shots.itertuples():
        end_z = s.end_z if pd.notna(s.end_z) else 0.0
        dist = float(np.hypot(s.end_x - s.x, s.end_y - s.y))
        lift = min(4.0, 0.10 * dist) + end_z * 0.3  # stylised arc height (yards)
        t = np.linspace(0, 1, 24)
        xs = s.x + (s.end_x - s.x) * t
        ys = s.y + (s.end_y - s.y) * t
        zs = end_z * t + 4 * lift * t * (1 - t)
        col = styling.outcome_color(s.shot_outcome)
        is_goal = s.shot_outcome == "Goal"
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=col, width=6 if is_goal else 3),
            opacity=1.0 if is_goal else 0.6, showlegend=False,
            hovertext=f"{labels.get(int(s.match_id),'')}<br>min {int(s.minute)} · "
                      f"xG {s.xg:.2f} · {s.shot_outcome}",
            hoverinfo="text",
        ))
        fig.add_trace(go.Scatter3d(
            x=[s.end_x], y=[s.end_y], z=[zs[-1]], mode="markers",
            marker=dict(size=5 if is_goal else 3, color=col,
                        symbol="diamond" if is_goal else "circle"),
            showlegend=False, hoverinfo="skip",
        ))

    # goal frame at x=120 (mouth y 36-44, crossbar 2.67 yd)
    gx, gy0, gy1, cb = 120, 36, 44, 2.67
    for seg in ([[gx, gx], [gy0, gy0], [0, cb]], [[gx, gx], [gy1, gy1], [0, cb]],
                [[gx, gx], [gy0, gy1], [cb, cb]]):
        fig.add_trace(go.Scatter3d(x=seg[0], y=seg[1], z=seg[2], mode="lines",
                                   line=dict(color=styling.PALETTE["pitch_line"], width=4),
                                   showlegend=False, hoverinfo="skip"))

    fig.update_layout(
        height=600, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor=styling.PALETTE["bg"], font=dict(color=styling.PALETTE["text"]),
        scene=dict(
            xaxis=dict(title="x (toward goal)", range=[60, 122], backgroundcolor=styling.PALETTE["pitch"],
                       gridcolor="#2a3340"),
            yaxis=dict(title="y", range=[0, 80], backgroundcolor=styling.PALETTE["pitch"],
                       gridcolor="#2a3340"),
            zaxis=dict(title="height (yd)", range=[0, 8], backgroundcolor=styling.PALETTE["bg"],
                       gridcolor="#2a3340"),
            aspectmode="manual", aspectratio=dict(x=2, y=2.4, z=0.6),
            camera=dict(eye=dict(x=-1.6, y=-1.4, z=0.9)),
        ),
    )
    return fig


def render_shots3d() -> None:
    """Visual 3.3 — 3D Shot Trajectories."""
    st.subheader("3D Shot Trajectories")
    player = state.get_player()
    if not player:
        st.info("Pick a **match** then a **player** in the sidebar to see their shots in 3D.")
        st.caption("Each shot arcs from its location toward the goal; colour = outcome, height = trajectory.")
        return

    scope = st.radio("Scope", ["This match", "Whole tournament"], horizontal=True, key="s3d_scope")
    match_id = state.get_match_id() if scope == "This match" else None
    shots = get_player_shots(player, match_id)

    if shots.empty:
        st.warning(f"No shots for {player} in this scope.")
    else:
        st.plotly_chart(build_shots3d_figure(shots), width="stretch", key="s3d_fig")

    scope_txt = "this match" if match_id is not None else "the whole tournament"
    n_goal = int((shots["shot_outcome"] == "Goal").sum()) if not shots.empty else 0
    st.caption(
        f"{player}'s {len(shots)} shots across {scope_txt} ({n_goal} goals) in 3D — "
        "drag to rotate. Green = goal; line height traces the ball's flight."
    )


def render() -> None:
    """Streamlit entry for Tab 3 — Player Spotlight."""
    render_heatmap()
    st.divider()
    render_progression()
    st.divider()
    render_shots3d()
