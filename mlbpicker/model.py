from __future__ import annotations

from mlbpicker.config import DEFAULT_SETTINGS, ModelSettings
from mlbpicker.features import build_features
from mlbpicker.schemas import GameContext, StrikeoutProjection


class StrikeoutProjector:
    def __init__(self, settings: ModelSettings | None = None) -> None:
        self.settings = settings or DEFAULT_SETTINGS

    def project(self, context: GameContext) -> StrikeoutProjection:
        features = build_features(context, self.settings)
        weights = self.settings.weights

        blended_k_per_inning = (
            weights.season_k_rate * features.season_k_per_inning
            + weights.recent_k_rate * features.recent_k_per_inning
            + weights.opponent_k_rate * self.settings.league_avg_starter_k_per_inning
        )
        adjusted = (
            blended_k_per_inning
            * features.expected_innings
            * features.opponent_k_factor
            * features.park_factor
            * features.weather_factor
            * features.matchup_factor
        )
        projected = max(
            self.settings.min_projection,
            min(self.settings.max_projection, adjusted),
        )

        return StrikeoutProjection(
            pitcher=context.pitcher.name,
            opponent=context.opponent.team,
            projected_strikeouts=round(projected, 1),
            confidence=_confidence(context),
            features=features,
            notes=_notes(context, projected),
        )


def _confidence(context: GameContext) -> str:
    score = 0
    if len(context.recent_starts) >= 3:
        score += 1
    if context.opponent.projected_lineup_confirmed:
        score += 1
    if context.matchup_history.plate_appearances >= 20:
        score += 1
    if context.pitcher.expected_pitch_count:
        score += 1

    if score >= 3:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _notes(context: GameContext, projected: float) -> list[str]:
    notes = []
    if not context.opponent.projected_lineup_confirmed:
        notes.append("Projected lineup is not confirmed; refresh before locking a pick.")
    if context.weather.precipitation_risk >= 0.45 and not context.weather.roof_closed:
        notes.append("Weather risk may shorten the starter's outing.")
    if len(context.recent_starts) < 3:
        notes.append("Recent-form sample is thin; season rates carry more of the projection.")
    if projected >= 8:
        notes.append("Ceiling projection: check pitch-count leash and bullpen freshness.")
    return notes

