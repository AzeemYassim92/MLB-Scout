# MLB Pitcher Strikeout Picker

A focused scaffold for predicting a starting pitcher's strikeouts on game day.

The project starts with a transparent baseline instead of a black box: combine recent pitcher form, opposing lineup strikeout tendencies, park/weather context, and pitcher-vs-batter history into a projection with confidence notes. An LLM can later sit on top of this pipeline to explain the pick, summarize risk, and generate betting-card style writeups.

## Current Scope

- Predict one target: pitcher strikeouts.
- Keep features explainable and game-day oriented.
- Support mock/local inputs first, then swap in live data providers.
- Separate numeric projection from narrative generation.

## Project Layout

```text
mlbpicker/
  config.py              Runtime settings and weights
  cli.py                 Command-line entry point
  schemas.py             Typed data models
  features.py            Feature engineering for strikeout prediction
  model.py               Baseline projection model
  providers/             Data-source adapters
  pipelines/             Provider/cache/model orchestration
  storage/               Local cache utilities
  data/
    sample_game.json     Example game-day input
tests/
  test_projection.py     Smoke tests for the baseline pipeline
```

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m mlbpicker.cli --input .\mlbpicker\data\sample_game.json
python -m mlbpicker.cli --provider mock --date 2026-06-04 --pitcher "Example Starter"
python -m mlbpicker.cli --matchups-date 2026-06-06
python -m unittest discover -s tests
```

To experiment with pybaseball as an optional data provider:

```powershell
python -m pip install -e ".[pybaseball]"
python -m mlbpicker.cli --provider pybaseball --date 2026-06-04 --pitcher "Pitcher Name" --opponent "NYY"
```

To run the basic GUI:

```powershell
python -m pip install -e ".[gui]"
python -m mlbpicker.gui
```

The GUI loads a date, fills a matchup dropdown from MLB Stats API, and shows away/home pitcher-vs-opponent boxes for the selected game. It now includes hover descriptions for stats, live pitcher K%, opponent K rate, expected pitch count/innings, recent swinging strike and CSW samples, opponent lineup strength, active hitter detail, injury statuses, reliability scoring, and a live baseline strikeout projection when enough inputs are available.

Probable pitchers are sourced from MLB Stats API's `probablePitcher` schedule hydration. The GUI defaults to today and includes Today/Tomorrow buttons because sportsbook boards often show today's slate while the app may be looking at tomorrow.

To show BetMGM pitcher strikeout props, set `THE_ODDS_API_KEY` as an environment variable or create a local `.env` file using `.env.example` as the template. The app only requests The Odds API's `pitcher_strikeouts` market for the selected game and `betmgm` bookmaker.

To debug a missing BetMGM pitcher strikeout line without opening the GUI:

```powershell
python -m mlbpicker.cli --odds-debug-date 2026-06-05 --odds-debug-matchup "Giants Cubs"
```

The diagnostic reports whether the API key is configured, whether the Odds API event matched the MLB game, whether BetMGM has the `pitcher_strikeouts` market, and which pitcher lines were returned.

## Modeling Notes

The baseline projection estimates expected innings, converts recent and season strikeout rates into per-inning strikeouts, then adjusts for:

- Opponent lineup strikeout rate.
- Park strikeout factor.
- Weather penalty/boost.
- Pitcher-to-batter matchup history.
- Recent workload and pitch count.

This is not meant to be final betting advice. It is the first working spine for a more serious model.

See [Stats, Sources, and Confidence](docs/stats-and-confidence.md) for the current tracked fields, acquisition path, and proposed reliability scoring.

## Next Data Integrations

Good near-term provider candidates:

- MLB Stats API for probable pitchers, lineups, game logs, and weather-adjacent venue metadata.
- Baseball Savant / Statcast exports for pitch-level form and batter whiff tendencies.
- Retrosheet or pybaseball for historical backtesting.
- Weather API provider for wind, temperature, humidity, and precipitation by venue.

## Provider Strategy

The model consumes our normalized `GameContext`, not provider-specific dataframes. That lets us use `pybaseball` while it is helpful, cache raw-ish provider outputs locally, and replace or reimplement narrow pieces later without changing the projection logic or future GUI.
