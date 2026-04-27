"""Tests for the Polyglot Concordance API v1.

Covers all five JSON endpoints + the HTML index + Swagger UI page,
plus CORS / Cache-Control headers and error envelopes.

See `docs/superpowers/specs/2026-04-27-api-v1-design.md` for the design.
"""
import pytest

from app import app


@pytest.fixture
def client():
    return app.test_client()


# --------------------------------------------------------- /api/v1/manifest

def test_manifest_returns_corpus_metadata(client):
    rv = client.get("/api/v1/manifest")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["api_version"] == "v1"
    assert data["project"] == "Polyglot Concordance"
    assert data["schema_version"] == 1
    assert any(b["id"] == "mark" for b in data["books"])
    mark = next(b for b in data["books"] if b["id"] == "mark")
    assert mark["verse_count"] >= 670
    assert isinstance(mark["verses"], list)
    assert len(data["witnesses"]) == 3
    assert len(data["verse_glosses"]) == 4
    assert sorted([g["lang"] for g in data["verse_glosses"]]) == ["en", "es", "zh-Hans", "zh-Hant"]
    assert "aligned" in data["variant_verdicts"]
    assert "harmonisation" in data["variant_types"]


# --------------------------------------------------------- /api/v1/alignment

def test_alignment_returns_canonical_json(client):
    rv = client.get("/api/v1/alignment/mark/13/14")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["api_version"] == "v1"
    assert data["ref"] == "Mark 13:14"
    assert data["chapter"] == 13
    assert data["verse"] == 14
    assert "traditions" in data
    assert "alignment" in data
    assert isinstance(data["alignment"], list)
    assert "schema_version" in data.get("meta", {})


def test_alignment_404_for_unknown_book(client):
    rv = client.get("/api/v1/alignment/luke/1/1")
    assert rv.status_code == 404
    data = rv.get_json()
    assert data["error"]["code"] == "book_not_found"


def test_alignment_404_for_unknown_verse(client):
    rv = client.get("/api/v1/alignment/mark/99/99")
    assert rv.status_code == 404
    data = rv.get_json()
    assert data["error"]["code"] == "alignment_not_found"


def test_alignment_book_param_is_case_insensitive(client):
    rv_lower = client.get("/api/v1/alignment/mark/1/1")
    rv_title = client.get("/api/v1/alignment/Mark/1/1")
    assert rv_lower.status_code == 200
    assert rv_title.status_code == 200
    assert rv_lower.get_json()["ref"] == rv_title.get_json()["ref"]


# --------------------------------------------------------- /api/v1/verse

def test_verse_returns_converted_dict(client):
    rv = client.get("/api/v1/verse/mark/1/1")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["api_version"] == "v1"
    assert data["ref"] == "Mark 1:1"
    assert data["book"] == "Mark"
    assert isinstance(data["witnesses"], list)
    assert len(data["witnesses"]) == 3


def test_verse_gloss_map_has_all_4_langs(client):
    rv = client.get("/api/v1/verse/mark/1/1")
    data = rv.get_json()
    gm = data.get("gloss_map", {})
    assert sorted(gm.keys()) == ["en", "es", "zh-Hans", "zh-Hant"]
    # All four should be non-empty for Mark 1:1 (every gloss CSV covers it)
    for lang in ("en", "es", "zh-Hans", "zh-Hant"):
        assert gm[lang], f"gloss_map[{lang!r}] is empty"


def test_verse_404_for_unknown_book(client):
    rv = client.get("/api/v1/verse/luke/1/1")
    assert rv.status_code == 404
    assert rv.get_json()["error"]["code"] == "book_not_found"


def test_verse_404_for_unknown_verse(client):
    rv = client.get("/api/v1/verse/mark/99/99")
    assert rv.status_code == 404
    assert rv.get_json()["error"]["code"] == "verse_not_found"


# --------------------------------------------------------- /api/v1/search

def test_search_returns_envelope(client):
    rv = client.get("/api/v1/search?q=evangelio")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["api_version"] == "v1"
    assert data["query"] == "evangelio"
    assert isinstance(data["count"], int)
    assert isinstance(data["items"], list)
    assert data["count"] == len(data["items"])


def test_search_chapter_verse_jump(client):
    rv = client.get("/api/v1/search?q=13:14")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["count"] == 1
    item = data["items"][0]
    assert item["ref"] == "Mark 13:14"
    assert item["kind"] == "reference"


def test_search_empty_query_returns_empty_items(client):
    rv = client.get("/api/v1/search")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["count"] == 0
    assert data["items"] == []


def test_search_limit_is_clamped(client):
    # limit > 100 must be clamped to 100; the Greek article ὁ matches many
    # verses, so this exercises the cap without assuming corpus contents.
    rv = client.get("/api/v1/search?q=ὁ&limit=500")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["count"] <= 100


def test_search_bad_limit_400(client):
    rv = client.get("/api/v1/search?q=evangelio&limit=notanumber")
    assert rv.status_code == 400
    assert rv.get_json()["error"]["code"] == "bad_request"


# --------------------------------------------------------- /api/v1/openapi.json

def test_openapi_json_is_valid_envelope(client):
    rv = client.get("/api/v1/openapi.json")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "Polyglot Concordance API"
    assert "/api/v1/alignment/{book}/{chapter}/{verse}" in spec["paths"]
    assert "/api/v1/verse/{book}/{chapter}/{verse}" in spec["paths"]
    assert "/api/v1/search" in spec["paths"]
    assert "/api/v1/manifest" in spec["paths"]


# --------------------------------------------------------- Headers

def test_cors_header_present_on_all_api_responses(client):
    for url in [
        "/api/v1/manifest",
        "/api/v1/alignment/mark/1/1",
        "/api/v1/verse/mark/1/1",
        "/api/v1/search?q=evangelio",
        "/api/v1/openapi.json",
    ]:
        rv = client.get(url)
        assert rv.headers.get("Access-Control-Allow-Origin") == "*", f"missing CORS on {url}"


def test_cache_header_long_for_stable_endpoints(client):
    for url in [
        "/api/v1/manifest",
        "/api/v1/alignment/mark/1/1",
        "/api/v1/verse/mark/1/1",
        "/api/v1/openapi.json",
    ]:
        rv = client.get(url)
        cc = rv.headers.get("Cache-Control", "")
        assert "max-age=86400" in cc, f"expected 86400 on {url}, got {cc!r}"


def test_cache_header_short_for_search(client):
    rv = client.get("/api/v1/search?q=evangelio")
    cc = rv.headers.get("Cache-Control", "")
    assert "max-age=300" in cc, f"expected 300 on /api/v1/search, got {cc!r}"


# --------------------------------------------------------- Index + docs HTML

def test_api_index_html_renders(client):
    rv = client.get("/api/v1/")
    assert rv.status_code == 200
    assert rv.content_type.startswith("text/html")
    body = rv.data.decode()
    assert "Polyglot Concordance" in body
    assert "/api/v1/manifest" in body
    assert "curl" in body.lower()


def test_docs_route_renders_swagger_shell(client):
    rv = client.get("/api/docs")
    assert rv.status_code == 200
    assert rv.content_type.startswith("text/html")
    body = rv.data.decode()
    assert "swagger-ui" in body.lower()
    assert "/api/v1/openapi.json" in body
