"""
viz/tab4_advanced.py — Tab 4 (Advanced Tactical Analysis).

Visual 4.1 — Voronoi Pitch Control:
  pick a key moment (a shot/goal that has 360 data) and partition the pitch into
  cells coloured by which team controls the surrounding space. Reveals defensive
  gaps and space dominance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import pitch_control
from data import loader, transforms
from utils import state, styling
from viz.pitch import get_pitch_figure


def _shot_events_with_360(mid: int) -> pd.DataFrame:
    """Shots in the match that have a 360 freeze-frame, newest first by xG."""
    events = loader.load_events(mid)
    shots = transforms.get_shots(events)
    if shots.empty:
        return shots
    shots = shots[shots["period"] < 5]
    frame_ids = set(loader.load_360(mid)["id"]) if not loader.load_360(mid).empty else set()
    shots = shots[shots["id"].isin(frame_ids)]
    return shots.sort_values("minute").reset_index(drop=True)


def build_pitch_control_figure(frame: pd.DataFrame, attacking_color: str,
                               defending_color: str) -> go.Figure:
    """Filled Voronoi cells coloured by team, with player markers on top."""
    fig = get_pitch_figure(height=560)
    fx = frame.copy()
    fx["px"] = fx["location"].apply(lambda v: float(v[0]) if v is not None else np.nan)
    fx["py"] = fx["location"].apply(lambda v: float(v[1]) if v is not None else np.nan)
    fx = fx.dropna(subset=["px", "py"])

    pts = fx[["px", "py"]].to_numpy()
    cells = pitch_control.voronoi_cells(pts)

    for cell, is_mate in zip(cells, fx["teammate"]):
        if cell is None:
            continue
        xs, ys = zip(*cell)
        col = attacking_color if is_mate else defending_color
        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself", mode="lines",
            line=dict(color="rgba(255,255,255,0.25)", width=1),
            fillcolor=col, hoverinfo="skip", showlegend=False, opacity=0.45,
        ))

    # player markers
    for is_mate, name, col, sym in [
        (True, "Attacking", attacking_color, "circle"),
        (False, "Defending", defending_color, "circle"),
    ]:
        g = fx[(fx["teammate"] == is_mate) & (~fx["keeper"])]
        if not g.empty:
            fig.add_trace(go.Scatter(
                x=g["px"], y=g["py"], mode="markers", name=name,
                marker=dict(size=11, color=col, line=dict(color="white", width=1)),
                hoverinfo="skip", showlegend=True))
    gk = fx[fx["keeper"]]
    if not gk.empty:
        fig.add_trace(go.Scatter(x=gk["px"], y=gk["py"], mode="markers", name="Keeper",
                                 marker=dict(size=12, color=styling.PALETTE["accent2"],
                                             symbol="diamond", line=dict(color="white", width=1)),
                                 hoverinfo="skip"))
    actor = fx[fx["actor"]]
    if not actor.empty:
        fig.add_trace(go.Scatter(x=actor["px"], y=actor["py"], mode="markers", name="Ball",
                                 marker=dict(size=15, color="white", symbol="star",
                                             line=dict(color="#0e1117", width=1))))

    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)))
    return fig


def render_pitch_control() -> None:
    """Visual 4.1 — Voronoi Pitch Control."""
    st.subheader("Voronoi Pitch Control")
    mid = state.get_match_id()
    if not mid:
        st.info("Pick a **match** in the sidebar to analyse pitch control at key moments.")
        st.caption("The pitch is split into cells coloured by which team controls the surrounding space.")
        return

    shots = _shot_events_with_360(mid)
    if shots.empty:
        st.warning("This match has no shots with 360 freeze-frame data.")
        return

    match_row = loader.load_matches().set_index("match_id").loc[mid]

    def label(r):
        tag = " ⚽" if r.shot_outcome == "Goal" else ""
        return f"min {int(r.minute)} — {r.player} ({r.shot_outcome}){tag}"

    options = {label(r): r.id for r in shots.itertuples()}
    c1, c2 = st.columns([3, 1])
    with c1:
        choice = st.selectbox("Key moment (shots with 360 data)", list(options), key="pc_event")
    with c2:
        st.radio("Mode", ["Simple"], key="pc_mode",
                 help="Weighted pitch-control was descoped per the project schedule.")

    sid = options[choice]
    shot_row = shots[shots["id"] == sid].iloc[0]
    frame = loader.load_360(mid)
    frame = frame[frame["id"] == sid]

    if len(frame) < 3:
        st.info("Not enough tracked players in this freeze-frame to compute control.")
        return

    att_team = shot_row["team"]
    def_team = match_row["away_team"] if att_team == match_row["home_team"] else match_row["home_team"]
    fig = build_pitch_control_figure(frame, styling.TEAM_COLORS["home"], styling.TEAM_COLORS["away"])
    st.plotly_chart(fig, width="stretch", key="pc_fig")

    summ = pitch_control.control_summary(
        np.array([[float(v[0]), float(v[1])] for v in frame["location"]]),
        frame["teammate"].to_numpy())
    st.caption(
        f"Pitch control at min {int(shot_row['minute'])} ({shot_row['player']}, {shot_row['shot_outcome']}). "
        f"Attacking side {att_team} controls {summ['teammate_pct']:.0f}% of the visible area, "
        f"{def_team} {summ['opponent_pct']:.0f}%. Cells clipped to the pitch."
    )


def render() -> None:
    """Streamlit entry for Tab 4 — Advanced Tactical Analysis."""
    render_pitch_control()
