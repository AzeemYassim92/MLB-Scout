from __future__ import annotations

from datetime import date
import json
from urllib.parse import urlencode
from urllib.request import urlopen

from mlbpicker.providers.base import ProviderError
from mlbpicker.schemas import (
    BatterStatLine,
    PitchMetrics,
    PitcherStatLine,
    RecentPitcherGame,
    ScheduledGame,
    TeamInjury,
    TeamStatLine,
)


SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"
TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
GAME_FEED_URL = "https://statsapi.mlb.com/api/v1.1/game"

WHIFF_CODES = {"S", "W"}
CALLED_STRIKE_CODES = {"C"}


class MlbStatsProvider:
    name = "mlb_stats"

    def __init__(self) -> None:
        self._json_cache: dict[str, dict] = {}

    def fetch_schedule(self, game_date: date) -> list[ScheduledGame]:
        params = {
            "sportId": "1",
            "date": game_date.isoformat(),
            "hydrate": "probablePitcher,team,venue",
        }
        payload = self._fetch_json(f"{SCHEDULE_URL}?{urlencode(params)}")

        games: list[ScheduledGame] = []
        for day in payload.get("dates", []):
            for game in day.get("games", []):
                games.append(_scheduled_game_from_api(game, game_date))
        return games

    def fetch_pitcher_stats(self, player_id: int, season: int) -> PitcherStatLine:
        params = {
            "personIds": str(player_id),
            "hydrate": f"stats(group=[pitching],type=[season,seasonAdvanced],season={season})",
        }
        payload = self._fetch_json(f"{PEOPLE_URL}?{urlencode(params)}")
        people = payload.get("people", [])
        if not people:
            return PitcherStatLine(player_id=player_id, name=f"Player {player_id}", season=season)
        return _pitcher_stat_line_from_person(people[0], season)

    def fetch_team_stats(self, team_id: int, season: int) -> TeamStatLine:
        params = {
            "stats": "season,seasonAdvanced",
            "group": "hitting",
            "season": str(season),
        }
        payload = self._fetch_json(f"{TEAMS_URL}/{team_id}/stats?{urlencode(params)}")
        return _team_stat_line_from_api(team_id, season, payload)

    def fetch_active_hitters(self, team_id: int, season: int, limit: int = 14) -> list[BatterStatLine]:
        roster = self._fetch_json(f"{TEAMS_URL}/{team_id}/roster?rosterType=active").get("roster", [])
        hitter_ids = [
            str(player["person"]["id"])
            for player in roster
            if player.get("position", {}).get("type") != "Pitcher"
        ]
        if not hitter_ids:
            return []

        params = {
            "personIds": ",".join(hitter_ids),
            "hydrate": f"stats(group=[hitting],type=[season,seasonAdvanced],season={season})",
        }
        payload = self._fetch_json(f"{PEOPLE_URL}?{urlencode(params)}")
        hitters = [_batter_stat_line_from_person(person) for person in payload.get("people", [])]
        hitters = [hitter for hitter in hitters if (hitter.plate_appearances or 0) > 0]
        return sorted(hitters, key=lambda hitter: hitter.plate_appearances or 0, reverse=True)[:limit]

    def fetch_team_injuries(self, team_id: int) -> list[TeamInjury]:
        roster = self._fetch_json(f"{TEAMS_URL}/{team_id}/roster?rosterType=40Man").get("roster", [])
        injuries: list[TeamInjury] = []
        for player in roster:
            status = player.get("status", {})
            status_code = status.get("code")
            if status_code == "A":
                continue
            person = player.get("person", {})
            injuries.append(
                TeamInjury(
                    player_id=int(person.get("id", 0)),
                    name=person.get("fullName", "Unknown"),
                    position=player.get("position", {}).get("abbreviation", "-"),
                    status=status.get("description", status_code or "Unknown"),
                    note=player.get("note"),
                )
            )
        return injuries

    def fetch_recent_pitcher_games(
        self,
        player_id: int,
        season: int,
        limit: int = 5,
    ) -> list[RecentPitcherGame]:
        params = {
            "stats": "gameLog",
            "group": "pitching",
            "season": str(season),
        }
        payload = self._fetch_json(f"{PEOPLE_URL}/{player_id}/stats?{urlencode(params)}")
        games = [_recent_pitcher_game_from_split(split) for split in _splits_for(payload, "gameLog")]
        starts = [game for game in games if game.number_of_pitches and game.number_of_pitches >= 35]
        return sorted(starts, key=lambda game: game.game_date, reverse=True)[:limit]

    def fetch_recent_pitch_metrics(
        self,
        player_id: int,
        season: int,
        max_games: int = 3,
    ) -> PitchMetrics:
        games = self.fetch_recent_pitcher_games(player_id, season, limit=max_games)
        total_pitches = 0
        called_strikes = 0
        whiffs = 0

        for game in games:
            payload = self._fetch_json(f"{GAME_FEED_URL}/{game.game_pk}/feed/live")
            for play in payload.get("liveData", {}).get("plays", {}).get("allPlays", []):
                pitcher_id = play.get("matchup", {}).get("pitcher", {}).get("id")
                if pitcher_id != player_id:
                    continue
                for event in play.get("playEvents", []):
                    if not event.get("isPitch"):
                        continue
                    total_pitches += 1
                    code = event.get("details", {}).get("code")
                    if code in CALLED_STRIKE_CODES:
                        called_strikes += 1
                    if code in WHIFF_CODES:
                        whiffs += 1

        csw = called_strikes + whiffs
        return PitchMetrics(
            sample_games=len(games),
            total_pitches=total_pitches,
            called_strikes=called_strikes,
            whiffs=whiffs,
            called_strikes_plus_whiffs=csw,
            swinging_strike_rate=_rate(whiffs, total_pitches),
            csw_rate=_rate(csw, total_pitches),
        )

    def _fetch_json(self, url: str) -> dict:
        if url in self._json_cache:
            return self._json_cache[url]
        try:
            with urlopen(url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except OSError as exc:
            raise ProviderError(f"Could not fetch MLB data: {exc}") from exc
        self._json_cache[url] = payload
        return payload


def _scheduled_game_from_api(game: dict, fallback_date: date) -> ScheduledGame:
    teams = game.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})
    away_team = away.get("team", {})
    home_team = home.get("team", {})
    venue = game.get("venue", {}).get("name", "Unknown Venue")
    status = game.get("status", {}).get("detailedState", "Unknown")

    return ScheduledGame(
        game_pk=int(game.get("gamePk", 0)),
        game_date=_parse_api_date(game.get("officialDate"), fallback_date),
        away_team_id=_optional_int(away_team.get("id")),
        away_team=away_team.get("name", "Unknown Away"),
        home_team_id=_optional_int(home_team.get("id")),
        home_team=home_team.get("name", "Unknown Home"),
        venue=venue,
        status=status,
        start_time_utc=game.get("gameDate"),
        probable_away_pitcher=away.get("probablePitcher", {}).get("fullName"),
        probable_away_pitcher_id=_optional_int(away.get("probablePitcher", {}).get("id")),
        probable_home_pitcher=home.get("probablePitcher", {}).get("fullName"),
        probable_home_pitcher_id=_optional_int(home.get("probablePitcher", {}).get("id")),
    )


def _pitcher_stat_line_from_api(player_id: int, season: int, payload: dict) -> PitcherStatLine:
    people = payload.get("people")
    if people:
        return _pitcher_stat_line_from_person(people[0], season)

    stats = payload.get("stats", [])
    person = {
        "id": player_id,
        "fullName": _player_name_from_stats(stats) or f"Player {player_id}",
        "stats": stats,
    }
    return _pitcher_stat_line_from_person(person, season)


def _pitcher_stat_line_from_person(person: dict, season: int) -> PitcherStatLine:
    player_id = int(person.get("id", 0))
    stats = person.get("stats", [])
    season_stat = _stat_for(stats, "season")
    advanced_stat = _stat_for(stats, "seasonAdvanced")
    strikeouts = _optional_int(season_stat.get("strikeOuts"))
    walks = _optional_int(season_stat.get("baseOnBalls"))
    batters_faced = _optional_int(season_stat.get("battersFaced") or advanced_stat.get("battersFaced"))
    total_swings = _optional_int(advanced_stat.get("totalSwings"))
    swing_and_misses = _optional_int(advanced_stat.get("swingAndMisses"))

    return PitcherStatLine(
        player_id=player_id,
        name=person.get("fullName", f"Player {player_id}"),
        season=season,
        pitch_hand=_hand_code(person.get("pitchHand", {}).get("code")),
        games_played=_optional_int(season_stat.get("gamesPlayed") or season_stat.get("gamesPitched")),
        games_started=_optional_int(season_stat.get("gamesStarted")),
        innings_pitched=season_stat.get("inningsPitched"),
        strikeouts=strikeouts,
        walks=walks,
        batters_faced=batters_faced,
        number_of_pitches=_optional_int(season_stat.get("numberOfPitches")),
        strikes=_optional_int(season_stat.get("strikes")),
        era=season_stat.get("era"),
        whip=season_stat.get("whip"),
        strikeouts_per_9=_optional_float(
            season_stat.get("strikeoutsPer9Inn") or advanced_stat.get("strikeoutsPer9")
        )
        or _strikeouts_per_9(strikeouts, season_stat.get("inningsPitched")),
        strikeout_rate=_optional_float(advanced_stat.get("strikeoutsPerPlateAppearance"))
        or _rate(strikeouts, batters_faced),
        walk_rate=_optional_float(advanced_stat.get("walksPerPlateAppearance")) or _rate(walks, batters_faced),
        strike_percentage=_optional_float(season_stat.get("strikePercentage") or advanced_stat.get("strikePercentage")),
        whiff_rate=_optional_float(advanced_stat.get("whiffPercentage")) or _rate(swing_and_misses, total_swings),
        strikeout_minus_walk_rate=_optional_float(advanced_stat.get("strikeoutsMinusWalksPercentage")),
        pitches_per_inning=_optional_float(season_stat.get("pitchesPerInning") or advanced_stat.get("pitchesPerInning")),
        pitches_per_plate_appearance=_optional_float(advanced_stat.get("pitchesPerPlateAppearance")),
    )


def _team_stat_line_from_api(team_id: int, season: int, payload: dict) -> TeamStatLine:
    stats = payload.get("stats", [])
    season_stat = _stat_for(stats, "season")
    advanced_stat = _stat_for(stats, "seasonAdvanced")
    strikeouts = _optional_int(season_stat.get("strikeOuts"))
    plate_appearances = _optional_int(season_stat.get("plateAppearances") or advanced_stat.get("plateAppearances"))
    total_swings = _optional_int(advanced_stat.get("totalSwings"))
    swing_and_misses = _optional_int(advanced_stat.get("swingAndMisses"))
    k_rate = _optional_float(advanced_stat.get("strikeoutsPerPlateAppearance")) or _rate(
        strikeouts,
        plate_appearances,
    )
    ops = season_stat.get("ops")
    ops_value = _optional_float(ops)

    return TeamStatLine(
        team_id=team_id,
        name=_team_name_from_stats(stats) or f"Team {team_id}",
        season=season,
        plate_appearances=plate_appearances,
        strikeouts=strikeouts,
        strikeout_rate=k_rate,
        runs=_optional_int(season_stat.get("runs")),
        home_runs=_optional_int(season_stat.get("homeRuns")),
        obp=season_stat.get("obp"),
        slg=season_stat.get("slg"),
        ops=ops,
        total_swings=total_swings,
        swing_and_misses=swing_and_misses,
        whiff_rate=_rate(swing_and_misses, total_swings),
        pitches_per_plate_appearance=_optional_float(advanced_stat.get("pitchesPerPlateAppearance")),
        lineup_strength_score=_lineup_strength_score(ops_value, k_rate),
        strikeout_friendliness_score=_strikeout_friendliness_score(ops_value, k_rate),
    )


def _batter_stat_line_from_person(person: dict) -> BatterStatLine:
    stats = person.get("stats", [])
    season_stat = _stat_for(stats, "season")
    advanced_stat = _stat_for(stats, "seasonAdvanced")
    strikeouts = _optional_int(season_stat.get("strikeOuts"))
    plate_appearances = _optional_int(season_stat.get("plateAppearances") or advanced_stat.get("plateAppearances"))
    total_swings = _optional_int(advanced_stat.get("totalSwings"))
    swing_and_misses = _optional_int(advanced_stat.get("swingAndMisses"))

    return BatterStatLine(
        player_id=int(person.get("id", 0)),
        name=person.get("fullName", "Unknown"),
        position=person.get("primaryPosition", {}).get("abbreviation", "-"),
        bat_side=_hand_code(person.get("batSide", {}).get("code"), allow_switch=True),
        plate_appearances=plate_appearances,
        strikeouts=strikeouts,
        strikeout_rate=_optional_float(advanced_stat.get("strikeoutsPerPlateAppearance"))
        or _rate(strikeouts, plate_appearances),
        avg=season_stat.get("avg"),
        obp=season_stat.get("obp"),
        slg=season_stat.get("slg"),
        ops=season_stat.get("ops"),
        total_swings=total_swings,
        swing_and_misses=swing_and_misses,
        whiff_rate=_rate(swing_and_misses, total_swings),
    )


def _recent_pitcher_game_from_split(split: dict) -> RecentPitcherGame:
    stat = split.get("stat", {})
    return RecentPitcherGame(
        game_pk=int(split.get("game", {}).get("gamePk", 0)),
        game_date=_parse_api_date(split.get("date"), date.min),
        opponent=split.get("opponent", {}).get("name", "Unknown"),
        is_home=bool(split.get("isHome")),
        innings_pitched=stat.get("inningsPitched"),
        strikeouts=_optional_int(stat.get("strikeOuts")),
        walks=_optional_int(stat.get("baseOnBalls")),
        number_of_pitches=_optional_int(stat.get("numberOfPitches")),
        batters_faced=_optional_int(stat.get("battersFaced")),
    )


def _stat_for(stats: list[dict], display_name: str) -> dict:
    for stat_group in stats:
        if stat_group.get("type", {}).get("displayName") != display_name:
            continue
        splits = stat_group.get("splits", [])
        if splits:
            return splits[0].get("stat", {})
    if display_name == "season" and len(stats) == 1 and "type" not in stats[0]:
        splits = stats[0].get("splits", [])
        if splits:
            return splits[0].get("stat", {})
    return {}


def _splits_for(payload: dict, display_name: str) -> list[dict]:
    for stat_group in payload.get("stats", []):
        if stat_group.get("type", {}).get("displayName") == display_name:
            return stat_group.get("splits", [])
    return []


def _player_name_from_stats(stats: list[dict]) -> str | None:
    for stat_group in stats:
        splits = stat_group.get("splits", [])
        if splits:
            return splits[0].get("player", {}).get("fullName")
    return None


def _team_name_from_stats(stats: list[dict]) -> str | None:
    for stat_group in stats:
        splits = stat_group.get("splits", [])
        if splits:
            return splits[0].get("team", {}).get("name")
    return None


def _strikeouts_per_9(strikeouts: int | None, innings_pitched: str | None) -> float | None:
    innings = _innings_to_float(innings_pitched)
    if strikeouts is None or not innings:
        return None
    return round((strikeouts / innings) * 9, 2)


def _innings_to_float(value: str | None) -> float | None:
    if not value:
        return None
    whole, _, partial = value.partition(".")
    outs = int(whole) * 3
    if partial:
        outs += int(partial)
    return outs / 3


def _rate(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return round(float(numerator) / float(denominator), 3)


def _lineup_strength_score(ops: float | None, strikeout_rate: float | None) -> int | None:
    if ops is None and strikeout_rate is None:
        return None
    ops_value = ops if ops is not None else 0.700
    k_value = strikeout_rate if strikeout_rate is not None else 0.225
    return _bounded_score(50 + (ops_value - 0.700) * 100 - (k_value - 0.225) * 100)


def _strikeout_friendliness_score(ops: float | None, strikeout_rate: float | None) -> int | None:
    if ops is None and strikeout_rate is None:
        return None
    ops_value = ops if ops is not None else 0.700
    k_value = strikeout_rate if strikeout_rate is not None else 0.225
    return _bounded_score(50 + (k_value - 0.225) * 160 - (ops_value - 0.700) * 40)


def _bounded_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _hand_code(value: object, allow_switch: bool = False):
    if value in {"L", "R"}:
        return value
    if allow_switch and value == "S":
        return value
    return None


def _optional_int(value: object) -> int | None:
    if value in (None, "", ".---"):
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value in (None, "", ".---"):
        return None
    return float(value)


def _parse_api_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    return date.fromisoformat(value)
