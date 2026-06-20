"""
app.py — Streamlit entry point: page config, styling, global sidebar filters,
and the tab router. Individual visuals live in viz/tabN_*.py.

Navigation is session-state driven (not st.tabs) so visuals can switch tabs
programmatically — clicking a bracket match jumps to the Match tab, clicking a
team in the xG scatter jumps to the Player tab. Only the active tab renders,
which also keeps reruns fast.
"""

import streamlit as st

from data import loader
from utils import state, styling
from viz import tab1_tournament, tab2_match, tab3_player, tab4_advanced

st.set_page_config(
    page_title="Stories from FIFA WC 2022",
    page_icon="⚽",
    layout="wide",
)

styling.inject_css()
state.init_state()

try:
    matches = loader.load_matches()
except FileNotFoundError as exc:
    st.error("⚠️ Data cache not found.")
    st.code(str(exc))
    st.info("Run the fetch script once, then reload:\n\n```\npython scripts/fetch_data.py\n```")
    st.stop()

TABS = [
    ("Tournament", "🏆 Tournament"),
    ("Match", "📊 Match"),
    ("Player", "👤 Player"),
    ("Tactical", "🎯 Tactical"),
]


def _match_label(row) -> str:
    return (
        f"{row.home_team} {int(row.home_score)}–{int(row.away_score)} {row.away_team}"
        f"  ·  {row.competition_stage}"
    )


def render_sidebar() -> None:
    """Global team / match / player filters, populated from the real data."""
    with st.sidebar:
        st.markdown("### ⚽ WC 2022 Analytics")
        st.caption("Global filters — shared across all tabs")

        teams = sorted(set(matches["home_team"]) | set(matches["away_team"]))
        team_choice = st.selectbox(
            "Team", ["(all)"] + teams,
            index=0 if state.get_team() is None else teams.index(state.get_team()) + 1,
        )
        state.set_team(None if team_choice == "(all)" else team_choice)

        match_pool = matches
        if state.get_team():
            match_pool = matches[
                (matches["home_team"] == state.get_team())
                | (matches["away_team"] == state.get_team())
            ]

        labels = {int(r.match_id): _match_label(r) for r in match_pool.itertuples()}
        ids = list(labels.keys())
        current = state.get_match_id()
        match_index = ids.index(current) + 1 if current in ids else 0

        match_choice = st.selectbox(
            "Match", ["(none)"] + ids,
            index=match_index,
            format_func=lambda mid: "(none)" if mid == "(none)" else labels[mid],
        )
        state.set_match_id(None if match_choice == "(none)" else match_choice)

        players: list[str] = []
        if state.get_match_id():
            ev = loader.load_events(state.get_match_id())
            if state.get_team():
                ev = ev[ev["team"] == state.get_team()]
            players = sorted(ev["player"].dropna().unique().tolist())

        player_choice = st.selectbox(
            "Player",
            ["(all)"] + players,
            index=0,
            disabled=not players,
            help="Pick a match to populate players" if not players else None,
        )
        state.set_player(None if player_choice == "(all)" else player_choice)

        st.divider()
        if st.button("🔄 Refresh data", width="stretch",
                     help="Clear cached parquet loads and reload from disk"):
            loader.clear_cache()
            st.rerun()

        st.caption(f"{len(matches)} matches · StatsBomb open data")


def render_nav() -> None:
    """Button-based tab navigation bound to session_state['active_tab']."""
    cols = st.columns(len(TABS))
    for col, (key, label) in zip(cols, TABS):
        is_active = st.session_state.get("active_tab") == key
        if col.button(label, key=f"nav_{key}", width="stretch",
                      type="primary" if is_active else "secondary"):
            st.session_state["active_tab"] = key
            st.rerun()


render_sidebar()

st.title("Stories from FIFA World Cup 2022")
st.caption("An interactive visual analytics system · CS661 Course Project")

render_nav()
st.divider()

_RENDERERS = {
    "Tournament": tab1_tournament.render,
    "Match": tab2_match.render,
    "Player": tab3_player.render,
    "Tactical": tab4_advanced.render,
}

active = st.session_state.get("active_tab", "Tournament")
try:
    _RENDERERS.get(active, tab1_tournament.render)()
except Exception as exc:  # never white-screen the whole app on one visual's error
    st.error(f"Something went wrong rendering the {active} tab.")
    with st.expander("Error details"):
        st.exception(exc)
