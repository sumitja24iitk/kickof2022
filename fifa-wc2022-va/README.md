# Stories from FIFA World Cup 2022 — Interactive Visual Analytics

CS661 course project. An interactive web app that tells the story of the 2022 FIFA
World Cup through **12 coordinated visualizations**, built on StatsBomb open data —
including the 360 freeze-frame dataset. Drill from tournament-wide trends down to a
single shot's tactical context.

Stack: **Streamlit · Plotly · statsbombpy · mplsoccer · scipy · networkx · shapely · pandas**

---

## Quick start

```bash
# 1. create + activate a virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell: .\.venv\Scripts\Activate.ps1)
# source .venv/bin/activate       # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt

# 3. fetch the data once (~5–10 min; writes parquet snapshots to data/cache/)
python scripts/fetch_data.py

# 4. run the app
streamlit run app.py
```

Open the printed `Local URL` (default http://localhost:8501). First load builds caches
(~a few seconds); afterwards everything is instant. Use the sidebar's **Refresh data**
button to clear caches.

> The data files in `data/cache/*.parquet` are **gitignored** — run step 3 after cloning.

---

## The 12 visualizations

| Tab | # | Visualization | What it shows |
|-----|---|---------------|---------------|
| **Tournament** | 1.1 | Interactive Knockout Bracket | R16→Final structure with scores; click a match to jump to the Match tab |
| | 1.2 | xG vs Goals Scatter | Team finishing efficiency vs a y=x line; click a team → Player tab |
| **Match** | 2.1 | Match Momentum | Cumulative xG timeline; box-select brushes a minute window (linking hub) |
| | 2.2 | Animated Time-Scrubber | Ball + 360 players animated through the match (Plotly frames) |
| | 2.3 | Passing Network | Players at avg position; edge = pass volume, colour = betweenness centrality |
| | 2.4 | Shot Map + 360 | Every shot (size=xG, colour=outcome); click → 360 freeze-frame panel |
| **Player** | 3.1 | Action Density Heatmap | Where a player operates (action-type + scope toggles) |
| | 3.2 | Progressive Pass & Carry Map | Passes/carries that moved the ball ≥25% closer to goal |
| | 3.3 | 3D Shot Trajectories | Player's shots arcing toward goal in 3D |
| | 3.4 | Goalmouth Placement | Shot end-placement in the goal-frame plane |
| **Tactical** | 4.1 | Voronoi Pitch Control | Pitch partitioned by which team controls each zone (scipy + shapely) |
| | 4.2 | xT Surface + Possession Replay | Markov-chain Expected Threat grid; animate a possession's xT gain |

Cross-tab links: **bracket → Match**, **team scatter → Player**, **momentum brush → shot
map / passing network / scrubber** (all share `session_state`).

---

## Architecture

Four horizontal layers — each file has a single responsibility.

```
fifa-wc2022-va/
├── app.py                  # entry: page config, sidebar filters, session-state tab nav
├── data/
│   ├── loader.py           # cached parquet loaders (matches / events / 360)
│   ├── transforms.py       # event → shots / passes / carries / possessions
│   └── cache/              # parquet snapshots (gitignored)
├── analytics/
│   ├── xt_model.py         # Expected Threat (Markov-chain value iteration)
│   ├── pitch_control.py    # Voronoi cells + pitch clipping
│   ├── network_metrics.py  # passing-network builder + betweenness
│   └── progression.py      # progressive pass / carry filters
├── viz/
│   ├── pitch.py            # reusable StatsBomb pitch (Plotly) — used by 7 visuals
│   ├── tab1_tournament.py  # 1.1, 1.2
│   ├── tab2_match.py       # 2.1–2.4
│   ├── tab3_player.py      # 3.1–3.4
│   └── tab4_advanced.py    # 4.1, 4.2
├── utils/
│   ├── state.py            # session_state keys + get_filtered_events()
│   └── styling.py          # palette + CSS injection
├── SCHEMA.md               # StatsBomb data dictionary
└── scripts/fetch_data.py   # one-time data download
```

## Data source

StatsBomb Open Data — FIFA World Cup 2022 (`competition_id=43`, `season_id=106`):
64 matches, 234,637 events, ~3M 360 freeze-frame rows. See [SCHEMA.md](SCHEMA.md) for
the full column dictionary. (One match, `3869152`, has no 360 data — handled with a
graceful fallback.)

## Notes

- Pitch coordinates are StatsBomb 120×80; attacking goal at x=120.
- xT uses the turnover-free Markov model (relative threat surface).
- Built solo with Claude Code as coding assistant.
