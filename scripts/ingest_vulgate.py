"""Ingest the Clementine Vulgate (Mark only for MVP) into our standard CSV format.

Input format expected: TSV with one verse per line, 'Mark 1:1\\tInitium...'.

The source file must be downloaded manually from a public-domain Clementine Vulgate
corpus. Place it at the path given via --source.

Usage:
    python scripts/ingest_vulgate.py --source /path/to/vulgate_nt.tsv --book Mark
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
from pathlib import Path
from typing import Iterator

from scripts.ingest_ara_corpora import BOOK_ORDER, REFERENCE_RE

logger = logging.getLogger(__name__)

LINE_RE = re.compile(r"^(?P<ref>.+?\s+\d+:\d+)\t(?P<text>.+)$")


def parse_vulgate_file(path: Path) -> Iterator[dict]:
    with Path(path).open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            m = LINE_RE.match(line)
            if not m:
                logger.debug("Skipping malformed line %d: %r", lineno, line[:80])
                continue
            ref = m.group("ref")
            ref_match = REFERENCE_RE.match(ref)
            if not ref_match:
                logger.debug("Skipping line with unparseable ref at %d: %r", lineno, ref)
                continue
            book = ref_match.group("book")
            if book not in BOOK_ORDER:
                continue
            yield {
                "book_order": BOOK_ORDER[book],
                "book": book,
                "chapter": int(ref_match.group("ch")),
                "verse": int(ref_match.group("v")),
                "reference": ref,
                "text": m.group("text"),
            }


def filter_to_book(rows: Iterator[dict], book: str) -> Iterator[dict]:
    for row in rows:
        if row["book"] == book:
            yield row


def write_csv(rows: list[dict], out_path: Path) -> None:
    fieldnames = ["book_order", "book", "chapter", "verse", "reference", "text"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["book_order"], r["chapter"], r["verse"]))
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    logger.info("Wrote %d rows to %s", len(rows), out_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path,
                    help="Path to the Clementine Vulgate TSV source file")
    ap.add_argument("--book", default=None,
                    help="Optional: filter to a single book (e.g., 'Mark')")
    ap.add_argument("--out", type=Path, default=Path("data/corpora/vulgate.csv"))
    args = ap.parse_args()

    rows = list(parse_vulgate_file(args.source))
    if args.book:
        rows = list(filter_to_book(rows, args.book))
    write_csv(rows, args.out)


if __name__ == "__main__":
    main()
