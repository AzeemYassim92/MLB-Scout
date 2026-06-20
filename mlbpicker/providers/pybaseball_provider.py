from __future__ import annotations

from datetime import timedelta

from mlbpicker.providers.base import ContextRequest, ProviderError
from mlbpicker.schemas import (
    GameContext,
    MatchupHistory,
    OpposingLineup,
    PitcherProfile,
    RecentStart,
    VenueContext,
    WeatherContext,
)


class PybaseballProvider:
    """Optional adapter around pybaseball.

    The rest of the app should not import pybaseball directly. This adapter is
    where we can borrow small pieces of pybaseball behavior while keeping our
    normalized GameContext as the real application contract.
    """

    name = "pybaseball"

    def __init__(self) -> None:
        try:
            from pybaseball import playerid_lookup, statcast_pitcher
        except ImportError as exc:
            raise ProviderError(
                "pybaseball is not installed. Install with `python -m pip install -e .[pybaseball]` "
                "or use `--provider mock` while developing."
            ) from exc

        self._playerid_lookup = playerid_lookup
        self._statcast_pitcher = statcast_pitcher

    def build_context(self, request: ContextRequest) -> GameContext:
        player_id = self._lookup_pitcher_id(request.pitcher_name)
        end_date = request.game_date.isoformat()
        start_date = (request.game_date - timedelta(days=45)).isoformat()
        pitch_data = self._statcast_pitcher(start_date, end_date, player_id)

        if pitch_data.empty:
            raise ProviderError(f"No Statcast data found for {request.pitcher_name}.")

        recent_starts = _recent_starts_from_statcast(pitch_data, request.opponent_team)
        season_k_per_9 = _season_k_per_9(pitch_data)
        expected_pitch_count = _expected_pitch_count(recent_starts)

        return GameContext(
            game_date=request.game_date,
            pitcher=PitcherProfile(
                name=request.pitcher_name,
                handedness=_pitcher_handedness(pitch_data),
                season_k_per_9=season_k_per_9,
                season_bb_per_9=0.0,
                season_pitch_count_avg=expected_pitch_count or 90,
                expected_pitch_count=expected_pitch_count,
            ),
            opponent=OpposingLineup(
                team=request.opponent_team or "Unknown Opponent",
                projected_batter_k_rate=0.225,
                projected_lineup_confirmed=False,
            ),
            venue=VenueContext(name=request.venue_name or "Unknown Venue"),
            weather=WeatherContext(
                temperature_f=72,
                wind_mph=0,
                wind_direction="none",
                precipitation_risk=0,
            ),
            recent_starts=recent_starts,
            matchup_history=MatchupHistory(),
        )

    def _lookup_pitcher_id(self, pitcher_name: str) -> int:
        parts = pitcher_name.strip().split()
        if len(parts) < 2:
            raise ProviderError("Provide pitcher name as first and last name for pybaseball lookup.")

        first_name = parts[0]
        last_name = " ".join(parts[1:])
        matches = self._playerid_lookup(last_name, first_name)
        if matches.empty:
            raise ProviderError(f"Could not find pybaseball player id for {pitcher_name}.")

        key_mlbam = matches.iloc[0].get("key_mlbam")
        if not key_mlbam:
            raise ProviderError(f"pybaseball lookup did not return an MLBAM id for {pitcher_name}.")
        return int(key_mlbam)


def _recent_starts_from_statcast(pitch_data, fallback_opponent: str | None) -> list[RecentStart]:
    starts: list[RecentStart] = []
    if "game_date" not in pitch_data.columns:
        return starts

    for game_date, game_df in pitch_data.groupby("game_date"):
        outs = _outs_recorded(game_df)
        innings = round(outs / 3, 1) if outs else 0.0
        strikeouts = _strikeouts(game_df)
        pitches = len(game_df)
        if pitches < 35:
            continue
        starts.append(
            RecentStart(
                date=game_date.date() if hasattr(game_date, "date") else game_date,
                innings_pitched=innings,
                strikeouts=strikeouts,
                pitches=pitches,
                opponent=_opponent_for_game(game_df) or fallback_opponent or "Unknown",
            )
        )

    return sorted(starts, key=lambda start: start.date, reverse=True)[:5]


def _season_k_per_9(pitch_data) -> float:
    strikeouts = _strikeouts(pitch_data)
    outs = _outs_recorded(pitch_data)
    if outs == 0:
        return 0.0
    return strikeouts / (outs / 27)


def _expected_pitch_count(recent_starts: list[RecentStart]) -> float | None:
    if not recent_starts:
        return None
    return round(sum(start.pitches for start in recent_starts[:3]) / min(3, len(recent_starts)), 1)


def _pitcher_handedness(pitch_data) -> str:
    if "p_throws" not in pitch_data.columns or pitch_data["p_throws"].empty:
        return "R"
    value = str(pitch_data["p_throws"].dropna().iloc[0]).upper()
    return "L" if value == "L" else "R"


def _strikeouts(pitch_data) -> int:
    if "events" not in pitch_data.columns:
        return 0
    return int((pitch_data["events"] == "strikeout").sum())


def _outs_recorded(pitch_data) -> int:
    if "events" not in pitch_data.columns:
        return 0
    event_outs = {
        "strikeout": 1,
        "field_out": 1,
        "force_out": 1,
        "grounded_into_double_play": 2,
        "double_play": 2,
        "triple_play": 3,
        "sac_fly": 1,
        "sac_bunt": 1,
    }
    return int(pitch_data["events"].map(event_outs).fillna(0).sum())


def _opponent_for_game(game_df) -> str | None:
    if {"home_team", "away_team"}.issubset(game_df.columns):
        home_team = str(game_df["home_team"].dropna().iloc[0])
        away_team = str(game_df["away_team"].dropna().iloc[0])
        pitching_half = str(game_df["inning_topbot"].dropna().iloc[0]) if "inning_topbot" in game_df.columns else ""
        if pitching_half == "Top":
            return away_team
        if pitching_half == "Bot":
            return home_team
    return None

