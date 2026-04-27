"""Translation dictionary + Accept-Language parsing.

Per design 2026-04-27. Zero external deps; pure-Python JSON loaders.
"""
from __future__ import annotations

import json
from pathlib import Path

SUPPORTED: tuple[str, ...] = ("en", "es", "zh-Hans", "zh-Hant")
DEFAULT: str = "en"


class Translations:
    """Loads per-language JSON dicts at startup; resolves keys with
    English fallback then literal-key fallback.

    Each JSON file is a flat dict of dotted keys → strings.
    Missing files are tolerated (treated as empty).
    """

    def __init__(self, root: Path) -> None:
        self._dicts: dict[str, dict[str, str]] = {}
        for lang in SUPPORTED:
            path = root / f"{lang}.json"
            if path.exists():
                self._dicts[lang] = json.loads(path.read_text(encoding="utf-8"))
            else:
                self._dicts[lang] = {}

    def t(self, key: str, lang: str = DEFAULT) -> str:
        """Lookup with English fallback. Returns the key itself if missing
        from both target and English (so missing keys are visible in the
        rendered page rather than silently empty).

        Empty-string values are honored — they are not treated as missing.
        """
        target = self._dicts.get(lang, {})
        if key in target:
            return target[key]
        english = self._dicts.get(DEFAULT, {})
        if key in english:
            return english[key]
        return key

    def has_key(self, key: str, lang: str = DEFAULT) -> bool:
        """Used by tests to assert key parity."""
        return key in self._dicts.get(lang, {})

    def keys(self, lang: str = DEFAULT) -> set[str]:
        return set(self._dicts.get(lang, {}).keys())


def parse_accept_language(header: str | None) -> str | None:
    """Map an Accept-Language header value to one of our supported
    non-English langs, or None if no useful match.

    Mappings:
      es*                 → 'es'
      zh-CN, zh-Hans, zh  → 'zh-Hans'   (mainland default)
      zh-TW, zh-HK, zh-Hant → 'zh-Hant'

    English / unsupported / empty / None → None (caller stays at bare root).
    """
    if not header:
        return None
    # Parse comma-separated tags; ignore q-values, just respect order.
    tags = [t.strip().split(";")[0].lower() for t in header.split(",") if t.strip()]
    for tag in tags:
        if tag.startswith("es"):
            return "es"
        if tag in ("zh-tw", "zh-hk", "zh-hant"):
            return "zh-Hant"
        if tag in ("zh-cn", "zh-hans", "zh"):
            return "zh-Hans"
    return None
