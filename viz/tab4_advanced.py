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

from analytics import pitch_control, xt_model
from data import loader, transforms
from utils import state, styling
from viz.pitch import get_pitch_figure, PITCH_LENGTH, PITCH_WIDTH


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


# --- 4.2 Expected Threat (xT) Surface + Possession Replay ------------------

@st.cache_data(show_spinner="Fitting xT model …")
def _fit_surface() -> np.ndarray:
    ev = loader.load_all_events(columns=[
        "type", "location", "pass_end_location", "carry_end_location",
        "pass_outcome", "shot_outcome"])
    return xt_model.fit_xt(ev)


def _xt_base_figure(surface: np.ndarray) -> go.Figure:
    """xT heatmap with pitch lines drawn on top for context."""
    cx = [xt_model.CELL_W * (i + 0.5) for i in range(xt_model.GRID_X)]
    cy = [xt_model.CELL_H * (j + 0.5) for j in range(xt_model.GRID_Y)]
    fig = go.Figure(go.Heatmap(
        z=surface, x=cx, y=cy, colorscale="Viridis", zsmooth="best", opacity=0.9,
        colorbar=dict(title="xT", thickness=12),
        hovertemplate="x %{x:.0f}, y %{y:.0f}<br>xT %{z:.3f}<extra></extra>"))

    L, W, line = PITCH_LENGTH, PITCH_WIDTH, "rgba(255,255,255,0.6)"
    box = dict(mode="lines", line=dict(color=line, width=1.5), hoverinfo="skip", showlegend=False)
    for seg in ([[0, L, L, 0, 0], [0, 0, W, W, 0]],            # outline
                [[L/2, L/2], [0, W]],                            # halfway
                [[0, 18, 18, 0], [18, 18, 62, 62]],             # left box
                [[L, L-18, L-18, L], [18, 18, 62, 62]]):        # right box
        fig.add_trace(go.Scatter(x=seg[0], y=seg[1], **box))

    fig.update_xaxes(range=[0, L], visible=False, constrain="domain")
    fig.update_yaxes(range=[W, 0], visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor=styling.PALETTE["bg"], font=dict(color=styling.PALETTE["text"]))
    return fig


def add_possession_replay(fig: go.Figure, surface: np.ndarray, coords: list) -> go.Figure:
    """Overlay an animated growing polyline of a possession with running xT added."""
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    xt_vals = [xt_model.xt_at(surface, x, y) for x, y in coords]
    cum = np.cumsum([0.0] + [max(0.0, xt_vals[k] - xt_vals[k - 1]) for k in range(1, len(coords))])

    # the possession trace is appended last; frames update only this trace index
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name="Possession",
                             line=dict(color="#ff5d73", width=3),
                             marker=dict(size=8, color="white", line=dict(color="#ff5d73", width=1))))
    poss_idx = len(fig.data) - 1

    frames = []
    for k in range(1, len(coords) + 1):
        frames.append(go.Frame(
            name=f"p{k}", traces=[poss_idx],
            data=[go.Scatter(x=xs[:k], y=ys[:k], mode="lines+markers",
                             line=dict(color="#ff5d73", width=3),
                             marker=dict(size=8, color="white", line=dict(color="#ff5d73", width=1)))],
            layout=go.Layout(annotations=[dict(
                x=0.5, y=1.06, xref="paper", yref="paper", showarrow=False,
                text=f"xT added: <b>{cum[k-1]:+.3f}</b>",
                font=dict(size=14, color=styling.PALETTE["accent"]))])))
    fig.frames = frames
    fig.update_layout(
        updatemenus=[dict(type="buttons", x=0.02, y=1.12, xanchor="left", direction="left",
                          buttons=[dict(label="▶ Replay", method="animate",
                                        args=[None, dict(frame=dict(duration=500, redraw=True),
                                                         fromcurrent=True)])])],
        annotations=[dict(x=0.5, y=1.06, xref="paper", yref="paper", showarrow=False,
                          text=f"xT added: <b>{cum[-1]:+.3f}</b>",
                          font=dict(size=14, color=styling.PALETTE["accent"]))])
    return fig, float(cum[-1])


def render_xt() -> None:
    """Visual 4.2 — xT surface + possession replay."""
    st.subheader("Expected Threat (xT) Surface")
    surface = _fit_surface()
    mid = state.get_match_id()

    if not mid:
        st.plotly_chart(_xt_base_figure(surface), width="stretch", key="xt_fig")
        st.caption("Each cell's value is the goal probability of having the ball there "
                   "(Markov-chain xT). Pick a match to replay a possession over the surface.")
        return

    poss = transforms.get_possessions(loader.load_events(mid))
    chains = poss[poss["ends_in_shot"]].copy()
    chains = chains[chains["coords"].apply(len) >= 3]
    if chains.empty:
        st.plotly_chart(_xt_base_figure(surface), width="stretch", key="xt_fig")
        st.caption("Markov-chain xT surface. No multi-touch shot-ending possessions to replay in this match.")
        return

    chains["label"] = chains.apply(
        lambda r: f"min {int(r['start_minute'])} — {r['possession_team']}"
                  f"{' ⚽ GOAL' if r['ends_in_goal'] else ' (shot)'} · {len(r['coords'])} touches", axis=1)
    choice = st.selectbox("Possession (shot-ending chains)", chains["label"].tolist(), key="xt_poss")
    coords = chains[chains["label"] == choice].iloc[0]["coords"]

    fig = _xt_base_figure(surface)
    fig, total = add_possession_replay(fig, surface, coords)
    st.plotly_chart(fig, width="stretch", key="xt_fig")
    st.caption(
        f"xT surface (Markov-chain, fitted on all tournament passes & carries). "
        f"Selected possession added **{total:+.3f}** xT over {len(coords)} touches — "
        "press ▶ Replay to animate the chain. Hover any cell for its xT value."
    )


def render() -> None:
    """Streamlit entry for Tab 4 — Advanced Tactical Analysis."""
    render_pitch_control()
    st.divider()
    render_xt()
