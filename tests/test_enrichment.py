"""Test enrichment data lookup."""
import json
from pathlib import Path

import pytest

from translation_core.enrichment import GreekEnrichment, PeshittaEnrichment


@pytest.fixture
def greek_data(tmp_path: Path) -> Path:
    p = tmp_path / "greek.json"
    p.write_text(json.dumps({
        "Mark 1:1": [
            {"token_idx": 0, "token": "Ἀρχὴ", "strong": "G0746",
             "morph": "N-NSF", "lemma": "ἀρχή", "gloss": "[The] beginning"},
            {"token_idx": 1, "token": "τοῦ", "strong": "G3588",
             "morph": "T-GSN", "lemma": "ὁ", "gloss": "[of] the"},
        ]
    }, ensure_ascii=False), encoding="utf-8")
    return p


def test_greek_lookup_returns_entry(greek_data):
    ge = GreekEnrichment(path=greek_data)
    entry = ge.lookup("Mark", 1, 1, 0)
    assert entry is not None
    assert entry["strong"] == "G0746"
    assert entry["lemma"] == "ἀρχή"


def test_greek_lookup_returns_none_for_missing(greek_data):
    ge = GreekEnrichment(path=greek_data)
    assert ge.lookup("Mark", 1, 1, 99) is None
    assert ge.lookup("Mark", 99, 99, 0) is None


def test_peshitta_lookup_returns_entry(tmp_path):
    p = tmp_path / "peshitta.json"
    p.write_text(json.dumps({
        "Mark 1:1": [
            {"token_idx": 0, "token": "ܪܫܐ", "root": "R-SH-A",
             "sister_roots": ["R-SH-M"], "cognates": {"hebrew": "ראש", "arabic": "رأس"}},
        ]
    }, ensure_ascii=False), encoding="utf-8")
    pe = PeshittaEnrichment(path=p)
    entry = pe.lookup("Mark", 1, 1, 0)
    assert entry is not None
    assert entry["root"] == "R-SH-A"
    assert "R-SH-M" in entry["sister_roots"]
