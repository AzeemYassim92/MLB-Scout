from __future__ import annotations

from datetime import date
import unittest

from mlbpicker.analytics import expected_innings, expected_pitch_count, score_reliability
from mlbpicker.schemas import (
    PitchMetrics,
    PitcherMatchupAnalytics,
    PitcherStatLine,
    RecentPitcherGame,
    TeamStatLine,
)


class AnalyticsTests(unittest.TestCase):
    def test_expected_pitch_count_and_innings_use_recent_games(self) -> None:
        analytics = PitcherMatchupAnalytics(
            side="away",
            team_name="Away",
            opponent_team_name="Home",
            pitcher_name="Starter",
            pitcher_id=1,
            pitcher_stats=None,
            opponent_stats=None,
            recent_games=[
                RecentPitcherGame(1, date(2026, 6, 1), "A", True, "6.0", 7, 1, 90, 24),
                RecentPitcherGame(2, date(2026, 5, 25), "B", False, "5.2", 6, 2, 84, 23),
            ],
        )

        self.assertEqual(expected_pitch_count(analytics), 87.0)
        self.assertEqual(expected_innings(analytics), 5.83)

    def test_reliability_scores_available_components(self) -> None:
        analytics = PitcherMatchupAnalytics(
            side="home",
            team_name="Home",
            opponent_team_name="Away",
            pitcher_name="Starter",
            pitcher_id=1,
            pitcher_stats=PitcherStatLine(
                player_id=1,
                name="Starter",
                season=2026,
                strikeout_rate=0.27,
                number_of_pitches=300,
                games_started=3,
            ),
            opponent_stats=TeamStatLine(
                team_id=2,
                name="Away",
                season=2026,
                strikeout_rate=0.24,
            ),
            recent_games=[
                RecentPitcherGame(1, date(2026, 6, 1), "A", True, "6.0", 7, 1, 90, 24),
                RecentPitcherGame(2, date(2026, 5, 25), "B", False, "5.2", 6, 2, 84, 23),
                RecentPitcherGame(3, date(2026, 5, 18), "C", False, "5.0", 5, 2, 82, 22),
            ],
            pitch_metrics=PitchMetrics(3, 250, 50, 28, 78, 0.112, 0.312),
            opponent_hitters=[],
        )

        reliability = score_reliability(analytics)

        self.assertEqual(reliability.label, "high")
        self.assertGreaterEqual(reliability.score, 80)


if __name__ == "__main__":
    unittest.main()
