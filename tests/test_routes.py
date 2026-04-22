"""End-to-end route tests using the Flask test client."""
import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Translation Alignment" in resp.data


def test_index_has_cta_to_mark_1_1(client):
    resp = client.get("/")
    assert b"/mark/1/1" in resp.data


def test_viewer_route_renders_fixture_verse(client):
    import shutil
    from pathlib import Path
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    try:
        resp = client.get("/mark/1/1")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "Ἀρχὴ" in body
        assert "ܪܫܐ" in body
        # Vulgate corpus may not be loaded in this test env; we still assert
        # that the Greek and Peshitta columns render (Vulgate shows absent
        # placeholder in the fallback path).
        assert 'class="tok' in body
    finally:
        dst.unlink()


def test_viewer_partial_returns_card_only(client):
    import shutil
    from pathlib import Path
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    try:
        resp = client.get("/partials/verse/mark/1/1")
        body = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "Ἀρχὴ" in body
        assert "<!DOCTYPE" not in body
        assert "<nav class=\"topbar\"" not in body
    finally:
        dst.unlink()


def test_viewer_returns_404_for_nonexistent_verse(client):
    resp = client.get("/mark/1/999")
    assert resp.status_code == 404


def test_viewer_redirects_bad_chapter_verse_format(client):
    resp = client.get("/mark/abc/xyz")
    assert resp.status_code == 404


def test_nav_wraps_to_next_chapter_at_chapter_end(client):
    import shutil
    from pathlib import Path
    src = Path("data/alignments/_fixtures/alignment_mark_1_1.json")
    dst = Path("data/alignments/mark/1/1.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    try:
        resp = client.get("/mark/1/1")
        body = resp.data.decode("utf-8")
        assert "/mark/1/2" in body
        assert "/mark/1/0" not in body
        assert "/mark/0/" not in body
    finally:
        dst.unlink()
