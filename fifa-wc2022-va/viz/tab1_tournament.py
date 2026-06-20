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


# --- 1.1 Interactive Knockout Bracket --------------------------------------

STAGE_ORDER = ["Round of 16", "Quarter-finals", "Semi-finals", "Final"]
STAGE_HEADERS = ["Round of 16", "Quarter-finals", "Semi-finals", "Final"]


def _teams(row: dict) -> set[str]:
    return {row["home_team"], row["away_team"]}


@st.cache_data(show_spinner=False)
def _knockout_scorers() -> dict[int, str]:
    """match_id -> '<br>'-joined goalscorer list (open play + ET), for hover."""
    ev = loader.load_all_events(
        columns=["type", "shot_outcome", "player", "team", "minute", "match_id", "period"]
    )
    goals = ev[(ev["type"] == "Shot") & (ev["shot_outcome"] == "Goal") & (ev["period"] < 5)]
    out: dict[int, str] = {}
    for mid, g in goals.groupby("match_id"):
        lines = [f"{r.player} {int(r.minute)}'" for r in g.sort_values("minute").itertuples()]
        out[int(mid)] = "<br>".join(lines) if lines else "—"
    return out


def build_bracket_layout(matches: pd.DataFrame):
    """Return (ko_df, pos{match_id:(x,y)}, edges[((x0,y0),(x1,y1))])."""
    ko = matches[matches["competition_stage"].isin(STAGE_ORDER + ["3rd Place Final"])]
    by_stage = {s: ko[ko["competition_stage"] == s].to_dict("records") for s in STAGE_ORDER}
    third = ko[ko["competition_stage"] == "3rd Place Final"].to_dict("records")
    levels = [by_stage[s] for s in STAGE_ORDER]  # index 0=R16 ... 3=Final
    final = by_stage["Final"][0]

    def feeders(match: dict, prev: list[dict]) -> list[dict]:
        f = [pm for pm in prev if _teams(pm) & _teams(match)]
        f.sort(key=lambda pm: 0 if match["home_team"] in _teams(pm) else 1)
        return f

    def order_leaves(match: dict, level: int) -> list[dict]:
        if level == 0:
            return [match]
        res: list[dict] = []
        for fdr in feeders(match, levels[level - 1]):
            res += order_leaves(fdr, level - 1)
        return res

    leaves = order_leaves(final, 3)
    n = len(leaves)
    pos: dict[int, tuple[float, float]] = {}
    placed: set[int] = set()
    for i, lf in enumerate(leaves):
        pos[int(lf["match_id"])] = (0.0, float(n - 1 - i))
        placed.add(int(lf["match_id"]))

    edges: list[tuple] = []

    def place(match: dict, level: int):
        mid = int(match["match_id"])
        if mid in placed:
            return pos[mid]
        fdrs = feeders(match, levels[level - 1])
        cps = [place(f, level - 1) for f in fdrs]
        xy = (float(level), sum(p[1] for p in cps) / len(cps))
        pos[mid] = xy
        placed.add(mid)
        for cp in cps:
            edges.append((cp, xy))
        return xy

    place(final, 3)

    if third:
        t = third[0]
        tpos = (3.0, -1.5)
        pos[int(t["match_id"])] = tpos
        for s in by_stage["Semi-finals"]:
            edges.append((pos[int(s["match_id"])], tpos))

    return ko, pos, edges


def build_bracket_figure(ko: pd.DataFrame, pos: dict, edges: list) -> go.Figure:
    fig = go.Figure()
    scorers = _knockout_scorers()

    # connector lines (behind)
    for (x0, y0), (x1, y1) in edges:
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines",
            line=dict(color=styling.PALETTE["muted"], width=1),
            hoverinfo="skip", showlegend=False,
        ))

    # match boxes as annotations + a clickable scatter point per box
    xs, ys, cd, hover = [], [], [], []
    for r in ko.itertuples():
        mid = int(r.match_id)
        x, y = pos[mid]
        label = f"{r.home_team} {int(r.home_score)}–{int(r.away_score)} {r.away_team}"
        fig.add_annotation(
            x=x, y=y, text=label, showarrow=False, font=dict(size=10, color=styling.PALETTE["text"]),
            bgcolor=styling.PALETTE["panel"], bordercolor=styling.PALETTE["muted"], borderwidth=1,
            borderpad=4, xanchor="center", yanchor="middle",
        )
        xs.append(x); ys.append(y); cd.append(mid)
        hover.append(f"<b>{label}</b><br>{r.competition_stage} · {r.match_date}<br><br>"
                     f"{scorers.get(mid, '—')}")

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", marker=dict(size=46, color="rgba(0,0,0,0)"),
        customdata=cd, hovertext=hover, hoverinfo="text", showlegend=False,
    ))

    # stage headers
    for i, h in enumerate(STAGE_HEADERS):
        fig.add_annotation(x=i, y=7.6, text=f"<b>{h}</b>", showarrow=False,
                           font=dict(size=12, color=styling.PALETTE["accent"]))
    fig.add_annotation(x=3, y=-0.7, text="<i>3rd place</i>", showarrow=False,
                       font=dict(size=9, color=styling.PALETTE["muted"]))

    fig.update_layout(
        height=560, margin=dict(l=10, r=10, t=20, b=10),
        plot_bgcolor=styling.PALETTE["bg"], paper_bgcolor=styling.PALETTE["bg"],
        xaxis=dict(visible=False, range=[-0.5, 3.5]),
        yaxis=dict(visible=False, range=[-2.5, 8.2]),
    )
    return fig


def render_bracket() -> None:
    """Visual 1.1 — Interactive Knockout Bracket (navigation spine)."""
    st.subheader("Knockout Bracket")
    matches = loader.load_matches()
    ko, pos, edges = build_bracket_layout(matches)
    fig = build_bracket_figure(ko, pos, edges)

    event = st.plotly_chart(fig, width="stretch", key="bracket_fig",
                            on_select="rerun", selection_mode="points")
    points = (event.get("selection", {}) or {}).get("points", []) if event else []
    if points:
        mid = points[0].get("customdata")
        if mid and mid != state.get_match_id():
            state.set_match_id(int(mid))
            st.rerun()

    if state.get_match_id():
        row = matches.set_index("match_id").loc[state.get_match_id()]
        st.success(f"Selected **{row.home_team} v {row.away_team}** — open the **Match** tab to dive in.")
    st.caption(
        "Full Round-of-16 → Final bracket with scores. Click any match to load it into the "
        "Match tab; hover for goalscorers and date."
    )


def render_xg_scatter() -> None:
    """Visual 1.2 — xG vs Goals efficiency scatter. Click a point to filter Tab 3 by team."""
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


def render() -> None:
    """Streamlit entry for Tab 1 — Tournament Overview."""
    render_bracket()
    st.divider()
    render_xg_scatter()
