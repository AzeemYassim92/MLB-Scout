# Stats, Sources, and Confidence

This document explains the stats currently tracked by the MLB strikeout picker, how each value is acquired or derived, and how we should think about reliability. The goal is to keep the model explainable as we move from a scaffold into a real game-day workflow.

## Data Sources

### MLB Stats API

Current live source for schedule, teams, probable pitchers, venues, pitcher season stats, team hitting stats, active roster hitter profiles, 40-man roster injury statuses, recent pitcher game logs, and recent pitch-level event samples.

- Schedule endpoint:
  `https://statsapi.mlb.com/api/v1/schedule`
- Pitcher stats endpoint:
  `https://statsapi.mlb.com/api/v1/people/{player_id}/stats`
- Team stats endpoint:
  `https://statsapi.mlb.com/api/v1/teams/{team_id}/stats`
- Active/40-man roster endpoint:
  `https://statsapi.mlb.com/api/v1/teams/{team_id}/roster`
- Game feed endpoint:
  `https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live`

In code:

- `mlbpicker/providers/mlb_stats_provider.py`
- `MlbStatsProvider.fetch_schedule()`
- `MlbStatsProvider.fetch_pitcher_stats()`

### Local Mock Data

Current projection scaffold source for full `GameContext` examples until live provider-to-projection conversion is complete.

- `mlbpicker/data/sample_game.json`
- `MockProvider`

### Optional pybaseball

Optional adapter for Statcast-style data. This is not yet the primary GUI path. It is useful for future recent-start reconstruction, pitch-level features, whiff rate, batter matchup history, and backtesting.

- `mlbpicker/providers/pybaseball_provider.py`

### The Odds API

Current source for BetMGM pitcher strikeout prop lines. BetMGM does not expose a public developer API directly, so the app uses The Odds API's normalized sportsbook feed and requests only:

- Sport: `baseball_mlb`
- Bookmaker: `betmgm`
- Market: `pitcher_strikeouts`

In code:

- `mlbpicker/providers/odds_provider.py`
- `OddsApiProvider.fetch_pitcher_strikeout_lines()`

## Currently Tracked Game Fields

| Field | Meaning | Current source | Reliability |
| --- | --- | --- | --- |
| `game_pk` | MLB game identifier | MLB Stats schedule API | High |
| `game_date` | Official game date | MLB Stats schedule API | High |
| `away_team_id` | Away team MLB ID | MLB Stats schedule API | High |
| `away_team` | Away team name | MLB Stats schedule API | High |
| `home_team_id` | Home team MLB ID | MLB Stats schedule API | High |
| `home_team` | Home team name | MLB Stats schedule API | High |
| `venue` | Ballpark name | MLB Stats schedule API | High |
| `status` | Game status, such as scheduled/final | MLB Stats schedule API | High |
| `start_time_utc` | Scheduled first pitch in UTC | MLB Stats schedule API | High, but subject to delays |
| `probable_away_pitcher` | Listed away probable starter | MLB Stats schedule API hydrate `probablePitcher` | Medium before lineups lock |
| `probable_home_pitcher` | Listed home probable starter | MLB Stats schedule API hydrate `probablePitcher` | Medium before lineups lock |
| `probable_away_pitcher_id` | MLBAM ID for away probable | MLB Stats schedule API | High when present |
| `probable_home_pitcher_id` | MLBAM ID for home probable | MLB Stats schedule API | High when present |

Probable pitchers are the most fragile schedule field. They can be missing, changed late, or affected by doubleheaders, bullpen games, rainouts, injuries, and roster moves.

## Currently Tracked Pitcher Stats

These are pulled with `MlbStatsProvider.fetch_pitcher_stats(player_id, season)`.

| Field | Meaning | Current source | Reliability |
| --- | --- | --- | --- |
| `player_id` | MLBAM player ID | Schedule probable pitcher object | High |
| `name` | Player full name | MLB Stats people/stats response | High |
| `season` | Season requested | App input from selected game year | High |
| `games_started` | Season starts | MLB Stats season pitching stat | High |
| `innings_pitched` | Season innings, baseball notation | MLB Stats season pitching stat | High |
| `strikeouts` | Season strikeouts | MLB Stats season pitching stat | High |
| `walks` | Season walks | MLB Stats season pitching stat | High |
| `era` | Season ERA | MLB Stats season pitching stat | High |
| `whip` | Season WHIP | MLB Stats season pitching stat | High |
| `pitches_per_inning` | Pitches per inning, when provided | MLB Stats season pitching stat | Medium |
| `strikeouts_per_9` | Strikeouts per nine innings | Derived from `strikeouts` and `innings_pitched` | High if source stats exist |
| `strikeout_rate` | Pitcher K% against batters faced | MLB advanced stat or `strikeouts / batters_faced` | High |
| `walk_rate` | Pitcher BB% against batters faced | MLB advanced stat or `walks / batters_faced` | High |
| `strike_percentage` | Total strikes / total pitches | MLB season or advanced pitching stat | High |
| `whiff_rate` | Swing and miss rate per swing | MLB advanced pitching stat | High |
| `strikeout_minus_walk_rate` | K% minus BB% | MLB advanced pitching stat | High |
| `pitches_per_plate_appearance` | Pitcher pitches per PA | MLB advanced pitching stat | High |

## Currently Tracked Opponent / Lineup Stats

These are pulled with `MlbStatsProvider.fetch_team_stats(team_id, season)` and `MlbStatsProvider.fetch_active_hitters(team_id, season)`.

| Field | Meaning | Current source | Reliability |
| --- | --- | --- | --- |
| `plate_appearances` | Team or hitter PA | MLB hitting stats | High |
| `strikeouts` | Team or hitter strikeouts | MLB hitting stats | High |
| `strikeout_rate` | Opponent K% | MLB advanced hitting stat or `strikeouts / PA` | High |
| `ops` | Team or hitter OPS | MLB hitting stats | High |
| `whiff_rate` | Swing and miss rate per swing | MLB advanced hitting stats | High |
| `lineup_strength_score` | Composite danger score using OPS and K% | Derived | Medium |
| `strikeout_friendliness_score` | Composite K opportunity score using K% and OPS | Derived | Medium |
| `opponent_hitters` | Active non-pitcher roster hitter profiles | MLB active roster plus people stats hydrate | Medium |
| `opponent_injuries` | Non-active 40-man statuses and notes | MLB 40-man roster status | Medium |

Active roster hitters are not the same as confirmed lineups. They are a useful early-day proxy until we add confirmed batting orders.

## Recent Pitch-Level Metrics

These are pulled from recent pitcher game logs and MLB game feeds.

| Field | Meaning | Current source | Reliability |
| --- | --- | --- | --- |
| `called_strikes` | Recent called strike count | MLB game feed pitch result code `C` | Medium |
| `whiffs` | Recent swinging strike style count | MLB game feed pitch result codes such as `S`/`W` | Medium |
| `called_strikes_plus_whiffs` | Called strikes plus whiffs | Derived from recent pitch feed | Medium |
| `swinging_strike_rate` | Whiffs / total pitches | Derived from recent pitch feed | Medium |
| `csw_rate` | Called strikes plus whiffs / total pitches | Derived from recent pitch feed | Medium |

This is a recent-game sample, not yet a full-season Statcast-grade CSW calculation.

## Currently Tracked Odds Fields

These are pulled from The Odds API for the selected game only.

| Field | Meaning | Current source | Reliability |
| --- | --- | --- | --- |
| `event_id` | The Odds API event identifier | The Odds API events endpoint | High when matched |
| `bookmaker` | Sportsbook source, currently BetMGM | The Odds API event odds response | High |
| `market` | Pitching prop market, currently pitcher strikeouts | The Odds API event odds response | High |
| `player_name` | Player attached to prop line | The Odds API outcome description | Medium |
| `line` | Strikeout over/under number | BetMGM via The Odds API | High |
| `over_price` | American odds for over | BetMGM via The Odds API | High |
| `under_price` | American odds for under | BetMGM via The Odds API | High |
| `requests_remaining` | Remaining API quota reported in response headers | The Odds API response headers | High |

The app does not scrape BetMGM. If the line is missing, it means no matching event or no BetMGM `pitcher_strikeouts` market was returned at request time.

### Derived K/9

`strikeouts_per_9` is calculated as:

```text
(strikeouts / innings_pitched) * 9
```

Baseball innings notation is converted before calculation:

- `21.0` means 21 innings.
- `42.2` means 42 innings and 2 outs, or 42.6667 innings.

## Projection Fields

These fields exist in the model scaffold and are currently populated by normalized `GameContext` data, not yet directly by the GUI matchup dropdown.

| Field | Meaning | Current source | Reliability |
| --- | --- | --- | --- |
| `season_k_per_9` | Pitcher's season strikeout rate | Live MLB pitcher stat in GUI projection path | High |
| `season_bb_per_9` | Pitcher's season walk rate | Mock data now | Medium until live-wired |
| `season_pitch_count_avg` | Average pitch count | Mock data now; pybaseball/Statcast candidate | Medium |
| `expected_pitch_count` | Estimated pitch leash today | Recent starts average, fallback season pitch/start average | Medium |
| `recent_starts` | Recent game-level pitcher form | MLB pitcher game logs | Medium |
| `projected_batter_k_rate` | Opponent lineup strikeout tendency | Live team K%, active hitter detail proxy | Medium |
| `vs_pitcher_handedness_k_rate` | Opponent K rate vs pitcher handedness | Pending handedness split | Low until live-wired |
| `park_k_factor` | Ballpark strikeout environment | Mock data now; future historical park factor | Low until live-wired |
| `weather` | Temperature, wind, precipitation, roof | Mock data now; future weather provider | Low until live-wired |
| `matchup_history` | Pitcher-vs-batter plate appearances and strikeouts | Mock data now; future Statcast/Retrosheet | Low until live-wired |

## Feature Engineering

The baseline projection creates these model features:

| Feature | How it is calculated | Reliability today |
| --- | --- | --- |
| `expected_innings` | Expected pitch count / 16.5, or recent innings average, or season pitch-count estimate | Medium with real pitch counts; low in mock mode |
| `season_k_per_inning` | `season_k_per_9 / 9` | High once live-wired |
| `recent_k_per_inning` | Recent-start strikeouts / recent-start innings | Medium, depends on recent-start quality |
| `opponent_k_factor` | Opponent K rate / league-average batter K rate | Low until lineup stats are live |
| `park_factor` | Bounded park K factor | Low until historical park factor is live |
| `weather_factor` | Rule-based adjustment from weather context | Low until weather is live |
| `matchup_factor` | Pitcher-vs-batter K rate adjustment when at least 10 PA exist | Low until matchup history is live |

## Proposed Reliability Score

Reliability should answer: "How much do we trust the inputs behind this projection?"

Use a 0-100 score and map it to labels:

| Score | Label |
| --- | --- |
| 80-100 | High |
| 55-79 | Medium |
| 0-54 | Low |

### Suggested Components

| Component | Points | Rationale |
| --- | ---: | --- |
| Probable pitcher confirmed/present | 20 | The projection is unusable without the right pitcher |
| Pitcher season stats available | 20 | Gives stable baseline K skill |
| At least 3 recent starts available | 15 | Captures current workload and form |
| Expected pitch count or recent pitch counts available | 15 | Strikeout overs depend heavily on leash |
| Opponent lineup or projected batter K rate available | 15 | Strikeout target depends on the batters faced |
| Weather/roof context available | 5 | Small but relevant outing-risk adjustment |
| Park factor available | 5 | Small contextual adjustment |
| Pitcher-vs-batter history available | 5 | Useful only when sample is meaningful |

### Example Interpretation

If a selected matchup has:

- Probable pitcher ID.
- Season pitching stats.
- No recent starts yet.
- No lineup-specific batter K rate yet.
- No weather yet.

Then reliability might be around 40-50. That is enough to display season context, but not enough to trust a betting-style projection.

## Proposed Projection Confidence Score

Projection confidence should answer: "How confident are we in this specific strikeout estimate?"

It should combine reliability plus model-specific signals:

```text
projection_confidence = input_reliability
  + recent_form_bonus
  + opponent_signal_bonus
  - volatility_penalties
```

Suggested penalties:

- Probable pitcher is `TBD`: hard cap at low.
- Bullpen game or opener risk: hard cap at low.
- Rain/delay risk above threshold: subtract 10-20.
- Pitcher returning from injury or low recent pitch count: subtract 10-20.
- Lineup not confirmed: subtract 5-10.
- Small MLB sample, such as fewer than 3 starts: subtract 10-15.

## Near-Term Implementation Plan

1. Add confirmed batting order ingestion.
2. Add opponent handedness splits against left/right pitchers.
3. Add pitcher-vs-batter history when sample size is meaningful.
4. Add weather and roof state.
5. Add park strikeout factors.
6. Expand recent pitch metrics into full-season Statcast-grade CSW when pybaseball or a direct Statcast pull is available.
