"""Tests for Accept-Language parsing and locale resolution."""
from translation_core.i18n import parse_accept_language


def test_parse_accept_language_spanish():
    assert parse_accept_language("es-MX,es;q=0.9,en;q=0.8") == "es"


def test_parse_accept_language_simplified_chinese_explicit():
    assert parse_accept_language("zh-CN,zh;q=0.9") == "zh-Hans"


def test_parse_accept_language_traditional_chinese():
    assert parse_accept_language("zh-TW") == "zh-Hant"


def test_parse_accept_language_hong_kong_traditional():
    assert parse_accept_language("zh-HK,en;q=0.5") == "zh-Hant"


def test_parse_accept_language_generic_chinese_defaults_to_simplified():
    assert parse_accept_language("zh") == "zh-Hans"


def test_parse_accept_language_unsupported_returns_none():
    assert parse_accept_language("de,en;q=0.5") is None


def test_parse_accept_language_empty_returns_none():
    assert parse_accept_language("") is None


def test_parse_accept_language_none_returns_none():
    assert parse_accept_language(None) is None


def test_parse_accept_language_english_returns_none():
    """English maps to None since English is the bare-root default
    (the caller stays at / instead of redirecting to /en/)."""
    assert parse_accept_language("en-US,en;q=0.9") is None
