"""Extract per-token enrichment (Strong's, morph, lemma, gloss) for Mark from
STEP Bible's tagged NT (TAGNT) file.

Usage:
    python scripts/extract_step_enrichment.py \
        --source /path/to/STEPBible-Data/Translators\\ Amalgamated\\ OT+NT/<TAGNT file> \
        --book Mark
"""
from __future__ import annotations

import argparse
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
_TRANSLIT_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _clean_token(raw: str) -> str:
    return _TRANSLIT_RE.sub("", raw).strip()


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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path,
                    help="Path to STEP TAGNT ... CC-BY.txt file")
    ap.add_argument("--book", default="Mark")
    ap.add_argument("--out", type=Path, default=Path("data/enrichment/greek_strong.json"))
    args = ap.parse_args()

    data = parse_tagnt_file(args.source)
    filtered = filter_to_book(data, args.book)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote enrichment for %d verses to %s", len(filtered), args.out)


if __name__ == "__main__":
    main()
