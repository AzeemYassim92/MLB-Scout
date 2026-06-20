from __future__ import annotations

from pathlib import Path

from mlbpicker.providers.base import ContextRequest
from mlbpicker.schemas import GameContext


class MockProvider:
    name = "mock"

    def __init__(self, sample_path: Path | str | None = None) -> None:
        self.sample_path = Path(sample_path or "mlbpicker/data/sample_game.json")

    def build_context(self, request: ContextRequest) -> GameContext:
        raw = self.sample_path.read_text(encoding="utf-8")
        return GameContext.from_json(raw)

