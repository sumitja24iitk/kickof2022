# StatsBomb WC 2022 — Data Schema Reference

> Generated from `notebooks/00_schema_exploration.ipynb` against the three parquet
> files in `data/cache/`. Paste this file into any prompt to give the LLM instant
> context about the data.

---

## matches.parquet

**Shape:** 64 rows × 55 columns (one row per match)

| column | dtype | example value | notes |
|--------|-------|---------------|-------|
| `match_id` | int64 | `3857276` | Primary key; FK into events/frames |
| `match_date` | str | `"2022-12-01"` | ISO date string |
| `kick_off` | str | `"15:00:00.000"` | Local kick-off time |
| `home_score` | int64 | `1` | FT score |
| `away_score` | int64 | `2` | FT score |
| `match_status` | str | `"available"` | StatsBomb data availability flag |
| `match_status_360` | str | `"available"` | 360° data availability flag |
| `match_week` | int64 | `3` | Group-stage week or knockout round ordinal |
| `competition_id` | int64 | `43` | Always 43 for FIFA World Cup |
| `competition_name` | str | `"FIFA World Cup"` | |
| `season_id` | int64 | `106` | Always 106 for WC 2022 |
| `season` | str | `"2022"` | |
| `home_team_id` | int64 | `1833` | StatsBomb team ID |
| `home_team` | str | `"Canada"` | |
| `home_team_gender` | str | `"male"` | |
| `home_team_group` | str | `"Group F"` | Null for knockout matches |
| `away_team_id` | int64 | `782` | |
| `away_team` | str | `"Morocco"` | |
| `competition_stage` | str | `"Group Stage"` | E.g. `"Quarter-finals"`, `"Final"` |
| `stadium` | str | `"Al Thumama Stadium"` | |
| `referee` | str | `"Ismail Elfath"` | |
| `home_manager_name` | str | `"John Herdman"` | |
| `away_manager_name` | str | `"Walid Regragui"` | |
| `data_version` | str | `"1.1.0"` | StatsBomb spec version |

### Sample row (JSON)

```json
{
  "match_id": 3857276,
  "match_date": "2022-12-01",
  "kick_off": "15:00:00.000",
  "home_score": 1,
  "away_score": 2,
  "match_status": "available",
  "match_status_360": "available",
  "match_week": 3,
  "competition_id": 43,
  "competition_name": "FIFA World Cup",
  "season_id": 106,
  "season": "2022",
  "home_team_id": 1833,
  "home_team": "Canada",
  "home_team_group": "Group F",
  "away_team_id": 782,
  "away_team": "Morocco",
  "competition_stage": "Group Stage",
  "stadium": "Al Thumama Stadium",
  "referee": "Ismail Elfath"
}
```

---

## events.parquet (flat columns)

**Shape:** 234,637 rows × 114 columns (one row per event)

> **Key convention:** statsbombpy flattens all nested event sub-dicts using
> underscore separators. There is **no** `shot` dict column — instead you get
> `shot_statsbomb_xg`, `shot_body_part`, `shot_end_location`, etc. as separate
> columns. Non-applicable columns are `NaN` for that row.

### Core columns (always populated)

| column | dtype | example value | notes |
|--------|-------|---------------|-------|
| `id` | str | `"473df22f-d159-4416-a5ce-62838698ea12"` | UUID; FK from frames_360 |
| `index` | int64 | `100` | Sequential event index within match |
| `period` | int64 | `1` | 1=first half, 2=second, 3/4=extra time, 5=penalties |
| `timestamp` | str | `"00:02:05.020"` | Elapsed time within period |
| `minute` | int64 | `2` | Match minute (cumulative) |
| `second` | int64 | `5` | Second within that minute |
| `type` | str | `"Shot"` | Event type label (see type counts below) |
| `possession` | int64 | `6` | Possession sequence number |
| `possession_team` | str | `"Canada"` | Team in possession |
| `possession_team_id` | int64 | `1833` | |
| `play_pattern` | str | `"Regular Play"` | E.g. `"From Corner"`, `"From Free Kick"` |
| `team` | str | `"Canada"` | Team that performed this event |
| `player` | str | `"Mark Anthony Kaye"` | Player name (null for some event types) |
| `player_id` | float64 | `16252.0` | float because nullable |
| `position` | str | `"Left Defensive Midfield"` | Player's listed position |
| `location` | object | `[96.5, 40.7]` | `[x, y]` numpy array; pitch coords 0–120 × 0–80 |
| `duration` | float64 | `0.397304` | Event duration in seconds |
| `related_events` | object | `["uuid1", "uuid2"]` | List of related event UUIDs |
| `tactics` | object | `{"formation": 433, "lineup": [...]}` | Populated only on `Tactics` events |
| `match_id` | int64 | `3857276` | Added by fetch script; FK into matches |

### Event type counts (WC 2022)

| type | count |
|------|-------|
| Pass | 68,515 |
| Ball Receipt* | 63,699 |
| Carry | 53,764 |
| Pressure | 16,554 |
| Ball Recovery | 5,821 |
| Duel | 4,389 |
| Clearance | 2,684 |
| Block | 2,386 |
| Dribble | 1,793 |
| Goal Keeper | 1,790 |
| Foul Committed | 1,775 |
| Miscontrol | 1,755 |
| Foul Won | 1,693 |
| **Shot** | **1,494** |
| Dispossessed | 1,431 |
| Interception | 1,371 |
| Dribbled Past | 1,036 |
| Substitution | 587 |
| Half Start / Half End | 286 each |
| *(+ ~15 other types)* | | |

---

## events.parquet — nested fields (as flat columns)

### shot.*

All `shot_*` columns are non-null only for rows where `type == "Shot"`.
**100% of shot rows have `shot_statsbomb_xg`** (1494/1494 confirmed).

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `shot_statsbomb_xg` | float64 | `0.0389` | Expected goals; always present for shots |
| `shot_end_location` | object | `[104.1, 39.4]` | `[x, y]` or `[x, y, z]` (z = height in metres when aerial) |
| `shot_body_part` | str | `"Left Foot"` | `"Right Foot"`, `"Head"`, `"No Touch"` |
| `shot_outcome` | str | `"Off T"` | `"Goal"`, `"Saved"`, `"Off T"`, `"Blocked"`, `"Wayward"`, `"Post"` |
| `shot_type` | str | `"Open Play"` | `"Free Kick"`, `"Corner"`, `"Penalty"` |
| `shot_technique` | str | `"Normal"` | `"Volley"`, `"Half Volley"`, `"Lob"`, `"Backheel"`, `"Diving Header"` |
| `shot_first_time` | object | `True` | Bool; null if not first-time |
| `shot_aerial_won` | object | `True` | Bool; null if not aerial |
| `shot_one_on_one` | object | `True` | Bool |
| `shot_open_goal` | object | `True` | Bool |
| `shot_follows_dribble` | object | `True` | Bool |
| `shot_key_pass_id` | str | `"uuid"` | UUID of the key pass that created the shot |
| `shot_freeze_frame` | object | `[{...}, ...]` | Array of player-position dicts at moment of shot (see below) |

**`shot_freeze_frame` structure** (one element per visible player):

```json
{
  "location": [108.6, 34.8],
  "player": {"id": 5594, "name": "Hugo Lloris"},
  "position": {"id": 1, "name": "Goalkeeper"},
  "teammate": false
}
```

### pass.*

All `pass_*` columns are non-null only for rows where `type == "Pass"`.

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `pass_recipient` | str | `"Kylian Mbappé"` | Recipient player name |
| `pass_recipient_id` | float64 | `234.0` | |
| `pass_length` | float64 | `14.3` | Pass distance in yards |
| `pass_angle` | float64 | `1.57` | Radians; 0 = right, π/2 = up pitch |
| `pass_height` | str | `"Ground Pass"` | `"Low Pass"`, `"High Pass"` |
| `pass_end_location` | object | `[65.2, 40.1]` | `[x, y]` destination |
| `pass_type` | str | `"Recovery"` | `"Corner"`, `"Free Kick"`, `"Goal Kick"`, `"Kick Off"`, `"Throw-in"` — null for open play |
| `pass_outcome` | str | `"Incomplete"` | Null means **completed**; also `"Out"`, `"Pass Offside"` |
| `pass_body_part` | str | `"Right Foot"` | `"Left Foot"`, `"Head"`, `"No Touch"` |
| `pass_switch` | object | `True` | Bool; switch of play |
| `pass_cross` | object | `True` | Bool |
| `pass_through_ball` | object | `True` | Bool |
| `pass_cut_back` | object | `True` | Bool |
| `pass_aerial_won` | object | `True` | Bool |

### carry.*

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `carry_end_location` | object | `[48.4, 42.5]` | `[x, y]` where carry ended |

### duel.*

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `duel_type` | str | `"Tackle"` | `"Aerial Lost"` |
| `duel_outcome` | str | `"Lost In Play"` | `"Won"`, `"Success In Play"`, `"Lost Out"` |

### dribble.*

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `dribble_outcome` | str | `"Complete"` | `"Incomplete"` |
| `dribble_overrun` | object | `True` | Bool |
| `dribble_nutmeg` | object | `True` | Bool |
| `dribble_no_touch` | object | `True` | Bool |

### goalkeeper.*

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `goalkeeper_type` | str | `"Shot Saved"` | `"Collected"`, `"Punch"`, `"Penalty Saved"` |
| `goalkeeper_outcome` | str | `"Success"` | |
| `goalkeeper_position` | str | `"Diving"` | |
| `goalkeeper_technique` | str | `"Diving"` | |
| `goalkeeper_body_part` | str | `"Right Hand"` | |

### foul_committed.*

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `foul_committed_card` | str | `"Yellow Card"` | `"Red Card"`, `"Second Yellow"` |
| `foul_committed_type` | str | `"Tackle"` | |
| `foul_committed_penalty` | object | `True` | Bool |

### Sample Shot event row (JSON)

```json
{
  "id": "473df22f-d159-4416-a5ce-62838698ea12",
  "index": 100,
  "period": 1,
  "timestamp": "00:02:05.020",
  "minute": 2,
  "second": 5,
  "type": "Shot",
  "location": [96.5, 40.7],
  "duration": 0.397304,
  "player": "Mark Anthony Kaye",
  "player_id": 16252.0,
  "team": "Canada",
  "position": "Left Defensive Midfield",
  "play_pattern": "Regular Play",
  "possession": 6,
  "possession_team": "Canada",
  "possession_team_id": 1833,
  "match_id": 3857276,
  "shot_statsbomb_xg": 0.038882375,
  "shot_body_part": "Left Foot",
  "shot_end_location": [104.1, 39.4],
  "shot_outcome": "Off T",
  "shot_technique": "Normal",
  "shot_type": "Open Play"
}
```

### Sample Pass event row (JSON)

```json
{
  "id": "fa742b13-32df-4dce-8b08-7c6ebb125d5a",
  "index": 7,
  "period": 1,
  "type": "Pass",
  "location": [48.5, 41.3],
  "play_pattern": "Regular Play",
  "match_id": 3857276,
  "pass_length": 14.3,
  "pass_angle": 1.57,
  "pass_height": "Ground Pass",
  "pass_end_location": [65.2, 40.1],
  "pass_body_part": "Right Foot",
  "pass_outcome": null
}
```

---

## frames_360.parquet

**Shape:** 3,084,800 rows × 7 columns

One row per **player entry** per event. A single event UUID appears as many rows
as there are visible players in the freeze frame (typically 12–22 players).
Join to `events.parquet` on `frames_360.id = events.id`.

**Join coverage:** 203,882 unique event UUIDs in frames_360; all 203,882 match a
row in events (100% join success).

| column | dtype | example | notes |
|--------|-------|---------|-------|
| `id` | str | `"05a57281-9295-408a-9c4f-e32d7fad4d96"` | = `event_uuid`; FK to `events.id` |
| `visible_area` | object | `[19.84, 80.0, 47.23, 0.0, ...]` | Flat array of 10 floats: 5 polygon vertices `[x1,y1, x2,y2, ...]` bounding the visible pitch region |
| `match_id` | int64 | `3857276` | FK to `matches.match_id` |
| `teammate` | bool | `true` | True if player is on same team as ball carrier |
| `actor` | bool | `false` | True if this player is the one performing the event |
| `keeper` | bool | `false` | True if this player is a goalkeeper |
| `location` | object | `[30.82, 49.38]` | `[x, y]` player position at moment of event |

### Sample event (3 player rows, JSON)

```json
[
  {
    "id": "05a57281-9295-408a-9c4f-e32d7fad4d96",
    "visible_area": [19.84, 80.0, 47.23, 0.0, 74.20, 0.0, 101.86, 80.0, 19.84, 80.0],
    "match_id": 3857276,
    "teammate": true,
    "actor": false,
    "keeper": false,
    "location": [30.82, 49.38]
  },
  {
    "id": "05a57281-9295-408a-9c4f-e32d7fad4d96",
    "visible_area": [19.84, 80.0, 47.23, 0.0, 74.20, 0.0, 101.86, 80.0, 19.84, 80.0],
    "match_id": 3857276,
    "teammate": true,
    "actor": false,
    "keeper": false,
    "location": [38.59, 65.06]
  },
  {
    "id": "05a57281-9295-408a-9c4f-e32d7fad4d96",
    "visible_area": [19.84, 80.0, 47.23, 0.0, 74.20, 0.0, 101.86, 80.0, 19.84, 80.0],
    "match_id": 3857276,
    "teammate": false,
    "actor": true,
    "keeper": false,
    "location": [48.38, 39.36]
  }
]
```

---

## Pitch coordinate system

StatsBomb uses a **120 × 80** pitch (length × width, in yards).

- Origin `(0, 0)` is the **top-left corner** from the attacking team's perspective.
- `x` increases left → right (toward the opposing goal).
- `y` increases top → bottom.
- The **attacking goal** is at `x = 120`; goal mouth spans `y ≈ 36–44`.
- The **defending goal** is at `x = 0`; goal mouth spans `y ≈ 36–44`.

**Confirmed from data:**

| measure | observed |
|---------|----------|
| x range (all events) | 0.1 – 120.0 |
| y range (all events) | 0.1 – 80.0 |
| Shot x range | 59.0 – 120.0 |
| Shot x median | 106.4 |

Shot x values cluster above 100, confirming goals are at `x = 120`.

---

## Useful invariants

- **One row per event** in `events.parquet`. Total: 234,637 events across 64 matches.
- **Every shot has `shot_statsbomb_xg`** — 100% coverage (1494/1494 verified).
- **360 freeze frames join via `frames_360.id = events.id`** — 100% of frame
  event IDs resolve to an events row.
- `pass_outcome` is **null for completed passes**, non-null for incomplete ones.
- `tactics` column is only populated for `type == "Tactics"` events (lineup/formation
  announcements at kick-off and after substitutions).
- `location` in both `events` and `frames_360` is stored as a **numpy array**
  after `pd.read_parquet()`; use `v[0]`, `v[1]` not dict-style access.
- `visible_area` in `frames_360` is a **flat 10-element array** (5 polygon
  vertices interleaved as `[x1,y1,x2,y2,x3,y3,x4,y4,x5,y5]`), not a list of
  `[x,y]` pairs.
- The `shot_freeze_frame` column in events (when non-null) gives player positions
  inline with the shot row; the `frames_360` table gives player positions for
  **all** event types that have 360 data.
