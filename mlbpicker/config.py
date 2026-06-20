from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProjectionWeights:
    """Tunable weights for the first transparent strikeout baseline."""

    season_k_rate: float = 0.45
    recent_k_rate: float = 0.35
    opponent_k_rate: float = 0.20
    matchup_adjustment_cap: float = 0.18
    weather_adjustment_cap: float = 0.12
    park_adjustment_cap: float = 0.12


@dataclass(frozen=True)
class ModelSettings:
    league_avg_batter_k_rate: float = 0.225
    league_avg_starter_k_per_inning: float = 1.02
    default_expected_innings: float = 5.6
    min_projection: float = 0.0
    max_projection: float = 14.0
    weights: ProjectionWeights = field(default_factory=ProjectionWeights)


DEFAULT_SETTINGS = ModelSettings()
