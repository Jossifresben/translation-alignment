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


def test_root_with_spanish_accept_language_redirects_to_es():
    with app.test_client() as c:
        rv = c.get("/", headers={"Accept-Language": "es-MX,es;q=0.9,en;q=0.5"})
        assert rv.status_code == 302
        assert rv.location.endswith("/es/")
        # Cookie set
        cookie = rv.headers.get("Set-Cookie", "")
        assert "lang=es" in cookie


def test_root_with_chinese_accept_language_redirects_to_zh_hans():
    with app.test_client() as c:
        rv = c.get("/", headers={"Accept-Language": "zh-CN,zh;q=0.9"})
        assert rv.status_code == 302
        assert rv.location.endswith("/zh-Hans/")


def test_root_with_traditional_chinese_redirects_to_zh_hant():
    with app.test_client() as c:
        rv = c.get("/", headers={"Accept-Language": "zh-TW"})
        assert rv.status_code == 302
        assert rv.location.endswith("/zh-Hant/")


def test_root_with_english_does_not_redirect():
    with app.test_client() as c:
        rv = c.get("/", headers={"Accept-Language": "en-US,en;q=0.9"})
        assert rv.status_code == 200
        # Cookie set to en
        cookie = rv.headers.get("Set-Cookie", "")
        assert "lang=en" in cookie


def test_root_with_zh_hans_cookie_redirects_even_without_accept_language():
    """If user previously chose Simplified Chinese, visiting / honors that."""
    with app.test_client() as c:
        c.set_cookie(key="lang", value="zh-Hans")
        rv = c.get("/", headers={"Accept-Language": "en-US"})
        assert rv.status_code == 302
        assert rv.location.endswith("/zh-Hans/")


def test_root_with_es_cookie_redirects():
    with app.test_client() as c:
        c.set_cookie(key="lang", value="es")
        rv = c.get("/")
        assert rv.status_code == 302
        assert rv.location.endswith("/es/")


def test_root_with_zh_hant_cookie_redirects():
    with app.test_client() as c:
        c.set_cookie(key="lang", value="zh-Hant")
        rv = c.get("/")
        assert rv.status_code == 302
        assert rv.location.endswith("/zh-Hant/")


def test_root_with_en_cookie_does_not_redirect():
    """English cookie = stay at bare root."""
    with app.test_client() as c:
        c.set_cookie(key="lang", value="en")
        rv = c.get("/", headers={"Accept-Language": "es-MX"})
        assert rv.status_code == 200


def test_localized_url_for_prefixes_non_english():
    """Inside a /es/ render, internal links must include the /es prefix."""
    with app.test_client() as c:
        rv = c.get("/es/")
        body = rv.data.decode()
        # The CTA on /es/ should point to /es/verse/mark/1/1
        assert "/es/verse/mark/1/1" in body, "Spanish CTA missing /es prefix"
        # The methodology nav link should point to /es/about
        assert "/es/about" in body, "Spanish nav link missing /es prefix"


def test_localized_url_for_keeps_english_unprefixed():
    """At bare root, internal links remain bare-root (no /en prefix)."""
    with app.test_client() as c:
        rv = c.get("/")
        body = rv.data.decode()
        assert "/verse/mark/1/1" in body
        assert "/en/" not in body, "Should never produce /en/ prefix"


def test_localized_url_for_does_not_prefix_static_assets():
    """CSS / JS / images must NEVER get a lang prefix."""
    with app.test_client() as c:
        rv = c.get("/zh-Hans/")
        body = rv.data.decode()
        assert "/zh-Hans/static/" not in body, "Static assets must not be lang-prefixed"
        assert "/static/css/styles.css" in body


def test_hreflang_tags_present_on_home():
    with app.test_client() as c:
        rv = c.get("/")
        body = rv.data.decode()
        assert 'hreflang="en"' in body
        assert 'hreflang="es"' in body
        assert 'hreflang="zh-Hans"' in body
        assert 'hreflang="zh-Hant"' in body
        assert 'hreflang="x-default"' in body


def test_hreflang_tags_use_canonical_path_on_localized_route():
    """On /es/about, hreflang should point to /about, /es/about, /zh-Hans/about, /zh-Hant/about."""
    with app.test_client() as c:
        rv = c.get("/es/about")
        body = rv.data.decode()
        # Each lang link points to the same canonical sub-path /about
        assert 'hreflang="es" href="http://localhost/es/about"' in body
        assert 'hreflang="zh-Hans" href="http://localhost/zh-Hans/about"' in body
        assert 'hreflang="zh-Hant" href="http://localhost/zh-Hant/about"' in body
        # The x-default should be the bare /about (no prefix)
        assert 'hreflang="x-default" href="http://localhost/about"' in body
