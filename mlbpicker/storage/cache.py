from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any


class JsonCache:
    def __init__(self, cache_dir: Path | str = ".mlbpicker_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def read(self, key: str) -> dict[str, Any] | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, key: str, payload: Any) -> Path:
        path = self._path_for(key)
        path.write_text(
            json.dumps(_to_jsonable(payload), indent=2, default=str),
            encoding="utf-8",
        )
        return path

    def _path_for(self, key: str) -> Path:
        clean = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in key)
        return self.cache_dir / f"{clean}.json"


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value

