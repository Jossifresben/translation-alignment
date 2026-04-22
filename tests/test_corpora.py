"""Test CSV loading and reference-based lookup."""
import pytest
from pathlib import Path

from translation_core.corpora import Corpus, CorpusRegistry


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "book_order,book,chapter,verse,reference,text\n"
        "41,Mark,1,1,Mark 1:1,Archē tou euangeliou\n"
        "41,Mark,1,2,Mark 1:2,Kathōs gegraptai\n"
        "41,Mark,16,20,Mark 16:20,Ekeinoi de exelthontes\n",
        encoding="utf-8",
    )
    return csv_path


def test_corpus_loads_csv_and_looks_up_verse(sample_csv):
    c = Corpus(tradition_id="greek_nt", label="Greek NT", csv_path=sample_csv)
    assert c.get("Mark", 1, 1) == "Archē tou euangeliou"
    assert c.get("Mark", 16, 20) == "Ekeinoi de exelthontes"


def test_corpus_returns_none_for_missing_verse(sample_csv):
    c = Corpus(tradition_id="greek_nt", label="Greek NT", csv_path=sample_csv)
    assert c.get("Mark", 99, 99) is None
    assert c.get("John", 1, 1) is None


def test_corpus_verse_range_returns_chapter_verses(sample_csv):
    c = Corpus(tradition_id="greek_nt", label="Greek NT", csv_path=sample_csv)
    verses = c.verses_in_chapter("Mark", 1)
    assert verses == [1, 2]


def test_registry_loads_multiple_corpora(sample_csv, tmp_path):
    other = tmp_path / "other.csv"
    other.write_text(
        "book_order,book,chapter,verse,reference,text\n"
        "41,Mark,1,1,Mark 1:1,Initium evangelii\n",
        encoding="utf-8",
    )
    reg = CorpusRegistry()
    reg.add("greek_nt", "Greek NT", sample_csv)
    reg.add("vulgate", "Vulgate", other)
    assert reg.get("greek_nt").get("Mark", 1, 1) == "Archē tou euangeliou"
    assert reg.get("vulgate").get("Mark", 1, 1) == "Initium evangelii"
    assert reg.tradition_ids() == ["greek_nt", "vulgate"]
