# Polyglot Concordance — API v1 Design

**Date:** 2026-04-27
**Author:** Jossi Fresco Benaim (with Claude)
**Status:** Approved — ready for implementation
**Live target:** `https://polyglotconcordance.com/api/v1/`

---

## 1. Goal

Expose the alignment data and search index of the Polyglot Concordance as a small, read-only, public, versioned JSON API. The artifacts powering the rendered HTML viewer (per-verse alignment JSON, the converted verse dict, the search index, and the corpus manifest) become directly machine-accessible to scholars, downstream tools, and grant reviewers — without requiring a repo clone or HTML scraping.

## 2. Scope

### In scope

- **Five endpoints** under `/api/v1/`:
  - `GET /api/v1/alignment/{book}/{chapter}/{verse}` — canonical alignment JSON (the on-disk artifact)
  - `GET /api/v1/verse/{book}/{chapter}/{verse}` — converted verse dict (template-shape; witnesses + variants + gloss_map)
  - `GET /api/v1/search` — verse-level search across all witnesses (alias + formalization of existing `/search`)
  - `GET /api/v1/manifest` — corpus metadata, witness list, schema version, and the `(book, chapter, verse)` tuples in scope
  - `GET /api/v1/openapi.json` — OpenAPI 3.0 spec for all v1 endpoints
- **One human-readable docs page** at `GET /api/docs` (rendered Swagger UI from the OpenAPI spec)
- **One root index** at `GET /api/v1/` listing the endpoints + a curl example
- **CORS** headers (`Access-Control-Allow-Origin: *`) on all `/api/v1/*` responses — public read-only data, safe to allow from any origin
- **Edge caching** via `Cache-Control: public, max-age=86400` on alignment/verse/manifest responses (data only changes on deploy)
- **Tests**: pytest cases for each endpoint covering 200, 404, malformed inputs, CORS headers, and response-shape stability

### Out of scope (deferred to API v2 or later)

- Authentication / API keys (read-only public data, no need)
- Rate limiting (Render's edge cache + Cloudflare absorb most load; revisit if abuse seen)
- Write endpoints (covered by ROADMAP Sub-project 2 — Machine Annotation Engine)
- GraphQL (overkill for 5 simple endpoints)
- Bulk endpoints (`GET /api/v1/alignment/mark` returning all 678 verses) — easy to add if requested
- Per-token enrichment endpoints (`GET /api/v1/strong/<num>`, `GET /api/v1/peshitta-root/<root>`) — useful follow-up but not in v1
- Server-Sent Events / WebSocket / live anything — purely synchronous request-response

## 3. Decisions (locked)

| # | Decision | Choice |
|---|---|---|
| 1 | URL versioning | Path prefix `/api/v1/` so we can iterate without breaking consumers. v2 lives at `/api/v2/` if it ever exists. |
| 2 | Response envelope | Object responses (never bare arrays) so we can add metadata fields later without breaking consumers. List endpoints wrap their results in `{"items": [...], "count": N}`. |
| 3 | Authentication | None (read-only public data; the corpus is CC BY 4.0). |
| 4 | CORS | Allow all origins (`Access-Control-Allow-Origin: *`). Read-only, no credentials, no preflight required for simple GETs. |
| 5 | Caching | `Cache-Control: public, max-age=86400` on stable endpoints (alignment, verse, manifest, openapi). `max-age=300` on `/api/v1/search` (query-keyed; Render edge will cache by URL). |
| 6 | Error format | `{"error": {"code": "<machine_code>", "message": "<human_string>"}}` with appropriate HTTP status. |
| 7 | Versioning of payloads | Each response includes `"api_version": "v1"` and (where relevant) `"schema_version": <int>` matching the alignment JSON's existing `meta.schema_version`. |
| 8 | Documentation | OpenAPI 3.0 spec at `/api/v1/openapi.json`, rendered as Swagger UI at `/api/docs`. |
| 9 | Localization | Endpoints are language-neutral. The `verse` endpoint returns the multi-language `gloss_map` so callers can pick. (No `/api/v1/es/` prefix — locale belongs to UI, not data.) |
| 10 | Book scope | `book` path parameter is `mark` only for v1 (matches the rendered HTML pilot). 404 with `{"error": {"code": "book_not_found", ...}}` for any other value. Forward-compatible — no schema change needed when Matthew etc. land. |

## 4. Endpoint catalog

### 4.1 `GET /api/v1/alignment/{book}/{chapter}/{verse}`

Returns the canonical alignment JSON — exactly what's in `data/alignments/mark/<ch>/<v>.json`, with `api_version` added at the top level.

**Path parameters:**
- `book` — currently `mark` (case-insensitive, normalized to lowercase). 404 for any other value.
- `chapter` — integer, 1–16 for Mark.
- `verse` — integer.

**Response 200:**
```json
{
  "api_version": "v1",
  "ref": "Mark 13:14",
  "chapter": 13,
  "verse": 14,
  "traditions": {
    "greek_nt":  { "tokens": ["...", "..."] },
    "peshitta":  { "tokens": ["...", "..."] },
    "vulgate":   { "tokens": ["...", "..."] }
  },
  "alignment": [
    {
      "id": "g1",
      "members": { "greek_nt": [0, 1], "peshitta": [0], "vulgate": [0, 1] },
      "verdict": "aligned",
      "type": "agreement",
      "confidence": 0.95
    },
    {
      "id": "g2",
      "members": { "greek_nt": [], "peshitta": [3, 4], "vulgate": [] },
      "verdict": "added",
      "type": "harmonisation",
      "note": "The Peshitta inserts \"by Daniel the prophet\" — likely harmonisation with Matt 24:15.",
      "confidence": 0.88
    }
  ],
  "meta": {
    "generated_by": "claude-sonnet-4-5",
    "generated_at": "2026-04-23T...",
    "confidence": 0.91,
    "schema_version": 1
  }
}
```

**Response 404** (book unknown, or verse out of corpus, or alignment file missing):
```json
{ "error": { "code": "alignment_not_found", "message": "No alignment for Mark 99:99" } }
```

**Headers:** `Content-Type: application/json`, `Access-Control-Allow-Origin: *`, `Cache-Control: public, max-age=86400`.

### 4.2 `GET /api/v1/verse/{book}/{chapter}/{verse}`

Returns the converted verse dict — the same shape consumed by `templates/verse.html` (witnesses, tokens with `align-id`, variants, multi-language `gloss_map`). Useful for clients that want the display-ready form rather than the raw alignment.

**Path parameters:** same as 4.1.

**Response 200** (abbreviated — actual shape mirrors what the converter produces):
```json
{
  "api_version": "v1",
  "ref": "Mark 13:14",
  "book": "Mark",
  "chapter": 13,
  "verse": 14,
  "pericope": "The Abomination of Desolation",
  "testament": "New Testament",
  "witnesses": [
    {
      "id": "grk",
      "sigil": "𝔊",
      "name": "Greek NT",
      "subtitle": "NA28 / STEP TAGNT",
      "script": "grc",
      "date": "1st c.",
      "dir": "ltr",
      "tokens": [
        { "t": "Ὅταν", "a": "g1", "idx": 0 },
        { "t": "δὲ",   "a": "g2", "idx": 1 }
      ]
    }
  ],
  "variants": [
    { "id": "v1", "type": "harmonisation", "label": "...", "title": [...], "summary": "...", "witnesses": ["syr"], "classes": ["major"] }
  ],
  "gloss_map": {
    "en":      "But when you see the abomination of desolation...",
    "es":      "Pero cuando viereis la abominación de desolación...",
    "zh-Hans": "你们看见…那行毁坏可憎的...",
    "zh-Hant": "你們看見...那行毀壞可憎的..."
  },
  "prev": { "book": "mark", "chapter": 13, "verse": 13, "label": "Mk 13:13" },
  "next": { "book": "mark", "chapter": 13, "verse": 15, "label": "Mk 13:15" }
}
```

**Response 404** for unknown verse: `{"error": {"code": "verse_not_found", "message": "..."}}`.

**Headers:** same as 4.1, including `Cache-Control: public, max-age=86400`.

### 4.3 `GET /api/v1/search`

Verse-level search across all witnesses + variant types.

**Query parameters:**
- `q` (required) — search string, or a `chapter:verse` reference jump like `13:14`.
- `limit` (optional, default 25, max 100) — max results to return.

**Response 200:**
```json
{
  "api_version": "v1",
  "query": "ὄχλος",
  "count": 8,
  "items": [
    {
      "ref": "Mark 5:21",
      "chapter": 5,
      "verse": 21,
      "snippet": "...συνήχθη ὄχλος πολὺς...",
      "kind": "greek",
      "matched_in": ["greek"]
    }
  ]
}
```

**Response 200 with empty results:** `{"api_version": "v1", "query": "...", "count": 0, "items": []}`.

**Headers:** same as above except `Cache-Control: public, max-age=300` (search is query-keyed; the edge cache will key on the full URL including query string).

### 4.4 `GET /api/v1/manifest`

Corpus-level metadata. Useful as a discovery endpoint: clients can fetch this once and learn the scope.

**Response 200:**
```json
{
  "api_version": "v1",
  "project": "Polyglot Concordance",
  "description": "A concordance initiative with alignment to the word level — Mark across Greek NT, Syriac Peshitta, and Latin Clementine Vulgate, with a critical apparatus on every divergence.",
  "license": "Code: open-source (intended). Derived alignment JSON: CC BY 4.0 + public domain mix; redistribute with attribution.",
  "schema_version": 1,
  "books": [
    {
      "id": "mark",
      "name": "Mark",
      "testament": "New Testament",
      "chapters": 16,
      "verse_count": 678,
      "verses": [[1,1], [1,2], "..."]
    }
  ],
  "witnesses": [
    { "id": "greek_nt",  "sigil": "𝔊", "name": "Greek NT",          "script": "grc", "dir": "ltr", "source": "STEP Bible TAGNT (Tyndale House Cambridge)" },
    { "id": "peshitta",  "sigil": "ℙ", "name": "Syriac Peshitta",    "script": "syr", "dir": "rtl", "source": "Aramaic Root Atlas corpus" },
    { "id": "vulgate",   "sigil": "𝔙", "name": "Clementine Vulgate", "script": "lat", "dir": "ltr", "source": "seven1m/open-bibles (USFX)" }
  ],
  "verse_glosses": [
    { "lang": "en",      "name": "English",            "edition": "World English Bible (WEB), public domain" },
    { "lang": "es",      "name": "Español",            "edition": "Reina-Valera 1909, public domain" },
    { "lang": "zh-Hans", "name": "简体中文",            "edition": "Chinese Union Version 1919 (Simplified), public domain" },
    { "lang": "zh-Hant", "name": "繁體中文",            "edition": "Chinese Union Version 1919 (Traditional), public domain" }
  ],
  "variant_verdicts": ["aligned", "minor", "major", "omitted", "added"],
  "variant_types":    ["agreement", "expansion", "omission", "substitution", "harmonisation", "word-order", "construction", "idiom", "punctuation", "grammar", "lexical", "gloss"],
  "alignment_generation": {
    "model": "claude-sonnet-4-5",
    "via":   "Anthropic Messages Batch API",
    "benchmark": {
      "name": "Berean Interlinear Bible",
      "task": "Greek → English token alignment",
      "verses": 673,
      "agreement_rate": 0.677
    }
  },
  "endpoints": [
    "/api/v1/alignment/{book}/{chapter}/{verse}",
    "/api/v1/verse/{book}/{chapter}/{verse}",
    "/api/v1/search?q={query}&limit={n}",
    "/api/v1/manifest",
    "/api/v1/openapi.json"
  ]
}
```

The exact `verses` list (~678 entries) lets a consumer enumerate the corpus without trial-and-error.

**Headers:** standard + `Cache-Control: public, max-age=86400`.

### 4.5 `GET /api/v1/openapi.json`

OpenAPI 3.0 spec describing all four data endpoints. Generated as a static dict in Python (no auto-generation framework) since the API surface is small.

**Headers:** standard + `Cache-Control: public, max-age=86400`.

### 4.6 `GET /api/v1/`

Index page (text/html) with a brief description and a `curl` example. Optional convenience for browser visitors who land at the root.

```html
<h1>Polyglot Concordance API v1</h1>
<p>Read-only JSON access to the alignment data, search index, and corpus manifest.</p>
<ul>
  <li><a href="/api/v1/manifest">/api/v1/manifest</a></li>
  <li><a href="/api/v1/alignment/mark/13/14">/api/v1/alignment/mark/13/14</a></li>
  <li><a href="/api/v1/verse/mark/13/14">/api/v1/verse/mark/13/14</a></li>
  <li><a href="/api/v1/search?q=harmonisation">/api/v1/search?q=harmonisation</a></li>
  <li><a href="/api/docs">/api/docs (Swagger UI)</a></li>
</ul>
<pre>curl https://polyglotconcordance.com/api/v1/alignment/mark/13/14 | jq .</pre>
```

### 4.7 `GET /api/docs`

Swagger UI. Single HTML page that loads `/api/v1/openapi.json` and renders the interactive docs. Implementation: serve a small inline HTML using the public swagger-ui-dist CDN (https://unpkg.com/swagger-ui-dist@5/) — no Python dependency, no build step.

## 5. Response conventions

### 5.1 Headers (every `/api/v1/*` response)

```
Content-Type: application/json; charset=utf-8
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Cache-Control: public, max-age=86400   # or 300 for /search
```

### 5.2 Error envelope

```json
{ "error": { "code": "<snake_case_code>", "message": "<human-readable string>" } }
```

Error codes used in v1:
- `book_not_found` (404) — `book` path param isn't in the corpus
- `verse_not_found` (404) — `(book, chapter, verse)` doesn't exist
- `alignment_not_found` (404) — alignment JSON missing for a corpus verse (rare; only if data hasn't been generated)
- `bad_request` (400) — malformed query parameters (e.g. non-integer `limit`)
- `internal_error` (500) — uncaught exception (logged server-side; generic message client-side)

### 5.3 Status codes

- `200 OK` — success
- `400 Bad Request` — malformed input
- `404 Not Found` — missing resource
- `500 Internal Server Error` — uncaught (should never happen for the v1 endpoints)

No `3xx`, no `2xx other than 200`, no `401/403` (no auth).

## 6. Architecture

### 6.1 New files

```
translation_core/api.py                 # Flask Blueprint with all /api/v1/* endpoints
translation_core/openapi.py             # Static OpenAPI spec dict
templates/api/index.html                # GET /api/v1/ landing
templates/api/docs.html                 # GET /api/docs Swagger UI host page
tests/test_api_v1.py                    # pytest suite for the API
```

### 6.2 Modified files

```
app.py                  # register the new blueprint
ROADMAP.md              # move "API" from Sub-project 2 prerequisite into "Shipped"
README.md               # link to /api/v1/manifest + /api/docs
llms.txt                # mention the API surface
```

### 6.3 Blueprint shape

```python
# translation_core/api.py
from flask import Blueprint, jsonify, request, render_template, abort

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

@api_v1.after_request
def _apply_api_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    if response.status_code == 200:
        if request.path == "/api/v1/search":
            response.headers["Cache-Control"] = "public, max-age=300"
        else:
            response.headers["Cache-Control"] = "public, max-age=86400"
    return response

@api_v1.route("/alignment/<book>/<int:chapter>/<int:verse>")
def alignment(book, chapter, verse):
    ...

@api_v1.route("/verse/<book>/<int:chapter>/<int:verse>")
def verse_endpoint(book, chapter, verse):
    ...

@api_v1.route("/search")
def search():
    ...

@api_v1.route("/manifest")
def manifest():
    ...

@api_v1.route("/openapi.json")
def openapi():
    ...

@api_v1.route("/")
def index():
    return render_template("api/index.html")
```

Registered in `app.py`:

```python
from translation_core.api import api_v1
app.register_blueprint(api_v1)
```

The `/api/docs` route is a separate top-level route in `app.py` (not under the `/api/v1/` prefix) so the docs URL stays stable across API versions.

### 6.4 Locale-prefix middleware compatibility

The existing `_LocalePrefixMiddleware` strips `/<lang>/` prefixes before Flask routes the request. Since our API URLs are language-neutral (`/api/v1/...`), they don't have a language prefix — the middleware leaves them alone, exactly as it does for `/static/...` and `/sitemap.xml`. No middleware change needed.

If a client mistakenly hits `/es/api/v1/manifest`, the middleware would strip `/es/` → `/api/v1/manifest` and the request resolves correctly. Side-effect: localization of the API isn't possible by URL prefix, which is the right behavior for a data API.

## 7. Tests

`tests/test_api_v1.py`:

- `test_manifest_returns_corpus_metadata` — count of books, witnesses, verses; `api_version` field present
- `test_alignment_returns_canonical_json` — Mark 13:14 returns expected ref + alignment groups; schema_version present
- `test_alignment_404_for_unknown_book` — `/api/v1/alignment/luke/1/1` → 404 with `book_not_found`
- `test_alignment_404_for_unknown_verse` — `/api/v1/alignment/mark/99/99` → 404 with `verse_not_found`
- `test_verse_returns_converted_dict` — Mark 1:1 returns witnesses array of length 3; gloss_map keys = en/es/zh-Hans/zh-Hant
- `test_verse_gloss_map_has_all_4_langs` — every key non-empty for Mark 1:1 (since all four CSVs are loaded)
- `test_search_returns_envelope` — `/api/v1/search?q=evangelio` → JSON object with `items`, `count`, `query`, `api_version`
- `test_search_chapter_verse_jump` — `/api/v1/search?q=13:14` → 1 result of kind `reference`
- `test_search_empty_query_returns_empty_items` — `/api/v1/search` → `count: 0`
- `test_search_limit_bounds` — `?limit=200` is clamped to 100
- `test_openapi_json_validates` — OpenAPI 3.0 envelope present (`openapi: "3.0.x"`, `info`, `paths`)
- `test_cors_header_present` — every endpoint sets `Access-Control-Allow-Origin: *`
- `test_cache_header_long_for_alignment` — alignment endpoint emits `Cache-Control: public, max-age=86400`
- `test_cache_header_short_for_search` — search endpoint emits `Cache-Control: public, max-age=300`
- `test_api_index_html_renders` — `GET /api/v1/` returns 200 with text/html
- `test_docs_route_renders_swagger_shell` — `GET /api/docs` returns 200 with text/html and references `swagger-ui`
- `test_book_param_is_case_insensitive` — `/api/v1/alignment/Mark/1/1` resolves the same as lowercase

Target: ~16 new tests. Total suite goes from 118 → ~134 passing.

## 8. Open implementation questions

1. **Should `/api/v1/verse/{ref}` accept compact references like `mark/13/14` AS path or `?ref=Mark+13:14` as query?**
   Decision: path only, matching the alignment endpoint's style. Keeps URLs RESTful and cache-friendly.

2. **Should `/api/v1/search` paginate?**
   Decision: no, just a `limit` (max 100) with no offset. The corpus is 678 verses; max useful results for any query is bounded by the corpus, and the existing `/search` already breaks early at the limit. Pagination can be added in v2 if needed.

3. **Do we expose Greek/Peshitta enrichment (Strong's, lemmas, roots) as separate endpoints?**
   Decision: not in v1. The `verse` endpoint already includes Greek glosses via the `tokens[].gloss` field. A dedicated `/api/v1/strong/<num>` and `/api/v1/peshitta-root/<root>` is a clean v2 addition. Out of scope here.

4. **CORS for non-GET methods?**
   Decision: don't bother. v1 is GET-only; if/when we add write endpoints (Sub-project 2), they'll need their own CORS+auth story. Explicit denial via the `Access-Control-Allow-Methods: GET, OPTIONS` header is the right signal.

## 9. Migration / rollout

This is purely additive:

1. Existing HTML routes continue to work unchanged.
2. The existing `/search` endpoint stays where it is for `aligner.js` (the search palette) — `/api/v1/search` is a new endpoint that proxies to the same search index. Both work; we remove the old one only if/when we want to consolidate (not in this task).
3. No DB migrations; no breaking schema changes; alignment JSON files unchanged.
4. Render auto-deploy on push; no env var changes.
5. After merge, update `llms.txt` and the README to advertise the API.

## 10. Roadmap impact

After this lands:

- ROADMAP "Export" section: the existing line *"Individual verse JSON endpoints (already work at `/data/alignments/mark/<ch>/<v>.json`)"* — that overclaim needs to be replaced with the actual API endpoint. (The `/data/...` URL was never live; this task makes the equivalent claim true.)
- ROADMAP Sub-project 2 — Machine Annotation Engine: this v1 read-API is the foundation; Sub-project 2 adds a `POST /api/v1/align` for live alignment of off-corpus verses.
- New roadmap line item: *"API v2 — per-token enrichment endpoints (Strong's, lemma, Peshitta root, sister-roots)"* as a small follow-up.

---

**End of design.**
