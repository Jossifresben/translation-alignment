"""Ingest Reina-Valera 1909 from eBible.org USFX → data/corpora/rv1909.csv.

Usage:
    python scripts/ingest_rv1909.py --download   # fetches USFX from eBible
    python scripts/ingest_rv1909.py              # re-runs from cached zip
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import ssl
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "data" / "corpora"
CACHE = ROOT / "data" / "_ingest_cache"
USFX_URL = "https://ebible.org/Scriptures/spaRV1909_usfx.zip"
USFX_ZIP = CACHE / "spaRV1909_usfx.zip"
OUT = CORPORA / "rv1909.csv"

BOOK_CODE = "MRK"
BOOK_NAME = "Mark"


def download() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {USFX_URL} ...", file=sys.stderr)
    req = urllib.request.Request(USFX_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            USFX_ZIP.write_bytes(response.read())
        return
    except (ssl.SSLError, urllib.error.URLError) as exc:
        # macOS Python.org builds often lack root certs. Fall back to curl,
        # which uses the system trust store.
        print(f"urllib failed ({exc}); falling back to curl", file=sys.stderr)
    if not shutil.which("curl"):
        raise RuntimeError("urllib failed and curl is not available")
    subprocess.run(
        [
            "curl", "-sSL", "-A", "Mozilla/5.0",
            "-o", str(USFX_ZIP), USFX_URL,
        ],
        check=True,
    )


def extract_mark_from_usfx(zip_path: Path) -> list[tuple[int, int, str]]:
    """Walk USFX XML inside the zip; return [(chapter, verse, text), ...] for Mark."""
    rows: list[tuple[int, int, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        usfx_name = next(
            (n for n in zf.namelist() if n.endswith("_usfx.xml") or n.endswith(".usfx.xml")),
            None,
        )
        if not usfx_name:
            raise RuntimeError(f"No .usfx.xml in {zip_path}")
        xml = zf.read(usfx_name).decode("utf-8")

    # Find the Mark book block
    book_re = re.compile(
        rf'<book\s+id="{BOOK_CODE}".*?</book>',
        re.DOTALL,
    )
    m = book_re.search(xml)
    if not m:
        raise RuntimeError(f"Book {BOOK_CODE} not found in USFX")
    book_xml = m.group(0)

    chapter = 0
    verse = 0
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, verse
        if chapter and verse and buf:
            text = _clean(" ".join(buf))
            if text:
                rows.append((chapter, verse, text))
        buf = []
        verse = 0

    parts = re.split(
        r'(<c\s+id="\d+"\s*/>|<v\s+id="\d+"\s*/>|<ve\s*/>)',
        book_xml,
    )
    for tok in parts:
        if not tok:
            continue
        m_c = re.match(r'<c\s+id="(\d+)"\s*/>', tok)
        m_v = re.match(r'<v\s+id="(\d+)"\s*/>', tok)
        if m_c:
            flush()
            chapter = int(m_c.group(1))
            continue
        if m_v:
            flush()
            verse = int(m_v.group(1))
            continue
        if tok.startswith("<ve"):
            flush()
            continue
        buf.append(_strip_tags(tok))

    flush()

    return rows


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def write_csv(rows: list[tuple[int, int, str]]) -> None:
    CORPORA.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "verse", "reference", "text"])
        for ch, v, text in rows:
            w.writerow([BOOK_NAME, ch, v, f"{BOOK_NAME} {ch}:{v}", text])
    print(f"Wrote {len(rows)} verses to {OUT}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    if args.download or not USFX_ZIP.exists():
        download()
    rows = extract_mark_from_usfx(USFX_ZIP)
    if len(rows) < 670:
        print(f"WARN: only {len(rows)} Mark verses extracted", file=sys.stderr)
    write_csv(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
