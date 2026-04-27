"""Tests for the Translations dict loader + key parity gate."""
import json
from pathlib import Path

import pytest

from translation_core.i18n import SUPPORTED, Translations

ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS = ROOT / "translations"


def test_en_json_exists_and_parses():
    assert (TRANSLATIONS / "en.json").exists()
    data = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_translations_loads_all_supported_langs():
    """Even if a lang file is missing, loader must not raise."""
    t = Translations(TRANSLATIONS)
    for lang in SUPPORTED:
        # has_key returns False for missing; that's fine, just must not raise
        assert t.has_key("__never__", lang) is False


def test_translations_falls_back_to_english_for_missing_key():
    t = Translations(TRANSLATIONS)
    # English value is the literal key when key is missing — by design
    assert t.t("nonexistent.key", "es") == "nonexistent.key"


def test_translations_uses_english_when_target_lang_missing_key():
    """If a key exists in en.json but not es.json, t('key', 'es') returns
    the English value."""
    en_path = TRANSLATIONS / "en.json"
    data = json.loads(en_path.read_text(encoding="utf-8"))
    if not data:
        pytest.skip("en.json empty until A3+ extracts strings")
    sample_key = next(iter(data))
    sample_value = data[sample_key]
    t = Translations(TRANSLATIONS)
    # If es.json doesn't have the key, the English value is returned.
    if not t.has_key(sample_key, "es"):
        assert t.t(sample_key, "es") == sample_value
