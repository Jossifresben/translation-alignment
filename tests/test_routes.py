"""End-to-end route tests (new designer-shell routes)."""
import shutil
from pathlib import Path

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_redirects_to_mark_1_1(client):
    resp = client.get("/")
    assert resp.status_code in (301, 302)
    assert "/verse/mark/1/1" in resp.headers["Location"]


def test_verse_route_renders_with_fixture(client):
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if dst.exists():
        backup = dst.read_bytes()
    shutil.copy(src, dst)
    try:
        resp = client.get("/verse/mark/1/1")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        # New designer chrome
        assert "Translation Aligner" in body
        # Greek content rendered
        assert "Ἀρχὴ" in body
    finally:
        if backup is not None:
            dst.write_bytes(backup)
        else:
            dst.unlink(missing_ok=True)


def test_legacy_mark_route_redirects(client):
    resp = client.get("/mark/1/1")
    assert resp.status_code == 301
    assert "/verse/mark/1/1" in resp.headers["Location"]


def test_verse_partial_returns_fragment(client):
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup = dst.read_bytes() if dst.exists() else None
    shutil.copy(src, dst)
    try:
        resp = client.get("/verse/mark/1/1/partial/parallel")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "<!DOCTYPE" not in body
        assert "Ἀρχὴ" in body
    finally:
        if backup is not None:
            dst.write_bytes(backup)
        else:
            dst.unlink(missing_ok=True)


def test_verse_returns_404_for_nonexistent(client):
    resp = client.get("/verse/mark/99/99")
    assert resp.status_code == 404


def test_tooltip_greek_404_for_missing_token(client):
    resp = client.get("/tooltip/greek/99/99/0")
    assert resp.status_code == 404


def test_tooltip_peshitta_404_for_missing_token(client):
    resp = client.get("/tooltip/peshitta/99/99/0")
    assert resp.status_code == 404
