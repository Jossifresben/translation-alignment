"""Test STEP TAGNT parsing."""
from pathlib import Path

import pytest

from scripts.extract_step_enrichment import (
    parse_tagnt_line, parse_tagnt_file, filter_to_book
)


def test_parse_tagnt_line_extracts_token_and_strong():
    line = ("Mrk.1.1#01\tἈρχὴ\t[The] beginning\tG0746=N-NSF\tἀρχή=beginning\t"
            "NA28+NA27+Tyn+SBL+WH+Treg+TR+Byz")
    result = parse_tagnt_line(line)
    assert result["book"] == "Mark"
    assert result["chapter"] == 1
    assert result["verse"] == 1
    assert result["token_idx"] == 0  # #01 -> zero-based
    assert result["token"] == "Ἀρχὴ"
    assert result["strong"] == "G0746"
    assert result["morph"] == "N-NSF"
    assert result["lemma"] == "ἀρχή"
    assert result["gloss"] == "[The] beginning"


def test_parse_tagnt_file_returns_dict_keyed_by_ref():
    src = Path("tests/fixtures/tagnt_sample.txt")
    result = parse_tagnt_file(src)
    assert "Mark 1:1" in result
    assert len(result["Mark 1:1"]) == 3
    assert result["Mark 1:1"][0]["token"] == "Ἀρχὴ"
    assert "Mark 1:2" in result


def test_filter_to_book_limits_to_single_book():
    data = {"Mark 1:1": [], "John 1:1": [], "Mark 2:1": []}
    out = filter_to_book(data, "Mark")
    assert set(out.keys()) == {"Mark 1:1", "Mark 2:1"}


def test_parse_tagnt_line_returns_none_on_comment_or_blank():
    assert parse_tagnt_line("#Ref\tGreek\t...") is None
    assert parse_tagnt_line("") is None
    assert parse_tagnt_line("\n") is None


def test_strip_translit_removes_trailing_paren():
    from scripts.extract_step_enrichment import strip_translit
    assert strip_translit("Ἀρχὴ (Archē)") == "Ἀρχὴ"
    assert strip_translit("τοῦ (tou)") == "τοῦ"
    assert strip_translit("Ἀρχὴ") == "Ἀρχὴ"  # no-op when no parenthetical
    assert strip_translit("  τοῦ (tou)  ") == "τοῦ"


def test_write_corpus_csv_joins_tokens_per_verse(tmp_path):
    import csv
    from scripts.extract_step_enrichment import write_corpus_csv
    data = {
        "Mark 1:1": [
            {"token_idx": 0, "token": "Ἀρχὴ"},
            {"token_idx": 1, "token": "τοῦ"},
            {"token_idx": 2, "token": "εὐαγγελίου"},
        ],
        "Mark 1:2": [
            {"token_idx": 0, "token": "Καθὼς"},
        ],
    }
    out = tmp_path / "greek_nt.csv"
    write_corpus_csv(data, "Mark", out)
    with out.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["text"] == "Ἀρχὴ τοῦ εὐαγγελίου"
    assert rows[0]["reference"] == "Mark 1:1"
    assert rows[0]["book_order"] == "41"
