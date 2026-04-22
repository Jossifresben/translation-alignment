"""Snapshot per-Peshitta-token root data from the Aramaic Root Atlas.

Requires a local clone of `aramaic-root-atlas` with its Python package importable.
We mirror ARA's own `_init()` wiring:

    corpus = AramaicCorpus()
    corpus.add_corpus('peshitta_nt', 'Peshitta NT', <ARA>/data/corpora/peshitta_nt.csv)
    corpus.load()
    extractor = RootExtractor(corpus, <ARA>/data/roots)
    extractor.build_index()
    cognates = CognateLookup(<ARA>/data/roots); cognates.load()

Then for each Peshitta token we compute:
    root          : Latin transliteration of the extracted Syriac root (e.g. "r-sh-m")
    sister_roots  : other Latin-key roots that share >=2 letters (ARA's own heuristic)
    cognates      : {hebrew, arabic} — first CognateWord for each, transliteration form

If extraction fails for a token, it becomes {root: None, sister_roots: [], cognates: {}}.

Usage:
    python scripts/snapshot_ara_roots.py \\
        --ara-path /path/to/aramaic-root-atlas --book Mark
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


# -------- pure helpers (testable, unchanged in shape) --------

def tokenize_verse(text: str) -> list[str]:
    return text.split()


def build_verse_entry(text: str, root_fn: Callable[[str], dict | None]) -> list[dict]:
    entries: list[dict] = []
    for i, tok in enumerate(tokenize_verse(text)):
        try:
            info = root_fn(tok)
        except Exception:
            info = None
        if info is None:
            info = {"root": None, "sister_roots": [], "cognates": {}}
        entries.append({
            "token_idx": i,
            "token": tok,
            "root": info.get("root"),
            "sister_roots": info.get("sister_roots", []),
            "cognates": info.get("cognates", {}),
        })
    return entries


# -------- ARA adapter --------

def _syriac_root_to_latin_key(root_syriac: str, translit_fn) -> str:
    """Convert a Syriac-script root like ܪܫܡ into ARA's dash key 'r-sh-m'.

    `translit_fn` is `transliterate_syriac` from ARA. Alaph (ܐ) maps to "'" in
    ARA's simple transliteration; cognates.json uses "a" for that slot, so we
    normalize "'" → "a" to align with CognateLookup keys.
    """
    parts = []
    for ch in root_syriac:
        t = translit_fn(ch)
        if not t:
            continue
        parts.append("a" if t == "'" else t)
    return "-".join(parts)


def _sister_root_keys(root_key: str, all_keys: list[str]) -> list[str]:
    """Return other 3-letter keys sharing >=2 positional letters with root_key.

    Mirrors ARA app.py `api_root` logic (sister roots block around line 1657).
    """
    parts = root_key.split("-")
    if len(parts) != 3:
        return []
    sisters: list[str] = []
    for other in all_keys:
        if other == root_key:
            continue
        op = other.split("-")
        if len(op) != 3:
            continue
        shared = sum(1 for a, b in zip(parts, op) if a == b)
        if shared >= 2:
            sisters.append(other)
    return sisters


def _load_ara_root_fn(ara_path: Path) -> Callable[[str], dict | None]:
    """Build an ARA-backed callable: token → {root, sister_roots, cognates} | None.

    Wires up AramaicCorpus + RootExtractor + CognateLookup the same way ARA's
    own app.py `_init()` does.
    """
    sys.path.insert(0, str(ara_path))
    try:
        from aramaic_core.corpus import AramaicCorpus
        from aramaic_core.extractor import RootExtractor
        from aramaic_core.cognates import CognateLookup
        from aramaic_core.characters import transliterate_syriac
    except Exception as e:
        logger.warning("Could not import aramaic_core: %s. Returning null extractor.", e)
        return lambda _t: None

    data_dir = ara_path / "data"
    roots_dir = data_dir / "roots"
    nt_csv = data_dir / "corpora" / "peshitta_nt.csv"
    if not nt_csv.exists():
        logger.error("ARA Peshitta NT CSV missing at %s. Returning null extractor.", nt_csv)
        return lambda _t: None

    corpus = AramaicCorpus()
    corpus.add_corpus("peshitta_nt", "Peshitta NT", str(nt_csv))
    # Load OT + Biblical Aramaic too, if present, so the root index is richer.
    ot_csv = data_dir / "corpora" / "peshitta_ot.csv"
    if ot_csv.exists():
        corpus.add_corpus("peshitta_ot", "Peshitta OT", str(ot_csv))
    ba_csv = data_dir / "corpora" / "biblical_aramaic.csv"
    if ba_csv.exists():
        corpus.add_corpus("biblical_aramaic", "Biblical Aramaic", str(ba_csv))
    corpus.load()

    extractor = RootExtractor(corpus, str(roots_dir))
    logger.info("Building ARA root index (this may take a few seconds)...")
    extractor.build_index()

    cognates = CognateLookup(str(roots_dir))
    cognates.load()
    all_cognate_keys = cognates.get_all_keys()

    # Memoize per surface form so verses with repeated tokens are fast.
    cache: dict[str, dict | None] = {}

    def root_fn(token: str) -> dict | None:
        if token in cache:
            return cache[token]

        syriac_root = extractor.lookup_word_root(token)
        if not syriac_root:
            cache[token] = None
            return None

        root_key = _syriac_root_to_latin_key(syriac_root, transliterate_syriac)
        sisters = _sister_root_keys(root_key, all_cognate_keys)

        cog_entry = cognates.lookup(syriac_root)
        cog_out: dict[str, str] = {}
        if cog_entry is not None:
            if cog_entry.hebrew:
                hw = cog_entry.hebrew[0]
                cog_out["hebrew"] = hw.word or hw.transliteration
            if cog_entry.arabic:
                aw = cog_entry.arabic[0]
                cog_out["arabic"] = aw.word or aw.transliteration

        result = {
            "root": root_key,
            "sister_roots": sisters,
            "cognates": cog_out,
        }
        cache[token] = result
        return result

    return root_fn


# -------- main --------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ara-path", required=True, type=Path)
    ap.add_argument("--book", default="Mark")
    ap.add_argument("--csv", type=Path, default=Path("data/corpora/peshitta_nt.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/enrichment/peshitta_roots.json"))
    args = ap.parse_args()

    root_fn = _load_ara_root_fn(args.ara_path)
    output: dict[str, list[dict]] = {}
    with args.csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # Auto-detect text column (peshitta_nt.csv from ARA uses 'syriac')
        text_col = None
        first_row = next(reader)
        for cand in ("text", "syriac", "latin", "hebrew", "greek"):
            if cand in first_row:
                text_col = cand
                break
        if text_col is None:
            logger.error("No text column found in CSV")
            sys.exit(1)
        rows = [first_row] + list(reader)
        for row in rows:
            if row["book"] != args.book:
                continue
            ref = row["reference"]
            output[ref] = build_verse_entry(row[text_col], root_fn)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    non_null = sum(1 for entries in output.values() for e in entries if e.get("root"))
    total = sum(len(entries) for entries in output.values())
    logger.info("Wrote %d verses (%d/%d tokens with non-null roots) to %s",
                len(output), non_null, total, args.out)


if __name__ == "__main__":
    main()
