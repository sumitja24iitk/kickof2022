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

from analytics import network_metrics
from data import loader, transforms
from utils import state, styling
from viz.pitch import get_pitch_figure

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


def render_momentum() -> None:
    """Visual 2.1 — Match Momentum (the Tab 2 linking hub)."""
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


# --- 2.3 Passing Network with Centrality -----------------------------------

def _surname(name: str) -> str:
    return str(name).split()[-1] if pd.notna(name) else ""


def build_network_figure(nodes: pd.DataFrame, edges: pd.DataFrame) -> go.Figure:
    """Draw the passing network over the pitch: edges then centrality-coloured nodes."""
    fig = get_pitch_figure(height=560)
    if nodes.empty:
        return fig
    pos = nodes.set_index("player")[["x", "y"]]

    # edges: width scaled by pass count
    max_count = edges["count"].max() if not edges.empty else 1
    for e in edges.itertuples():
        if e.a not in pos.index or e.b not in pos.index:
            continue
        x0, y0 = pos.loc[e.a]
        x1, y1 = pos.loc[e.b]
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines",
            line=dict(color="rgba(233,238,242,0.35)", width=1 + 6 * e.count / max_count),
            hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=[(x0 + x1) / 2], y=[(y0 + y1) / 2], mode="markers",
            marker=dict(size=10, color="rgba(0,0,0,0)"),
            hovertemplate=f"{_surname(e.a)} ↔ {_surname(e.b)}<br>"
                          f"{e.count} passes · {e.completion:.0%} completed<extra></extra>",
            showlegend=False,
        ))

    # nodes: size = passes, colour = betweenness
    fig.add_trace(go.Scatter(
        x=nodes["x"], y=nodes["y"], mode="markers+text",
        text=[_surname(p) for p in nodes["player"]], textposition="bottom center",
        textfont=dict(size=9, color=styling.PALETTE["text"]),
        marker=dict(
            size=12 + 28 * nodes["passes"] / max(nodes["passes"].max(), 1),
            color=nodes["betweenness"], colorscale="Plasma", showscale=True,
            colorbar=dict(title="Betweenness", thickness=12),
            line=dict(color="#0e1117", width=1),
        ),
        customdata=np.stack([nodes["player"], nodes["passes"], nodes["betweenness"]], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} passes<br>"
                      "betweenness %{customdata[2]:.3f}<extra></extra>",
        showlegend=False,
    ))
    return fig


def render_passing_network() -> None:
    """Visual 2.3 — Dynamic passing network with centrality."""
    st.subheader("Passing Network & Centrality")
    mid = state.get_match_id()
    if not mid:
        st.info("Pick a **match** in the sidebar to build its passing network.")
        st.caption("Players at average position; edge width = pass volume, node colour = betweenness centrality.")
        return

    match_row = loader.load_matches().set_index("match_id").loc[mid]
    teams = [match_row["home_team"], match_row["away_team"]]
    events = loader.load_events(mid)
    max_min = int(events["minute"].max())

    c1, c2 = st.columns([1, 2])
    with c1:
        team = st.radio("Team", teams, key="net_team")
    with c2:
        # default the window to the global brush (2.1) if one is active
        tr = state.get_time_range() or (0, max_min)
        default = (max(0, tr[0]), min(max_min, tr[1]))
        window = st.slider("Minute window", 0, max_min, default, key="net_window")

    passes = transforms.get_passes(events)
    passes = passes[(passes["team"] == team) & passes["minute"].between(window[0], window[1])]
    nodes, edges = network_metrics.build_network(passes, min_pair=2)

    if nodes.empty:
        st.warning(f"Not enough completed passes for {team} in minutes {window[0]}–{window[1]}.")
        return

    st.plotly_chart(build_network_figure(nodes, edges), width="stretch", key="net_fig")

    key = nodes.loc[nodes["betweenness"].idxmax(), "player"]
    st.caption(
        f"{team} passing network, minutes {window[0]}–{window[1]} "
        f"({int(passes['completed'].sum())} completed passes). Node size = passes made, "
        f"colour = betweenness centrality. Key connector: **{key}**."
    )


# --- 2.4 Shot Map + 360 Freeze-Frames --------------------------------------

def build_shot_map_figure(shots: pd.DataFrame, colors: dict) -> go.Figure:
    """Half-pitch shot map: position = location, size = xG, colour = outcome."""
    fig = get_pitch_figure(half=True, height=560)
    if shots.empty:
        return fig
    for outcome, grp in shots.groupby("shot_outcome"):
        fig.add_trace(go.Scatter(
            x=grp["x"], y=grp["y"], mode="markers", name=str(outcome),
            marker=dict(
                size=8 + 34 * grp["xg"], sizemode="diameter",
                color=styling.outcome_color(outcome),
                symbol=["star" if g else "circle" for g in (grp["shot_outcome"] == "Goal")],
                line=dict(color="#0e1117", width=1), opacity=0.85),
            customdata=np.stack([grp["id"], grp["player"].fillna("—"), grp["xg"],
                                 grp["minute"]], axis=-1),
            hovertemplate="<b>%{customdata[1]}</b><br>min %{customdata[3]:.0f} · xG %{customdata[2]:.2f}<br>"
                          f"{outcome}<extra></extra>",
        ))
    return fig


def build_freeze_frame_figure(frame: pd.DataFrame, shot_row) -> go.Figure:
    """Render a single shot's 360 freeze-frame: players + shot trajectory."""
    fig = get_pitch_figure(half=True, height=520)
    fx = frame.copy()
    fx["fx"] = fx["location"].apply(lambda v: float(v[0]) if v is not None else None)
    fx["fy"] = fx["location"].apply(lambda v: float(v[1]) if v is not None else None)

    groups = [
        (fx[(fx["teammate"]) & (~fx["keeper"]) & (~fx["actor"])], "Teammates",
         styling.TEAM_COLORS["home"], "circle"),
        (fx[(~fx["teammate"]) & (~fx["keeper"])], "Opponents",
         styling.TEAM_COLORS["away"], "circle"),
        (fx[fx["keeper"]], "Goalkeeper", styling.PALETTE["accent2"], "diamond"),
    ]
    for g, name, col, sym in groups:
        if g.empty:
            continue
        fig.add_trace(go.Scatter(
            x=g["fx"], y=g["fy"], mode="markers", name=name,
            marker=dict(size=12, color=col, symbol=sym, line=dict(color="#0e1117", width=1)),
            hoverinfo="skip", showlegend=True))

    # shooter + shot trajectory
    sx, sy = shot_row["x"], shot_row["y"]
    ex, ey = shot_row["end_x"], shot_row["end_y"]
    fig.add_trace(go.Scatter(
        x=[sx], y=[sy], mode="markers", name="Shooter",
        marker=dict(size=15, color="white", symbol="star", line=dict(color="#0e1117", width=1))))
    if pd.notna(ex) and pd.notna(ey):
        col = styling.outcome_color(shot_row["shot_outcome"])
        fig.add_annotation(x=ex, y=ey, ax=sx, ay=sy, xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=2, arrowwidth=3, arrowcolor=col)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, x=0,
                                                   font=dict(size=9)))
    return fig


def render_shot_map() -> None:
    """Visual 2.4 — Shot Map with linked 360 freeze-frames."""
    st.subheader("Shot Map & 360 Freeze-Frames")
    mid = state.get_match_id()
    if not mid:
        st.info("Pick a **match** in the sidebar to see its shot map.")
        st.caption("Every shot by location (size = xG, colour = outcome); click one for its 360 freeze-frame.")
        return

    match_row = loader.load_matches().set_index("match_id").loc[mid]
    teams = [match_row["home_team"], match_row["away_team"]]
    colors = _team_colors(match_row)
    events = loader.load_events(mid)
    shots = transforms.get_shots(events)
    shots = shots[shots["period"] < 5] if not shots.empty else shots

    f1, f2 = st.columns(2)
    with f1:
        team_sel = st.radio("Team", ["Both", *teams], horizontal=True, key="sm_team")
    with f2:
        body = st.radio("Body part", ["All", "Foot", "Head"], horizontal=True, key="sm_body")
    if team_sel != "Both":
        shots = shots[shots["team"] == team_sel]
    if body != "All":
        parts = {"Left Foot", "Right Foot"} if body == "Foot" else {"Head"}
        shots = shots[shots["shot_body_part"].isin(parts)]

    # apply the global time-window brush from 2.1
    tr = state.get_time_range()
    if tr:
        shots = shots[shots["minute"].between(tr[0], tr[1])]

    if shots.empty:
        st.warning("No shots match these filters.")
        st.caption("Every shot by location (size = xG, colour = outcome); click one for its 360 freeze-frame.")
        return

    left, right = st.columns([3, 2])
    with left:
        event = st.plotly_chart(build_shot_map_figure(shots, colors), width="stretch",
                                key="shotmap_fig", on_select="rerun", selection_mode="points")
        points = (event.get("selection", {}) or {}).get("points", []) if event else []
        if points:
            sid = points[0].get("customdata", [None])[0]
            if sid:
                st.session_state["sel_shot_id"] = sid
                st.rerun()

    # default to the highest-xG shot if none picked
    sel_id = st.session_state.get("sel_shot_id")
    if sel_id not in set(shots["id"]):
        sel_id = shots.loc[shots["xg"].idxmax(), "id"]
    shot_row = shots[shots["id"] == sel_id].iloc[0]

    with right:
        frame = loader.load_360(mid)
        frame = frame[frame["id"] == sel_id] if not frame.empty else frame
        if frame.empty:
            st.info("No 360 freeze-frame available for this shot.")
        else:
            st.plotly_chart(build_freeze_frame_figure(frame, shot_row), width="stretch",
                            key="freeze_fig")
        st.caption(f"**{shot_row['player']}** · min {int(shot_row['minute'])} · "
                   f"xG {shot_row['xg']:.2f} · {shot_row['shot_outcome']}")

    st.caption(
        f"{len(shots)} shots shown. Marker size = xG, colour = outcome, ★ = goal. "
        "Click a shot to load its 360 freeze-frame (white ★ shooter, amber ◆ keeper)."
        + (f" Time filter {tr[0]}–{tr[1]}′ active." if tr else "")
    )


def render() -> None:
    """Streamlit entry for Tab 2 — Match Analysis."""
    render_momentum()
    st.divider()
    render_passing_network()
    st.divider()
    render_shot_map()
