# i18n: Spanish + Chinese (Simplified + Traditional) — Design

**Date:** 2026-04-27
**Author:** Jossi Fresco Benaim (with Claude)
**Status:** Approved — ready for implementation plan
**Target phase:** Top of "Up next" on the public roadmap

---

## 1. Goal

Ship a complete internationalization layer for the Translation Aligner viewer:

- UI chrome (navbar, headings, buttons, search palette, apparatus labels, hints) translated into **Spanish** and **Chinese (Simplified + Traditional)**
- Verse content available in **Reina-Valera 1909** (Spanish) and **Chinese Union Version 1919** (Simplified + Traditional editions) as gloss lines, multi-selectable independently of the chrome language
- A settings cog in the topbar that surfaces interface language, gloss-language checkboxes, and the existing theme toggle
- Path-prefixed URLs (`/es/...`, `/zh-Hans/...`, `/zh-Hant/...`) for SEO with bare-root English, cookie-persisted user preference, and an Accept-Language-driven first-visit redirect

Apparatus prose notes remain English-only in this phase. Translating the ~2,600 scholarly notes is scheduled as Phase 2 (separate Claude batch + scholar-reviewed sample).

## 2. Scope

### In scope

- Three new languages (`es`, `zh-Hans`, `zh-Hant`) on top of the existing English baseline (`en`)
- Three new verse-text corpora: `rv1909.csv`, `cuv_hans.csv`, `cuv_hant.csv`
- New per-language UI string dicts: `translations/{en,es,zh-Hans,zh-Hant}.json`
- New settings panel in the topbar
- Multi-gloss stack rendering above the alignment grid
- Locale-aware URL routing with auto-redirect on first visit
- `<link rel="alternate" hreflang>` tags for SEO
- Tests for locale resolution, translation loading, route localization, gloss CSV ingestion, and template smoke

### Out of scope (Phase 2 candidates, tracked in roadmap)

- Apparatus note translation (custom Claude batch with field-aware prompt + scholar review)
- Spanish/Chinese as **first-class aligned witnesses** (alignment grid 4th column with per-token coloring + shift-click apparatus). This belongs with the Orthodox Chinese cluster expansion and similar witness-coverage work.
- Syriac font selector (still in roadmap; needs its own `@font-face` work)
- Per-token Spanish/Chinese cognate tooltips
- Translating verse search snippets (search backend stays English-keyed; cross-lang search is a separate concern)

## 3. Decisions (locked)

| # | Decision | Choice |
|---|---|---|
| 1 | Translation sources for verse content | RV1909 (Spanish, public domain); CUV 1919 Simplified + Traditional (Chinese, public domain) |
| 2 | UI translation tooling | Per-language JSON dicts (`translations/<lang>.json`), zero build step. No Flask-Babel, no gettext, no `.po` files. |
| 3 | URL strategy | Path prefix `/<lang>/...` with bare-root English. Cookie persistence (1-year). Auto-redirect from `/` only when no cookie + Accept-Language matches a supported non-English lang. |
| 4 | Display strategy for translated verse content | Replace/extend the existing English WEB gloss line above the alignment grid. Multiple glosses can be checked simultaneously and stack vertically with a small lang-tag prefix. The 3-witness alignment grid (Greek/Peshitta/Vulgate) is unchanged. |
| 5 | Apparatus notes | English-only this phase. Phase 2 = Claude-translated `note_es`, `note_zh-Hans`, `note_zh-Hant` fields added forward-compatibly to alignment JSON. |
| 6 | Settings panel | Settings cog in topbar with: (a) interface-language single-radio (en / es / zh-Hans / zh-Hant), (b) gloss-language multi-checkbox (same four), (c) theme light/dark. |

## 4. Architecture

A single Flask `before_request` hook handles locale resolution. Routes register without lang prefixes; the prefix is purely a request-time concern. All UI strings flow through one `t()` Jinja global, backed by JSON dicts loaded once at startup. Verse glosses come from per-language CSV maps that mirror the existing `_web_map`. The settings panel writes interface-language to a server-readable cookie (so the next request gets the right prefix) and gloss + theme prefs to client-side `localStorage` (no roundtrip needed).

### Data flow

```
Request /es/verse/mark/13/14
  │
  ▼
before_request:
  - Match prefix: ^/(es|zh-Hans|zh-Hant)/
  - Strip prefix; set g.lang = 'es'; request.path = /verse/mark/13/14
  │
  ▼
verse() route resolves with original handler
  │
  ▼
_load_verse() returns alignment data + gloss_map = {
    'en':       'But when you see...',
    'es':       'Pero cuando viereis...',
    'zh-Hans':  '你们看见…那行毁坏可憎的...',
    'zh-Hant':  '你們看見...那行毀壞可憎的...',
}
  │
  ▼
render_template('verse.html', verse=data, gloss_map=gloss_map, ...)
  │
  ▼
Template:
  - {{ t('verse.shift_click_hint') }} → resolved via lang='es' lookup
  - _gloss_stack.html iterates langs the *user* has checked (from JS-side localStorage)
  - All other UI strings localized via t()
```

### First-visit auto-redirect

```
Request /
  │
  ▼
before_request:
  cookie['lang']?
    ├─ set        → no redirect; render English at /; refresh cookie
    └─ unset      → parse Accept-Language
                    ├─ matches es*           → 302 /es/   ; set cookie
                    ├─ matches zh-CN/zh-Hans → 302 /zh-Hans/; set cookie
                    ├─ matches zh-TW/zh-Hant → 302 /zh-Hant/; set cookie
                    └─ otherwise            → render /; set cookie='en'
```

Auto-redirect fires **only at the bare root** `/`. Other paths (`/about`, `/verse/...`) never trigger redirects, so shared deep links always render the requested language.

## 5. Components

### 5.1 `translation_core/i18n.py` (new)

```python
class Translations:
    SUPPORTED = ('en', 'es', 'zh-Hans', 'zh-Hant')
    DEFAULT = 'en'

    def __init__(self, root: Path):
        self._dicts: dict[str, dict[str, str]] = {}
        for lang in self.SUPPORTED:
            path = root / f'{lang}.json'
            self._dicts[lang] = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

    def t(self, key: str, lang: str = DEFAULT) -> str:
        # Lookup with English fallback for missing keys
        return (self._dicts.get(lang, {}).get(key)
                or self._dicts[self.DEFAULT].get(key)
                or key)


def parse_accept_language(header: str | None) -> str | None:
    """Return one of SUPPORTED langs (or None if no match).

    Maps:
      es*                              → 'es'
      zh-CN, zh-Hans, plain 'zh'       → 'zh-Hans'
      zh-TW, zh-HK, zh-Hant            → 'zh-Hant'
      everything else                   → None (caller falls back to English)
    """
```

### 5.2 `app.py` — locale hook

A `before_request` hook (registered before the existing `_ensure_init`):

```python
LANG_PREFIXES = {'es', 'zh-Hans', 'zh-Hant'}

@app.before_request
def _resolve_locale():
    path = request.path
    g.lang = 'en'
    for lang in LANG_PREFIXES:
        if path == f'/{lang}' or path.startswith(f'/{lang}/'):
            g.lang = lang
            # Rewrite path so existing routes match unchanged
            new_path = path[len(f'/{lang}'):] or '/'
            request.environ['PATH_INFO'] = new_path
            break
    # Auto-redirect logic for bare root only
    if path == '/' and 'lang' not in request.cookies:
        wanted = parse_accept_language(request.headers.get('Accept-Language'))
        if wanted and wanted != 'en':
            resp = redirect(f'/{wanted}/', code=302)
            resp.set_cookie('lang', wanted, max_age=60*60*24*365, samesite='Lax')
            return resp
        # Set cookie='en' so we don't re-check next visit
        # Done by post-request hook (below)
```

A `_set_lang_cookie` `after_request` hook ensures every response carries an up-to-date `lang` cookie when one wasn't set.

### 5.3 Jinja global registration

```python
translations = Translations(BASE_DIR / 'translations')

def t(key: str) -> str:
    return translations.t(key, getattr(g, 'lang', 'en'))

app.jinja_env.globals['t'] = t
app.jinja_env.globals['supported_langs'] = Translations.SUPPORTED
```

### 5.4 Template conversion

Every user-visible string in `templates/*.html` becomes `{{ t('key.path') }}`. Keys follow dot notation by area:

```
nav.methodology              "Methodology"
nav.search_aria              "Search (⌘K)"
home.kicker                  "Translation Aligner · Pilot"
home.title                   "The Gospel of Mark,"
home.title_accent            "three witnesses in parallel."
home.cta_primary             "Open the Gospel of Mark"
home.cta_secondary           "About the project"
verse.shift_click_hint       "Shift-click any colored token..."
verse.view_interlinear       "Interlinear"
verse.view_grid              "Alignment Grid"
verse.view_apparatus         "Apparatus"
search.placeholder           "Search Greek, Vulgate, Peshitta..."
search.hint                  "↑↓ navigate · ↵ open · Esc close"
settings.interface_language  "Interface Language"
settings.verse_translations  "Verse Translations"
settings.theme               "Theme"
...
```

`translations/en.json` is **the source of truth** — the only file where we edit strings; ES and ZH files mirror its key set.

### 5.5 Gloss CSVs and loader

Three new files in `data/corpora/`:

```
rv1909.csv
cuv_hans.csv
cuv_hant.csv
```

Same shape as `web.csv`:

```csv
book,chapter,verse,reference,text
Mark,1,1,Mark 1:1,Principio del evangelio de Jesucristo, Hijo de Dios.
```

Loaded into per-language maps at startup:

```python
_gloss_maps: dict[str, dict[str, str]] = {
    'en':      {},  # already populated from web.csv
    'es':      {},  # rv1909.csv
    'zh-Hans': {},  # cuv_hans.csv
    'zh-Hant': {},  # cuv_hant.csv
}
```

`_load_verse()` populates a `gloss_map` containing all four entries (or empty string if absent for that verse) and passes it to the template.

### 5.6 `templates/_gloss_stack.html` (new)

```jinja
{% if gloss_map %}
<div class="gloss-stack" id="gloss-stack" data-glosses="en">
  {% for lang in supported_langs %}
    {% if gloss_map.get(lang) %}
      <p class="gloss-row gloss-row-{{ lang }}" data-lang="{{ lang }}">
        <span class="gloss-tag">{{ lang | upper }}</span>
        <span class="gloss-text">{{ gloss_map[lang] }}</span>
      </p>
    {% endif %}
  {% endfor %}
</div>
{% endif %}
```

JS toggles `display: none` on rows whose `data-lang` is not in the user's `localStorage.gloss_langs` set. Default `localStorage.gloss_langs` is the chrome `g.lang` only; user overrides via settings panel.

### 5.7 Settings cog

Two new files:

- `templates/_settings.html` — the panel markup (radio + checkboxes + theme)
- `static/js/settings.js` — toggles the panel, persists checkboxes to `localStorage.gloss_langs` (JSON array), persists theme to `localStorage.theme`, applies them on page load, and posts a small form for interface-language changes (server roundtrip → cookie → redirect to new prefix)

Topbar in `base.html` gets a new button between the search button and Methodology link:

```html
<button class="iconbtn iconbtn-icon" id="settings-trigger"
        aria-label="{{ t('nav.settings_aria') }}"
        title="{{ t('nav.settings_aria') }}">
  <svg class="icon-cog" .../>
</button>
```

### 5.8 `static/js/aligner.js` strings

A new top-of-file constant:

```js
const I18N = window.__I18N__ || {};
function t(key) { return I18N[key] || key; }
```

Populated by `base.html` injection:

```jinja
<script id="i18n-data" type="application/json">{{ i18n_for_js | tojson }}</script>
<script>
  window.__I18N__ = JSON.parse(document.getElementById('i18n-data').textContent);
</script>
```

`i18n_for_js` = subset of the lang dict containing only keys with the `js.` prefix.

### 5.9 SEO — hreflang tags

`base.html` head additions:

```jinja
{% set canonical_path = request.path | strip_lang_prefix %}
<link rel="alternate" hreflang="en"      href="{{ url_root }}{{ canonical_path }}" />
<link rel="alternate" hreflang="es"      href="{{ url_root }}/es{{ canonical_path }}" />
<link rel="alternate" hreflang="zh-Hans" href="{{ url_root }}/zh-Hans{{ canonical_path }}" />
<link rel="alternate" hreflang="zh-Hant" href="{{ url_root }}/zh-Hant{{ canonical_path }}" />
<link rel="alternate" hreflang="x-default" href="{{ url_root }}{{ canonical_path }}" />
```

`/sitemap.xml` is extended to include localized URLs for each supported language with `<xhtml:link rel="alternate">` siblings per the Google sitemap spec.

## 6. File structure

### New files

```
translation_core/i18n.py                       # Translations class + accept-lang parser
translations/en.json                           # source-of-truth keys + English values
translations/es.json                           # Spanish overrides
translations/zh-Hans.json                      # Simplified Chinese
translations/zh-Hant.json                      # Traditional Chinese
data/corpora/rv1909.csv                        # Spanish verse text
data/corpora/cuv_hans.csv                      # Simplified Chinese verse text
data/corpora/cuv_hant.csv                      # Traditional Chinese verse text
templates/_gloss_stack.html                    # multi-language gloss rows
templates/_settings.html                       # settings panel markup
static/js/settings.js                          # settings panel behavior
scripts/ingest_rv1909.py                       # one-shot ingestion from open source
scripts/ingest_cuv.py                          # one-shot ingestion (handles Hans + Hant)
tests/test_i18n_locale_resolution.py
tests/test_translation_loader.py
tests/test_routes_localized.py
tests/test_gloss_csv_load.py
```

### Modified files

```
app.py                          + locale hook, hreflang context, Translations init,
                                  gloss_map plumbing, sitemap localization
templates/base.html             + hreflang block, settings cog button, i18n-data script,
                                  all chrome strings → t()
templates/home.html             all strings → t()
templates/about.html            all strings → t()
templates/verse.html            include _gloss_stack.html; replace single gloss line;
                                  all chrome strings → t()
templates/_alignment_grid.html  variant labels, ARIA → t()
templates/_interlinear.html     same
templates/_apparatus.html       same; verdict / type label translations
templates/_rail.html            same
templates/macros.html           same
templates/404.html              all strings → t()
static/js/aligner.js            string constants → t() lookups
static/css/styles.css           + .gloss-stack, .gloss-row, .gloss-tag, .settings-panel
                                  styles
```

## 7. Tests

### `tests/test_i18n_locale_resolution.py`

- `parse_accept_language('es-MX,es;q=0.9,en;q=0.8')` → `'es'`
- `parse_accept_language('zh-CN,zh;q=0.9')` → `'zh-Hans'`
- `parse_accept_language('zh-TW')` → `'zh-Hant'`
- `parse_accept_language('zh')` → `'zh-Hans'` (Mainland default)
- `parse_accept_language('de,en;q=0.5')` → `None`
- `parse_accept_language('')` → `None`
- `parse_accept_language(None)` → `None`

### `tests/test_translation_loader.py`

- All four files load without `JSONDecodeError`
- Every key in `en.json` exists in `es.json`, `zh-Hans.json`, `zh-Hant.json`. (This test will fail intentionally during early authoring; it's the keys-completeness gate before ship.)
- `t('nonexistent.key', 'es')` falls back to English then to the literal key
- `t('home.title', 'es')` returns the Spanish string

### `tests/test_routes_localized.py`

- `GET /es/` → 200, `g.lang == 'es'`, body contains the Spanish home title
- `GET /zh-Hans/verse/mark/13/14` → 200, `g.lang == 'zh-Hans'`
- `GET /zh-Hant/about` → 200, `g.lang == 'zh-Hant'`
- `GET /` with `Accept-Language: es-ES` and no cookie → 302 to `/es/`, sets `lang=es` cookie
- `GET /` with `Accept-Language: en-US` → 200 (no redirect), sets `lang=en` cookie
- `GET /` with existing `lang=zh-Hans` cookie → 200 (no redirect, English content; cookie does NOT override path)
- `GET /verse/mark/1/1` with `Accept-Language: es` → 200 (no redirect, only `/` redirects)

### `tests/test_gloss_csv_load.py`

- All three new CSVs (`rv1909.csv`, `cuv_hans.csv`, `cuv_hant.csv`) load without error
- All three contain a row for every (book, chapter, verse) tuple present in `web.csv` for Mark — i.e. no missing verses
- Sample row check: `rv1909` Mark 1:1 contains "evangelio"; `cuv_hans` Mark 1:1 contains "福音"; `cuv_hant` Mark 1:1 contains "福音"

### Smoke tests (one per language)

- `GET /es/verse/mark/1/1` renders without `UndefinedError`, contains the Spanish CTA word, contains the Greek text (unchanged)
- Same for `/zh-Hans/verse/mark/1/1` and `/zh-Hant/verse/mark/1/1`
- All three carry the correct `<html lang="…">` attribute

## 8. Open implementation questions

The plan must resolve these before merging:

- **Gloss CSV ingestion sources**: which open-data mirror provides the cleanest RV1909 and CUV (Hans + Hant) data? Candidates: `openbible.com/textfiles/`, `bible.com` (terms forbid scraping), `getbible.net`. Likely answer: `bible-databases` repo on GitHub, which has both in CSV/JSON form with verse references already normalized.
- **Verse-numbering parity**: does CUV's Mark match NA28 versification, or are there splits (similar to the Vulgate Mark 9 fix)? Verify before ship; if drift exists, document in `known-issues.md` and apply remap.
- **Where to put the cookie write for `lang=en` on a non-redirect first visit**: cleanest in an `after_request` hook that only writes when the cookie is absent.
- **JS-side translation of `aligner.js` constants**: should `aligner.js` accept a server-injected `__I18N__` object (recommended), or fetch `/i18n/<lang>.json` lazily on boot? Decision: server-injected is one less roundtrip and keeps the page atomic.

## 9. Migration / rollout

This change is purely additive:

1. Existing English URLs (`/`, `/about`, `/verse/mark/1/1`) continue to work unchanged.
2. New users with non-English browsers see auto-redirect to their language.
3. No database migrations; no breaking schema changes; alignment JSON files unchanged.
4. Render auto-deploy on `main` push; no env var changes.

Rollout sequence (one PR per phase to minimize merge conflicts):

1. **Phase A** — i18n plumbing only: `translation_core/i18n.py`, `Translations` class, locale hook, `t()` global, `translations/en.json` extracting all current English strings. Site behaves identically; just internally routed through `t()`. Tests for resolver + loader.
2. **Phase B** — Spanish UI + RV1909 verses. Translates `es.json`; ingests `rv1909.csv`; gloss-stack partial; settings cog with single radio (en/es) and gloss checkboxes (en/es).
3. **Phase C** — Chinese UI + CUV verses (both editions). Translates `zh-Hans.json` and `zh-Hant.json`; ingests `cuv_hans.csv` and `cuv_hant.csv`; settings panel expanded to four langs.
4. **Phase D** — SEO polish: hreflang tags, localized sitemap entries, `/llms.txt` updated to mention multilingual availability.

## 10. Roadmap updates

After the spec is approved, the roadmap entry for i18n moves from "Up next" to "In progress" (or equivalent). New roadmap line items added:

- **Phase 2 — Apparatus translation** (Spanish + Chinese). Custom Claude batch with field-aware textual-criticism prompt. Scholar-reviewed sample of 50 notes per language before publishing all ~2,600.
- **Phase 2 — Spanish/Chinese as first-class aligned witnesses** (4th column). Re-run alignment with RV1909 / CUV included in the prompt; per-token coloring + shift-click apparatus.

Existing roadmap items for Syriac font selection and the Orthodox Chinese cluster (Slavonic 1751 + 1864 Küri + 1910 Innokenti) are unchanged.

---

**End of design.**
