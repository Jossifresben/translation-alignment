"""Test Vulgate ingestion."""
from pathlib import Path

import pytest

from scripts.ingest_vulgate import parse_vulgate_file, filter_to_book


def test_parse_vulgate_file_reads_tsv_format(tmp_path):
    src = Path("tests/fixtures/vulgate_mark_sample.txt")
    rows = list(parse_vulgate_file(src))
    assert len(rows) == 3
    assert rows[0]["book"] == "Mark"
    assert rows[0]["chapter"] == 1
    assert rows[0]["verse"] == 1
    assert rows[0]["text"].startswith("Initium Evangelii")
    assert rows[0]["book_order"] == 41


def test_filter_to_book_returns_only_target_book():
    rows = [
        {"book": "Mark", "chapter": 1, "verse": 1, "text": "a", "book_order": 41,
         "reference": "Mark 1:1"},
        {"book": "John", "chapter": 1, "verse": 1, "text": "b", "book_order": 43,
         "reference": "John 1:1"},
    ]
    filtered = list(filter_to_book(rows, "Mark"))
    assert len(filtered) == 1
    assert filtered[0]["book"] == "Mark"


def test_parse_vulgate_file_skips_malformed_lines(tmp_path):
    src = tmp_path / "bad.txt"
    src.write_text("Mark 1:1\tgood text\nNOT A LINE\n\nMark 1:2\tanother good\n", encoding="utf-8")
    rows = list(parse_vulgate_file(src))
    assert len(rows) == 2
