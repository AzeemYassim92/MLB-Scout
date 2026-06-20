from __future__ import annotations

import json
from pathlib import Path
import unittest

from mlbpicker.model import StrikeoutProjector
from mlbpicker.schemas import GameContext


class ProjectionTests(unittest.TestCase):
    def test_sample_projection_runs(self) -> None:
        raw = Path("mlbpicker/data/sample_game.json").read_text(encoding="utf-8")
        context = GameContext.from_json(raw)

        projection = StrikeoutProjector().project(context)

        self.assertEqual(projection.pitcher, "Example Starter")
        self.assertEqual(projection.opponent, "Example Opponent")
        self.assertGreater(projection.projected_strikeouts, 0)
        self.assertIn(projection.confidence, {"low", "medium", "high"})

    def test_projection_is_json_serializable(self) -> None:
        raw = Path("mlbpicker/data/sample_game.json").read_text(encoding="utf-8")
        context = GameContext.from_json(raw)

        projection = StrikeoutProjector().project(context)

        self.assertTrue(json.dumps(projection.to_dict(), default=str))


if __name__ == "__main__":
    unittest.main()
