"""Load and look up per-verse alignment JSON from the data/alignments tree."""
from __future__ import annotations

import json
from pathlib import Path

from translation_core.schema import validate_alignment


class AlignmentStore:
    """Serves alignment JSON from `<root>/<book_lower>/<chapter>/<verse>.json`.

    Validates each JSON on first load and caches the parsed dict in memory.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._cache: dict[tuple[str, int, int], dict] = {}

    def _path_for(self, book: str, chapter: int, verse: int) -> Path:
        return self.root / book.lower() / str(chapter) / f"{verse}.json"

    def get(self, book: str, chapter: int, verse: int) -> dict | None:
        key = (book, chapter, verse)
        if key in self._cache:
            return self._cache[key]
        path = self._path_for(book, chapter, verse)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_alignment(data)
        self._cache[key] = data
        return data

    def has(self, book: str, chapter: int, verse: int) -> bool:
        return self._path_for(book, chapter, verse).exists()
