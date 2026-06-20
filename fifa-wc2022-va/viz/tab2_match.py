"""
viz/tab2_match.py — Tab 2 (Match Analysis) visuals.

Visual 2.1 — Match Momentum (rolling/cumulative xG timeline):
  cumulative xG for each team across the match. Crossings and steep climbs show
  momentum swings. Goals are starred on each line; red cards and substitutions
  are marked on the timeline. A Plotly box-select brushes a minute window and
  writes time_range to session_state — this is the linking hub for Tab 2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import loader, transforms
from utils import state, styling

RED_CARDS = {"Red Card", "Second Yellow"}


def _team_colors(match_row) -> dict[str, str]:
    return {
        match_row["home_team"]: styling.TEAM_COLORS["home"],
        match_row["away_team"]: styling.TEAM_COLORS["away"],
    }


def get_match_markers(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Red-card and substitution rows (minute, team, player) for the timeline."""
    red_mask = pd.Series(False, index=events.index)
    for col in ("foul_committed_card", "bad_behaviour_card"):
        if col in events.columns:
            red_mask |= events[col].isin(RED_CARDS)
    reds = events[red_mask][["minute", "team", "player"]].copy()

    subs = (
        events[events["type"] == "Substitution"][["minute", "team", "player"]].copy()
        if "Substitution" in set(events["type"]) else pd.DataFrame(columns=["minute", "team", "player"])
    )
    return {"reds": reds, "subs": subs}


def get_momentum(events: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    """Per-team cumulative xG over match time (open play + ET, shootouts dropped)."""
    shots = transforms.get_shots(events)
    if shots.empty:
        return shots
    shots = shots[shots["period"] < 5].copy()
    shots["t"] = shots["minute"] + shots.get("second", 0) / 60.0
    shots = shots.sort_values("t")
    shots["cum_xg"] = shots.groupby("team")["xg"].cumsum()
    return shots


def build_momentum_figure(shots: pd.DataFrame, markers: dict, colors: dict,
                          teams: list[str]) -> go.Figure:
    fig = go.Figure()
    if shots.empty:
        return fig

    t_max = float(shots["t"].max())
    for team in teams:
        ts = shots[shots["team"] == team]
        col = colors.get(team, styling.PALETTE["accent"])
        # step line anchored at (0,0) and extended to the final minute
        x = [0.0, *ts["t"].tolist(), t_max]
        y = [0.0, *ts["cum_xg"].tolist(), ts["cum_xg"].max() if len(ts) else 0.0]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", line=dict(color=col, width=2.5, shape="hv"),
            name=team, hovertemplate=f"{team}<br>min %{{x:.0f}} · xG %{{y:.2f}}<extra></extra>",
        ))
        # goals as stars on the line
        goals = ts[ts["is_goal"]]
        if not goals.empty:
            fig.add_trace(go.Scatter(
                x=goals["t"], y=goals["cum_xg"], mode="markers",
                marker=dict(symbol="star", size=15, color=col,
                            line=dict(color="white", width=1)),
                customdata=np.stack([goals["player"].fillna("—"), goals["xg"]], axis=-1),
                hovertemplate="⚽ GOAL %{customdata[0]}<br>min %{x:.0f} · xG %{customdata[1]:.2f}<extra></extra>",
                showlegend=False,
            ))

    y_top = float(shots["cum_xg"].max()) * 1.15 + 0.1
    # red cards: full-height dashed lines
    for _, r in markers["reds"].iterrows():
        fig.add_vline(x=r["minute"], line=dict(color="#ff4d4d", width=1.5, dash="dot"))
        fig.add_annotation(x=r["minute"], y=y_top, text="🟥", showarrow=False, font=dict(size=12))
    # subs: faint ticks along the baseline
    if not markers["subs"].empty:
        fig.add_trace(go.Scatter(
            x=markers["subs"]["minute"], y=[0] * len(markers["subs"]),
            mode="markers", marker=dict(symbol="triangle-up", size=7,
                                        color=styling.PALETTE["muted"], opacity=0.6),
            customdata=markers["subs"][["team", "player"]].values,
            hovertemplate="Sub off · %{customdata[1]} (%{customdata[0]})<br>min %{x:.0f}<extra></extra>",
            showlegend=False,
        ))

    fig.update_layout(
        height=480, margin=dict(l=50, r=20, t=30, b=40),
        plot_bgcolor=styling.PALETTE["panel"], paper_bgcolor=styling.PALETTE["bg"],
        font=dict(color=styling.PALETTE["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        xaxis=dict(title="Match minute", gridcolor="#232a33", range=[0, y_max_x(shots)]),
        yaxis=dict(title="Cumulative xG", gridcolor="#232a33"),
        dragmode="select",
    )
    return fig


def y_max_x(shots: pd.DataFrame) -> float:
    return float(shots["t"].max()) + 2


def render() -> None:
    """Streamlit entry for visual 2.1 — the Tab 2 linking hub."""
    st.subheader("Match Momentum — Cumulative xG")
    mid = state.get_match_id()
    if not mid:
        st.info("Pick a **match** in the sidebar to see its momentum timeline.")
        st.caption("Cumulative xG per team across the match — box-select a window to filter the other Tab 2 visuals.")
        return

    match_row = loader.load_matches().set_index("match_id").loc[mid]
    teams = [match_row["home_team"], match_row["away_team"]]
    colors = _team_colors(match_row)

    events = loader.load_events(mid)
    shots = get_momentum(events, teams)
    markers = get_match_markers(events)

    if shots.empty:
        st.warning("No shots recorded for this match.")
        return

    fig = build_momentum_figure(shots, markers, colors, teams)
    event = st.plotly_chart(fig, width="stretch", key="momentum_fig",
                            on_select="rerun", selection_mode="box")

    # box-select -> write the global time_range filter
    boxes = (event.get("selection", {}) or {}).get("box", []) if event else []
    if boxes:
        xr = boxes[0].get("x", [])
        if len(xr) >= 2:
            lo, hi = sorted(int(round(v)) for v in (xr[0], xr[-1]))
            if (lo, hi) != state.get_time_range():
                state.set_time_range((lo, hi))
                st.rerun()

    tr = state.get_time_range()
    cols = st.columns([3, 1])
    with cols[0]:
        if tr:
            st.success(f"⏱ Time filter active: minutes **{tr[0]}–{tr[1]}** (applies to passing network & shot map).")
        else:
            st.caption("Tip: drag a box across the chart to brush a time window.")
    with cols[1]:
        if tr and st.button("Clear time filter", width="stretch"):
            state.set_time_range(None)
            st.rerun()

    home_xg = shots[shots["team"] == teams[0]]["xg"].sum()
    away_xg = shots[shots["team"] == teams[1]]["xg"].sum()
    st.caption(
        f"{teams[0]} {home_xg:.2f} xG vs {teams[1]} {away_xg:.2f} xG · "
        f"{match_row['home_score']}–{match_row['away_score']} final. "
        "Stars = goals, 🟥 = red card, triangles = subs. Box-select to brush a minute window."
    )
