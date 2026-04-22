"""Extract a range of verses from a Clementine USFX XML file into TSV.

USFX structure is roughly:
    <book id="MRK">
      <h>Marcus</h>
      <c id="1"/>
      <v id="1"/>Initium Evangelii...<ve/>
      ...
    </book>

In practice the verse text lives in the ``.tail`` of the ``<v>`` element
(and the ``.tail`` of any inline elements between ``<v>`` and ``<ve/>``).
This script streams the tree in document order, tracks the current book +
chapter + verse, and accumulates text into each verse's buffer.

Usage:
    python scripts/extract_vulgate_range.py \\
        --source /tmp/lat-clementine.usfx.xml \\
        --book MRK \\
        --include /tmp/mark_remap_ch8.txt \\
        --map-book Mark \\
        --map-chapter 9 --verse-offset -38 \\
        --out /tmp/vulgate_mark_9_from8.tsv

--include is a text file with one ``chapter verse`` pair per line (source
numbering, i.e. Clementine chapter/verse). Only those verses are written out.

--map-book / --map-chapter / --verse-offset let you relabel the output into
a target versification (e.g. NA28) without touching the source content.
"""
from __future__ import annotations

import argparse
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


def _tag(elem: ET.Element) -> str:
    t = elem.tag
    return t.split("}", 1)[1] if "}" in t else t


def iter_verses(usfx_path: Path, book_id: str):
    """Yield (chapter:int, verse:int, text:str) tuples for a given book.

    Walks the Mark element in document order. Chapter is set by ``<c id=N/>``,
    verse starts at ``<v id=N/>`` and ends at the next ``<v>`` or ``<ve/>``.
    """
    tree = ET.parse(str(usfx_path))
    root = tree.getroot()

    # Find the target book
    target_book: ET.Element | None = None
    for b in root.iter():
        if _tag(b) == "book":
            bid = b.get("id") or b.get("code") or ""
            if bid == book_id:
                target_book = b
                break
    if target_book is None:
        raise ValueError(f"Book {book_id!r} not found in {usfx_path}")

    cur_ch: int | None = None
    cur_v: int | None = None
    buf: list[str] = []

    def finish(ch, v, buf_local):
        text = "".join(buf_local).strip()
        text = re.sub(r"\s+", " ", text)
        return (ch, v, text) if text else None

    # iter() yields elements in document order; tails are sibling text.
    for elem in target_book.iter():
        et = _tag(elem)
        if et == "c":
            if cur_v is not None:
                out = finish(cur_ch, cur_v, buf)
                if out:
                    yield out
                buf = []
                cur_v = None
            cid = elem.get("id")
            cur_ch = int(cid) if cid else None
        elif et == "v":
            if cur_v is not None:
                out = finish(cur_ch, cur_v, buf)
                if out:
                    yield out
                buf = []
            vid = elem.get("id")
            if vid:
                m = re.match(r"\d+", vid)
                cur_v = int(m.group(0)) if m else None
            else:
                cur_v = None
        elif et == "ve":
            if cur_v is not None:
                out = finish(cur_ch, cur_v, buf)
                if out:
                    yield out
                buf = []
                cur_v = None
        # Capture text content following this element (belongs to current verse).
        if elem.tail and cur_v is not None:
            buf.append(elem.tail)
        # Capture direct .text too (mostly empty for markers, but safe).
        if elem.text and cur_v is not None and et not in {"v", "ve", "c"}:
            buf.append(elem.text)

    # Final flush for the last verse
    if cur_v is not None:
        out = finish(cur_ch, cur_v, buf)
        if out:
            yield out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--book", required=True, help="USFX book id, e.g. MRK")
    ap.add_argument("--include", required=True, type=Path,
                    help="Text file with one 'chapter verse' per line (source numbering)")
    ap.add_argument("--map-book", default=None,
                    help="Output book name, e.g. 'Mark'")
    ap.add_argument("--map-chapter", type=int, default=None,
                    help="Force all output verses into this chapter (used for remap)")
    ap.add_argument("--verse-offset", type=int, default=0,
                    help="Add this offset to each source verse number in the output label")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    wanted: set[tuple[int, int]] = set()
    with args.include.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ch, v = line.split()
            wanted.add((int(ch), int(v)))

    book_out = args.map_book or args.book
    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.out.open("w", encoding="utf-8") as out:
        for ch, v, text in iter_verses(args.source, args.book):
            if (ch, v) not in wanted:
                continue
            out_ch = args.map_chapter if args.map_chapter is not None else ch
            out_v = v + args.verse_offset
            out.write(f"{book_out} {out_ch}:{out_v}\t{text}\n")
            written += 1
    logger.info("Extracted %d matching verses (of %d wanted) to %s",
                written, len(wanted), args.out)


if __name__ == "__main__":
    main()
