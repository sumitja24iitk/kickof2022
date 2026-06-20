"""
viz/tab1_tournament.py — Tab 1 (Tournament Overview) visuals.

Visual 1.2 — xG vs Goals team-efficiency scatter:
  each team is a point (x = total xG generated, y = actual goals scored). A y=x
  reference line splits clinical finishers (above) from wasteful sides (below).
  Click a team -> writes selected_team to session_state (feeds Tab 3).

Penalty shootouts (period 5) are excluded from both xG and goals so the two
axes describe the same run-of-play universe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import loader
from utils import state, styling


@st.cache_data(show_spinner="Aggregating team xG …")
def compute_team_efficiency() -> pd.DataFrame:
    """One row per team: matches played, total xG, goals, and xG difference."""
    ev = loader.load_all_events(
        columns=["type", "team", "shot_statsbomb_xg", "shot_outcome", "period"]
    )
    shots = ev[(ev["type"] == "Shot") & (ev["period"] < 5)]  # drop shootouts

    agg = shots.groupby("team").agg(
        xg=("shot_statsbomb_xg", "sum"),
        goals=("shot_outcome", lambda s: (s == "Goal").sum()),
    )

    # matches played, counted from the fixture list (home or away)
    matches = loader.load_matches()
    played: dict[str, int] = {}
    for _, m in matches.iterrows():
        for t in (m["home_team"], m["away_team"]):
            played[t] = played.get(t, 0) + 1
    agg["matches"] = agg.index.map(played).fillna(0).astype(int)

    agg["xg_diff"] = agg["goals"] - agg["xg"]
    return agg.reset_index().sort_values("goals", ascending=False).reset_index(drop=True)


def build_figure(eff: pd.DataFrame) -> go.Figure:
    """Scatter of goals vs xG with a y=x efficiency reference line."""
    fig = go.Figure()

    axis_max = float(np.ceil(max(eff["xg"].max(), eff["goals"].max()))) + 1
    fig.add_trace(
        go.Scatter(
            x=[0, axis_max], y=[0, axis_max], mode="lines",
            line=dict(color=styling.PALETTE["muted"], width=1, dash="dash"),
            hoverinfo="skip", showlegend=False, name="xG = Goals",
        )
    )

    # colour by over/under-performance vs xG
    colors = np.where(eff["xg_diff"] >= 0, styling.PALETTE["accent"], styling.PALETTE["accent2"])
    fig.add_trace(
        go.Scatter(
            x=eff["xg"], y=eff["goals"], mode="markers+text",
            text=eff["team"], textposition="top center",
            textfont=dict(size=9, color=styling.PALETTE["muted"]),
            marker=dict(size=12, color=colors, line=dict(color="#0e1117", width=1)),
            customdata=np.stack([eff["team"], eff["matches"], eff["xg_diff"]], axis=-1),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Matches: %{customdata[1]}<br>"
                "xG: %{x:.2f}<br>"
                "Goals: %{y}<br>"
                "xG diff: %{customdata[2]:+.2f}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    fig.update_layout(
        height=560,
        margin=dict(l=50, r=20, t=30, b=50),
        plot_bgcolor=styling.PALETTE["panel"],
        paper_bgcolor=styling.PALETTE["bg"],
        font=dict(color=styling.PALETTE["text"]),
        xaxis=dict(title="Expected Goals (xG)", gridcolor="#232a33", zeroline=False),
        yaxis=dict(title="Goals scored", gridcolor="#232a33", zeroline=False),
    )
    return fig


def render() -> None:
    """Streamlit entry for visual 1.2. Click a point to filter Tab 3 by team."""
    st.subheader("xG vs Goals — Team Efficiency")
    eff = compute_team_efficiency()
    fig = build_figure(eff)

    event = st.plotly_chart(
        fig, width="stretch", key="xg_scatter",
        on_select="rerun", selection_mode="points",
    )

    # click -> set the global team filter
    points = (event.get("selection", {}) or {}).get("points", []) if event else []
    if points:
        team = points[0].get("customdata", [None])[0]
        if team and team != state.get_team():
            state.set_team(team)
            st.rerun()

    if state.get_team():
        st.success(f"Filtering by **{state.get_team()}** — open the Player tab to drill in.")

    st.caption(
        "Each team plotted by expected goals vs goals scored; points above the "
        "dashed y=x line out-performed their xG. Click a team to filter the Player tab. "
        "Penalty shootouts excluded."
    )
