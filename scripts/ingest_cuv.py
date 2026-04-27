"""Ingest Chinese Union Version (CUV) Simplified and Traditional from
eBible.org USFX → data/corpora/cuv_hans.csv and cuv_hant.csv.

Usage:
    python scripts/ingest_cuv.py --download --hans --hant
    python scripts/ingest_cuv.py --hans
    python scripts/ingest_cuv.py --hant
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "data" / "corpora"
CACHE = ROOT / "data" / "_ingest_cache"

SOURCES = {
    "hans": {
        "url":   "https://ebible.org/Scriptures/cmn-cu89s_usfx.zip",
        "zip":   CACHE / "cuv_hans_usfx.zip",
        "out":   CORPORA / "cuv_hans.csv",
    },
    "hant": {
        "url":   "https://ebible.org/Scriptures/cmn-cu89t_usfx.zip",
        "zip":   CACHE / "cuv_hant_usfx.zip",
        "out":   CORPORA / "cuv_hant.csv",
    },
}

BOOK_CODE = "MRK"
BOOK_NAME = "Mark"


def download(meta: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    url = meta["url"]
    out = meta["zip"]
    print(f"Downloading {url} ...", file=sys.stderr)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            out.write_bytes(response.read())
    except Exception as e:
        # Fallback to curl (handles macOS Python.org cert issues)
        print(f"  urllib failed ({e}); falling back to curl", file=sys.stderr)
        subprocess.run(["curl", "-sL", url, "-o", str(out)], check=True)


def extract_mark_from_usfx(zip_path: Path) -> list[tuple[int, int, str]]:
    """Walk USFX XML inside the zip; return [(chapter, verse, text), ...] for Mark.

    Uses a flush() helper that:
      - Skips emitting rows whose cleaned text is empty
      - Resets verse to 0 after each flush so trailing whitespace can't
        reattach to the prior verse.

    Mark 7:16 and 15:28 are absent from the CUV main text (the 1989 punctuation
    edition follows the critical text) but appear inside <f caller="-">...<fv>N</fv>
    text</f> footnotes. We recover those by walking the footnote markers and
    splicing them in to keep WEB versification parity.
    """
    rows: list[tuple[int, int, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        usfx_name = next(
            (n for n in zf.namelist() if "_usfx.xml" in n or n.endswith(".usfx.xml")),
            None,
        )
        if not usfx_name:
            raise RuntimeError(f"No usfx.xml in {zip_path}")
        xml = zf.read(usfx_name).decode("utf-8")

    book_re = re.compile(rf'<book\s+id="{BOOK_CODE}".*?</book>', re.DOTALL)
    m = book_re.search(xml)
    if not m:
        raise RuntimeError(f"Book {BOOK_CODE} not found")
    book_xml = m.group(0)

    # First pass: collect alt-verse readings from footnotes, keyed by (chapter, verse).
    # These are textual-criticism verses (e.g., Mark 7:16, 15:28) that some CUV
    # editions move out of the main text. We only fall back to these if the main
    # parse doesn't emit the verse.
    footnote_alts = _extract_footnote_verses(book_xml)

    state = {"chapter": 0, "verse": 0, "buf": []}

    def flush() -> None:
        if state["chapter"] and state["verse"] and state["buf"]:
            # Strip any footnote blocks from the buffer text — they contain
            # alt readings (numbered <fv>N</fv>) that don't belong to the
            # current verse. Then strip remaining tags.
            joined = " ".join(state["buf"])
            joined = re.sub(r"<f\s[^>]*>.*?</f>", " ", joined, flags=re.DOTALL)
            text = _clean(_strip_tags(joined))
            if text:
                rows.append((state["chapter"], state["verse"], text))
        state["buf"] = []
        state["verse"] = 0

    parts = re.split(
        r'(<c\s+id="\d+"[^/]*/>|<v\s+id="\d+"[^/]*/>|<ve\s*/>)',
        book_xml,
    )
    for tok in parts:
        if not tok:
            continue
        m_c = re.match(r'<c\s+id="(\d+)"[^/]*/>', tok)
        m_v = re.match(r'<v\s+id="(\d+)"[^/]*/>', tok)
        if m_c:
            flush()
            state["chapter"] = int(m_c.group(1))
            continue
        if m_v:
            flush()
            state["verse"] = int(m_v.group(1))
            continue
        if tok.startswith("<ve"):
            flush()
            continue
        state["buf"].append(tok)

    flush()

    # Splice in any missing verses from footnote alt readings, keeping rows sorted.
    have = {(c, v) for c, v, _ in rows}
    extras = [(c, v, t) for (c, v), t in footnote_alts.items() if (c, v) not in have]
    if extras:
        rows.extend(extras)
        rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def _extract_footnote_verses(book_xml: str) -> dict[tuple[int, int], str]:
    """Find <f>...<fv>N</fv>verse-text</f> blocks and return their alt-verse text.

    The chapter is inferred from the most recent <c id="N"/> tag preceding the
    footnote. Used to recover Mark 7:16 / 15:28 in the CUV-1989 critical edition.
    """
    found: dict[tuple[int, int], str] = {}
    cur_chapter = 0
    # Scan in order, tracking chapter as we go.
    token_re = re.compile(
        r'<c\s+id="(\d+)"[^/]*/>|<f\s[^>]*>(.*?)</f>',
        re.DOTALL,
    )
    fv_re = re.compile(r'<fv>(\d+)</fv>(.*)', re.DOTALL)
    for tm in token_re.finditer(book_xml):
        if tm.group(1) is not None:
            cur_chapter = int(tm.group(1))
            continue
        body = tm.group(2)
        fm = fv_re.search(body)
        if not fm:
            continue
        verse_num = int(fm.group(1))
        # Strip nested tags from the alt text.
        alt = _clean(_strip_tags(fm.group(2)))
        if alt and cur_chapter:
            found[(cur_chapter, verse_num)] = alt
    return found


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _clean(s: str) -> str:
    # Normalize all whitespace (incl. CJK spaces) to a single ASCII space, then trim.
    return re.sub(r"\s+", " ", s).strip()


def write_csv(rows: list[tuple[int, int, str]], out: Path) -> None:
    CORPORA.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "verse", "reference", "text"])
        for ch, v, text in rows:
            w.writerow([BOOK_NAME, ch, v, f"{BOOK_NAME} {ch}:{v}", text])
    print(f"Wrote {len(rows)} verses to {out}", file=sys.stderr)


def run(variant: str, do_download: bool) -> None:
    meta = SOURCES[variant]
    if do_download or not meta["zip"].exists():
        download(meta)
    rows = extract_mark_from_usfx(meta["zip"])
    if len(rows) < 670:
        print(f"WARN: only {len(rows)} Mark verses extracted from {variant}", file=sys.stderr)
    write_csv(rows, meta["out"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--hans", action="store_true")
    ap.add_argument("--hant", action="store_true")
    args = ap.parse_args()
    if not (args.hans or args.hant):
        ap.error("specify --hans and/or --hant")
    if args.hans:
        run("hans", args.download)
    if args.hant:
        run("hant", args.download)
    return 0


if __name__ == "__main__":
    sys.exit(main())
