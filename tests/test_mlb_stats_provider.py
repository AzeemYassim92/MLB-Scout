from __future__ import annotations

from datetime import date
import unittest

from mlbpicker.providers.mlb_stats_provider import (
    _pitcher_stat_line_from_api,
    _scheduled_game_from_api,
    _team_stat_line_from_api,
)


class MlbStatsProviderTests(unittest.TestCase):
    def test_scheduled_game_from_api_parses_probables(self) -> None:
        game = _scheduled_game_from_api(
            {
                "gamePk": 123,
                "officialDate": "2026-06-06",
                "gameDate": "2026-06-06T23:05:00Z",
                "venue": {"name": "Example Field"},
                "status": {"detailedState": "Scheduled"},
                "teams": {
                    "away": {
                        "team": {"name": "Away Team"},
                        "probablePitcher": {"fullName": "Away Starter", "id": 111},
                    },
                    "home": {
                        "team": {"name": "Home Team"},
                        "probablePitcher": {"fullName": "Home Starter", "id": 222},
                    },
                },
            },
            date(2026, 6, 6),
        )

        self.assertEqual(game.game_pk, 123)
        self.assertIsNone(game.away_team_id)
        self.assertEqual(game.away_team, "Away Team")
        self.assertIsNone(game.home_team_id)
        self.assertEqual(game.home_team, "Home Team")
        self.assertEqual(game.probable_away_pitcher, "Away Starter")
        self.assertEqual(game.probable_away_pitcher_id, 111)
        self.assertEqual(game.probable_home_pitcher, "Home Starter")
        self.assertEqual(game.probable_home_pitcher_id, 222)

    def test_pitcher_stat_line_from_api_calculates_k_per_9(self) -> None:
        stat_line = _pitcher_stat_line_from_api(
            111,
            2026,
            {
                "stats": [
                    {
                        "splits": [
                            {
                                "player": {"fullName": "Away Starter"},
                                "stat": {
                                    "gamesStarted": "7",
                                    "inningsPitched": "42.2",
                                    "strikeOuts": "50",
                                    "baseOnBalls": "12",
                                    "era": "3.12",
                                    "whip": "1.08",
                                    "pitchesPerInning": "15.8",
                                },
                            }
                        ]
                    }
                ]
            },
        )

        self.assertEqual(stat_line.name, "Away Starter")
        self.assertEqual(stat_line.games_started, 7)
        self.assertEqual(stat_line.strikeouts, 50)
        self.assertEqual(stat_line.strikeouts_per_9, 10.55)

    def test_team_stat_line_calculates_opponent_k_rate_and_strength(self) -> None:
        stat_line = _team_stat_line_from_api(
            111,
            2026,
            {
                "stats": [
                    {
                        "type": {"displayName": "season"},
                        "splits": [
                            {
                                "team": {"name": "Away Team"},
                                "stat": {
                                    "plateAppearances": 1000,
                                    "strikeOuts": 250,
                                    "ops": ".720",
                                    "runs": 100,
                                    "homeRuns": 30,
                                },
                            }
                        ],
                    },
                    {
                        "type": {"displayName": "seasonAdvanced"},
                        "splits": [
                            {
                                "stat": {
                                    "totalSwings": 500,
                                    "swingAndMisses": 125,
                                    "pitchesPerPlateAppearance": "3.900",
                                },
                            }
                        ],
                    },
                ]
            },
        )

        self.assertEqual(stat_line.name, "Away Team")
        self.assertEqual(stat_line.strikeout_rate, 0.25)
        self.assertEqual(stat_line.whiff_rate, 0.25)
        self.assertIsNotNone(stat_line.lineup_strength_score)


if __name__ == "__main__":
    unittest.main()
