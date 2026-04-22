"""Per-token enrichment lookup for Greek (STEP) and Peshitta (ARA) tokens."""
from __future__ import annotations

import json
from pathlib import Path


class _EnrichmentBase:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._data: dict[str, list[dict]] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def lookup(self, book: str, chapter: int, verse: int, token_idx: int) -> dict | None:
        ref = f"{book} {chapter}:{verse}"
        entries = self._data.get(ref)
        if not entries:
            return None
        for entry in entries:
            if entry.get("token_idx") == token_idx:
                return entry
        return None


class GreekEnrichment(_EnrichmentBase):
    """Strong's number, lemma, morph, English gloss per Greek token."""


class PeshittaEnrichment(_EnrichmentBase):
    """Root, sister roots, Hebrew/Arabic cognates per Peshitta token."""
