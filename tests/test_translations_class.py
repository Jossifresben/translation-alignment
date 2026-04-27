"""Tests for the Translations class fallback behavior."""
import json
from pathlib import Path

from translation_core.i18n import Translations


def test_translations_returns_empty_string_when_target_lang_has_empty_value(tmp_path: Path):
    """An intentionally-empty translation must NOT fall back to English."""
    en = tmp_path / "en.json"
    es = tmp_path / "es.json"
    en.write_text(json.dumps({"some.key": "English value"}), encoding="utf-8")
    es.write_text(json.dumps({"some.key": ""}), encoding="utf-8")
    t = Translations(tmp_path)
    assert t.t("some.key", "es") == ""


def test_translations_falls_back_to_english_when_key_missing_from_target(tmp_path: Path):
    en = tmp_path / "en.json"
    es = tmp_path / "es.json"
    en.write_text(json.dumps({"some.key": "English value"}), encoding="utf-8")
    es.write_text(json.dumps({}), encoding="utf-8")
    t = Translations(tmp_path)
    assert t.t("some.key", "es") == "English value"


def test_translations_returns_literal_key_when_missing_everywhere(tmp_path: Path):
    en = tmp_path / "en.json"
    en.write_text(json.dumps({}), encoding="utf-8")
    t = Translations(tmp_path)
    assert t.t("some.key", "es") == "some.key"
