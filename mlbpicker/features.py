from __future__ import annotations

from statistics import mean

from mlbpicker.config import ModelSettings
from mlbpicker.schemas import FeatureVector, GameContext


def build_features(context: GameContext, settings: ModelSettings) -> FeatureVector:
    recent_k_per_inning = _recent_k_per_inning(context, settings)
    season_k_per_inning = context.pitcher.season_k_per_9 / 9
    expected_innings = _expected_innings(context, settings)
    opponent_k_factor = _opponent_k_factor(context, settings)
    park_factor = _bounded_factor(
        context.venue.park_k_factor,
        settings.weights.park_adjustment_cap,
    )
    weather_factor = _weather_factor(context, settings)
    matchup_factor = _matchup_factor(context, settings)

    return FeatureVector(
        expected_innings=expected_innings,
        season_k_per_inning=season_k_per_inning,
        recent_k_per_inning=recent_k_per_inning,
        opponent_k_factor=opponent_k_factor,
        park_factor=park_factor,
        weather_factor=weather_factor,
        matchup_factor=matchup_factor,
    )


def _recent_k_per_inning(context: GameContext, settings: ModelSettings) -> float:
    starts = [start for start in context.recent_starts if start.innings_pitched > 0]
    if not starts:
        return context.pitcher.season_k_per_9 / 9
    return sum(start.strikeouts for start in starts) / sum(start.innings_pitched for start in starts)


def _expected_innings(context: GameContext, settings: ModelSettings) -> float:
    if context.pitcher.expected_pitch_count:
        return max(3.0, min(7.4, context.pitcher.expected_pitch_count / 16.5))

    recent_innings = [
        start.innings_pitched
        for start in context.recent_starts
        if start.innings_pitched > 0 and start.pitches >= 60
    ]
    if recent_innings:
        return max(3.0, min(7.2, mean(recent_innings)))

    if context.pitcher.season_pitch_count_avg:
        return max(3.0, min(7.0, context.pitcher.season_pitch_count_avg / 16.5))

    return settings.default_expected_innings


def _opponent_k_factor(context: GameContext, settings: ModelSettings) -> float:
    lineup_k_rate = (
        context.opponent.vs_pitcher_handedness_k_rate
        or context.opponent.projected_batter_k_rate
    )
    return lineup_k_rate / settings.league_avg_batter_k_rate


def _weather_factor(context: GameContext, settings: ModelSettings) -> float:
    if context.weather.roof_closed:
        return 1.0

    adjustment = 0.0
    if context.weather.temperature_f < 50:
        adjustment += 0.03
    elif context.weather.temperature_f > 88:
        adjustment -= 0.03

    if context.weather.wind_mph >= 14 and context.weather.wind_direction == "in":
        adjustment += 0.02
    elif context.weather.wind_mph >= 14 and context.weather.wind_direction == "out":
        adjustment -= 0.02

    if context.weather.precipitation_risk >= 0.45:
        adjustment -= 0.04

    cap = settings.weights.weather_adjustment_cap
    return 1 + max(-cap, min(cap, adjustment))


def _matchup_factor(context: GameContext, settings: ModelSettings) -> float:
    history = context.matchup_history
    if history.plate_appearances < 10:
        return 1.0

    observed_k_rate = history.strikeouts / history.plate_appearances
    raw_delta = observed_k_rate - settings.league_avg_batter_k_rate
    capped_delta = max(
        -settings.weights.matchup_adjustment_cap,
        min(settings.weights.matchup_adjustment_cap, raw_delta),
    )
    return 1 + capped_delta


def _bounded_factor(value: float, cap: float) -> float:
    return max(1 - cap, min(1 + cap, value))

