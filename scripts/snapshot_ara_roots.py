"""Snapshot per-Peshitta-token root data from the Aramaic Root Atlas.

Requires a local clone of `aramaic-root-atlas` with its Python package importable.
If the ARA API doesn't match our expectations, emits a stub with empty entries.

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


def _load_ara_root_fn(ara_path: Path) -> Callable[[str], dict | None]:
    """Best-effort: probe ARA's aramaic_core for a Syriac root-extraction callable.

    Returns a callable that takes a Syriac word and returns {root, sister_roots, cognates}.
    If nothing usable is found, returns a function that always returns None.
    """
    sys.path.insert(0, str(ara_path))
    try:
        import aramaic_core
    except Exception as e:
        logger.warning("Could not import aramaic_core: %s. Returning null extractor.", e)
        return lambda _: None

    # Try common entry points in order of likelihood.
    try:
        from aramaic_core.extractor import RootExtractor
        extractor = RootExtractor()
        def root_fn(token: str) -> dict | None:
            try:
                root = extractor.extract(token) if hasattr(extractor, "extract") else None
            except Exception:
                return None
            if not root:
                return None
            sisters = []
            if hasattr(extractor, "sister_roots"):
                try:
                    sisters = list(extractor.sister_roots(root)) or []
                except Exception:
                    pass
            return {"root": str(root), "sister_roots": sisters, "cognates": {}}
        return root_fn
    except Exception as e:
        logger.warning("RootExtractor import/call failed: %s. Returning null extractor.", e)
        return lambda _: None


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
    logger.info("Wrote %d verses (%d tokens with non-null roots) to %s",
                len(output), non_null, args.out)


if __name__ == "__main__":
    main()
