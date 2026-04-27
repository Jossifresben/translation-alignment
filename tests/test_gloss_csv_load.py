"""Tests for verse-text CSVs used as gloss sources."""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "data" / "corpora"


def _load_mark_refs(path: Path) -> set[tuple[int, int]]:
    """Return {(chapter, verse), ...} for Mark from a corpora CSV."""
    refs: set[tuple[int, int]] = set()
    if not path.exists():
        return refs
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("book") == "Mark":
                refs.add((int(row["chapter"]), int(row["verse"])))
    return refs


def test_rv1909_exists_and_has_mark():
    path = CORPORA / "rv1909.csv"
    assert path.exists(), "Run scripts/ingest_rv1909.py first"
    refs = _load_mark_refs(path)
    assert len(refs) >= 670, f"expected ~676 Mark verses, got {len(refs)}"


def test_rv1909_mark_matches_web_versification():
    """RV1909 must cover the same (chapter, verse) tuples as web.csv for Mark."""
    rv = _load_mark_refs(CORPORA / "rv1909.csv")
    web = _load_mark_refs(CORPORA / "web.csv")
    if not rv:
        pytest.skip("rv1909.csv not yet ingested")
    missing = web - rv
    extra = rv - web
    assert not missing, f"RV1909 missing {len(missing)} Mark verses: {sorted(missing)[:10]}"
    assert not extra, f"RV1909 has {len(extra)} verses not in web.csv: {sorted(extra)[:10]}"


def test_rv1909_mark_1_1_contains_evangelio():
    path = CORPORA / "rv1909.csv"
    if not path.exists():
        pytest.skip("rv1909.csv not yet ingested")
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("book") == "Mark" and row.get("chapter") == "1" and row.get("verse") == "1":
                assert "evangelio" in row["text"].lower(), f"got: {row['text']!r}"
                return
    pytest.fail("Mark 1:1 not found in rv1909.csv")
