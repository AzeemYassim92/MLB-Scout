from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mlbpicker.pipelines import build_context
from mlbpicker.providers.base import ContextRequest
from mlbpicker.providers.mock_provider import MockProvider
from mlbpicker.storage import JsonCache


class PipelineTests(unittest.TestCase):
    def test_mock_provider_builds_and_caches_context(self) -> None:
        request = ContextRequest.from_strings("2026-06-04", "Example Starter")

        with TemporaryDirectory() as tmpdir:
            cache = JsonCache(tmpdir)
            context = build_context(MockProvider(), request, cache=cache)

            self.assertEqual(context.pitcher.name, "Example Starter")
            self.assertTrue(list(Path(tmpdir).glob("*.json")))

    def test_cached_context_is_reused(self) -> None:
        request = ContextRequest.from_strings("2026-06-04", "Example Starter")

        with TemporaryDirectory() as tmpdir:
            cache = JsonCache(tmpdir)
            first = build_context(MockProvider(), request, cache=cache)
            second = build_context(MockProvider(sample_path="missing.json"), request, cache=cache)

            self.assertEqual(first.pitcher.name, second.pitcher.name)


if __name__ == "__main__":
    unittest.main()
