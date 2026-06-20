from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import json
from typing import Literal


Handedness = Literal["L", "R"]


@dataclass(frozen=True)
class PitcherProfile:
    name: str
    handedness: Handedness
    season_k_per_9: float
    season_bb_per_9: float
    season_pitch_count_avg: float
    expected_pitch_count: float | None = None


@dataclass(frozen=True)
class RecentStart:
    date: date
    innings_pitched: float
    strikeouts: int
    pitches: int
    opponent: str


@dataclass(frozen=True)
class OpposingLineup:
    team: str
    projected_batter_k_rate: float
    projected_lineup_confirmed: bool = False
    vs_pitcher_handedness_k_rate: float | None = None


@dataclass(frozen=True)
class VenueContext:
    name: str
    park_k_factor: float = 1.0


@dataclass(frozen=True)
class WeatherContext:
    temperature_f: float
    wind_mph: float
    wind_direction: Literal["in", "out", "cross", "none"] = "none"
    precipitation_risk: float = 0.0
    roof_closed: bool = False


@dataclass(frozen=True)
class MatchupHistory:
    plate_appearances: int = 0
    strikeouts: int = 0


@dataclass(frozen=True)
class ScheduledGame:
    game_pk: int
    game_date: date
    away_team_id: int | None
    away_team: str
    home_team_id: int | None
    home_team: str
    venue: str
    status: str
    start_time_utc: str | None = None
    probable_away_pitcher: str | None = None
    probable_away_pitcher_id: int | None = None
    probable_home_pitcher: str | None = None
    probable_home_pitcher_id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PitcherStatLine:
    player_id: int
    name: str
    season: int
    pitch_hand: Handedness | None = None
    games_played: int | None = None
    games_started: int | None = None
    innings_pitched: str | None = None
    strikeouts: int | None = None
    walks: int | None = None
    batters_faced: int | None = None
    number_of_pitches: int | None = None
    strikes: int | None = None
    era: str | None = None
    whip: str | None = None
    strikeouts_per_9: float | None = None
    strikeout_rate: float | None = None
    walk_rate: float | None = None
    strike_percentage: float | None = None
    whiff_rate: float | None = None
    strikeout_minus_walk_rate: float | None = None
    pitches_per_inning: float | None = None
    pitches_per_plate_appearance: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TeamStatLine:
    team_id: int
    name: str
    season: int
    plate_appearances: int | None = None
    strikeouts: int | None = None
    strikeout_rate: float | None = None
    runs: int | None = None
    home_runs: int | None = None
    obp: str | None = None
    slg: str | None = None
    ops: str | None = None
    total_swings: int | None = None
    swing_and_misses: int | None = None
    whiff_rate: float | None = None
    pitches_per_plate_appearance: float | None = None
    lineup_strength_score: int | None = None
    strikeout_friendliness_score: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BatterStatLine:
    player_id: int
    name: str
    position: str
    bat_side: Handedness | Literal["S"] | None = None
    plate_appearances: int | None = None
    strikeouts: int | None = None
    strikeout_rate: float | None = None
    avg: str | None = None
    obp: str | None = None
    slg: str | None = None
    ops: str | None = None
    total_swings: int | None = None
    swing_and_misses: int | None = None
    whiff_rate: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TeamInjury:
    player_id: int
    name: str
    position: str
    status: str
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RecentPitcherGame:
    game_pk: int
    game_date: date
    opponent: str
    is_home: bool
    innings_pitched: str | None = None
    strikeouts: int | None = None
    walks: int | None = None
    number_of_pitches: int | None = None
    batters_faced: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PitchMetrics:
    sample_games: int
    total_pitches: int
    called_strikes: int
    whiffs: int
    called_strikes_plus_whiffs: int
    swinging_strike_rate: float | None
    csw_rate: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReliabilityScore:
    score: int
    label: Literal["low", "medium", "high"]
    components: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PitcherMatchupAnalytics:
    side: Literal["away", "home"]
    team_name: str
    opponent_team_name: str
    pitcher_name: str | None
    pitcher_id: int | None
    pitcher_stats: PitcherStatLine | None
    opponent_stats: TeamStatLine | None
    recent_games: list[RecentPitcherGame] = field(default_factory=list)
    pitch_metrics: PitchMetrics | None = None
    opponent_hitters: list[BatterStatLine] = field(default_factory=list)
    opponent_injuries: list[TeamInjury] = field(default_factory=list)
    reliability: ReliabilityScore | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PitcherPropLine:
    player_name: str
    market: str
    line: float | None
    over_price: int | float | None = None
    under_price: int | float | None = None
    bookmaker: str = "betmgm"
    last_update: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OddsQuota:
    requests_remaining: int | None = None
    requests_used: int | None = None
    requests_last: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GamePitchingOdds:
    event_id: str | None
    home_team: str | None
    away_team: str | None
    bookmaker: str = "betmgm"
    market: str = "pitcher_strikeouts"
    lines: list[PitcherPropLine] = field(default_factory=list)
    quota: OddsQuota | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GameContext:
    game_date: date
    pitcher: PitcherProfile
    opponent: OpposingLineup
    venue: VenueContext
    weather: WeatherContext
    recent_starts: list[RecentStart] = field(default_factory=list)
    matchup_history: MatchupHistory = field(default_factory=MatchupHistory)

    @classmethod
    def from_json(cls, raw: str) -> "GameContext":
        data = json.loads(raw)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "GameContext":
        return cls(
            game_date=_parse_date(data["game_date"]),
            pitcher=PitcherProfile(**data["pitcher"]),
            opponent=OpposingLineup(**data["opponent"]),
            venue=VenueContext(**data["venue"]),
            weather=WeatherContext(**data["weather"]),
            recent_starts=[
                RecentStart(date=_parse_date(start["date"]), **{k: v for k, v in start.items() if k != "date"})
                for start in data.get("recent_starts", [])
            ],
            matchup_history=MatchupHistory(**data.get("matchup_history", {})),
        )


@dataclass(frozen=True)
class FeatureVector:
    expected_innings: float
    season_k_per_inning: float
    recent_k_per_inning: float
    opponent_k_factor: float
    park_factor: float
    weather_factor: float
    matchup_factor: float


@dataclass(frozen=True)
class StrikeoutProjection:
    pitcher: str
    opponent: str
    projected_strikeouts: float
    confidence: Literal["low", "medium", "high"]
    features: FeatureVector
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)
