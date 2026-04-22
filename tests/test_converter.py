"""Test the alignment → designer-shape converter."""
import json
from pathlib import Path

import pytest

from translation_core.converter import (
    convert_alignment_to_verse,
    _split_punctuation,
    _normalize_pericope_lookup,
)


def test_split_punctuation_trailing():
    assert _split_punctuation("θεοῦ.") == [{"t": "θεοῦ"}, {"t": ".", "punct": True}]


def test_split_punctuation_solo():
    assert _split_punctuation(",") == [{"t": ",", "punct": True}]


def test_split_punctuation_no_punct():
    assert _split_punctuation("Ἀρχή") == [{"t": "Ἀρχή"}]


def test_pericope_lookup_hit():
    pericopes = {"Mark": [{"range": [[13, 1], [13, 37]], "title": "Little Apocalypse"}]}
    assert _normalize_pericope_lookup(pericopes, "Mark", 13, 14) == "Little Apocalypse"


def test_pericope_lookup_miss():
    pericopes = {"Mark": [{"range": [[13, 1], [13, 37]], "title": "Little Apocalypse"}]}
    assert _normalize_pericope_lookup(pericopes, "Mark", 1, 1) is None


@pytest.fixture
def min_alignment():
    return {
        "ref": "Mark 1:1", "chapter": 1, "verse": 1,
        "traditions": {
            "greek_nt": {"tokens": ["Ἀρχὴ", "τοῦ", "εὐαγγελίου."]},
            "peshitta": {"tokens": ["ܪܫܐ", "ܕܐܘܢܓܠܝܘܢ"]},
            "vulgate":  {"tokens": ["Initium", "evangelii."]},
        },
        "alignment": [
            {"greek_nt": [0], "peshitta": [0], "vulgate": [0], "variant": "aligned"},
            {"greek_nt": [1, 2], "peshitta": [1], "vulgate": [1], "variant": "minor",
             "note": "Construction differs: Greek uses genitive article + noun; Syriac and Latin use a single possessive."},
        ],
        "meta": {"generated_by": "test", "generated_at": "2026-04-22",
                 "confidence": 0.9, "schema_version": 1},
    }


def test_convert_returns_designer_shape(min_alignment):
    pericopes = {"Mark": [{"range": [[1, 1], [1, 8]], "title": "Proclamation of John the Baptist"}]}
    result = convert_alignment_to_verse(
        min_alignment, book="Mark", book_lower="mark",
        prev_cv=None, next_cv=(1, 2), pericopes=pericopes,
        testament="New Testament",
        gloss_en="The beginning of the gospel of Jesus Christ.",
    )
    assert result["book"] == "Mark"
    assert result["pericope"] == "Proclamation of John the Baptist"
    assert result["testament"] == "New Testament"
    assert result["gloss_en"].startswith("The beginning")
    assert result["prev"] is None
    assert result["next"]["verse"] == 2
    ids = [w["id"] for w in result["witnesses"]]
    assert ids == ["grk", "syr", "vul"]
    grk = result["witnesses"][0]
    # At least one token carries an align id starting with "g"
    assert any(t.get("a", "").startswith("g") for t in grk["tokens"] if t.get("a"))
    # Punctuation split: the trailing "." on εὐαγγελίου becomes its own punct token
    punct_tokens = [t for t in grk["tokens"] if t.get("punct")]
    assert any(t["t"] == "." for t in punct_tokens)
    # Variants list has one entry (the minor group)
    assert len(result["variants"]) == 1
    v = result["variants"][0]
    assert v["id"].startswith("v")
    assert v["summary"].startswith("Construction differs")
    assert set(v["witnesses"]) == {"grk", "syr", "vul"}
