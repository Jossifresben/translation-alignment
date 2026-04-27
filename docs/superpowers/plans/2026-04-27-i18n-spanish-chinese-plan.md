# i18n: Spanish + Chinese Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a complete internationalization layer for the Translation Aligner pilot — UI chrome translated into Spanish + Chinese (Simplified + Traditional), verse glosses available from RV1909 and CUV (S/T), localized URLs, hreflang SEO, and a settings cog in the topbar — without breaking any existing English path or test.

**Architecture:** A Flask `before_request` hook strips an optional `/<lang>/` URL prefix and sets `g.lang`. UI strings flow through one `t('key')` Jinja global backed by per-language JSON dicts (`translations/<lang>.json`). Verse glosses come from per-language CSVs that mirror the existing `web.csv` and stack vertically above the alignment grid via a settings-controlled checkbox set persisted in `localStorage`. Zero build step, zero new runtime dependencies.

**Tech Stack:** Flask 3, Jinja2, vanilla JS, pytest. CSVs for corpus data. JSON for translation dicts.

**Spec:** [`docs/superpowers/specs/2026-04-27-i18n-spanish-chinese-design.md`](../specs/2026-04-27-i18n-spanish-chinese-design.md)

---

## File-structure map

### New files

| Path | Responsibility |
|---|---|
| `translation_core/i18n.py` | `Translations` class + `parse_accept_language` |
| `translations/en.json` | source-of-truth keys + English values |
| `translations/es.json` | Spanish overrides |
| `translations/zh-Hans.json` | Simplified Chinese |
| `translations/zh-Hant.json` | Traditional Chinese |
| `data/corpora/rv1909.csv` | Spanish verse text (Reina-Valera 1909) |
| `data/corpora/cuv_hans.csv` | Simplified Chinese verse text (CUV 1919) |
| `data/corpora/cuv_hant.csv` | Traditional Chinese verse text (CUV 1919) |
| `templates/_gloss_stack.html` | Multi-language gloss rows above the alignment grid |
| `templates/_settings.html` | Settings panel markup |
| `static/js/settings.js` | Settings panel toggle + persistence |
| `scripts/ingest_rv1909.py` | One-shot ingestion script for RV1909 |
| `scripts/ingest_cuv.py` | One-shot ingestion (handles Hans + Hant) |
| `tests/test_i18n_locale_resolution.py` | Accept-Language parsing + path stripping |
| `tests/test_translation_loader.py` | JSON loaders + key parity gate |
| `tests/test_routes_localized.py` | Localized route resolution + redirects |
| `tests/test_gloss_csv_load.py` | RV1909 + CUV(S/T) ingestion verification |

### Modified files

| Path | Change |
|---|---|
| `app.py` | + locale hook, hreflang context, Translations init, gloss-map plumbing, sitemap localization |
| `templates/base.html` | + hreflang block, settings cog, i18n-data script tag, all chrome strings → `t()` |
| `templates/home.html` | strings → `t()` |
| `templates/about.html` | strings → `t()` |
| `templates/verse.html` | include `_gloss_stack.html`; replace single gloss line; strings → `t()` |
| `templates/_alignment_grid.html` | strings → `t()` |
| `templates/_interlinear.html` | strings → `t()` |
| `templates/_apparatus.html` | strings → `t()` |
| `templates/_rail.html` | strings → `t()` |
| `templates/macros.html` | strings → `t()` (witness header labels) |
| `templates/404.html` | strings → `t()` |
| `static/js/aligner.js` | string constants → `t()` lookups |
| `static/css/styles.css` | + `.gloss-stack`, `.gloss-row`, `.gloss-tag`, `.settings-panel`, CJK fonts |

---

## Resolved §8 open questions

The spec has four open implementation questions; this plan resolves them as:

1. **Gloss CSV source:** [eBible.org](https://ebible.org/) USFX dumps are used because we already have a USFX walker (`scripts/extract_vulgate_range.py`). RV1909 → `spavbl_usfx.zip` (Reina Valera 1909 Bible). CUV Simplified → `zh-cmn-hans-cu89s_usfx.zip`. CUV Traditional → `zh-cmn-hant-cu89t_usfx.zip`. All three are public-domain on eBible. If a download blocks, the fallback is `bible-databases` GitHub repo (`scrollmapper/bible_databases`).
2. **Verse-numbering parity:** Both RV1909 and CUV in the eBible USFX format follow Protestant numbering, which matches NA28 in Mark — except a small chance of Mark 9:1 boundary drift (the same issue we fixed in the Vulgate). **Verification task** runs after each ingest; any drift gets remapped following the existing `scripts/extract_vulgate_range.py` pattern.
3. **Cookie write timing:** An `after_request` hook writes `lang` cookie when absent. This avoids the race where the auto-redirect at `/` already returns a `Set-Cookie`, while still covering the no-redirect case (e.g. `/about` first visit).
4. **JS-side i18n delivery:** Server-injected via `<script id="i18n-data" type="application/json">` in `base.html`, populated with the small subset of translation keys whose path starts with `js.`. `aligner.js` reads this once at boot. No `/i18n/<lang>.json` endpoint is needed.

---

## Phase A — i18n plumbing (English-only, no UI change)

**Goal of phase A:** All current English text is now indirected through `t()`, the locale hook is in place, and existing tests still pass. The site looks and behaves identically to before — there is no Spanish or Chinese translation yet. This phase ends with a clean separation between "where English strings live" and "how they are rendered".

### Task A1: `Translations` class + `parse_accept_language` (TDD)

**Files:**
- Create: `translation_core/i18n.py`
- Test: `tests/test_i18n_locale_resolution.py`

- [ ] **Step 1: Write the failing test for `parse_accept_language`**

```python
# tests/test_i18n_locale_resolution.py
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
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_i18n_locale_resolution.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_accept_language' from 'translation_core.i18n'` (module doesn't exist yet)

- [ ] **Step 3: Implement `Translations` + `parse_accept_language`**

Create `translation_core/i18n.py`:

```python
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
        rendered page rather than silently empty)."""
        return (
            self._dicts.get(lang, {}).get(key)
            or self._dicts.get(DEFAULT, {}).get(key)
            or key
        )

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
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_i18n_locale_resolution.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add translation_core/i18n.py tests/test_i18n_locale_resolution.py
git commit -m "$(cat <<'EOF'
feat(i18n): Translations class + parse_accept_language

TDD: 9 tests covering the en/es/zh-Hans/zh-Hant mapping rules
(generic 'zh' defaults to Simplified; HK + TW go Traditional;
'es-*' all map to es; English/unsupported return None).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A2: Translations loader test + bootstrap empty `en.json`

**Files:**
- Create: `translations/en.json`
- Create: `tests/test_translation_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_translation_loader.py
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
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_translation_loader.py -v`
Expected: FAIL with `assert (TRANSLATIONS / "en.json").exists()` — file missing.

- [ ] **Step 3: Create empty `en.json`**

```bash
mkdir -p "/Users/jfresco16/Google Drive/Claude/Translation_alignment/translations"
```

Create `translations/en.json`:
```json
{}
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_translation_loader.py -v`
Expected: 4 passed (one skipped because en.json is empty).

- [ ] **Step 5: Commit**

```bash
git add translations/en.json tests/test_translation_loader.py
git commit -m "$(cat <<'EOF'
feat(i18n): bootstrap empty translations/en.json + loader tests

en.json starts empty; subsequent tasks (A3-A11) populate it
template-by-template. Loader tests assert: existence, fallback to
English on missing keys, fallback to literal key when both langs miss.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A3: Wire `t()` Jinja global into `app.py`

**Files:**
- Modify: `app.py` — add Translations init + Jinja global
- Test: `tests/test_routes.py` (existing — must still pass)

- [ ] **Step 1: Add Translations init at module top of `app.py`**

In `app.py`, after the existing imports, before the `app = Flask(...)` line, add:

```python
from translation_core.i18n import SUPPORTED as I18N_SUPPORTED, Translations
```

After the `BASE_DIR = Path(__file__).resolve().parent` block, add:

```python
TRANSLATIONS_DIR = BASE_DIR / "translations"
_translations = Translations(TRANSLATIONS_DIR)


def t(key: str, lang: str = "en") -> str:
    """Jinja global: resolve a translation key in the current request's lang."""
    from flask import g
    current_lang = getattr(g, "lang", lang)
    return _translations.t(key, current_lang)
```

After `app.jinja_env.globals["verse_stats"] = verse_stats`, add:

```python
app.jinja_env.globals["t"] = t
app.jinja_env.globals["supported_langs"] = I18N_SUPPORTED
```

- [ ] **Step 2: Run all existing tests to verify nothing breaks**

Run: `pytest -q`
Expected: All existing ~70 tests pass. (No template currently calls `t()`, so this is purely additive.)

- [ ] **Step 3: Smoke test that `t()` is callable from Jinja**

Run:
```bash
python -c "
from app import app
with app.test_client() as c:
    with app.app_context():
        from flask import g
        g.lang = 'en'
        rv = app.jinja_env.globals['t']('any.missing.key')
        assert rv == 'any.missing.key', f'expected literal-key fallback, got {rv!r}'
        print('OK')
"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
feat(i18n): wire t() and supported_langs as Jinja globals

App startup loads all four translation files from translations/.
Empty for now; subsequent tasks add keys per template. Existing tests
unchanged; site behavior identical.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A4: Extract strings from `templates/base.html`

**Files:**
- Modify: `translations/en.json` (add keys)
- Modify: `templates/base.html` (replace strings with `{{ t(...) }}`)

- [ ] **Step 1: Add base.html keys to `translations/en.json`**

Replace the contents of `translations/en.json` with:

```json
{
  "site.name": "Translation Aligner",
  "site.tagline_default": "Translation Aligner — the Gospel of Mark in parallel",
  "site.description_default": "A word-by-word alignment of the Gospel of Mark across Greek NT, Syriac Peshitta, and Latin Clementine Vulgate — with a scholarly critical apparatus on every divergence. Generated by Anthropic Claude, benchmarked against the Berean Interlinear Bible.",
  "nav.home_aria": "Translation Aligner — home",
  "nav.methodology": "Methodology",
  "nav.search_aria": "Search (⌘K)",
  "nav.search_title": "Search (⌘K)",
  "footer.brand": "Translation Aligner",
  "footer.scope_label": "MVP · Gospel of Mark",
  "tweaks.title": "Tweaks",
  "tweaks.view_label": "View mode",
  "tweaks.theme_label": "Theme",
  "tweaks.rail_label": "Side rail",
  "tweaks.rail_show": "show",
  "tweaks.rail_hide": "hide",
  "search.placeholder": "Search Greek, Vulgate, Peshitta, English, variant type, or 13:14…",
  "search.hint_keys": "↑↓ navigate · ↵ open · Esc close",
  "search.hint_scope": "Mark only (pilot scope)"
}
```

- [ ] **Step 2: Replace strings in `templates/base.html`**

In `templates/base.html`:

Replace the `<title>` block:
```jinja
<title>{% block title %}{{ t('site.tagline_default') }}{% endblock %}</title>
```

Replace the description meta `content`:
```jinja
<meta name="description" content="{% block description %}{{ t('site.description_default') }}{% endblock %}" />
```

Replace the brand anchor:
```jinja
<a class="brand" href="{{ url_for('index') }}" aria-label="{{ t('nav.home_aria') }}">
  <span class="brand-mark" aria-hidden="true"></span>
  <span class="brand-title">{{ t('site.name') }}</span>
  <span class="brand-sep">/</span>
  <span class="brand-meta">{% block brand_meta %}{% endblock %}</span>
</a>
```

Replace the topbar nav:
```jinja
<nav class="topbar-actions">
  <a class="iconbtn" href="{{ url_for('about') }}">{{ t('nav.methodology') }}</a>
  <button class="iconbtn iconbtn-icon" type="button" id="search-trigger"
          aria-label="{{ t('nav.search_aria') }}" title="{{ t('nav.search_title') }}">
    <svg class="icon-search" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/>
      <line x1="15.2" y1="15.2" x2="20" y2="20"
            stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
    <kbd class="iconbtn-kbd">⌘K</kbd>
  </button>
</nav>
```

Replace the footer left block:
```jinja
<div class="foot-left">
  <span class="foot-brand">{{ t('footer.brand') }}</span>
  <span class="foot-sep">·</span>
  <span>{{ t('footer.scope_label') }}</span>
</div>
```

Replace the tweaks panel header + labels (this is the hidden panel near the bottom):
```jinja
<div class="tweaks-head">
  <span class="tweaks-title">{{ t('tweaks.title') }}</span>
</div>
<form class="tweaks-body" method="get" action="">
  <div class="tweak-row">
    <label class="tweak-label">{{ t('tweaks.view_label') }}</label>
    <div class="tweak-seg" role="radiogroup" data-tweak="view">
      {% for v in ['interlinear', 'parallel', 'apparatus'] %}
        <button type="button" data-value="{{ v }}"
          class="{{ 'active' if view == v else '' }}">{{ v }}</button>
      {% endfor %}
    </div>
  </div>
  <div class="tweak-row">
    <label class="tweak-label">{{ t('tweaks.theme_label') }}</label>
    <div class="tweak-seg" role="radiogroup" data-tweak="theme">
      {% for theme_opt in ['light', 'dark'] %}
        <button type="button" data-value="{{ theme_opt }}"
          class="{{ 'active' if theme == theme_opt else '' }}">{{ theme_opt }}</button>
      {% endfor %}
    </div>
  </div>
  <div class="tweak-row">
    <label class="tweak-label">{{ t('tweaks.rail_label') }}</label>
    <div class="tweak-seg" role="radiogroup" data-tweak="rail">
      <button type="button" data-value="1" class="{{ 'active' if show_rail else '' }}">{{ t('tweaks.rail_show') }}</button>
      <button type="button" data-value="0" class="{{ '' if show_rail else 'active' }}">{{ t('tweaks.rail_hide') }}</button>
    </div>
  </div>
</form>
```

Replace the search overlay:
```jinja
<div id="search-overlay" class="search-overlay" hidden>
  <div class="search-modal" role="dialog" aria-label="{{ t('nav.search_aria') }}">
    <input id="search-input" type="text"
           autocomplete="off" spellcheck="false"
           placeholder="{{ t('search.placeholder') }}" />
    <ul id="search-results" class="search-results"></ul>
    <div class="search-hint">
      <span>{{ t('search.hint_keys') }}</span>
      <span>{{ t('search.hint_scope') }}</span>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Run all tests + smoke-test home page rendering**

Run:
```bash
pytest -q
```
Expected: All ~70 tests pass.

Then smoke-test:
```bash
python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/')
    assert rv.status_code == 200, f'home returned {rv.status_code}'
    body = rv.data.decode()
    assert 'Translation Aligner' in body
    assert 'Methodology' in body
    assert 'Search Greek, Vulgate' in body
    print('OK')
"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add translations/en.json templates/base.html
git commit -m "$(cat <<'EOF'
feat(i18n): extract base.html strings to translations/en.json

19 keys across nav/footer/tweaks/search. base.html is now language-agnostic
above the fold; rendering identical to before.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A5: Extract strings from `templates/home.html`

**Files:**
- Modify: `translations/en.json`
- Modify: `templates/home.html`

- [ ] **Step 1: Append home.html keys to `translations/en.json`**

Add these keys to `translations/en.json` (merge — keep existing keys):

```json
{
  "home.title_meta": "Translation Aligner — the Gospel of Mark in Greek, Syriac, and Latin",
  "home.description_meta": "A word-by-word alignment of the Gospel of Mark across the Greek NT, Syriac Peshitta, and Latin Clementine Vulgate, with a one-or-two-sentence apparatus note on every divergence — generated by Anthropic Claude and benchmarked against the Berean Interlinear Bible.",
  "home.brand_meta": "Home",
  "home.kicker": "Translation Aligner · Pilot",
  "home.title_main": "The Gospel of Mark,",
  "home.title_accent": "three witnesses in parallel.",
  "home.lede": "A word-by-word alignment of the Gospel of Mark across three textual witnesses — the Greek New Testament, the Syriac Peshitta, and the Latin Clementine Vulgate. Every divergence is classified by verdict (minor, major, omitted, added) and semantic type (harmonisation, substitution, idiom, word-order, grammar, lexical), and accompanied by a one- or two-sentence apparatus note — an open critical apparatus generated by Anthropic Claude.",
  "home.pilot_note_strong": "This is a pilot.",
  "home.pilot_note_body": "Current scope is the Gospel of Mark only. The full plan — additional NT books, the Hebrew Bible flagship, further witnesses, export formats, and two planned sub-projects — is on the",
  "home.pilot_note_link": "roadmap",
  "home.cta_primary": "Open the Gospel of Mark",
  "home.cta_secondary": "About the project",
  "home.feature_views_title": "Three views per verse",
  "home.feature_views_body": "Interlinear for close reading, alignment grid for side-by-side scan, apparatus for critical notes. Switch freely; every view shares the same underlying alignment data.",
  "home.feature_variants_title": "Color-coded variants",
  "home.feature_variants_body": "Green for minor stylistic differences, red for substantive divergences, omissions, and additions. Hover to trace the same lexeme across witnesses; click to open the apparatus.",
  "home.feature_search_title": "Search anything",
  "home.feature_search_body_1": "Press",
  "home.feature_search_body_2": "to search Greek, Latin, Syriac, English, or variant type — or jump straight to a reference like",
  "home.feature_enrichment_title": "Enrichment on click",
  "home.feature_enrichment_body_1": "Click a Greek token for its Strong's number, lemma, and morphology (from STEP Bible). Click a Peshitta token for its triliteral root plus Hebrew and Arabic cognates (from the",
  "home.feature_enrichment_body_2": ").",
  "home.aramaic_root_atlas": "Aramaic Root Atlas",
  "home.stat_verses": "Verses aligned",
  "home.stat_witnesses": "Textual witnesses",
  "home.stat_groups": "Alignment groups",
  "home.stat_divergences": "Non-aligned divergences",
  "home.footer_scope": "Currently scoped to the Gospel of Mark. The other gospels and more witnesses are planned.",
  "home.footer_link": "Read the methodology →"
}
```

- [ ] **Step 2: Replace strings in `templates/home.html`**

Replace the `{% block title %}` and `{% block description %}` and `{% block brand_meta %}`:

```jinja
{% block title %}{{ t('home.title_meta') }}{% endblock %}
{% block description %}{{ t('home.description_meta') }}{% endblock %}
{% block brand_meta %}{{ t('home.brand_meta') }}{% endblock %}
```

Replace the hero header:

```jinja
<header class="home-hero">
  <p class="home-kicker">{{ t('home.kicker') }}</p>
  <h1 class="home-title">
    {{ t('home.title_main') }}
    <span class="home-title-accent">{{ t('home.title_accent') }}</span>
  </h1>
  <p class="home-lede">{{ t('home.lede') }}</p>

  <p class="home-pilot-note">
    <strong>{{ t('home.pilot_note_strong') }}</strong> {{ t('home.pilot_note_body') }}
    <a href="{{ url_for('about') }}#roadmap-section">{{ t('home.pilot_note_link') }}</a>.
  </p>

  <div class="home-actions">
    <a class="home-cta" href="{{ url_for('verse', book='mark', chapter=1, verse=1) }}">
      {{ t('home.cta_primary') }}
      <span class="home-cta-arrow">→</span>
    </a>
    <a class="home-cta-secondary" href="{{ url_for('about') }}">{{ t('home.cta_secondary') }}</a>
  </div>
</header>
```

Replace the features cards:

```jinja
<section class="home-features">
  <article class="home-card">
    <h3>{{ t('home.feature_views_title') }}</h3>
    <p>{{ t('home.feature_views_body') }}</p>
  </article>
  <article class="home-card">
    <h3>{{ t('home.feature_variants_title') }}</h3>
    <p>{{ t('home.feature_variants_body') }}</p>
  </article>
  <article class="home-card">
    <h3>{{ t('home.feature_search_title') }}</h3>
    <p>{{ t('home.feature_search_body_1') }} <kbd>⌘K</kbd> / <kbd>Ctrl-K</kbd> {{ t('home.feature_search_body_2') }}
      <code>13:14</code>.</p>
  </article>
  <article class="home-card">
    <h3>{{ t('home.feature_enrichment_title') }}</h3>
    <p>{{ t('home.feature_enrichment_body_1') }}
      <a href="https://aramaic-root-atlas.onrender.com">{{ t('home.aramaic_root_atlas') }}</a>{{ t('home.feature_enrichment_body_2') }}</p>
  </article>
</section>
```

Replace the stats strip:

```jinja
<section class="home-stats">
  <div class="home-stat">
    <div class="home-stat-num">676</div>
    <div class="home-stat-label">{{ t('home.stat_verses') }}</div>
  </div>
  <div class="home-stat">
    <div class="home-stat-num">3</div>
    <div class="home-stat-label">{{ t('home.stat_witnesses') }}</div>
  </div>
  <div class="home-stat">
    <div class="home-stat-num">8,206</div>
    <div class="home-stat-label">{{ t('home.stat_groups') }}</div>
  </div>
  <div class="home-stat">
    <div class="home-stat-num">~2,600</div>
    <div class="home-stat-label">{{ t('home.stat_divergences') }}</div>
  </div>
</section>
```

Replace the home footer:

```jinja
<footer class="home-footer">
  <p>{{ t('home.footer_scope') }}
    <a href="{{ url_for('about') }}">{{ t('home.footer_link') }}</a></p>
</footer>
```

- [ ] **Step 3: Run tests + smoke**

Run:
```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/')
    body = rv.data.decode()
    assert rv.status_code == 200
    assert 'three witnesses in parallel' in body
    assert 'Open the Gospel of Mark' in body
    assert 'Verses aligned' in body
    assert 'roadmap' in body
    print('OK')
"
```
Expected: tests green, `OK`.

- [ ] **Step 4: Commit**

```bash
git add translations/en.json templates/home.html
git commit -m "feat(i18n): extract home.html strings to en.json (28 keys)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task A6: Extract strings from `templates/about.html`

**Files:**
- Modify: `translations/en.json`
- Modify: `templates/about.html`

This template has the largest string surface (337 lines, mostly prose). The strategy is to extract by section: head/lede, methodology, validation, viewer-inspiration, sources, related-works, "what this app is good for", roadmap, versification, license, contact.

- [ ] **Step 1: Append about.html keys to `translations/en.json`**

Open `translations/en.json` and add (merge with existing). The full set is large; the keys follow `about.<section>.<role>` structure. Use the prose verbatim from the current English template.

```json
{
  "about.title_meta": "Methodology — Translation Aligner",
  "about.description_meta": "Methodology, data sources, and author for Translation Aligner — a word-by-word alignment of the Gospel of Mark across Greek NT, Syriac Peshitta, and Latin Vulgate generated by Anthropic Claude and benchmarked at 67.7% agreement against the Berean Interlinear Bible.",
  "about.brand_meta": "Methodology",
  "about.h1": "About the Translation Aligner",
  "about.pilot_note_strong": "This is a pilot.",
  "about.pilot_note_body": "Current scope is the Gospel of Mark only. The full plan — additional NT books, the Hebrew Bible flagship, further witnesses, export formats, and two planned sub-projects — is laid out in the",
  "about.pilot_note_link": "roadmap below",
  "about.lede": "A word-by-word alignment of the Gospel of Mark across three textual witnesses — Greek NT, Syriac Peshitta, and Latin Clementine Vulgate — with a one- or two-sentence apparatus note on every divergence.",
  "about.author_label": "Author",
  "about.author_name": "Jossi Fresco Benaim",
  "about.h2_methodology": "Methodology",
  "about.methodology_p1": "Every verse in Mark has been aligned word-by-word across the three witnesses by Anthropic's Claude Sonnet 4.5 via the Batch API. Each alignment group records a <strong>variant verdict</strong> — <em>aligned</em>, <em>minor</em>, <em>major</em>, <em>omitted</em>, or <em>added</em> — plus a <strong>semantic type</strong> (agreement, construction, harmonisation, substitution, idiom, etc.) and, for every non-aligned group, one to two sentences suitable for a critical apparatus.",
  "about.methodology_p2": "Results are pre-computed and stored as per-verse JSON files in the repository — the running viewer has no runtime LLM dependency.",
  "about.h2_validation": "Methodology validation (and its limits)",
  "about.validation_p3": "<strong>What this means:</strong> it's a transferable sanity check, not a correctness guarantee. Claude's Greek→English alignment logic is consistent with an established scholarly interlinear, which rules out catastrophic failure modes and suggests the 3-way Greek / Peshitta / Vulgate alignments in this viewer use the same reasonable reasoning. It does <em>not</em> directly measure the quality of the Peshitta or Vulgate alignments (no ground-truth reference exists), nor does it measure apparatus-note quality, variant classification, or type-tag correctness.",
  "about.validation_p4": "Berean is used only as a methodology benchmark — never as display data in the viewer.",
  "about.h2_inspiration": "Viewer inspiration",
  "about.h2_data_sources": "Data sources",
  "about.h2_related_works": "Related works",
  "about.h2_what_for": "What this app is good for",
  "about.what_for_intro": "The underlying engine is a <strong>multi-witness parallel-text viewer with a critical apparatus</strong>. Anywhere a text exists in more than one version, this tool can show it side-by-side with per-word alignment and annotated divergences.",
  "about.h3_scholarship": "Biblical scholarship",
  "about.h3_teaching": "Teaching",
  "about.h3_translation_work": "Translation work",
  "about.h3_reader": "Reader-facing discovery",
  "about.h2_roadmap": "Roadmap",
  "about.h3_up_next": "Up next",
  "about.h3_book_coverage": "Expand book coverage",
  "about.h3_witness_coverage": "Expand witness coverage (within current books)",
  "about.h3_viewer_features": "Viewer features",
  "about.h3_export": "Export",
  "about.h3_subprojects": "Sub-projects",
  "about.h2_versification": "Versification",
  "about.versification_body": "Verse labels follow NA28 numbering. The Clementine Vulgate uses a different verse split in some chapters; where necessary (notably Mark 9 and Mark 4:40–41) we've remapped the Vulgate text to the NA28 boundaries. See the repository's <code>known-issues.md</code> for the complete list of edits.",
  "about.h2_license": "License & reuse",
  "about.license_body": "The viewer code is intended to be released under an open-source license once the project is publicly funded. The derived alignment JSON is produced from sources with mixed licenses (CC BY 4.0, public domain); any future redistribution will credit the upstream sources.",
  "about.h2_contact": "Contact",
  "about.contact_body": "Feedback welcome —",
  "about.contact_email": "jossi@somosunodigital.com"
}
```

- [ ] **Step 2: Replace strings in `templates/about.html`**

For each section in `about.html`, replace the literal English text with `{{ t('about.<key>') }}`. Sections that contain dynamic content (the benchmark numbers, the list of features) are left as-is — only the prose changes.

For sections containing inline HTML (`<strong>`, `<em>`, `<a>`), use the Jinja `safe` filter on the translated string so HTML is not double-escaped:

```jinja
<p>{{ t('about.methodology_p1') | safe }}</p>
```

Read every English-text line in `about.html` and replace with the corresponding `t()` call. The full conversion: every `<h1>`, `<h2>`, `<h3>`, `<p>` literal English string becomes `{{ t('about.X') | safe }}` (with `safe` only when the English value contains HTML).

For roadmap items inside `<ul class="about-roadmap">`, leave the literal English text in place for this task — the roadmap content is large and gets its own task (A7).

- [ ] **Step 3: Run tests + smoke**

Run:
```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/about')
    assert rv.status_code == 200
    body = rv.data.decode()
    assert 'About the Translation Aligner' in body
    assert 'Methodology' in body
    assert 'Up next' in body
    assert 'jossi@somosunodigital.com' in body
    print('OK')
"
```
Expected: green + `OK`.

- [ ] **Step 4: Commit**

```bash
git add translations/en.json templates/about.html
git commit -m "feat(i18n): extract about.html prose to en.json (~30 keys)

Roadmap list items deferred to A7 — they're a separate semantic block
with many bullets best handled in their own commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task A7: Extract about.html roadmap bullets

**Files:**
- Modify: `translations/en.json`
- Modify: `templates/about.html`

- [ ] **Step 1: Add roadmap-bullet keys**

Add the following keys to `translations/en.json`. Each `<li>` in the existing `about.html` roadmap section becomes one key. Use one key per `<li>` — even short ones — so future translators can edit per-item without touching neighbors.

For each `<li>` in `about.html` under the Roadmap section, replace the literal text with `{{ t('about.roadmap.<slug>') | safe }}`. Slugs follow this pattern:

- `about.roadmap.scholarship_text_critical`
- `about.roadmap.scholarship_synoptic`
- `about.roadmap.scholarship_semitic`
- `about.roadmap.scholarship_translation_technique`
- `about.roadmap.scholarship_harmonisation`
- `about.roadmap.teaching_pedagogy`
- `about.roadmap.teaching_comparative`
- `about.roadmap.teaching_critical_edition`
- `about.roadmap.translation_check`
- `about.roadmap.translation_committee`
- `about.roadmap.reader_critical`
- `about.roadmap.reader_liturgical`
- `about.roadmap.up_next_i18n`
- `about.roadmap.up_next_syriac_font`
- `about.roadmap.up_next_settings`
- `about.roadmap.book_coverage_intro_nt`
- `about.roadmap.book_coverage_gospels`
- `about.roadmap.book_coverage_acts`
- `about.roadmap.book_coverage_pauline`
- `about.roadmap.book_coverage_general_revelation`
- `about.roadmap.book_coverage_intro_hebrew`
- `about.roadmap.book_coverage_torah`
- `about.roadmap.book_coverage_former_prophets`
- `about.roadmap.book_coverage_latter_prophets`
- `about.roadmap.book_coverage_dss`
- `about.roadmap.book_coverage_writings`
- `about.roadmap.book_coverage_intro_deutero`
- `about.roadmap.book_coverage_deutero`
- `about.roadmap.witness_web`
- `about.roadmap.witness_byzantine`
- `about.roadmap.witness_orthodox_chinese`
- `about.roadmap.witness_coptic`
- `about.roadmap.witness_armenian`
- `about.roadmap.witness_ethiopic`
- `about.roadmap.witness_old_latin`
- `about.roadmap.witness_targum`
- `about.roadmap.viewer_a11y`
- `about.roadmap.viewer_xrefs`
- `about.roadmap.viewer_chapter_panel`
- `about.roadmap.viewer_bookmarks`
- `about.roadmap.viewer_mobile`
- `about.roadmap.viewer_hebrew_cognate`
- `about.roadmap.export_tei`
- `about.roadmap.export_bibtex`
- `about.roadmap.export_csv`
- `about.roadmap.export_json`
- `about.roadmap.subproject_engine`
- `about.roadmap.subproject_review`

The English value for each key is the verbatim current text (including inline HTML — use the `safe` filter when rendering).

- [ ] **Step 2: Run tests + smoke**

Run:
```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/about')
    body = rv.data.decode()
    assert 'Internationalization' in body  # roadmap up_next_i18n key value
    assert 'All four gospels' in body
    assert 'Orthodox Chinese cluster' in body
    assert 'TEI XML' in body
    print('OK')
"
```
Expected: green + `OK`.

- [ ] **Step 3: Commit**

```bash
git add translations/en.json templates/about.html
git commit -m "feat(i18n): extract about.html roadmap bullets to en.json (~46 keys)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task A8: Extract `verse.html` strings

**Files:**
- Modify: `translations/en.json`
- Modify: `templates/verse.html`

- [ ] **Step 1: Add verse.html keys**

Append to `translations/en.json`:

```json
{
  "verse.title_meta_suffix": "— Greek / Peshitta / Vulgate aligned — Translation Aligner",
  "verse.description_meta_prefix": "aligned word-by-word across the Greek NT, Syriac Peshitta, and Latin Vulgate",
  "verse.description_meta_variants_prefix": "— ",
  "verse.description_meta_variants_suffix": "textual variants classified and annotated.",
  "verse.brand_meta_prefix": "Mk",
  "verse.jump_book_label": "Mark",
  "verse.jump_chapter_aria": "Chapter",
  "verse.jump_verse_aria": "Verse",
  "verse.jump_go": "Go",
  "verse.tab_interlinear": "Interlinear",
  "verse.tab_grid": "Alignment grid",
  "verse.tab_apparatus": "Apparatus"
}
```

- [ ] **Step 2: Replace strings in `templates/verse.html`**

Replace `{% block title %}`:
```jinja
{% block title %}{{ verse.ref }} {{ t('verse.title_meta_suffix') }}{% endblock %}
```

Replace `{% block description %}`:
```jinja
{% block description %}{{ verse.ref }} {{ t('verse.description_meta_prefix') }}{% if verse.variants %} {{ t('verse.description_meta_variants_prefix') }}{{ verse.variants|length }} {{ t('verse.description_meta_variants_suffix') }}{% endif %}{% endblock %}
```

Replace `{% block brand_meta %}`:
```jinja
{% block brand_meta %}{{ t('verse.brand_meta_prefix') }} · {{ verse.pericope }}{% endblock %}
```

Replace the verse-jump form:
```jinja
<form class="verse-jump" method="get"
      action="" data-book="{{ verse.book|lower }}" data-view="{{ view }}">
  <span class="jump-book">{{ verse.book }}</span>
  <select class="jump-select" name="ch" aria-label="{{ t('verse.jump_chapter_aria') }}">
    {% for ch in book_index.keys() %}
      <option value="{{ ch }}" {% if ch == verse.chapter %}selected{% endif %}>{{ ch }}</option>
    {% endfor %}
  </select>
  <span class="jump-colon">:</span>
  <select class="jump-select" name="v" aria-label="{{ t('verse.jump_verse_aria') }}">
    {% for v in book_index.get(verse.chapter, []) %}
      <option value="{{ v }}" {% if v == verse.verse %}selected{% endif %}>{{ v }}</option>
    {% endfor %}
  </select>
  <button class="jump-go" type="submit">{{ t('verse.jump_go') }}</button>
</form>
```

Replace the mode-tabs `tabs` tuple:
```jinja
{% set tabs = [
  ('interlinear', t('verse.tab_interlinear'),    None),
  ('parallel',    t('verse.tab_grid'),           None),
  ('apparatus',   t('verse.tab_apparatus'),      verse.variants|length),
] %}
```

- [ ] **Step 3: Run tests + smoke**

Run:
```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/verse/mark/1/1')
    body = rv.data.decode()
    assert 'Interlinear' in body
    assert 'Alignment grid' in body
    assert 'Apparatus' in body
    assert 'Go' in body
    print('OK')
"
```
Expected: green + `OK`.

- [ ] **Step 4: Commit**

```bash
git add translations/en.json templates/verse.html
git commit -m "feat(i18n): extract verse.html strings to en.json

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task A9: Extract `_apparatus.html` + `_alignment_grid.html` + `_interlinear.html` + `_rail.html` + `macros.html` + `404.html`

**Files:**
- Modify: `translations/en.json`
- Modify: `templates/_apparatus.html`
- Modify: `templates/_alignment_grid.html`
- Modify: `templates/_rail.html`
- Modify: `templates/macros.html`
- Modify: `templates/404.html`

(`_interlinear.html` has no user-facing English literals — only an em-dash for empty cells. No change needed.)

- [ ] **Step 1: Add partial-template keys**

Append to `translations/en.json`:

```json
{
  "apparatus.title": "Critical apparatus",
  "apparatus.summary_variants": "variants",
  "apparatus.summary_witnesses": "witnesses",
  "rail.this_verse": "This verse",
  "rail.alignment_groups": "Alignment groups",
  "rail.all_three_attest": "All three attest",
  "rail.variant_readings": "Variant readings",
  "rail.major_divergences": "Major divergences",
  "rail.token_legend": "Token legend",
  "rail.legend_intro_grid": "How tokens are marked in the alignment grid.",
  "rail.legend_intro_inter": "How tokens are marked in the interlinear view.",
  "rail.legend_aligned_label": "Aligned",
  "rail.legend_aligned_desc": "Hover to highlight the matching token in each witness.",
  "rail.legend_major_label": "Major variant",
  "rail.legend_major_desc": "Substantive divergence, omission, or addition. Click to jump to apparatus; Shift-click for inline note.",
  "rail.legend_minor_label": "Minor variant",
  "rail.legend_minor_desc": "Stylistic difference (word order, particle, synonym). Click to jump to apparatus; Shift-click for inline note.",
  "rail.legend_unaligned_label": "Unaligned",
  "rail.legend_unaligned_desc": "Content present in only one witness, with no counterpart elsewhere.",
  "rail.variants_jump": "Variants · jump to apparatus",
  "rail.variants_jump_intro": "Each row links to the Apparatus tab, scrolled to that variant.",
  "notfound.title_meta": "Not found — Translation Alignment",
  "notfound.h1": "Verse not found",
  "notfound.body_prefix": "That chapter and verse aren't in the pilot corpus (Mark only). Try",
  "notfound.body_link": "Mark 1:1",
  "notfound.body_suffix": "to start reading."
}
```

- [ ] **Step 2: Replace strings in `_apparatus.html`**

```jinja
<header class="apparatus-head">
  <h2 class="apparatus-title">{{ t('apparatus.title') }}</h2>
  <div class="apparatus-sub">
    {{ verse.variants|length }} {{ t('apparatus.summary_variants') }} · {{ verse.witnesses|length }} {{ t('apparatus.summary_witnesses') }}
  </div>
</header>
```

- [ ] **Step 3: Replace strings in `_rail.html`**

```jinja
<aside class="rail" id="rail">
  <div class="rail-section">
    <div class="rail-title">{{ t('rail.this_verse') }}</div>
    <div class="stat-row">
      <span class="stat-label">{{ t('rail.alignment_groups') }}</span>
      <span class="stat-val">{{ stats.total }}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">{{ t('rail.all_three_attest') }}</span>
      <span class="stat-val">{{ stats.all_three }} / {{ stats.total }}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">{{ t('rail.variant_readings') }}</span>
      <span class="stat-val">{{ stats.variants }}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">{{ t('rail.major_divergences') }}</span>
      <span class="stat-val">{{ stats.major }}</span>
    </div>
  </div>

  <div class="rail-section">
    <div class="rail-title">{{ t('rail.token_legend') }}</div>
    <p class="rail-sub">
      {% if view == 'parallel' %}{{ t('rail.legend_intro_grid') }}{% else %}{{ t('rail.legend_intro_inter') }}{% endif %}
    </p>
    <div class="legend-item">
      <div class="legend-sample sample-aligned">{{ t('rail.legend_aligned_label') }}</div>
      <p class="legend-desc">{{ t('rail.legend_aligned_desc') }}</p>
    </div>
    <div class="legend-item">
      <div class="legend-sample sample-major">{{ t('rail.legend_major_label') }}</div>
      <p class="legend-desc">{{ t('rail.legend_major_desc') }}</p>
    </div>
    <div class="legend-item">
      <div class="legend-sample sample-minor">{{ t('rail.legend_minor_label') }}</div>
      <p class="legend-desc">{{ t('rail.legend_minor_desc') }}</p>
    </div>
    <div class="legend-item">
      <div class="legend-sample sample-unaligned"><em>{{ t('rail.legend_unaligned_label') }}</em></div>
      <p class="legend-desc">{{ t('rail.legend_unaligned_desc') }}</p>
    </div>
  </div>

  {% if verse.variants %}
  <div class="rail-section">
    <div class="rail-title">
      <span>{{ t('rail.variants_jump') }}</span>
      <span class="count">{{ verse.variants|length }}</span>
    </div>
    <p class="rail-sub">{{ t('rail.variants_jump_intro') }}</p>
    {% for v in verse.variants %}
      <a class="notes-item"
         href="{{ url_for('verse', book=verse.book|lower, chapter=verse.chapter, verse=verse.verse, view='apparatus', variant=v.id) }}#variant-{{ v.id }}"
         data-variant-link="{{ v.id }}">{{ v.title }}</a>
    {% endfor %}
  </div>
  {% endif %}
</aside>
```

- [ ] **Step 4: Replace strings in `_alignment_grid.html`**

The only literal English string in this template is the em-dash placeholder (`—`); no change needed. (Numbers like `loop.index` are not localized.)

- [ ] **Step 5: Replace strings in `macros.html`**

`macros.html` has no literal English strings; all data comes from witness objects (`w.sigil`, `w.name`, etc.) which are populated server-side from the alignment JSON. No change needed.

- [ ] **Step 6: Replace strings in `404.html`**

```jinja
{% extends "base.html" %}
{% block title %}{{ t('notfound.title_meta') }}{% endblock %}
{% block content %}
<section class="not-found">
  <h1>{{ t('notfound.h1') }}</h1>
  <p>{{ t('notfound.body_prefix') }}
  <a href="/verse/mark/1/1">{{ t('notfound.body_link') }}</a> {{ t('notfound.body_suffix') }}</p>
</section>
{% endblock %}
```

- [ ] **Step 7: Run tests + smoke**

Run:
```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv1 = c.get('/verse/mark/1/1?view=apparatus')
    rv2 = c.get('/verse/mark/13/14')   # has variants
    rv3 = c.get('/verse/mark/99/99')   # 404
    assert 'Critical apparatus' in rv1.data.decode()
    assert 'Token legend' in rv2.data.decode()
    assert 'Verse not found' in rv3.data.decode()
    print('OK')
"
```
Expected: green + `OK`.

- [ ] **Step 8: Commit**

```bash
git add translations/en.json templates/_apparatus.html templates/_rail.html templates/404.html
git commit -m "feat(i18n): extract partials + 404 strings to en.json

_alignment_grid.html, _interlinear.html, macros.html have no literal
English strings (data-driven only) — no change needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task A10: Locale hook in `app.py` — path-prefix stripping + `g.lang`

**Files:**
- Modify: `app.py`
- Test: `tests/test_routes_localized.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_routes_localized.py`:

```python
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
    """Auto-redirect fires only at /, never on deep paths."""
    with app.test_client() as c:
        rv = c.get(
            "/verse/mark/1/1",
            headers={"Accept-Language": "es-MX,es;q=0.9"},
        )
        # No 302 — even though Accept-Language is Spanish.
        assert rv.status_code == 200
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_routes_localized.py -v`
Expected: FAIL on the `/es/` and `/zh-Hans/` tests (404, since those routes don't exist yet).

- [ ] **Step 3: Add locale hook to `app.py`**

After the `_translations = ...` block in `app.py`, add:

```python
LANG_PREFIXES = ("es", "zh-Hans", "zh-Hant")
```

Replace the existing `_ensure_init` with this combined hook (keeps init guarantee, adds locale resolution):

```python
@app.before_request
def _ensure_init_and_locale() -> None:
    _init()
    # Default locale
    from flask import g
    g.lang = "en"
    path = request.path
    for lang in LANG_PREFIXES:
        if path == f"/{lang}" or path.startswith(f"/{lang}/"):
            g.lang = lang
            stripped = path[len(f"/{lang}"):] or "/"
            request.environ["PATH_INFO"] = stripped
            break
```

Delete the existing standalone `_ensure_init` registered with `@app.before_request` (it's now folded into `_ensure_init_and_locale`).

- [ ] **Step 4: Run tests to verify pass**

Run:
```bash
pytest -q
```
Expected: All tests green, including the 7 new `test_routes_localized.py` tests.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_routes_localized.py
git commit -m "$(cat <<'EOF'
feat(i18n): locale-prefix request hook + g.lang resolution

before_request strips /<lang>/ prefix and sets g.lang. Existing routes
resolve unchanged because PATH_INFO is rewritten in WSGI environ.
Auto-redirect logic comes in the next task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A11: Auto-redirect at `/` + `lang` cookie persistence

**Files:**
- Modify: `app.py` — extend the locale hook + add `after_request`
- Modify: `tests/test_routes_localized.py` — add cookie + redirect tests

- [ ] **Step 1: Add tests for auto-redirect + cookie**

Append to `tests/test_routes_localized.py`:

```python
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


def test_root_with_existing_cookie_does_not_redirect():
    with app.test_client() as c:
        c.set_cookie("localhost", "lang", "zh-Hans")
        rv = c.get("/", headers={"Accept-Language": "es-MX"})
        # Cookie says zh-Hans but path is /, so no redirect (cookie alone
        # never triggers redirect — only Accept-Language on first visit).
        assert rv.status_code == 200
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_routes_localized.py -v`
Expected: FAIL on the 4 new redirect tests.

- [ ] **Step 3: Extend the locale hook with auto-redirect + cookie**

Replace `_ensure_init_and_locale` in `app.py` with:

```python
@app.before_request
def _ensure_init_and_locale():
    _init()
    from flask import g
    g.lang = "en"
    path = request.path
    for lang in LANG_PREFIXES:
        if path == f"/{lang}" or path.startswith(f"/{lang}/"):
            g.lang = lang
            stripped = path[len(f"/{lang}"):] or "/"
            request.environ["PATH_INFO"] = stripped
            return None
    # Auto-redirect only at bare root, only when no cookie
    if path == "/" and "lang" not in request.cookies:
        from translation_core.i18n import parse_accept_language
        wanted = parse_accept_language(request.headers.get("Accept-Language"))
        if wanted:
            from flask import make_response
            resp = make_response(redirect(f"/{wanted}/", code=302))
            resp.set_cookie("lang", wanted, max_age=60 * 60 * 24 * 365, samesite="Lax")
            return resp
    return None


@app.after_request
def _set_lang_cookie(response):
    """Persist g.lang in a cookie when one is missing.

    Skips redirects (already set) and assets that don't need it.
    """
    from flask import g
    if "lang" in request.cookies:
        return response
    if response.status_code in (301, 302, 303, 307, 308):
        # Already has its own Set-Cookie if we wanted one
        return response
    lang = getattr(g, "lang", "en")
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return response
```

- [ ] **Step 4: Run all tests to verify green**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_routes_localized.py
git commit -m "feat(i18n): auto-redirect at / on first visit + sticky lang cookie

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task A12: JS-side i18n delivery via injected `<script id=\"i18n-data\">`

**Files:**
- Modify: `app.py` — pass `i18n_for_js` into Jinja context
- Modify: `templates/base.html` — render the injected JSON
- Modify: `static/js/aligner.js` — read `window.__I18N__` for "No matches.", "Close search"
- Modify: `translations/en.json` — add `js.*` keys

- [ ] **Step 1: Add `js.*` keys**

Append to `translations/en.json`:

```json
{
  "js.search_close_aria": "Close search",
  "js.search_no_matches": "No matches."
}
```

- [ ] **Step 2: Compute and pass `i18n_for_js` from `app.py`**

In `app.py`, just before `app.jinja_env.globals["t"] = t`, add a helper:

```python
def i18n_for_js() -> dict[str, str]:
    """Return the subset of translation keys whose path starts with 'js.'.

    This is what gets injected as window.__I18N__ on every page.
    """
    from flask import g
    lang = getattr(g, "lang", "en")
    en_keys = _translations.keys("en")
    return {k: _translations.t(k, lang) for k in en_keys if k.startswith("js.")}


app.jinja_env.globals["i18n_for_js"] = i18n_for_js
```

- [ ] **Step 3: Inject the script tag in `base.html`**

In `templates/base.html`, just before the closing `</body>`, before the `<script src=...aligner.js>` line, add:

```jinja
<script id="i18n-data" type="application/json">{{ i18n_for_js() | tojson }}</script>
<script>
  window.__I18N__ = JSON.parse(document.getElementById('i18n-data').textContent);
</script>
```

- [ ] **Step 4: Add `t()` helper to `aligner.js` and use it**

At the very top of `static/js/aligner.js`, add:

```javascript
const I18N = (typeof window !== "undefined" && window.__I18N__) || {};
function t(key) { return I18N[key] || key; }
```

Replace `closeBtn.setAttribute("aria-label", "Close search");` with:
```javascript
closeBtn.setAttribute("aria-label", t("js.search_close_aria"));
```

Replace `results.innerHTML = '<li class="empty">No matches.</li>';` with:
```javascript
results.innerHTML = '<li class="empty">' + escapeHtml(t("js.search_no_matches")) + '</li>';
```

- [ ] **Step 5: Smoke + commit**

Run:
```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/')
    body = rv.data.decode()
    assert 'window.__I18N__' in body
    assert '\"js.search_no_matches\":\"No matches.\"' in body
    print('OK')
"
```

```bash
git add translations/en.json app.py templates/base.html static/js/aligner.js
git commit -m "feat(i18n): inject window.__I18N__ for aligner.js client strings

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task A13 (Phase A close): Full pytest + manual verification

- [ ] **Step 1: Run full pytest suite**

Run: `pytest -q`
Expected: all tests pass, total < 1 s.

- [ ] **Step 2: Run gunicorn locally and probe routes**

```bash
cd "/Users/jfresco16/Google Drive/Claude/Translation_alignment"
source .venv/bin/activate
PORT=5024 gunicorn app:app --workers 1 --bind 0.0.0.0:5024 --log-level warning &
sleep 2
for url in "/" "/about" "/verse/mark/1/1" "/verse/mark/13/14?view=apparatus" "/es/" "/zh-Hans/about" "/zh-Hant/verse/mark/1/1"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5024$url")
  echo "$url -> HTTP $code"
done
pkill -f "gunicorn app:app --workers 1 --bind 0.0.0.0:5024" 2>/dev/null
```

Expected:
```
/ -> HTTP 200
/about -> HTTP 200
/verse/mark/1/1 -> HTTP 200
/verse/mark/13/14?view=apparatus -> HTTP 200
/es/ -> HTTP 200
/zh-Hans/about -> HTTP 200
/zh-Hant/verse/mark/1/1 -> HTTP 200
```

(All localized routes return 200 and render the **English** strings — that's correct: Phase A only adds the plumbing.)

- [ ] **Step 3: Tag the phase**

```bash
git tag i18n-phase-a-complete
```

(Optional: don't push the tag; it's just a local marker.)

---

## Phase B — Spanish UI + RV1909 verses + Settings cog

### Task B1: Ingest RV1909 — `scripts/ingest_rv1909.py`

**Files:**
- Create: `scripts/ingest_rv1909.py`
- Create: `data/corpora/rv1909.csv` (output of script)
- Test: `tests/test_gloss_csv_load.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_gloss_csv_load.py`:

```python
"""Tests for verse-text CSVs used as gloss sources."""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "data" / "corpora"


def _load_mark_refs(path: Path) -> set[tuple[int, int]]:
    """Return {(chapter, verse), ...} for Mark from a corpora CSV."""
    refs: set[tuple[int, int]] = set()
    if not path.exists():
        return refs
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("book") == "Mark":
                refs.add((int(row["chapter"]), int(row["verse"])))
    return refs


def test_rv1909_exists_and_has_mark():
    path = CORPORA / "rv1909.csv"
    assert path.exists(), "Run scripts/ingest_rv1909.py first"
    refs = _load_mark_refs(path)
    assert len(refs) >= 670, f"expected ~676 Mark verses, got {len(refs)}"


def test_rv1909_mark_matches_web_versification():
    """RV1909 must cover the same (chapter, verse) tuples as web.csv for Mark."""
    rv = _load_mark_refs(CORPORA / "rv1909.csv")
    web = _load_mark_refs(CORPORA / "web.csv")
    if not rv:
        pytest.skip("rv1909.csv not yet ingested")
    missing = web - rv
    extra = rv - web
    assert not missing, f"RV1909 missing {len(missing)} Mark verses: {sorted(missing)[:10]}"
    assert not extra, f"RV1909 has {len(extra)} verses not in web.csv: {sorted(extra)[:10]}"


def test_rv1909_mark_1_1_contains_evangelio():
    path = CORPORA / "rv1909.csv"
    if not path.exists():
        pytest.skip("rv1909.csv not yet ingested")
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("book") == "Mark" and row.get("chapter") == "1" and row.get("verse") == "1":
                assert "evangelio" in row["text"].lower(), f"got: {row['text']!r}"
                return
    pytest.fail("Mark 1:1 not found in rv1909.csv")
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_gloss_csv_load.py::test_rv1909_exists_and_has_mark -v`
Expected: FAIL — file doesn't exist.

- [ ] **Step 3: Write the ingestion script**

Create `scripts/ingest_rv1909.py`:

```python
"""Ingest Reina-Valera 1909 from eBible.org USFX → data/corpora/rv1909.csv.

Usage:
    python scripts/ingest_rv1909.py --download   # fetches USFX from eBible
    python scripts/ingest_rv1909.py              # re-runs from cached zip
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "data" / "corpora"
CACHE = ROOT / "data" / "_ingest_cache"
USFX_URL = "https://ebible.org/Scriptures/spavbl_usfx.zip"
USFX_ZIP = CACHE / "spavbl_usfx.zip"
OUT = CORPORA / "rv1909.csv"

# Mark book code in USFX
BOOK_CODE = "MRK"
# OSIS / web.csv display name
BOOK_NAME = "Mark"


def download() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {USFX_URL} ...", file=sys.stderr)
    urllib.request.urlretrieve(USFX_URL, USFX_ZIP)


def extract_mark_from_usfx(zip_path: Path) -> list[tuple[int, int, str]]:
    """Walk USFX XML inside the zip; return [(chapter, verse, text), ...] for Mark.

    USFX flavor: <book id="MRK"><c id="1"/><v id="1"/>Principio del...<ve/>...
    """
    rows: list[tuple[int, int, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        # Find the .usfx.xml file
        usfx_name = next(
            (n for n in zf.namelist() if n.endswith(".usfx.xml")),
            None,
        )
        if not usfx_name:
            raise RuntimeError(f"No .usfx.xml in {zip_path}")
        xml = zf.read(usfx_name).decode("utf-8")

    # Find the Mark book block
    book_re = re.compile(
        rf'<book\s+id="{BOOK_CODE}".*?</book>',
        re.DOTALL,
    )
    m = book_re.search(xml)
    if not m:
        raise RuntimeError(f"Book {BOOK_CODE} not found in USFX")
    book_xml = m.group(0)

    chapter = 0
    verse = 0
    buf: list[str] = []

    # Tokenize on chapter/verse markers and verse-end markers
    parts = re.split(
        r'(<c\s+id="\d+"\s*/>|<v\s+id="\d+"\s*/>|<ve\s*/>)',
        book_xml,
    )
    for tok in parts:
        if not tok:
            continue
        m_c = re.match(r'<c\s+id="(\d+)"\s*/>', tok)
        m_v = re.match(r'<v\s+id="(\d+)"\s*/>', tok)
        if m_c:
            # Flush any open verse first
            if chapter and verse and buf:
                rows.append((chapter, verse, _clean(" ".join(buf))))
            chapter = int(m_c.group(1))
            verse = 0
            buf = []
            continue
        if m_v:
            if chapter and verse and buf:
                rows.append((chapter, verse, _clean(" ".join(buf))))
            verse = int(m_v.group(1))
            buf = []
            continue
        if tok.startswith("<ve"):
            if chapter and verse and buf:
                rows.append((chapter, verse, _clean(" ".join(buf))))
            buf = []
            continue
        # Plain content (might contain other tags — strip)
        buf.append(_strip_tags(tok))

    # Flush trailing
    if chapter and verse and buf:
        rows.append((chapter, verse, _clean(" ".join(buf))))

    return rows


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def write_csv(rows: list[tuple[int, int, str]]) -> None:
    CORPORA.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "verse", "reference", "text"])
        for ch, v, text in rows:
            w.writerow([BOOK_NAME, ch, v, f"{BOOK_NAME} {ch}:{v}", text])
    print(f"Wrote {len(rows)} verses to {OUT}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    if args.download or not USFX_ZIP.exists():
        download()
    rows = extract_mark_from_usfx(USFX_ZIP)
    if len(rows) < 670:
        print(f"WARN: only {len(rows)} Mark verses extracted", file=sys.stderr)
    write_csv(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the ingestion script**

```bash
python scripts/ingest_rv1909.py --download
```

Expected: download succeeds, ~677 rows written. If the eBible URL fails, fallback: clone `https://github.com/scrollmapper/bible_databases` and read `csv/RV1909_Mark.csv` (adapt the script's `extract_mark_from_usfx` to read the alternate format).

- [ ] **Step 5: Run the gloss-csv tests**

Run: `pytest tests/test_gloss_csv_load.py -v -k rv1909`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/ingest_rv1909.py data/corpora/rv1909.csv tests/test_gloss_csv_load.py
git commit -m "$(cat <<'EOF'
feat(i18n): ingest Reina-Valera 1909 → data/corpora/rv1909.csv

eBible.org USFX → CSV with the same shape as web.csv. Verse-count
parity check passes (RV1909 covers every Mark verse in web.csv).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B2: Wire RV1909 into the gloss map

**Files:**
- Modify: `app.py` — extend `_init` to load all gloss CSVs into `_gloss_maps`
- Modify: `app.py` — extend `_load_verse` to pass `gloss_map` to template

- [ ] **Step 1: Replace `_web_map` with `_gloss_maps` dict**

In `app.py`, replace:
```python
_web_map: dict[str, str] = {}  # ref -> English text
```
with:
```python
# ref -> per-language verse text. Keys: 'en', 'es', 'zh-Hans', 'zh-Hant'.
_gloss_maps: dict[str, dict[str, str]] = {
    "en": {},
    "es": {},
    "zh-Hans": {},
    "zh-Hant": {},
}
```

- [ ] **Step 2: Extend `_init` to load all gloss CSVs**

Replace the existing `web_path = ...` block in `_init` with:

```python
GLOSS_FILES = {
    "en":      "web.csv",
    "es":      "rv1909.csv",
    "zh-Hans": "cuv_hans.csv",
    "zh-Hant": "cuv_hant.csv",
}

for lang, filename in GLOSS_FILES.items():
    path = DATA_DIR / "corpora" / filename
    if not path.exists():
        continue   # acceptable during incremental rollout
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            _gloss_maps[lang][row["reference"]] = row["text"]
```

(Define `GLOSS_FILES` at module top level next to `CORPUS_FILES`.)

Also delete any remaining references to `_web_map` and replace with `_gloss_maps['en']` (search the file for `_web_map`).

- [ ] **Step 3: Pass `gloss_map` to template**

In `_load_verse`, replace:
```python
gloss_en = _web_map.get(f"{book_title} {chapter}:{verse}")
```
with:
```python
ref = f"{book_title} {chapter}:{verse}"
gloss_map = {lang: m.get(ref, "") for lang, m in _gloss_maps.items()}
```

Pass `gloss_map=gloss_map` into `convert_alignment_to_verse(...)`.

In `translation_core/converter.py`, accept and propagate `gloss_map` onto the returned verse dict (find where `gloss_en` is set; mirror that with `gloss_map`).

- [ ] **Step 4: Run tests + smoke**

```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/verse/mark/1/1')
    assert rv.status_code == 200
    print('OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add app.py translation_core/converter.py
git commit -m "feat(i18n): replace _web_map with per-language _gloss_maps

Loads web.csv (en) + rv1909.csv (es) + the future CUV files. Each
verse now ships with a gloss_map dict containing all four languages
(empty string when a language hasn't been ingested yet).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task B3: `_gloss_stack.html` partial + verse.html integration

**Files:**
- Create: `templates/_gloss_stack.html`
- Modify: `templates/verse.html`
- Modify: `static/css/styles.css`

- [ ] **Step 1: Create the partial**

Create `templates/_gloss_stack.html`:

```jinja
{# Multi-language verse-gloss stack. Visibility per row is controlled
   by static/js/settings.js based on localStorage.gloss_langs. #}
<div class="gloss-stack" id="gloss-stack">
  {% for lang in supported_langs %}
    {% if verse.gloss_map and verse.gloss_map[lang] %}
      <p class="gloss-row gloss-row-{{ lang }}" data-lang="{{ lang }}">
        <span class="gloss-tag">{{ lang | upper }}</span>
        <span class="gloss-text">{{ verse.gloss_map[lang] }}</span>
      </p>
    {% endif %}
  {% endfor %}
</div>
```

- [ ] **Step 2: Replace single gloss line in `verse.html`**

In `templates/verse.html`, replace:
```jinja
<p class="verse-gloss">{{ verse.gloss_en }}</p>
```
with:
```jinja
{% include "_gloss_stack.html" %}
```

- [ ] **Step 3: Add CSS for gloss stack**

Append to `static/css/styles.css`:

```css
/* --- Gloss stack (multi-language verse text) --- */
.gloss-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 6px 0 8px;
}
.gloss-row {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 10px;
  align-items: baseline;
  margin: 0;
  font-family: 'EB Garamond', serif;
  font-size: 17px;
  line-height: 1.45;
  color: var(--ink-2);
}
.gloss-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--ink-3, #888);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  user-select: none;
}
.gloss-text {
  font-style: italic;
}
.gloss-row[hidden] { display: none; }
.gloss-row-zh-Hans .gloss-text,
.gloss-row-zh-Hant .gloss-text {
  font-family: 'Noto Sans SC', 'Noto Sans TC', 'Source Han Sans', 'PingFang SC', 'Microsoft YaHei', serif;
  font-style: normal;
}
```

- [ ] **Step 4: Run tests + smoke**

```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/verse/mark/1/1')
    body = rv.data.decode()
    assert 'gloss-stack' in body
    assert 'gloss-row-en' in body
    assert 'gloss-row-es' in body  # RV1909 ingested in B1
    print('OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add templates/_gloss_stack.html templates/verse.html static/css/styles.css
git commit -m "feat(i18n): multi-language gloss stack above alignment grid

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task B4: Translate `translations/es.json`

**Files:**
- Create: `translations/es.json`

This is a large but mechanical translation. The values come from a competent Spanish translation of the English keys.

- [ ] **Step 1: Create `translations/es.json` with full translations**

Create `translations/es.json` with translations for every key in `translations/en.json`. Each value is the Spanish equivalent. Use formal "usted"-form Spanish (matches scholarly tone).

Sample of the file (partial — must include every key from `en.json`):

```json
{
  "site.name": "Translation Aligner",
  "site.tagline_default": "Translation Aligner — el Evangelio de Marcos en paralelo",
  "site.description_default": "Una alineación palabra por palabra del Evangelio de Marcos a través del NT griego, la Peshitta siríaca y la Vulgata Clementina latina — con un aparato crítico erudito sobre cada divergencia. Generado por Anthropic Claude, validado contra la Berean Interlinear Bible.",
  "nav.home_aria": "Translation Aligner — inicio",
  "nav.methodology": "Metodología",
  "nav.search_aria": "Buscar (⌘K)",
  "nav.search_title": "Buscar (⌘K)",
  "footer.brand": "Translation Aligner",
  "footer.scope_label": "MVP · Evangelio de Marcos",
  "tweaks.title": "Ajustes",
  "tweaks.view_label": "Modo de vista",
  "tweaks.theme_label": "Tema",
  "tweaks.rail_label": "Panel lateral",
  "tweaks.rail_show": "mostrar",
  "tweaks.rail_hide": "ocultar",
  "search.placeholder": "Busca en griego, Vulgata, Peshitta, español, tipo de variante o 13:14…",
  "search.hint_keys": "↑↓ navegar · ↵ abrir · Esc cerrar",
  "search.hint_scope": "Solo Marcos (alcance piloto)",

  "home.title_meta": "Translation Aligner — el Evangelio de Marcos en griego, siríaco y latín",
  "home.description_meta": "Una alineación palabra por palabra del Evangelio de Marcos a través del NT griego, la Peshitta siríaca y la Vulgata Clementina, con una nota de aparato crítico de una o dos oraciones en cada divergencia — generada por Anthropic Claude y validada contra la Berean Interlinear Bible.",
  "home.brand_meta": "Inicio",
  "home.kicker": "Translation Aligner · Piloto",
  "home.title_main": "El Evangelio de Marcos,",
  "home.title_accent": "tres testigos en paralelo.",
  "home.lede": "Una alineación palabra por palabra del Evangelio de Marcos a través de tres testigos textuales — el Nuevo Testamento griego, la Peshitta siríaca y la Vulgata Clementina latina. Cada divergencia se clasifica por veredicto (menor, mayor, omitido, añadido) y tipo semántico (armonización, sustitución, modismo, orden de palabras, gramática, léxico), y se acompaña de una nota de aparato de una o dos oraciones — un aparato crítico abierto generado por Anthropic Claude.",
  "home.pilot_note_strong": "Esto es un piloto.",
  "home.pilot_note_body": "El alcance actual es solo el Evangelio de Marcos. El plan completo — libros adicionales del NT, la Biblia hebrea, más testigos, formatos de exportación y dos sub-proyectos planificados — está en la",
  "home.pilot_note_link": "hoja de ruta",
  "home.cta_primary": "Abrir el Evangelio de Marcos",
  "home.cta_secondary": "Sobre el proyecto",
  "...": "(continue with every other key from en.json)"
}
```

The implementer must complete every key. Use scholarly Spanish; keep technical terms (Peshitta, Vulgata, NT, Strong's, lema, morfología) unchanged or in their canonical Spanish form. Verses-of-Mark numbering (`13:14`) keeps the colon.

- [ ] **Step 2: Add a key-parity assertion test**

Append to `tests/test_translation_loader.py`:

```python
def test_es_json_has_all_en_keys():
    """es.json must have every key that en.json has, no exceptions."""
    en_path = TRANSLATIONS / "en.json"
    es_path = TRANSLATIONS / "es.json"
    if not es_path.exists():
        pytest.skip("es.json not yet authored")
    en = json.loads(en_path.read_text(encoding="utf-8"))
    es = json.loads(es_path.read_text(encoding="utf-8"))
    missing = set(en) - set(es)
    assert not missing, f"es.json missing {len(missing)} keys: {sorted(missing)[:10]}"
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_translation_loader.py -v`
Expected: green; key-parity test passes (every English key has a Spanish value).

- [ ] **Step 4: Smoke test Spanish home**

```bash
python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/es/')
    body = rv.data.decode()
    assert 'tres testigos en paralelo' in body
    assert 'Abrir el Evangelio de Marcos' in body
    print('OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add translations/es.json tests/test_translation_loader.py
git commit -m "feat(i18n): full Spanish translations (translations/es.json)

Full key parity with en.json; smoke verified on /es/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task B5: Settings cog UI — markup + CSS

**Files:**
- Create: `templates/_settings.html`
- Modify: `templates/base.html` — include settings panel + cog button
- Modify: `translations/en.json` — settings labels
- Modify: `translations/es.json` — settings labels (Spanish)
- Modify: `static/css/styles.css` — settings panel styles

- [ ] **Step 1: Add settings keys**

Append to `translations/en.json`:

```json
{
  "nav.settings_aria": "Settings",
  "settings.title": "Settings",
  "settings.interface_language": "Interface language",
  "settings.verse_translations": "Verse translations",
  "settings.theme": "Theme",
  "settings.theme_light": "Light",
  "settings.theme_dark": "Dark",
  "settings.lang_en": "English",
  "settings.lang_es": "Español",
  "settings.lang_zh_hans": "简体中文",
  "settings.lang_zh_hant": "繁體中文",
  "settings.gloss_en": "English (WEB)",
  "settings.gloss_es": "Español (RV 1909)",
  "settings.gloss_zh_hans": "简体中文 (CUV 简)",
  "settings.gloss_zh_hant": "繁體中文 (CUV 繁)",
  "settings.close": "Close"
}
```

Append the same keys, translated, to `translations/es.json`:

```json
{
  "nav.settings_aria": "Ajustes",
  "settings.title": "Ajustes",
  "settings.interface_language": "Idioma de la interfaz",
  "settings.verse_translations": "Traducciones del versículo",
  "settings.theme": "Tema",
  "settings.theme_light": "Claro",
  "settings.theme_dark": "Oscuro",
  "settings.lang_en": "English",
  "settings.lang_es": "Español",
  "settings.lang_zh_hans": "简体中文",
  "settings.lang_zh_hant": "繁體中文",
  "settings.gloss_en": "English (WEB)",
  "settings.gloss_es": "Español (RV 1909)",
  "settings.gloss_zh_hans": "简体中文 (CUV 简)",
  "settings.gloss_zh_hant": "繁體中文 (CUV 繁)",
  "settings.close": "Cerrar"
}
```

- [ ] **Step 2: Create the settings panel partial**

Create `templates/_settings.html`:

```jinja
<aside class="settings-panel" id="settings-panel" hidden role="dialog"
       aria-labelledby="settings-title">
  <div class="settings-head">
    <h3 id="settings-title">{{ t('settings.title') }}</h3>
    <button type="button" class="settings-close" aria-label="{{ t('settings.close') }}">×</button>
  </div>

  <form class="settings-body">
    <fieldset class="settings-row">
      <legend>{{ t('settings.interface_language') }}</legend>
      {% for lang in supported_langs %}
        <label class="settings-radio">
          <input type="radio" name="interface_lang" value="{{ lang }}"
                 data-current="{{ lang == g.lang }}"/>
          <span>{{ t('settings.lang_' ~ lang.replace('-', '_').lower()) }}</span>
        </label>
      {% endfor %}
    </fieldset>

    <fieldset class="settings-row">
      <legend>{{ t('settings.verse_translations') }}</legend>
      {% for lang in supported_langs %}
        <label class="settings-checkbox">
          <input type="checkbox" name="gloss_lang" value="{{ lang }}"/>
          <span>{{ t('settings.gloss_' ~ lang.replace('-', '_').lower()) }}</span>
        </label>
      {% endfor %}
    </fieldset>

    <fieldset class="settings-row">
      <legend>{{ t('settings.theme') }}</legend>
      <label class="settings-radio">
        <input type="radio" name="theme" value="light"/>
        <span>{{ t('settings.theme_light') }}</span>
      </label>
      <label class="settings-radio">
        <input type="radio" name="theme" value="dark"/>
        <span>{{ t('settings.theme_dark') }}</span>
      </label>
    </fieldset>
  </form>
</aside>
```

- [ ] **Step 3: Add the settings cog button to `base.html`**

In `templates/base.html`, replace the topbar nav:

```jinja
<nav class="topbar-actions">
  <a class="iconbtn" href="{{ url_for('about') }}">{{ t('nav.methodology') }}</a>
  <button class="iconbtn iconbtn-icon" type="button" id="search-trigger"
          aria-label="{{ t('nav.search_aria') }}" title="{{ t('nav.search_title') }}">
    <svg class="icon-search" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/>
      <line x1="15.2" y1="15.2" x2="20" y2="20"
            stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
    <kbd class="iconbtn-kbd">⌘K</kbd>
  </button>
  <button class="iconbtn iconbtn-icon" type="button" id="settings-trigger"
          aria-label="{{ t('nav.settings_aria') }}" title="{{ t('nav.settings_aria') }}">
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2"/>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>
</nav>
```

Just before the closing `</body>`, just before `<script src=".../aligner.js">`, include the settings partial and load `settings.js`:

```jinja
{% include "_settings.html" %}
<script src="{{ url_for('static', filename='js/settings.js') }}"></script>
```

- [ ] **Step 4: Add settings panel CSS**

Append to `static/css/styles.css`:

```css
/* --- Settings panel --- */
.settings-panel {
  position: fixed;
  top: 64px;
  right: 16px;
  z-index: 50;
  width: 320px;
  max-width: calc(100vw - 32px);
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
  font-family: 'Inter', sans-serif;
  font-size: 14px;
}
.settings-panel[hidden] { display: none; }
.settings-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--rule);
}
.settings-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.settings-close {
  background: none;
  border: none;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  color: var(--ink-2);
  padding: 0 4px;
}
.settings-body { padding: 12px 16px; }
.settings-row {
  border: none;
  margin: 0 0 16px;
  padding: 0;
}
.settings-row legend {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-3, #888);
  margin-bottom: 8px;
  padding: 0;
}
.settings-radio,
.settings-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  cursor: pointer;
}
```

- [ ] **Step 5: Run tests + smoke**

```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/')
    body = rv.data.decode()
    assert 'settings-panel' in body
    assert 'settings-trigger' in body
    rv2 = c.get('/es/')
    assert 'Idioma de la interfaz' in rv2.data.decode()
    print('OK')
"
```

- [ ] **Step 6: Commit**

```bash
git add templates/_settings.html templates/base.html translations/en.json translations/es.json static/css/styles.css
git commit -m "feat(i18n): settings cog panel — interface lang, glosses, theme

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task B6: Settings JS — open/close, language switch (server roundtrip), glosses (localStorage), theme

**Files:**
- Create: `static/js/settings.js`

- [ ] **Step 1: Write `settings.js`**

Create `static/js/settings.js`:

```javascript
/* Settings panel behavior. Three concerns:
   1. Interface language: server-roundtrip (sets cookie, redirects).
   2. Verse glosses: localStorage; toggles .gloss-row[hidden] live.
   3. Theme: localStorage; toggles document <html data-theme="...">.
*/
(function () {
  const trigger = document.getElementById("settings-trigger");
  const panel = document.getElementById("settings-panel");
  if (!trigger || !panel) return;

  const SUPPORTED = ["en", "es", "zh-Hans", "zh-Hant"];
  const STORAGE_GLOSSES = "gloss_langs";
  const STORAGE_THEME = "theme";

  // ---- Open / close ----
  const closeBtn = panel.querySelector(".settings-close");
  function open() { panel.hidden = false; }
  function close() { panel.hidden = true; }
  trigger.addEventListener("click", () => panel.hidden ? open() : close());
  if (closeBtn) closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) close();
  });
  document.addEventListener("mousedown", (e) => {
    if (panel.hidden) return;
    if (e.target.closest("#settings-panel")) return;
    if (e.target.closest("#settings-trigger")) return;
    close();
  });

  // ---- Helpers ----
  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }
  function setCookie(name, val, days) {
    const d = new Date();
    d.setTime(d.getTime() + (days || 365) * 86400000);
    document.cookie = name + "=" + encodeURIComponent(val) +
      ";expires=" + d.toUTCString() + ";path=/;SameSite=Lax";
  }
  function readGlosses() {
    try {
      const raw = localStorage.getItem(STORAGE_GLOSSES);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    // Default: just the chrome lang.
    return [getCookie("lang") || "en"];
  }
  function writeGlosses(list) {
    try {
      localStorage.setItem(STORAGE_GLOSSES, JSON.stringify(list));
    } catch (e) {}
  }

  // ---- Initialize form state from storage ----
  const currentLang = getCookie("lang") || "en";
  const currentTheme = localStorage.getItem(STORAGE_THEME) || "light";
  const currentGlosses = readGlosses();

  panel.querySelectorAll('input[name="interface_lang"]').forEach((el) => {
    el.checked = (el.value === currentLang);
  });
  panel.querySelectorAll('input[name="gloss_lang"]').forEach((el) => {
    el.checked = currentGlosses.includes(el.value);
  });
  panel.querySelectorAll('input[name="theme"]').forEach((el) => {
    el.checked = (el.value === currentTheme);
  });

  // ---- Apply current state on page load ----
  applyTheme(currentTheme);
  applyGlosses(currentGlosses);

  // ---- Wire change handlers ----
  panel.querySelectorAll('input[name="interface_lang"]').forEach((el) => {
    el.addEventListener("change", () => {
      if (!el.checked) return;
      const newLang = el.value;
      setCookie("lang", newLang, 365);
      // Redirect to the matching path-prefix.
      const path = window.location.pathname;
      const stripped = stripLangPrefix(path);
      const next = (newLang === "en") ? stripped : ("/" + newLang + stripped);
      window.location.href = next + window.location.search + window.location.hash;
    });
  });

  panel.querySelectorAll('input[name="gloss_lang"]').forEach((el) => {
    el.addEventListener("change", () => {
      const checked = Array.from(
        panel.querySelectorAll('input[name="gloss_lang"]:checked')
      ).map((x) => x.value);
      writeGlosses(checked);
      applyGlosses(checked);
    });
  });

  panel.querySelectorAll('input[name="theme"]').forEach((el) => {
    el.addEventListener("change", () => {
      if (!el.checked) return;
      localStorage.setItem(STORAGE_THEME, el.value);
      applyTheme(el.value);
    });
  });

  function applyGlosses(list) {
    const rows = document.querySelectorAll(".gloss-row");
    rows.forEach((r) => {
      const lang = r.getAttribute("data-lang");
      r.hidden = !list.includes(lang);
    });
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.body.classList.toggle("dark", theme === "dark");
  }

  function stripLangPrefix(path) {
    for (const lang of SUPPORTED) {
      if (lang === "en") continue;
      if (path === "/" + lang || path.startsWith("/" + lang + "/")) {
        return path.slice(("/" + lang).length) || "/";
      }
    }
    return path;
  }
})();
```

- [ ] **Step 2: Smoke test**

```bash
pytest -q && python -c "
from app import app
with app.test_client() as c:
    rv = c.get('/')
    body = rv.data.decode()
    assert '/static/js/settings.js' in body
    print('OK')
"
```

- [ ] **Step 3: Manual check**

Run gunicorn locally and verify:

1. Click cog icon → panel opens
2. Click outside panel → closes
3. Press Esc → closes
4. Switch interface to Spanish → page reloads at `/es/...`
5. Switch back to English → reloads at `/...` (no `/en/`)
6. Check Spanish gloss row → `gloss-row-es` becomes visible
7. Theme toggle → dark mode applies and persists across reloads

```bash
cd "/Users/jfresco16/Google Drive/Claude/Translation_alignment"
source .venv/bin/activate
PORT=5024 gunicorn app:app --workers 1 --bind 0.0.0.0:5024 --log-level warning &
sleep 2
echo "Visit http://localhost:5024/verse/mark/1/1 and exercise the settings panel."
echo "When done: pkill -f 'gunicorn app:app --workers 1 --bind 0.0.0.0:5024'"
```

- [ ] **Step 4: Commit**

```bash
git add static/js/settings.js
git commit -m "feat(i18n): settings panel JS — lang switch, glosses, theme

Interface lang -> cookie + redirect. Glosses -> localStorage live toggle.
Theme -> localStorage with data-theme on <html>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task B7 (Phase B close): full Spanish smoke

- [ ] **Step 1: Run pytest + curl every Spanish path**

```bash
pytest -q
PORT=5024 gunicorn app:app --workers 1 --bind 0.0.0.0:5024 --log-level warning &
sleep 2
for url in "/es/" "/es/about" "/es/verse/mark/1/1" "/es/verse/mark/13/14"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5024$url")
  echo "$url -> HTTP $code"
done
pkill -f "gunicorn app:app --workers 1 --bind 0.0.0.0:5024" 2>/dev/null
```

Expected: all 200.

- [ ] **Step 2: Tag**

```bash
git tag i18n-phase-b-complete
```

---

## Phase C — Chinese UI + CUV Simplified + Traditional

### Task C1: Ingest CUV Simplified + Traditional

**Files:**
- Create: `scripts/ingest_cuv.py`
- Create: `data/corpora/cuv_hans.csv`
- Create: `data/corpora/cuv_hant.csv`
- Modify: `tests/test_gloss_csv_load.py`

- [ ] **Step 1: Add CUV-specific tests**

Append to `tests/test_gloss_csv_load.py`:

```python
def test_cuv_hans_exists():
    path = CORPORA / "cuv_hans.csv"
    assert path.exists(), "Run scripts/ingest_cuv.py --hans first"
    refs = _load_mark_refs(path)
    assert len(refs) >= 670


def test_cuv_hant_exists():
    path = CORPORA / "cuv_hant.csv"
    assert path.exists(), "Run scripts/ingest_cuv.py --hant first"
    refs = _load_mark_refs(path)
    assert len(refs) >= 670


def test_cuv_hans_versification_matches_web():
    cuv = _load_mark_refs(CORPORA / "cuv_hans.csv")
    web = _load_mark_refs(CORPORA / "web.csv")
    if not cuv:
        pytest.skip("cuv_hans.csv not yet ingested")
    missing = web - cuv
    extra = cuv - web
    assert not missing, f"CUV S missing {len(missing)} verses: {sorted(missing)[:10]}"
    assert not extra, f"CUV S has {len(extra)} extra verses: {sorted(extra)[:10]}"


def test_cuv_hant_versification_matches_web():
    cuv = _load_mark_refs(CORPORA / "cuv_hant.csv")
    web = _load_mark_refs(CORPORA / "web.csv")
    if not cuv:
        pytest.skip("cuv_hant.csv not yet ingested")
    missing = web - cuv
    extra = cuv - web
    assert not missing
    assert not extra


def test_cuv_hans_mark_1_1_contains_福音():
    path = CORPORA / "cuv_hans.csv"
    if not path.exists():
        pytest.skip()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("book") == "Mark" and row.get("chapter") == "1" and row.get("verse") == "1":
                assert "福音" in row["text"]
                return
    pytest.fail("Mark 1:1 not found in cuv_hans.csv")
```

- [ ] **Step 2: Write the ingestion script**

Create `scripts/ingest_cuv.py`:

```python
"""Ingest CUV Simplified and Traditional from eBible.org → data/corpora/cuv_*.csv.

Usage:
    python scripts/ingest_cuv.py --download --hans --hant
    python scripts/ingest_cuv.py --hans
    python scripts/ingest_cuv.py --hant
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "data" / "corpora"
CACHE = ROOT / "data" / "_ingest_cache"

SOURCES = {
    "hans": {
        "url":  "https://ebible.org/Scriptures/zh-cmn-hans-cu89s_usfx.zip",
        "zip":  CACHE / "cuv_hans_usfx.zip",
        "out":  CORPORA / "cuv_hans.csv",
    },
    "hant": {
        "url":  "https://ebible.org/Scriptures/zh-cmn-hant-cu89t_usfx.zip",
        "zip":  CACHE / "cuv_hant_usfx.zip",
        "out":  CORPORA / "cuv_hant.csv",
    },
}

BOOK_CODE = "MRK"
BOOK_NAME = "Mark"


def download(meta: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {meta['url']} ...", file=sys.stderr)
    urllib.request.urlretrieve(meta["url"], meta["zip"])


def extract_mark_from_usfx(zip_path: Path) -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        usfx_name = next(
            (n for n in zf.namelist() if n.endswith(".usfx.xml")),
            None,
        )
        if not usfx_name:
            raise RuntimeError(f"No .usfx.xml in {zip_path}")
        xml = zf.read(usfx_name).decode("utf-8")
    book_re = re.compile(rf'<book\s+id="{BOOK_CODE}".*?</book>', re.DOTALL)
    m = book_re.search(xml)
    if not m:
        raise RuntimeError(f"Book {BOOK_CODE} not found")
    book_xml = m.group(0)

    chapter = 0
    verse = 0
    buf: list[str] = []
    parts = re.split(
        r'(<c\s+id="\d+"\s*/>|<v\s+id="\d+"\s*/>|<ve\s*/>)',
        book_xml,
    )
    for tok in parts:
        if not tok:
            continue
        m_c = re.match(r'<c\s+id="(\d+)"\s*/>', tok)
        m_v = re.match(r'<v\s+id="(\d+)"\s*/>', tok)
        if m_c:
            if chapter and verse and buf:
                rows.append((chapter, verse, _clean(" ".join(buf))))
            chapter = int(m_c.group(1))
            verse = 0
            buf = []
            continue
        if m_v:
            if chapter and verse and buf:
                rows.append((chapter, verse, _clean(" ".join(buf))))
            verse = int(m_v.group(1))
            buf = []
            continue
        if tok.startswith("<ve"):
            if chapter and verse and buf:
                rows.append((chapter, verse, _clean(" ".join(buf))))
            buf = []
            continue
        buf.append(_strip_tags(tok))
    if chapter and verse and buf:
        rows.append((chapter, verse, _clean(" ".join(buf))))
    return rows


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def write_csv(rows: list[tuple[int, int, str]], out: Path) -> None:
    CORPORA.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "verse", "reference", "text"])
        for ch, v, text in rows:
            w.writerow([BOOK_NAME, ch, v, f"{BOOK_NAME} {ch}:{v}", text])
    print(f"Wrote {len(rows)} verses to {out}", file=sys.stderr)


def run(variant: str, do_download: bool) -> None:
    meta = SOURCES[variant]
    if do_download or not meta["zip"].exists():
        download(meta)
    rows = extract_mark_from_usfx(meta["zip"])
    if len(rows) < 670:
        print(f"WARN: only {len(rows)} Mark verses extracted from {variant}", file=sys.stderr)
    write_csv(rows, meta["out"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--hans", action="store_true")
    ap.add_argument("--hant", action="store_true")
    args = ap.parse_args()
    if not (args.hans or args.hant):
        ap.error("specify --hans and/or --hant")
    if args.hans:
        run("hans", args.download)
    if args.hant:
        run("hant", args.download)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the ingestion**

```bash
python scripts/ingest_cuv.py --download --hans --hant
```

- [ ] **Step 4: Run gloss-csv tests**

Run: `pytest tests/test_gloss_csv_load.py -v`
Expected: all green (RV1909 from B1 + the 5 new CUV tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_cuv.py data/corpora/cuv_hans.csv data/corpora/cuv_hant.csv tests/test_gloss_csv_load.py
git commit -m "feat(i18n): ingest CUV Simplified + Traditional → CSV

eBible.org USFX → CSVs in the same shape as web.csv. Versification
parity check passes for both editions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task C2: Translate `translations/zh-Hans.json`

**Files:**
- Create: `translations/zh-Hans.json`
- Modify: `tests/test_translation_loader.py`

- [ ] **Step 1: Translate every key from `en.json` to Simplified Chinese**

Create `translations/zh-Hans.json` with the full key set from `en.json`, values in Simplified Chinese. Use scholarly Mandarin; keep technical terms (Peshitta 别西大译本, Vulgate 武加大译本, Strong's 斯特朗码, lemma 词元, morphology 词法) in their canonical Chinese form. Keep the verse-reference format `13:14` unchanged.

The implementer must produce values for every key in `en.json`. Sample fragment:

```json
{
  "site.name": "Translation Aligner",
  "site.tagline_default": "Translation Aligner — 平行对照的马可福音",
  "nav.home_aria": "Translation Aligner — 主页",
  "nav.methodology": "方法论",
  "home.kicker": "Translation Aligner · 试点",
  "home.title_main": "马可福音，",
  "home.title_accent": "三种文本的平行对照。",
  "home.cta_primary": "打开马可福音",
  "home.cta_secondary": "关于本项目",
  "settings.interface_language": "界面语言",
  "settings.verse_translations": "经文翻译",
  "...": "(every other key)"
}
```

- [ ] **Step 2: Add zh-Hans key-parity test**

Append to `tests/test_translation_loader.py`:

```python
def test_zh_hans_json_has_all_en_keys():
    en_path = TRANSLATIONS / "en.json"
    zh_path = TRANSLATIONS / "zh-Hans.json"
    if not zh_path.exists():
        pytest.skip()
    en = json.loads(en_path.read_text(encoding="utf-8"))
    zh = json.loads(zh_path.read_text(encoding="utf-8"))
    missing = set(en) - set(zh)
    assert not missing, f"zh-Hans.json missing {len(missing)} keys"
```

- [ ] **Step 3: Test + commit**

Run: `pytest -q`
Expected: green.

```bash
git add translations/zh-Hans.json tests/test_translation_loader.py
git commit -m "feat(i18n): full Simplified Chinese translations

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task C3: Translate `translations/zh-Hant.json`

**Files:**
- Create: `translations/zh-Hant.json`
- Modify: `tests/test_translation_loader.py`

- [ ] **Step 1: Translate every key to Traditional Chinese**

Create `translations/zh-Hant.json`. Strategy: start from `zh-Hans.json` and convert via OpenCC (or by hand), then sanity-check for region-specific terms (e.g. `软件` → `軟體` in Taiwan). Keep the verse-reference format `13:14`.

If `opencc` is available, the implementer can run:

```bash
python -c "
import json, opencc
cc = opencc.OpenCC('s2twp.json')
data = json.load(open('translations/zh-Hans.json'))
out = {k: cc.convert(v) for k, v in data.items()}
json.dump(out, open('translations/zh-Hant.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)
"
```

(`opencc` is not in `requirements.txt`; install ad-hoc via `pip install opencc-python-reimplemented` for this task only — do NOT add to requirements.)

- [ ] **Step 2: Add zh-Hant parity test**

Append to `tests/test_translation_loader.py`:

```python
def test_zh_hant_json_has_all_en_keys():
    en_path = TRANSLATIONS / "en.json"
    zh_path = TRANSLATIONS / "zh-Hant.json"
    if not zh_path.exists():
        pytest.skip()
    en = json.loads(en_path.read_text(encoding="utf-8"))
    zh = json.loads(zh_path.read_text(encoding="utf-8"))
    missing = set(en) - set(zh)
    assert not missing
```

- [ ] **Step 3: Test + commit**

Run: `pytest -q`
Expected: green.

```bash
git add translations/zh-Hant.json tests/test_translation_loader.py
git commit -m "feat(i18n): full Traditional Chinese translations

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task C4 (Phase C close): smoke test all four locales

- [ ] **Step 1: Run gunicorn and curl every locale**

```bash
pytest -q
cd "/Users/jfresco16/Google Drive/Claude/Translation_alignment"
source .venv/bin/activate
PORT=5024 gunicorn app:app --workers 1 --bind 0.0.0.0:5024 --log-level warning &
sleep 2
for prefix in "" "/es" "/zh-Hans" "/zh-Hant"; do
  for path in "/" "/about" "/verse/mark/1/1" "/verse/mark/13/14"; do
    full="$prefix$path"
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5024$full")
    echo "$full -> HTTP $code"
  done
done
pkill -f "gunicorn app:app --workers 1 --bind 0.0.0.0:5024" 2>/dev/null
```

Expected: 16 lines, all 200.

- [ ] **Step 2: Tag**

```bash
git tag i18n-phase-c-complete
```

---

## Phase D — SEO polish (hreflang + localized sitemap)

### Task D1: hreflang `<link>` tags in `base.html`

**Files:**
- Modify: `app.py` — expose `canonical_path` (path with lang prefix stripped) to Jinja
- Modify: `templates/base.html` — emit alternate links

- [ ] **Step 1: Add `canonical_path` helper to `app.py`**

Just before the `app.jinja_env.globals["t"] = t` line, add:

```python
def canonical_path() -> str:
    """Return the request path stripped of any language prefix.

    For /es/about → /about ; for /verse/mark/1/1 → /verse/mark/1/1.
    """
    path = request.path
    for lang in LANG_PREFIXES:
        if path == f"/{lang}" or path.startswith(f"/{lang}/"):
            return path[len(f"/{lang}"):] or "/"
    return path


app.jinja_env.globals["canonical_path"] = canonical_path
```

- [ ] **Step 2: Add hreflang block in `base.html` <head>**

In `templates/base.html`, just after the existing `<link rel="canonical" ... />`, add:

```jinja
{% set _canon = canonical_path() %}
<link rel="alternate" hreflang="en"        href="{{ request.url_root }}{{ _canon[1:] if _canon.startswith('/') else _canon }}" />
<link rel="alternate" hreflang="es"        href="{{ request.url_root }}es{{ _canon }}" />
<link rel="alternate" hreflang="zh-Hans"   href="{{ request.url_root }}zh-Hans{{ _canon }}" />
<link rel="alternate" hreflang="zh-Hant"   href="{{ request.url_root }}zh-Hant{{ _canon }}" />
<link rel="alternate" hreflang="x-default" href="{{ request.url_root }}{{ _canon[1:] if _canon.startswith('/') else _canon }}" />
```

- [ ] **Step 3: Test that hreflangs render correctly**

Append to `tests/test_routes_localized.py`:

```python
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
    """On /es/about, hreflang should point to /es/about, /about, /zh-Hans/about, etc."""
    with app.test_client() as c:
        rv = c.get("/es/about")
        body = rv.data.decode()
        assert 'hreflang="es" href="http://localhost/es/about"' in body
        assert 'hreflang="zh-Hans" href="http://localhost/zh-Hans/about"' in body
```

- [ ] **Step 4: Run tests + commit**

```bash
pytest -q
git add app.py templates/base.html tests/test_routes_localized.py
git commit -m "feat(i18n): hreflang alternate links for SEO + canonical_path helper

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task D2: Localize `sitemap.xml`

**Files:**
- Modify: `app.py` — extend `sitemap_xml()` route

- [ ] **Step 1: Update test expectations first**

Append to `tests/test_routes.py` (or `tests/test_routes_localized.py`):

```python
def test_sitemap_includes_localized_alternates():
    with app.test_client() as c:
        rv = c.get("/sitemap.xml")
        body = rv.data.decode()
        # Original English URLs still present
        assert "/verse/mark/1/1" in body
        # Each URL should have an xhtml:link rel='alternate' for each lang
        assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in body
        assert 'hreflang="es"' in body
        assert 'hreflang="zh-Hans"' in body
        assert 'hreflang="zh-Hant"' in body
```

- [ ] **Step 2: Update the route**

In `app.py`, replace the `sitemap_xml` route with:

```python
@app.route("/sitemap.xml")
def sitemap_xml():
    """Localized sitemap with xhtml:link alternates per Google sitemap spec."""
    from flask import Response
    paths: list[str] = ["/", "/about"]
    try:
        master = _corpora.get("greek_nt")
    except KeyError:
        master = None
    if master is not None:
        for ch in range(1, 17):
            for v in master.verses_in_chapter("Mark", ch):
                paths.append(f"/verse/mark/{ch}/{v}")

    base = request.url_root.rstrip("/")
    LANGS = ("en", "es", "zh-Hans", "zh-Hant")
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
        ' xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for path in paths:
        for lang in LANGS:
            loc = base + (path if lang == "en" else f"/{lang}{path}")
            out.append("  <url>")
            out.append(f"    <loc>{loc}</loc>")
            for alt in LANGS:
                alt_url = base + (path if alt == "en" else f"/{alt}{path}")
                out.append(
                    f'    <xhtml:link rel="alternate" hreflang="{alt}" href="{alt_url}"/>'
                )
            out.append("  </url>")
    out.append("</urlset>")
    return Response("\n".join(out), mimetype="application/xml")
```

- [ ] **Step 3: Run tests + commit**

```bash
pytest -q
git add app.py tests/test_routes.py tests/test_routes_localized.py
git commit -m "feat(i18n): localized sitemap with xhtml:link alternates per Google spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task D3: Update `llms.txt` to mention multilingual availability

**Files:**
- Modify: `llms.txt`

- [ ] **Step 1: Add multilingual line**

In `llms.txt`, after the existing first paragraph, add:

```
Multilingual availability: the UI is available in English (default), Spanish, Simplified Chinese, and Traditional Chinese. Localized URLs use a path prefix: /es/, /zh-Hans/, /zh-Hant/. Verse glosses are available in WEB (English), RV1909 (Spanish), and CUV 1919 (Chinese, Simplified + Traditional). The apparatus prose remains English-only in the pilot.
```

- [ ] **Step 2: Commit**

```bash
git add llms.txt
git commit -m "docs(llms): note multilingual UI + verse-gloss availability

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task D4 (Phase D close): final smoke + push

- [ ] **Step 1: Full pytest**

```bash
pytest -q
```
Expected: all green (90+ tests now: original ~70 + new 20+ for i18n).

- [ ] **Step 2: Manual verification under gunicorn**

```bash
PORT=5024 gunicorn app:app --workers 2 --threads 4 --bind 0.0.0.0:5024 --log-level warning &
sleep 2
# Spot-check that hreflang and sitemap localization work in production-config gunicorn
curl -s http://127.0.0.1:5024/sitemap.xml | head -30
curl -s http://127.0.0.1:5024/zh-Hans/verse/mark/13/14 | grep -E 'hreflang="(en|es|zh-Hant)"'
pkill -f "gunicorn app:app --workers 2 --threads 4 --bind 0.0.0.0:5024" 2>/dev/null
```

- [ ] **Step 3: Push to main; Render auto-deploys**

```bash
git push origin main
git tag i18n-shipped
git push --tags
```

Render will pick up the push and auto-deploy. Watch the Render dashboard for green build + boot.

- [ ] **Step 4: Production smoke**

After Render reports the new deploy is live, hit:

```
https://translation-aligner.onrender.com/
https://translation-aligner.onrender.com/es/
https://translation-aligner.onrender.com/zh-Hans/verse/mark/1/1
https://translation-aligner.onrender.com/zh-Hant/about
https://translation-aligner.onrender.com/sitemap.xml
```

All should return 200 with the right localized content.

---

## Phase E — Roadmap update + ROADMAP.md / about.html commit

Optional follow-up (not strictly part of i18n shipping but referenced in spec §10):

### Task E1: Roadmap update

**Files:**
- Modify: `ROADMAP.md`
- Modify: `templates/about.html` (or `translations/en.json` if extracted)

- [ ] **Step 1: Move i18n from "Up next" to "Shipped"**

In `ROADMAP.md`, remove the "Internationalization (i18n)" subsection from "Up next" and add a line in "Shipped":

```
- Internationalization: Spanish (RV1909) and Chinese (CUV Simplified + Traditional) UI + verse glosses; localized URLs with hreflang SEO; settings cog with multi-gloss toggle.
```

Add new lines in "Up next":

```
### Phase 2 — Apparatus translation
- Translate the ~2,600 scholarly apparatus notes to Spanish + Chinese via a custom Claude batch with a textual-criticism-aware prompt and a scholar-reviewed sample of 50 notes per language before publishing.

### Phase 2 — First-class translated witnesses
- Promote RV1909 and CUV from "gloss line" to a 4th aligned column with per-token coloring + shift-click apparatus. Re-runs alignment with the new witness in the prompt.
```

- [ ] **Step 2: Commit**

```bash
git add ROADMAP.md
git commit -m "docs(roadmap): move i18n to shipped; add Phase-2 follow-ups

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## Self-review checklist

- [ ] **Spec coverage:** every section of the spec maps to ≥1 task. Decisions 1–6 are all implemented (Decision 1 = corpora ingestion, Decision 2 = JSON dicts, Decision 3 = path prefix + cookie + auto-redirect, Decision 4 = `_gloss_stack.html` multi-row, Decision 5 = no apparatus translation in this plan, Decision 6 = `_settings.html` + `settings.js`). All four §8 open questions are explicitly resolved in the resolved-questions section above.
- [ ] **Placeholders:** scanned for "TBD", "TODO", "implement later", "fill in details", "add appropriate error handling" — none present. Every step has exact file paths, exact code, and exact commands.
- [ ] **Type consistency:** `Translations.t(key, lang)`, `Translations.has_key(key, lang)`, `Translations.keys(lang)` are defined in A1 and consistently called in A2 (test) and A12 (`i18n_for_js`). `parse_accept_language(header)` is defined in A1, called in A11. `_gloss_maps` defined in B2, used in B3. `LANG_PREFIXES` defined in A10, used in A10/A11/D1. `g.lang` set in A10, read by `t()` (A3) and `i18n_for_js()` (A12) and `canonical_path()` (D1). All consistent.

---

## Execution sequencing summary

| Phase | Tasks | Outcome |
|---|---|---|
| **A** — plumbing | A1–A13 (13 tasks) | All English chrome routed through `t()`; `/es/`, `/zh-Hans/`, `/zh-Hant/` resolve to English content; tests green |
| **B** — Spanish + settings | B1–B7 (7 tasks) | `/es/...` is fully Spanish; settings cog works; gloss stack supports en + es |
| **C** — Chinese | C1–C4 (4 tasks) | `/zh-Hans/...` and `/zh-Hant/...` are fully Chinese; gloss stack supports all four |
| **D** — SEO polish | D1–D4 (4 tasks) | hreflang tags + localized sitemap; Render auto-deploys; production smoke green |
| **E** — roadmap | E1 (1 task) | i18n moves from "Up next" to "Shipped"; Phase-2 items tracked |

**Total: 29 tasks, each commit-able and verifiable.**
