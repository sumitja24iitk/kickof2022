# Project Proposal — CS661

## Stories from FIFA World Cup 2022: An Interactive Visual Analytics System

**Contributor:** Sole developer, with Claude Code as coding assistant
**Course:** CS661 — Visual Analytics
**Submission:** HelloIITK

---

### 1. Domain

Football (association football) tournament analysis using **spatial + event data**.
Modern match data captures not just outcomes (goals, passes) but the precise pitch
location of every action and, via StatsBomb's 360 product, the positions of all
visible players at key moments. This richness makes the sport an ideal domain for
visual analytics: the same dataset supports tournament-level storytelling, single-match
tactical breakdowns, individual player profiling, and spatial-control modelling.

### 2. Data source

**StatsBomb Open Data — FIFA World Cup 2022** (`competition_id=43`, `season_id=106`),
accessed through the official `statsbombpy` client and cached locally as parquet.

| Table | Size | Contents |
|-------|------|----------|
| matches | 64 rows | fixtures, scores, stages, teams |
| events | 234,637 rows × 114 cols | every on-ball action (passes, shots, carries, …) with xG and pitch coordinates |
| 360 frames | ~3.0M rows | positions of all visible players at tracked events |

Coordinates use the StatsBomb 120×80 pitch. Every shot carries an `xG` value; the 360
data enables pitch-control and freeze-frame analysis that most projects omit. One match
lacks 360 data and is handled with an explicit fallback.

### 3. Analytical tasks (the 12 visualizations)

The system is organised as a four-tab web app, drilling from broad to specific.

**Tab 1 — Tournament Overview**
1. Interactive knockout bracket (navigation spine; click a match to inspect it)
2. xG vs Goals team-efficiency scatter (finishing quality vs a y=x reference)

**Tab 2 — Match Analysis**
3. Match momentum — cumulative xG timeline with goal/card/sub markers
4. Animated time-scrubber — ball and 360 players replayed on the pitch
5. Passing network — players at average position, edges by volume, nodes by betweenness centrality
6. Shot map + 360 freeze-frames — every shot, linked to its tracked player snapshot

**Tab 3 — Player Spotlight**
7. Action-density heatmap — a player's operating zones
8. Progressive pass & carry map — ball advancement toward goal
9. 3D shot trajectories — shots arcing toward the goal frame
10. Goalmouth placement — where shots finished in the goal plane

**Tab 4 — Advanced Tactical Analysis**
11. Voronoi pitch control — spatial dominance at key moments (scipy + shapely)
12. Expected Threat (xT) surface + possession replay — Markov-chain threat model with animated chains

The tabs are **coordinated**: clicking a bracket match opens the Match tab; clicking a
team opens the Player tab; brushing a time window on the momentum chart filters the shot
map, passing network, and scrubber. State is shared through `st.session_state`.

### 4. Architecture

A Streamlit single-page web application with a layered codebase:

- **Data layer** — cached `statsbombpy`/parquet loaders and pure-pandas transforms.
- **Analytics layer** — Expected Threat, Voronoi pitch control, passing-network
  centrality, and progression filters.
- **Visualization layer** — Plotly for all charts (2D, 3D, animation, selection events);
  `mplsoccer`-style pitch geometry rendered as a reusable Plotly background; `networkx`
  for centrality; `scipy.spatial` + `shapely` for spatial geometry.
- **App shell** — session-state-driven tab navigation and global team/match/player filters.

**Rendering:** Plotly + custom pitch geometry. **Analytics:** scipy / networkx / numpy.
No external BI tools (Tableau / PowerBI / Superset), databases, or web frameworks beyond
Streamlit, per course rules.

### 5. Deliverables

- Interactive Streamlit application (12 coordinated visualizations).
- Reproducible setup: `requirements.txt`, one-command data fetch, README.
- Public GitHub repository, clonable and runnable end-to-end.
