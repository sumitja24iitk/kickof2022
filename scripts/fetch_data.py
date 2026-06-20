"""
Fetch StatsBomb open data for FIFA World Cup 2022 and save to data/cache/.
Usage:
    python scripts/fetch_data.py          # skips files that already exist
    python scripts/fetch_data.py --force  # re-downloads everything
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
from statsbombpy import sb
from statsbombpy import public as sb_public

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
COMPETITION_ID = 43
SEASON_ID = 106


def safe_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write df to parquet, JSON-stringifying any column that fails to serialize."""
    problem_cols = []
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
        tmp_path = tmp.name
    for col in df.columns:
        try:
            df[[col]].to_parquet(tmp_path, index=False)
        except Exception:
            problem_cols.append(col)

    if problem_cols:
        df = df.copy()
        for col in problem_cols:
            print(f"  [warn] column '{col}' not parquet-serializable — converting to JSON string")
            df[col] = df[col].apply(lambda v: json.dumps(v) if v is not None else None)

    df.to_parquet(path, index=False)


def fetch_matches(force: bool) -> pd.DataFrame:
    path = CACHE_DIR / "matches.parquet"
    if path.exists() and not force:
        print(f"[skip] {path.name} already exists (use --force to re-download)")
        return pd.read_parquet(path)

    print("Fetching matches …")
    df = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    safe_parquet(df, path)
    print(f"[done] matches.parquet — shape {df.shape}")
    return df


def fetch_events(match_ids: list[int], force: bool) -> pd.DataFrame:
    path = CACHE_DIR / "events.parquet"
    if path.exists() and not force:
        print(f"[skip] {path.name} already exists (use --force to re-download)")
        return pd.read_parquet(path)

    print(f"Fetching events for {len(match_ids)} matches …")
    chunks = []
    for i, mid in enumerate(match_ids, 1):
        df = sb.events(match_id=mid)
        df["match_id"] = mid
        chunks.append(df)
        if i % 8 == 0 or i == len(match_ids):
            print(f"  … {i}/{len(match_ids)} matches fetched")

    combined = pd.concat(chunks, ignore_index=True)
    safe_parquet(combined, path)
    print(f"[done] events.parquet — shape {combined.shape}")
    return combined


def _frames_compat(match_id: int) -> pd.DataFrame:
    """
    Replacement for sb.frames() that works with pandas 3.x.
    sb.frames() uses pd.concat(axis=1) on a non-unique index after explode(),
    which raises InvalidIndexError in pandas >= 2.0 strict mode.
    """
    raw = sb_public.frames(match_id)  # list of dicts
    if not raw:
        return pd.DataFrame()

    keys = ["event_uuid", "visible_area", "match_id", "freeze_frame"]
    trimmed = [{k: r[k] for k in keys if k in r} for r in raw]

    base = pd.DataFrame(trimmed).explode("freeze_frame").reset_index(drop=True)
    ff_expanded = pd.json_normalize(base["freeze_frame"].tolist())
    result = pd.concat(
        [base.drop("freeze_frame", axis=1).reset_index(drop=True), ff_expanded],
        axis=1,
    )
    return result.rename(columns={"event_uuid": "id"})


def fetch_frames(match_ids: list[int], force: bool) -> pd.DataFrame:
    path = CACHE_DIR / "frames_360.parquet"
    if path.exists() and not force:
        print(f"[skip] {path.name} already exists (use --force to re-download)")
        return pd.read_parquet(path)

    print(f"Fetching 360 frames for {len(match_ids)} matches …")
    chunks = []
    failed = []
    for mid in match_ids:
        try:
            df = _frames_compat(mid)
            if df is not None and not df.empty:
                df["match_id"] = mid
                chunks.append(df)
        except Exception as exc:
            print(f"  [warn] match_id={mid} has no 360 data — {exc}")
            failed.append(mid)

    if failed:
        print(f"  [info] {len(failed)} match(es) with no 360 data: {failed}")

    combined = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    safe_parquet(combined, path)
    print(f"[done] frames_360.parquet — shape {combined.shape}")
    return combined


def main():
    parser = argparse.ArgumentParser(description="Fetch WC 2022 StatsBomb data")
    parser.add_argument("--force", action="store_true", help="Re-download even if files exist")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    matches = fetch_matches(args.force)
    match_ids = matches["match_id"].tolist()

    fetch_events(match_ids, args.force)
    fetch_frames(match_ids, args.force)

    print("\nAll done. Files in data/cache/:")
    for f in sorted(CACHE_DIR.glob("*.parquet")):
        print(f"  {f.name}  ({f.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
