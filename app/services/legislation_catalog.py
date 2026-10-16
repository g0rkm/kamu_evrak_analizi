"""Mevzuat metadata veritabanı (app/data/legislation.json)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("legislation_catalog")

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "legislation.json"


class LegislationCatalog:
    def __init__(self, entries: list[dict]) -> None:
        self.entries = entries

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> LegislationCatalog:
        try:
            with path.open("r", encoding="utf-8") as f:
                return cls(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("Mevzuat veritabanı yüklenemedi (%s): %s", path, exc)
            return cls([])

    def __len__(self) -> int:
        return len(self.entries)

    def to_prompt(self) -> str:
        return json.dumps(self.entries, ensure_ascii=False, separators=(",", ":")) if self.entries else "[]"
