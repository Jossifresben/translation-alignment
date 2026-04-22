"""Ingest WEB (World English Bible) from ARA's translations_en.json into corpus CSV.

The WEB text provides the full-verse English gloss shown at the top of each verse view.

Usage:
    python scripts/ingest_web.py --ara-path /path/to/aramaic-root-atlas
"""
from __future__ import annotations

import argparse
import logging
import json
from pathlib import Path

from scripts.ingest_ara_corpora import (
    BOOK_ORDER, parse_reference, write_csv,
)

logger = logging.getLogger(__name__)


def convert_en_to_rows(raw: dict[str, str]):
    for ref, text in raw.items():
        try:
            book, ch, v = parse_reference(ref)
        except ValueError:
            continue
        if book not in BOOK_ORDER:
            continue
        yield {
            "book_order": BOOK_ORDER[book],
            "book": book,
            "chapter": ch,
            "verse": v,
            "reference": ref,
            "text": text,
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ara-path", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/corpora/web.csv"))
    args = ap.parse_args()

    src = args.ara_path / "data" / "translations" / "translations_en.json"
    if not src.exists():
        raise FileNotFoundError(f"WEB source not found at {src}")
    raw = json.loads(src.read_text(encoding="utf-8"))
    rows = list(convert_en_to_rows(raw))
    write_csv(rows, args.out)


if __name__ == "__main__":
    main()
