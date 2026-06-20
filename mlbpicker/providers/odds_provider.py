from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen

from mlbpicker.providers.base import ProviderError
from mlbpicker.schemas import GamePitchingOdds, OddsQuota, PitcherPropLine, ScheduledGame


BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "baseball_mlb"
BOOKMAKER = "betmgm"
PITCHER_STRIKEOUTS = "pitcher_strikeouts"


class OddsApiProvider:
    name = "the_odds_api"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("THE_ODDS_API_KEY") or _api_key_from_dotenv()
        if not self.api_key:
            raise ProviderError("Set THE_ODDS_API_KEY to load BetMGM pitching prop lines.")
        self._json_cache: dict[str, tuple[dict | list, OddsQuota]] = {}

    def fetch_mlb_events(self) -> list[dict]:
        params = {"apiKey": self.api_key}
        payload, _quota = self._fetch_json(f"{BASE_URL}/sports/{SPORT_KEY}/events?{urlencode(params)}")
        return payload if isinstance(payload, list) else []

    def fetch_pitcher_strikeout_lines(self, game: ScheduledGame) -> GamePitchingOdds:
        event = self.find_event_for_game(game)
        if not event:
            return GamePitchingOdds(
                event_id=None,
                home_team=None,
                away_team=None,
                note="No matching The Odds API event found for this MLB matchup.",
            )

        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "bookmakers": BOOKMAKER,
            "markets": PITCHER_STRIKEOUTS,
            "oddsFormat": "american",
        }
        payload, quota = self._fetch_json(
            f"{BASE_URL}/sports/{SPORT_KEY}/events/{event['id']}/odds?{urlencode(params)}"
        )
        if not isinstance(payload, dict):
            return GamePitchingOdds(
                event_id=event["id"],
                home_team=event.get("home_team"),
                away_team=event.get("away_team"),
                quota=quota,
                note="Unexpected odds response shape.",
            )

        lines = _pitcher_lines_from_event_odds(payload)
        note = None if lines else "BetMGM pitcher strikeout market is not available for this event yet."
        return GamePitchingOdds(
            event_id=event["id"],
            home_team=event.get("home_team"),
            away_team=event.get("away_team"),
            lines=lines,
            quota=quota,
            note=note,
        )

    def fetch_event_markets(self, event_id: str) -> tuple[dict, OddsQuota]:
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "bookmakers": BOOKMAKER,
        }
        payload, quota = self._fetch_json(
            f"{BASE_URL}/sports/{SPORT_KEY}/events/{event_id}/markets?{urlencode(params)}"
        )
        if not isinstance(payload, dict):
            raise ProviderError("Unexpected event markets response shape.")
        return payload, quota

    def debug_game_pitching_odds(self, game: ScheduledGame) -> dict:
        event = self.find_event_for_game(game)
        if not event:
            return {
                "status": "no_event_match",
                "mlb_matchup": f"{game.away_team} at {game.home_team}",
                "mlb_start_time_utc": game.start_time_utc,
            }

        markets_payload, markets_quota = self.fetch_event_markets(event["id"])
        bookmakers = markets_payload.get("bookmakers", [])
        betmgm = next((book for book in bookmakers if book.get("key") == BOOKMAKER), None)
        market_keys = [market.get("key") for market in betmgm.get("markets", [])] if betmgm else []
        odds = self.fetch_pitcher_strikeout_lines(game)

        return {
            "status": "ok" if odds.lines else "no_pitcher_strikeouts_lines",
            "mlb_matchup": f"{game.away_team} at {game.home_team}",
            "mlb_probables": [game.probable_away_pitcher, game.probable_home_pitcher],
            "odds_event": {
                "id": event.get("id"),
                "away_team": event.get("away_team"),
                "home_team": event.get("home_team"),
                "commence_time": event.get("commence_time"),
            },
            "betmgm_market_count": len(market_keys),
            "betmgm_pitcher_strikeouts_available": PITCHER_STRIKEOUTS in market_keys,
            "betmgm_market_sample": market_keys[:20],
            "pitcher_strikeout_lines": [line.to_dict() for line in odds.lines],
            "market_quota": markets_quota.to_dict(),
            "odds_quota": odds.quota.to_dict() if odds.quota else None,
            "note": odds.note,
        }

    def find_event_for_game(self, game: ScheduledGame) -> dict | None:
        for event in self.fetch_mlb_events():
            if _same_matchup(event, game):
                return event
        return None

    def _fetch_json(self, url: str) -> tuple[dict | list, OddsQuota]:
        if url in self._json_cache:
            return self._json_cache[url]
        try:
            with urlopen(url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
                quota = OddsQuota(
                    requests_remaining=_optional_int(response.headers.get("x-requests-remaining")),
                    requests_used=_optional_int(response.headers.get("x-requests-used")),
                    requests_last=_optional_int(response.headers.get("x-requests-last")),
                )
        except OSError as exc:
            raise ProviderError(f"Could not fetch odds data from The Odds API: {exc}") from exc
        self._json_cache[url] = (payload, quota)
        return payload, quota


def _pitcher_lines_from_event_odds(payload: dict) -> list[PitcherPropLine]:
    lines_by_player: dict[str, dict] = {}
    for bookmaker in payload.get("bookmakers", []):
        if bookmaker.get("key") != BOOKMAKER:
            continue
        bookmaker_update = bookmaker.get("last_update")
        for market in bookmaker.get("markets", []):
            if market.get("key") != PITCHER_STRIKEOUTS:
                continue
            last_update = market.get("last_update") or bookmaker_update
            for outcome in market.get("outcomes", []):
                player_name = outcome.get("description") or outcome.get("name")
                if not player_name:
                    continue
                record = lines_by_player.setdefault(
                    player_name,
                    {
                        "player_name": player_name,
                        "market": market.get("key", PITCHER_STRIKEOUTS),
                        "line": outcome.get("point"),
                        "bookmaker": BOOKMAKER,
                        "last_update": last_update,
                    },
                )
                if outcome.get("point") is not None:
                    record["line"] = outcome.get("point")
                side = str(outcome.get("name", "")).lower()
                if side == "over":
                    record["over_price"] = outcome.get("price")
                elif side == "under":
                    record["under_price"] = outcome.get("price")

    return [
        PitcherPropLine(
            player_name=record["player_name"],
            market=record["market"],
            line=_optional_float(record.get("line")),
            over_price=record.get("over_price"),
            under_price=record.get("under_price"),
            bookmaker=record["bookmaker"],
            last_update=record.get("last_update"),
        )
        for record in sorted(lines_by_player.values(), key=lambda item: item["player_name"])
    ]


def _same_matchup(event: dict, game: ScheduledGame) -> bool:
    event_home = _normalize_team(event.get("home_team"))
    event_away = _normalize_team(event.get("away_team"))
    game_home = _normalize_team(game.home_team)
    game_away = _normalize_team(game.away_team)
    if event_home != game_home or event_away != game_away:
        return False

    commence_time = _parse_datetime(event.get("commence_time"))
    game_time = _parse_datetime(game.start_time_utc)
    if not commence_time or not game_time:
        return True
    delta_hours = abs((commence_time - game_time).total_seconds()) / 3600
    return delta_hours <= 36


def _normalize_team(value: str | None) -> str:
    if not value:
        return ""
    clean = value.lower()
    clean = clean.replace("st.", "st")
    clean = re.sub(r"[^a-z0-9]+", "", clean)
    return clean


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _api_key_from_dotenv(path: Path | str = ".env") -> str | None:
    env_path = Path(path)
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "THE_ODDS_API_KEY":
            return value.strip().strip('"').strip("'") or None
    return None
