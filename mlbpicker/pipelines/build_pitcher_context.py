from __future__ import annotations

from mlbpicker.providers.base import ContextRequest, DataProvider
from mlbpicker.schemas import GameContext
from mlbpicker.storage.cache import JsonCache


def build_context(
    provider: DataProvider,
    request: ContextRequest,
    cache: JsonCache | None = None,
    refresh: bool = False,
) -> GameContext:
    key = _cache_key(provider.name, request)
    if cache and not refresh:
        cached = cache.read(key)
        if cached:
            return GameContext.from_dict(cached)

    context = provider.build_context(request)
    if cache:
        cache.write(key, context)
    return context


def _cache_key(provider_name: str, request: ContextRequest) -> str:
    return "_".join(
        [
            provider_name,
            request.game_date.isoformat(),
            request.pitcher_name,
            request.opponent_team or "unknown_opponent",
            request.venue_name or "unknown_venue",
        ]
    )

