"""Extract per-token enrichment (Strong's, morph, lemma, gloss) for Mark from
STEP Bible's tagged NT (TAGNT) file.

Usage:
    python scripts/extract_step_enrichment.py \
        --source /path/to/STEPBible-Data/Translators\\ Amalgamated\\ OT+NT/<TAGNT file> \
        --book Mark
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

STEP_BOOK_MAP: dict[str, str] = {
    "Mat": "Matthew", "Mrk": "Mark", "Luk": "Luke", "Jhn": "John",
    "Act": "Acts",
    "Rom": "Romans", "1Co": "1 Corinthians", "2Co": "2 Corinthians",
    "Gal": "Galatians", "Eph": "Ephesians", "Php": "Philippians", "Col": "Colossians",
    "1Th": "1 Thessalonians", "2Th": "2 Thessalonians",
    "1Ti": "1 Timothy", "2Ti": "2 Timothy", "Tit": "Titus", "Phm": "Philemon",
    "Heb": "Hebrews", "Jas": "James",
    "1Pe": "1 Peter", "2Pe": "2 Peter",
    "1Jn": "1 John", "2Jn": "2 John", "3Jn": "3 John",
    "Jud": "Jude", "Rev": "Revelation",
}

REF_RE = re.compile(r"^(?P<book>[A-Za-z0-9]+)\.(?P<ch>\d+)\.(?P<v>\d+)#(?P<tok>\d+)")

# The STEP TAGNT 'Greek' column sometimes includes a transliteration in
# parentheses, e.g. 'Ἀρχὴ (Archē)'. Strip that to recover the bare Greek token.
# The parenthetical contains only Latin/Greek letters (no digits/punctuation),
# which distinguishes it from rare cases where parens are part of the token.
_TRANSLIT_RE = re.compile(r"\s*\([A-Za-zĀ-ſ\u0100-\u024F\u0370-\u03FF]+\)\s*$")


def strip_translit(s: str) -> str:
    """Remove a trailing ` (Latin)` transliteration parenthetical from a Greek token.

    Examples:
        "Ἀρχὴ (Archē)" -> "Ἀρχὴ"
        "τοῦ (tou)"    -> "τοῦ"
        "Ἀρχὴ"         -> "Ἀρχὴ" (no-op)
    """
    return _TRANSLIT_RE.sub("", s).strip()


def _clean_token(raw: str) -> str:
    return strip_translit(raw)


def parse_tagnt_line(line: str) -> dict | None:
    if not line or line.startswith("#") or line.strip() == "":
        return None
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 5:
        return None
    ref_m = REF_RE.match(parts[0])
    if not ref_m:
        return None
    book_code = ref_m.group("book")
    book = STEP_BOOK_MAP.get(book_code)
    if not book:
        return None
    strong_morph = parts[3] if len(parts) > 3 else ""
    strong, _, morph = strong_morph.partition("=")
    lemma_gloss = parts[4] if len(parts) > 4 else ""
    lemma, _, _lemma_gloss = lemma_gloss.partition("=")
    return {
        "book": book,
        "chapter": int(ref_m.group("ch")),
        "verse": int(ref_m.group("v")),
        "token_idx": int(ref_m.group("tok")) - 1,
        "token": _clean_token(parts[1]),
        "gloss": parts[2] if len(parts) > 2 else "",
        "strong": strong,
        "morph": morph,
        "lemma": lemma,
    }


def parse_tagnt_file(path: Path) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            entry = parse_tagnt_line(line)
            if not entry:
                continue
            ref = f"{entry['book']} {entry['chapter']}:{entry['verse']}"
            result.setdefault(ref, []).append({
                "token_idx": entry["token_idx"],
                "token": entry["token"],
                "strong": entry["strong"],
                "morph": entry["morph"],
                "lemma": entry["lemma"],
                "gloss": entry["gloss"],
            })
    for entries in result.values():
        entries.sort(key=lambda e: e["token_idx"])
    return result


def filter_to_book(data: dict[str, list[dict]], book: str) -> dict[str, list[dict]]:
    prefix = f"{book} "
    return {k: v for k, v in data.items() if k.startswith(prefix)}


_REF_SPLIT_RE = re.compile(r"^(?P<book>.+?)\s+(?P<ch>\d+):(?P<v>\d+)$")


def write_corpus_csv(
    data: dict[str, list[dict]],
    book_filter: str | None,
    out_path: Path,
) -> None:
    """Emit a corpus CSV by joining each verse's tokens with spaces.

    The resulting CSV matches the schema of ``data/corpora/greek_nt.csv``:
    ``book_order, book, chapter, verse, reference, text``. Because the tokens
    come from the same STEP TAGNT source as the enrichment JSON, the
    tokenization of the ``text`` column matches the enrichment per-token
    indices by construction.
    """
    # Import lazily to avoid a hard dependency when this function is unused.
    # Support both `python -m scripts.extract_step_enrichment` and
    # `python scripts/extract_step_enrichment.py` invocations.
    try:
        from scripts.ingest_ara_corpora import BOOK_ORDER
    except ModuleNotFoundError:
        import sys
        repo_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(repo_root))
        from scripts.ingest_ara_corpora import BOOK_ORDER

    rows: list[dict] = []
    for ref, entries in data.items():
        m = _REF_SPLIT_RE.match(ref)
        if not m:
            logger.warning("Skipping unparseable ref: %r", ref)
            continue
        book = m.group("book")
        if book_filter and book != book_filter:
            continue
        if book not in BOOK_ORDER:
            logger.warning("Skipping unknown book: %r", book)
            continue
        chapter = int(m.group("ch"))
        verse = int(m.group("v"))
        tokens = [e["token"] for e in sorted(entries, key=lambda x: x["token_idx"])]
        text = " ".join(tokens)
        rows.append({
            "book_order": BOOK_ORDER[book],
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "reference": ref,
            "text": text,
        })

    rows.sort(key=lambda r: (r["book_order"], r["chapter"], r["verse"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["book_order", "book", "chapter", "verse", "reference", "text"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    logger.info("Wrote corpus for %d verses to %s", len(rows), out_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path,
                    help="Path to STEP TAGNT ... CC-BY.txt file")
    ap.add_argument("--book", default="Mark")
    ap.add_argument("--out", type=Path, default=Path("data/enrichment/greek_strong.json"))
    ap.add_argument("--emit-corpus", type=Path, default=None,
                    help="If set, also emit a corpus CSV (joined tokens) to this path.")
    args = ap.parse_args()

    data = parse_tagnt_file(args.source)
    filtered = filter_to_book(data, args.book)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote enrichment for %d verses to %s", len(filtered), args.out)

    if args.emit_corpus is not None:
        write_corpus_csv(data, args.book, args.emit_corpus)


if __name__ == "__main__":
    main()
