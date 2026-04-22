"""Test alignment loading and lookup."""
import json
import shutil
from pathlib import Path

import pytest

from translation_core.alignment import AlignmentStore


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    fixture = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dest = tmp_path / "mark" / "1"
    dest.mkdir(parents=True)
    shutil.copy(fixture, dest / "1.json")
    return tmp_path


def test_load_existing_verse(store_dir):
    store = AlignmentStore(root=store_dir)
    data = store.get("Mark", 1, 1)
    assert data is not None
    assert data["ref"] == "Mark 1:1"
    assert len(data["alignment"]) == 4


def test_load_missing_verse_returns_none(store_dir):
    store = AlignmentStore(root=store_dir)
    assert store.get("Mark", 99, 99) is None


def test_validates_on_load(store_dir):
    bad = store_dir / "mark" / "1" / "2.json"
    bad.write_text(json.dumps({"ref": "Mark 1:2"}), encoding="utf-8")
    store = AlignmentStore(root=store_dir)
    with pytest.raises(Exception):
        store.get("Mark", 1, 2)


def test_caches_after_first_load(store_dir):
    store = AlignmentStore(root=store_dir)
    first = store.get("Mark", 1, 1)
    second = store.get("Mark", 1, 1)
    assert first is second
