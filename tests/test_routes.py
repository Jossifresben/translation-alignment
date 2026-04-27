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


def test_index_renders_home_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Translation Aligner" in body
    assert "/verse/mark/1/1" in body
    assert "Open the Gospel of Mark" in body


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


def test_variants_data_embedded_in_verse_page(client):
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup = dst.read_bytes() if dst.exists() else None
    shutil.copy(src, dst)
    try:
        resp = client.get("/verse/mark/1/1")
        body = resp.data.decode("utf-8")
        assert 'id="variants-data"' in body
    finally:
        if backup is not None:
            dst.write_bytes(backup)
        else:
            dst.unlink(missing_ok=True)


def test_interlinear_partial_renders_tok_spans(client):
    resp = client.get("/verse/mark/1/1/partial/interlinear")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    # Interlinear tokens should now carry data-align attributes (per-token markup)
    assert 'data-align=' in body


def test_search_returns_results_for_greek_substring(client):
    resp = client.get("/search?q=%CE%B2%CE%B4%CE%AD%CE%BB%CF%85%CE%B3%CE%BC%CE%B1")  # βδέλυγμα
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data


def test_search_reference_shortcut(client):
    resp = client.get("/search?q=1%3A1")
    data = resp.get_json()
    assert any(r["chapter"] == 1 and r["verse"] == 1 for r in data.get("results", []))


def test_search_empty_query_returns_empty(client):
    resp = client.get("/search?q=")
    assert resp.get_json() == {"results": []}


def test_about_page_renders(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "About the Translation Aligner" in body
    assert "STEP" in body


def test_topbar_has_about_link(client):
    resp = client.get("/verse/mark/1/1")
    body = resp.data.decode("utf-8")
    assert 'href="/about"' in body


def test_sitemap_includes_localized_alternates():
    with app.test_client() as c:
        rv = c.get("/sitemap.xml")
        body = rv.data.decode()
        # Original English URLs still present
        assert "/verse/mark/1/1" in body
        # xhtml namespace declared
        assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in body
        # Each lang has alternates
        assert 'hreflang="es"' in body
        assert 'hreflang="zh-Hans"' in body
        assert 'hreflang="zh-Hant"' in body
        # English alternate too (so consumers see it as one of four)
        assert 'hreflang="en"' in body
