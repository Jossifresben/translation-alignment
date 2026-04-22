"""Corpus loading and verse lookup.

A `Corpus` wraps a single tradition's CSV; a `CorpusRegistry` holds multiple
corpora keyed by tradition_id.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Corpus:
    tradition_id: str
    label: str
    csv_path: Path
    _index: dict[tuple[str, int, int], str] = field(default_factory=dict, init=False, repr=False)
    _chapters: dict[tuple[str, int], list[int]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        with Path(self.csv_path).open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                book = row["book"]
                ch = int(row["chapter"])
                v = int(row["verse"])
                self._index[(book, ch, v)] = row["text"]
                self._chapters.setdefault((book, ch), []).append(v)
        for key in self._chapters:
            self._chapters[key].sort()

    def get(self, book: str, chapter: int, verse: int) -> str | None:
        """Return verse text or None if not present."""
        return self._index.get((book, chapter, verse))

    def verses_in_chapter(self, book: str, chapter: int) -> list[int]:
        """Return sorted list of verse numbers present in the given chapter."""
        return list(self._chapters.get((book, chapter), []))

    def has_verse(self, book: str, chapter: int, verse: int) -> bool:
        return (book, chapter, verse) in self._index


class CorpusRegistry:
    """Holds multiple corpora; preserves insertion order."""

    def __init__(self) -> None:
        self._corpora: dict[str, Corpus] = {}

    def add(self, tradition_id: str, label: str, csv_path: Path) -> None:
        self._corpora[tradition_id] = Corpus(tradition_id, label, csv_path)

    def get(self, tradition_id: str) -> Corpus:
        return self._corpora[tradition_id]

    def tradition_ids(self) -> list[str]:
        return list(self._corpora.keys())
