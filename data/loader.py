"""
data/loader.py — cached parquet loaders for the WC 2022 StatsBomb snapshot.

All data lives in data/cache/*.parquet (produced by scripts/fetch_data.py).
Every loader is wrapped in @st.cache_data so the first load (~a few seconds for
the 3M-row 360 table) is paid once per session and subsequent calls are instant.

Schema reference: SCHEMA.md. Key facts honoured here:
  - events is the flattened table (shot_statsbomb_xg, pass_recipient, ...).
  - location / *_end_location columns are numpy arrays of [x, y] (0-120 x 0-80).
  - frames_360 joins to events on  frames_360.id == events.id.
  - matches.match_id is the primary key linking all three tables.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

CACHE_DIR = Path(__file__).parent / "cache"

MATCHES_PARQUET = CACHE_DIR / "matches.parquet"
EVENTS_PARQUET = CACHE_DIR / "events.parquet"
FRAMES_PARQUET = CACHE_DIR / "frames_360.parquet"


def _require(path: Path) -> Path:
    """Fail loudly with an actionable message if the cache is missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing data file: {path}\n"
            "Run the fetch script first:  python scripts/fetch_data.py"
        )
    return path


@st.cache_data(show_spinner="Loading matches …")
def load_matches() -> pd.DataFrame:
    """All 64 WC 2022 matches, one row each. Sorted by date then match_id."""
    df = pd.read_parquet(_require(MATCHES_PARQUET))
    sort_cols = [c for c in ("match_date", "match_id") if c in df.columns]
    return df.sort_values(sort_cols).reset_index(drop=True)


@st.cache_data(show_spinner="Loading events …")
def load_events(match_id: int) -> pd.DataFrame:
    """
    Events for a single match, ordered by their in-match index.

    Reads only the rows for `match_id` via a parquet predicate pushdown, so this
    stays cheap even though events.parquet holds 234k rows across all matches.
    """
    df = pd.read_parquet(
        _require(EVENTS_PARQUET),
        filters=[("match_id", "==", int(match_id))],
    )
    if "index" in df.columns:
        df = df.sort_values("index")
    return df.reset_index(drop=True)


@st.cache_data(show_spinner="Loading all events …")
def load_all_events(columns: list[str] | None = None) -> pd.DataFrame:
    """
    Every event across all 64 matches (234,637 rows x 114 cols).

    Used by tournament-wide visuals (xG scatter, xT model fitting). Pass
    `columns` to read just the columns you need — a big speed/memory win for
    aggregations that only touch a handful of fields.
    """
    df = pd.read_parquet(_require(EVENTS_PARQUET), columns=columns)
    return df.reset_index(drop=True)


@st.cache_data(show_spinner="Loading 360 frames …")
def load_360(match_id: int) -> pd.DataFrame:
    """
    StatsBomb 360 freeze-frame rows for a single match (one row per visible
    player per event). Join to events on id. Empty frame if the match has no
    360 data — callers should handle that as a "no 360 data" fallback.
    """
    df = pd.read_parquet(
        _require(FRAMES_PARQUET),
        filters=[("match_id", "==", int(match_id))],
    )
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def has_360(match_id: int) -> bool:
    """True if any 360 freeze-frame rows exist for this match."""
    return not load_360(match_id).empty


def clear_cache() -> None:
    """Drop every cached loader result. Wired to the sidebar 'Refresh data' button."""
    st.cache_data.clear()
