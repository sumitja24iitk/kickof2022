"""
utils/styling.py — shared colour palette + CSS injection.

One import gives every visual the same colours, and one call to inject_css()
gives the app a consistent, non-default "web app" feel (dark pitch-green theme,
Streamlit chrome hidden). Keep all colour decisions here so the 12 visuals stay
visually coherent.
"""

from __future__ import annotations

import streamlit as st

# --- palette ----------------------------------------------------------------

PALETTE = {
    "bg": "#0e1117",
    "panel": "#161b22",
    "pitch": "#1b6b3a",        # pitch green
    "pitch_line": "#e9eef2",
    "text": "#e9eef2",
    "muted": "#8b98a5",
    "accent": "#00c2ff",       # primary accent / highlight
    "accent2": "#ffb703",      # secondary accent
}

# Two team colours for home/away within a single match view.
TEAM_COLORS = {
    "home": "#00c2ff",
    "away": "#ff5d73",
}

# Shot-outcome colours, reused by the shot map (2.4), goalmouth (3.4) and 3D (3.3).
OUTCOME_COLORS = {
    "Goal": "#2ecc71",
    "Saved": "#3498db",
    "Off T": "#e74c3c",
    "Blocked": "#f39c12",
    "Wayward": "#9b59b6",
    "Post": "#e67e22",
    "Saved Off Target": "#1abc9c",
    "Saved to Post": "#16a085",
}

# Sequential scale for heatmaps / xT surface.
SEQUENTIAL_SCALE = "Viridis"


def outcome_color(outcome: str | None) -> str:
    """Colour for a shot outcome, falling back to muted grey for unknowns."""
    return OUTCOME_COLORS.get(outcome, PALETTE["muted"])


# --- CSS injection ----------------------------------------------------------

_CSS = f"""
<style>
    .stApp {{
        background-color: {PALETTE["bg"]};
        color: {PALETTE["text"]};
    }}
    /* Hide Streamlit chrome for a cleaner web-app feel */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header[data-testid="stHeader"] {{background: transparent;}}

    section[data-testid="stSidebar"] {{
        background-color: {PALETTE["panel"]};
        border-right: 1px solid #232a33;
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: {PALETTE["panel"]};
        border-radius: 8px 8px 0 0;
        padding: 8px 18px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {PALETTE["pitch"]};
        color: #ffffff;
    }}

    h1, h2, h3 {{ color: {PALETTE["text"]}; }}
    .stCaption, .st-emotion-cache-1 caption {{ color: {PALETTE["muted"]}; }}
</style>
"""


def inject_css() -> None:
    """Apply the global stylesheet. Call once near the top of app.py."""
    st.markdown(_CSS, unsafe_allow_html=True)
