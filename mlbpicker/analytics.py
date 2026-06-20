from __future__ import annotations

from dataclasses import replace
from datetime import date

from mlbpicker.providers.mlb_stats_provider import MlbStatsProvider
from mlbpicker.schemas import (
    GameContext,
    MatchupHistory,
    OpposingLineup,
    PitcherMatchupAnalytics,
    PitcherProfile,
    RecentStart,
    ReliabilityScore,
    ScheduledGame,
    VenueContext,
    WeatherContext,
)


def build_pitcher_matchup_analytics(
    provider: MlbStatsProvider,
    game: ScheduledGame,
    side: str,
) -> PitcherMatchupAnalytics:
    if side == "away":
        team_name = game.away_team
        opponent_team_name = game.home_team
        pitcher_name = game.probable_away_pitcher
        pitcher_id = game.probable_away_pitcher_id
        opponent_team_id = game.home_team_id
    elif side == "home":
        team_name = game.home_team
        opponent_team_name = game.away_team
        pitcher_name = game.probable_home_pitcher
        pitcher_id = game.probable_home_pitcher_id
        opponent_team_id = game.away_team_id
    else:
        raise ValueError(f"Unknown side: {side}")

    pitcher_stats = provider.fetch_pitcher_stats(pitcher_id, game.game_date.year) if pitcher_id else None
    opponent_stats = (
        provider.fetch_team_stats(opponent_team_id, game.game_date.year) if opponent_team_id else None
    )
    recent_games = (
        provider.fetch_recent_pitcher_games(pitcher_id, game.game_date.year, limit=5) if pitcher_id else []
    )
    pitch_metrics = (
        provider.fetch_recent_pitch_metrics(pitcher_id, game.game_date.year, max_games=3) if pitcher_id else None
    )
    opponent_hitters = (
        provider.fetch_active_hitters(opponent_team_id, game.game_date.year, limit=14) if opponent_team_id else []
    )
    opponent_injuries = provider.fetch_team_injuries(opponent_team_id) if opponent_team_id else []

    analytics = PitcherMatchupAnalytics(
        side=side,
        team_name=team_name,
        opponent_team_name=opponent_team_name,
        pitcher_name=pitcher_name,
        pitcher_id=pitcher_id,
        pitcher_stats=pitcher_stats,
        opponent_stats=opponent_stats,
        recent_games=recent_games,
        pitch_metrics=pitch_metrics,
        opponent_hitters=opponent_hitters,
        opponent_injuries=opponent_injuries,
    )
    return replace(analytics, reliability=score_reliability(analytics))


def score_reliability(analytics: PitcherMatchupAnalytics) -> ReliabilityScore:
    score = 0
    components: list[str] = []
    missing: list[str] = []

    if analytics.pitcher_id and analytics.pitcher_name:
        score += 20
        components.append("Probable pitcher listed with MLBAM id.")
    else:
        missing.append("Probable pitcher is TBD or missing an MLBAM id.")

    if analytics.pitcher_stats and analytics.pitcher_stats.strikeout_rate is not None:
        score += 20
        components.append("Pitcher season strikeout baseline is available.")
    else:
        missing.append("Pitcher season K% is unavailable.")

    if len(analytics.recent_games) >= 3:
        score += 15
        components.append("At least three recent starts are available.")
    elif analytics.recent_games:
        score += 5
        missing.append("Fewer than three recent starts are available.")
    else:
        missing.append("Recent start sample is unavailable.")

    if expected_pitch_count(analytics) is not None and expected_innings(analytics) is not None:
        score += 15
        components.append("Expected pitch count and innings can be estimated.")
    else:
        missing.append("Expected pitch count or innings cannot be estimated.")

    if analytics.opponent_stats and analytics.opponent_stats.strikeout_rate is not None:
        score += 15
        components.append("Opponent team strikeout rate is available.")
    else:
        missing.append("Opponent strikeout rate is unavailable.")

    if analytics.pitch_metrics and analytics.pitch_metrics.total_pitches:
        score += 10
        components.append("Recent pitch-level whiff and CSW sample is available.")
    else:
        missing.append("Recent pitch-level whiff/CSW sample is unavailable.")

    if len(analytics.opponent_hitters) >= 8:
        score += 5
        components.append("Active opponent hitter profiles are available.")
    else:
        missing.append("Active opponent hitter sample is thin.")

    score = max(0, min(100, score))
    return ReliabilityScore(score=score, label=_label(score), components=components, missing=missing)


def expected_pitch_count(analytics: PitcherMatchupAnalytics) -> float | None:
    recent_pitches = [
        game.number_of_pitches
        for game in analytics.recent_games[:3]
        if game.number_of_pitches is not None
    ]
    if recent_pitches:
        return round(sum(recent_pitches) / len(recent_pitches), 1)

    stats = analytics.pitcher_stats
    if stats and stats.number_of_pitches and stats.games_started:
        return round(stats.number_of_pitches / stats.games_started, 1)
    return None


def expected_innings(analytics: PitcherMatchupAnalytics) -> float | None:
    recent_innings = [
        innings
        for innings in (_innings_to_float(game.innings_pitched) for game in analytics.recent_games[:3])
        if innings is not None
    ]
    if recent_innings:
        return round(sum(recent_innings) / len(recent_innings), 2)

    stats = analytics.pitcher_stats
    season_innings = _innings_to_float(stats.innings_pitched if stats else None)
    if stats and season_innings and stats.games_started:
        return round(season_innings / stats.games_started, 2)
    return None


def build_projection_context(
    game_date: date,
    venue_name: str,
    analytics: PitcherMatchupAnalytics,
) -> GameContext | None:
    stats = analytics.pitcher_stats
    opponent = analytics.opponent_stats
    if not stats or not opponent or stats.strikeouts_per_9 is None:
        return None

    recent_starts = [
        RecentStart(
            date=game.game_date,
            innings_pitched=_innings_to_float(game.innings_pitched) or 0,
            strikeouts=game.strikeouts or 0,
            pitches=game.number_of_pitches or 0,
            opponent=game.opponent,
        )
        for game in analytics.recent_games
    ]
    season_innings = _innings_to_float(stats.innings_pitched)
    season_bb_per_9 = (
        round((stats.walks / season_innings) * 9, 2)
        if stats.walks is not None and season_innings
        else 0.0
    )
    pitch_count = expected_pitch_count(analytics)

    return GameContext(
        game_date=game_date,
        pitcher=PitcherProfile(
            name=analytics.pitcher_name or stats.name,
            handedness=stats.pitch_hand or "R",
            season_k_per_9=stats.strikeouts_per_9,
            season_bb_per_9=season_bb_per_9,
            season_pitch_count_avg=pitch_count or 90,
            expected_pitch_count=pitch_count,
        ),
        opponent=OpposingLineup(
            team=analytics.opponent_team_name,
            projected_batter_k_rate=opponent.strikeout_rate or 0.225,
            projected_lineup_confirmed=False,
            vs_pitcher_handedness_k_rate=None,
        ),
        venue=VenueContext(name=venue_name),
        weather=WeatherContext(
            temperature_f=72,
            wind_mph=0,
            wind_direction="none",
            precipitation_risk=0,
        ),
        recent_starts=recent_starts,
        matchup_history=MatchupHistory(),
    )


def _label(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _innings_to_float(value: str | None) -> float | None:
    if not value:
        return None
    whole, _, partial = value.partition(".")
    outs = int(whole) * 3
    if partial:
        outs += int(partial)
    return outs / 3
