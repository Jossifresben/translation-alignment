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


def test_cuv_hans_exists():
    path = CORPORA / "cuv_hans.csv"
    assert path.exists(), "Run scripts/ingest_cuv.py --hans first"
    refs = _load_mark_refs(path)
    assert len(refs) >= 670, f"expected ~676 Mark verses, got {len(refs)}"


def test_cuv_hant_exists():
    path = CORPORA / "cuv_hant.csv"
    assert path.exists(), "Run scripts/ingest_cuv.py --hant first"
    refs = _load_mark_refs(path)
    assert len(refs) >= 670, f"expected ~676 Mark verses, got {len(refs)}"


def test_cuv_hans_versification_matches_web():
    cuv = _load_mark_refs(CORPORA / "cuv_hans.csv")
    web = _load_mark_refs(CORPORA / "web.csv")
    if not cuv:
        pytest.skip("cuv_hans.csv not yet ingested")
    missing = web - cuv
    extra = cuv - web
    assert not missing, f"CUV S missing {len(missing)} verses: {sorted(missing)[:10]}"
    assert not extra, f"CUV S has {len(extra)} extra verses: {sorted(extra)[:10]}"


def test_cuv_hant_versification_matches_web():
    cuv = _load_mark_refs(CORPORA / "cuv_hant.csv")
    web = _load_mark_refs(CORPORA / "web.csv")
    if not cuv:
        pytest.skip("cuv_hant.csv not yet ingested")
    missing = web - cuv
    extra = cuv - web
    assert not missing
    assert not extra


def test_cuv_hans_mark_1_1_contains_福音():
    path = CORPORA / "cuv_hans.csv"
    if not path.exists():
        pytest.skip()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("book") == "Mark" and row.get("chapter") == "1" and row.get("verse") == "1":
                assert "福音" in row["text"], f"got: {row['text']!r}"
                return
    pytest.fail("Mark 1:1 not found in cuv_hans.csv")
