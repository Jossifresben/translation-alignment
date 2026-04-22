"""Ingest Greek NT (JSON) and Peshitta NT (CSV) from the Aramaic Root Atlas repo
into our standard corpus CSV format.

Usage:
    python scripts/ingest_ara_corpora.py --ara-path /path/to/aramaic-root-atlas
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Canonical Protestant NT book order (matches ARA's convention)
BOOK_ORDER: dict[str, int] = {
    "Matthew": 40, "Mark": 41, "Luke": 42, "John": 43, "Acts": 44,
    "Romans": 45, "1 Corinthians": 46, "2 Corinthians": 47,
    "Galatians": 48, "Ephesians": 49, "Philippians": 50, "Colossians": 51,
    "1 Thessalonians": 52, "2 Thessalonians": 53,
    "1 Timothy": 54, "2 Timothy": 55, "Titus": 56, "Philemon": 57,
    "Hebrews": 58, "James": 59,
    "1 Peter": 60, "2 Peter": 61,
    "1 John": 62, "2 John": 63, "3 John": 64,
    "Jude": 65, "Revelation": 66,
}

REFERENCE_RE = re.compile(r"^(?P<book>.+?)\s+(?P<ch>\d+):(?P<v>\d+)$")


def parse_reference(ref: str) -> tuple[str, int, int]:
    """Parse 'Mark 1:1' or '1 Corinthians 13:4' into (book, chapter, verse)."""
    m = REFERENCE_RE.match(ref.strip())
    if not m:
        raise ValueError(f"Unparseable reference: {ref!r}")
    return m.group("book"), int(m.group("ch")), int(m.group("v"))


def convert_greek_translations_to_rows(raw: dict[str, str]) -> Iterator[dict]:
    """Convert {'Mark 1:1': 'text', ...} into CSV rows. Skips NT-only books;
    malformed keys are logged and skipped."""
    for ref, text in raw.items():
        try:
            book, ch, v = parse_reference(ref)
        except ValueError:
            logger.warning("Skipping malformed reference: %r", ref)
            continue
        if book not in BOOK_ORDER:
            continue  # OT book or unknown
        yield {
            "book_order": BOOK_ORDER[book],
            "book": book,
            "chapter": ch,
            "verse": v,
            "reference": ref,
            "text": text,
        }


def write_csv(rows: list[dict], out_path: Path) -> None:
    fieldnames = ["book_order", "book", "chapter", "verse", "reference", "text"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in sorted(rows, key=lambda r: (r["book_order"], r["chapter"], r["verse"])):
            w.writerow(row)
    logger.info("Wrote %d rows to %s", len(rows), out_path)


def ingest_greek(ara_path: Path, out_dir: Path) -> None:
    src = ara_path / "data" / "translations" / "translations_el.json"
    if not src.exists():
        raise FileNotFoundError(f"Greek NT source not found at {src}")
    raw = json.loads(src.read_text(encoding="utf-8"))
    rows = list(convert_greek_translations_to_rows(raw))
    write_csv(rows, out_dir / "greek_nt.csv")


def ingest_peshitta(ara_path: Path, out_dir: Path) -> None:
    src = ara_path / "data" / "corpora" / "peshitta_nt.csv"
    if not src.exists():
        raise FileNotFoundError(f"Peshitta NT source not found at {src}")
    out = out_dir / "peshitta_nt.csv"
    shutil.copy(src, out)
    logger.info("Copied %s -> %s", src, out)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ara-path", required=True, type=Path,
                    help="Path to the aramaic-root-atlas repo root")
    ap.add_argument("--out-dir", type=Path, default=Path("data/corpora"))
    args = ap.parse_args()

    ingest_greek(args.ara_path, args.out_dir)
    ingest_peshitta(args.ara_path, args.out_dir)


if __name__ == "__main__":
    main()
