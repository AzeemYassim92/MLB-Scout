from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mlbpicker.providers.odds_provider import OddsApiProvider, _api_key_from_dotenv, _pitcher_lines_from_event_odds, _same_matchup
from mlbpicker.schemas import ScheduledGame


class OddsProviderTests(unittest.TestCase):
    def test_pitcher_lines_from_event_odds_groups_over_under(self) -> None:
        lines = _pitcher_lines_from_event_odds(
            {
                "bookmakers": [
                    {
                        "key": "betmgm",
                        "last_update": "2026-06-05T12:00:00Z",
                        "markets": [
                            {
                                "key": "pitcher_strikeouts",
                                "outcomes": [
                                    {
                                        "name": "Over",
                                        "description": "Sonny Gray",
                                        "price": -120,
                                        "point": 5.5,
                                    },
                                    {
                                        "name": "Under",
                                        "description": "Sonny Gray",
                                        "price": 100,
                                        "point": 5.5,
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        )

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].player_name, "Sonny Gray")
        self.assertEqual(lines[0].line, 5.5)
        self.assertEqual(lines[0].over_price, -120)
        self.assertEqual(lines[0].under_price, 100)

    def test_same_matchup_matches_teams_and_nearby_time(self) -> None:
        game = ScheduledGame(
            game_pk=1,
            game_date=date(2026, 6, 5),
            away_team_id=111,
            away_team="Boston Red Sox",
            home_team_id=147,
            home_team="New York Yankees",
            venue="Yankee Stadium",
            status="Scheduled",
            start_time_utc="2026-06-05T23:05:00Z",
        )
        event = {
            "id": "event-1",
            "away_team": "Boston Red Sox",
            "home_team": "New York Yankees",
            "commence_time": "2026-06-05T23:05:00Z",
        }

        self.assertTrue(_same_matchup(event, game))

    def test_api_key_from_dotenv(self) -> None:
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("THE_ODDS_API_KEY='abc123'\n", encoding="utf-8")

            self.assertEqual(_api_key_from_dotenv(env_path), "abc123")

    def test_debug_game_pitching_odds_reports_no_event_match(self) -> None:
        provider = OddsApiProvider(api_key="test")
        provider.fetch_mlb_events = lambda: []
        game = ScheduledGame(
            game_pk=1,
            game_date=date(2026, 6, 5),
            away_team_id=137,
            away_team="San Francisco Giants",
            home_team_id=112,
            home_team="Chicago Cubs",
            venue="Wrigley Field",
            status="Scheduled",
            start_time_utc="2026-06-05T18:20:00Z",
        )

        debug = provider.debug_game_pitching_odds(game)

        self.assertEqual(debug["status"], "no_event_match")


if __name__ == "__main__":
    unittest.main()
