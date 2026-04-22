"""Test the ARA-to-CSV ingestion of Greek NT and Peshitta NT."""
import csv
import json
from pathlib import Path

from scripts.ingest_ara_corpora import (
    parse_reference,
    convert_greek_translations_to_rows,
    BOOK_ORDER,
)


def test_parse_reference_handles_single_word_books():
    assert parse_reference("Mark 1:1") == ("Mark", 1, 1)
    assert parse_reference("John 3:16") == ("John", 3, 16)


def test_parse_reference_handles_multi_word_books():
    assert parse_reference("1 Corinthians 13:4") == ("1 Corinthians", 13, 4)
    assert parse_reference("Song of Solomon 2:1") == ("Song of Solomon", 2, 1)


def test_book_order_contains_all_27_nt_books():
    assert len(BOOK_ORDER) == 27
    assert BOOK_ORDER["Matthew"] == 40
    assert BOOK_ORDER["Mark"] == 41
    assert BOOK_ORDER["Revelation"] == 66


def test_convert_greek_translations_yields_expected_row_for_mark_1_1():
    raw = {"Mark 1:1": "Ἀρχὴ τοῦ εὐαγγελίου Ἰησοῦ Χριστοῦ."}
    rows = list(convert_greek_translations_to_rows(raw))
    assert rows == [
        {
            "book_order": 41,
            "book": "Mark",
            "chapter": 1,
            "verse": 1,
            "reference": "Mark 1:1",
            "text": "Ἀρχὴ τοῦ εὐαγγελίου Ἰησοῦ Χριστοῦ.",
        }
    ]


def test_convert_greek_translations_skips_malformed_keys(caplog):
    raw = {"Mark 1:1": "ok", "NotARef": "bad", "Mark 1": "missing verse"}
    rows = list(convert_greek_translations_to_rows(raw))
    assert len(rows) == 1
    assert rows[0]["reference"] == "Mark 1:1"
