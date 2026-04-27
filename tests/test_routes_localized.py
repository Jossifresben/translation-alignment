"""Tests for locale-aware request routing."""
from app import app


def test_bare_root_resolves_with_lang_en():
    """No prefix → g.lang = 'en', renders home."""
    with app.test_client() as c:
        rv = c.get("/", headers={"Accept-Language": "en-US"})
        assert rv.status_code == 200


def test_es_prefix_resolves_home():
    with app.test_client() as c:
        rv = c.get("/es/")
        assert rv.status_code == 200


def test_es_prefix_resolves_about():
    with app.test_client() as c:
        rv = c.get("/es/about")
        assert rv.status_code == 200


def test_zh_hans_prefix_resolves_verse():
    with app.test_client() as c:
        rv = c.get("/zh-Hans/verse/mark/1/1")
        assert rv.status_code == 200


def test_zh_hant_prefix_resolves_verse():
    with app.test_client() as c:
        rv = c.get("/zh-Hant/verse/mark/13/14")
        assert rv.status_code == 200


def test_unknown_lang_prefix_404s():
    with app.test_client() as c:
        rv = c.get("/de/verse/mark/1/1")
        # Either 404 (route doesn't exist) or our handler ignores 'de' and
        # the bare /de/verse/mark/1/1 also 404s. Both acceptable.
        assert rv.status_code == 404


def test_es_verse_does_not_redirect():
    """Auto-redirect logic comes in A11; this test just confirms that
    a deep localized URL resolves to 200 and doesn't redirect anywhere."""
    with app.test_client() as c:
        rv = c.get(
            "/verse/mark/1/1",
            headers={"Accept-Language": "es-MX,es;q=0.9"},
        )
        # No 302 — even though Accept-Language is Spanish.
        assert rv.status_code == 200
