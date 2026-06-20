from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from mlbpicker.schemas import GameContext


class ProviderError(RuntimeError):
    """Raised when a provider cannot build the requested context."""


@dataclass(frozen=True)
class ContextRequest:
    game_date: date
    pitcher_name: str
    opponent_team: str | None = None
    venue_name: str | None = None

    @classmethod
    def from_strings(
        cls,
        game_date: str,
        pitcher_name: str,
        opponent_team: str | None = None,
        venue_name: str | None = None,
    ) -> "ContextRequest":
        return cls(
            game_date=date.fromisoformat(game_date),
            pitcher_name=pitcher_name,
            opponent_team=opponent_team,
            venue_name=venue_name,
        )


class DataProvider(Protocol):
    name: str

    def build_context(self, request: ContextRequest) -> GameContext:
        """Build a normalized game context for the projection model."""

