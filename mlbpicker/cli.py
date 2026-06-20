from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path

from mlbpicker.model import StrikeoutProjector
from mlbpicker.pipelines import build_context
from mlbpicker.providers.base import ContextRequest, ProviderError
from mlbpicker.providers.mlb_stats_provider import MlbStatsProvider
from mlbpicker.providers.mock_provider import MockProvider
from mlbpicker.providers.odds_provider import OddsApiProvider
from mlbpicker.schemas import GameContext
from mlbpicker.storage import JsonCache


def main() -> None:
    parser = argparse.ArgumentParser(description="Project MLB pitcher strikeouts.")
    parser.add_argument("--input", help="Path to a normalized game context JSON file.")
    parser.add_argument("--provider", choices=["mock", "pybaseball"], default="mock")
    parser.add_argument("--matchups-date", help="Print MLB matchups for a date in YYYY-MM-DD format.")
    parser.add_argument("--odds-debug-date", help="Debug BetMGM pitcher K odds for a date in YYYY-MM-DD format.")
    parser.add_argument("--odds-debug-matchup", help="Optional matchup substring, such as 'Giants at Cubs'.")
    parser.add_argument("--tomorrow", action="store_true", help="Print MLB matchups for tomorrow.")
    parser.add_argument("--date", help="Game date in YYYY-MM-DD format when using a provider.")
    parser.add_argument("--pitcher", help="Pitcher first and last name when using a provider.")
    parser.add_argument("--opponent", help="Opponent team abbreviation/name when using a provider.")
    parser.add_argument("--venue", help="Venue name when using a provider.")
    parser.add_argument("--cache-dir", default=".mlbpicker_cache")
    parser.add_argument("--refresh", action="store_true", help="Refresh provider data instead of reading cache.")
    args = parser.parse_args()

    if args.tomorrow or args.matchups_date:
        matchup_date = date.today() + timedelta(days=1) if args.tomorrow else date.fromisoformat(args.matchups_date)
        games = MlbStatsProvider().fetch_schedule(matchup_date)
        print(json.dumps([game.to_dict() for game in games], indent=2, default=str))
        return

    if args.odds_debug_date:
        debug_date = date.fromisoformat(args.odds_debug_date)
        games = MlbStatsProvider().fetch_schedule(debug_date)
        game = _find_game_for_debug(games, args.odds_debug_matchup)
        if not game:
            raise SystemExit("No matching MLB game found for odds debug.")
        try:
            debug = OddsApiProvider().debug_game_pitching_odds(game)
        except ProviderError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(debug, indent=2, default=str))
        return

    context = _load_context(args)
    projection = StrikeoutProjector().project(context)
    print(json.dumps(projection.to_dict(), indent=2, default=str))


def _load_context(args: argparse.Namespace) -> GameContext:
    if args.input:
        return GameContext.from_json(Path(args.input).read_text(encoding="utf-8"))

    if not args.date or not args.pitcher:
        raise SystemExit("Provide --input, or provide --date and --pitcher for provider mode.")

    request = ContextRequest.from_strings(
        game_date=args.date,
        pitcher_name=args.pitcher,
        opponent_team=args.opponent,
        venue_name=args.venue,
    )
    provider = _provider_for(args.provider)
    try:
        return build_context(
            provider=provider,
            request=request,
            cache=JsonCache(args.cache_dir),
            refresh=args.refresh,
        )
    except ProviderError as exc:
        raise SystemExit(str(exc)) from exc


def _provider_for(name: str):
    if name == "mock":
        return MockProvider()
    if name == "pybaseball":
        from mlbpicker.providers.pybaseball_provider import PybaseballProvider

        return PybaseballProvider()
    raise SystemExit(f"Unknown provider: {name}")


def _find_game_for_debug(games, matchup: str | None):
    if not games:
        return None
    if not matchup:
        return games[0]
    needle_tokens = _tokens(matchup)
    for game in games:
        label = f"{game.away_team} at {game.home_team}"
        label_tokens = set(_tokens(label))
        if all(token in label_tokens for token in needle_tokens):
            return game
    return None


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in "".join(char.lower() if char.isalnum() else " " for char in value).split()
        if token != "at"
    ]


if __name__ == "__main__":
    main()
