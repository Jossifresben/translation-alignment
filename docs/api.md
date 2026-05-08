# Polyglot Concordance — API v1

Read-only public JSON access to the alignment data, search index, and corpus
manifest. The same artifacts that power the rendered HTML viewer are exposed
directly so scholars and downstream tools can fetch them without scraping HTML
or cloning the repo.

- **Base URL:** `https://polyglotconcordance.com/api/v1/`
- **Interactive docs:** [https://polyglotconcordance.com/api/docs](https://polyglotconcordance.com/api/docs) (Swagger UI)
- **OpenAPI 3.0 spec:** [https://polyglotconcordance.com/api/v1/openapi.json](https://polyglotconcordance.com/api/v1/openapi.json)
- **Auth:** none — public read-only data
- **CORS:** `Access-Control-Allow-Origin: *` on every response
- **Versioning:** path prefix `/api/v1/`; payloads include `"api_version": "v1"`
- **License (data):** CC BY 4.0 + public domain mix; redistribute with attribution to upstream sources
- **Rate limits:** none in v1; please be reasonable

---

## Quick start

```bash
# Discover the corpus
curl -s https://polyglotconcordance.com/api/v1/manifest | jq .

# Pull one verse's full alignment
curl -s https://polyglotconcordance.com/api/v1/alignment/mark/13/14 | jq .

# Just the apparatus notes for non-aligned groups
curl -s https://polyglotconcordance.com/api/v1/alignment/mark/13/14 \
  | jq '.alignment[] | select(.verdict != "aligned") | {id, verdict, type, note}'

# Search for a Greek lexeme across all witnesses
curl -s 'https://polyglotconcordance.com/api/v1/search?q=ὄχλος&limit=20' | jq '.items[].ref'

# Reference jump
curl -s 'https://polyglotconcordance.com/api/v1/search?q=13:14' | jq .
```

---

## Endpoints

| Method | Path | Returns |
|---|---|---|
| `GET` | [`/api/v1/`](https://polyglotconcordance.com/api/v1/) | Human-readable index (HTML) |
| `GET` | [`/api/v1/manifest`](https://polyglotconcordance.com/api/v1/manifest) | Corpus + API metadata |
| `GET` | [`/api/v1/alignment/{book}/{chapter}/{verse}`](https://polyglotconcordance.com/api/v1/alignment/mark/13/14) | Canonical alignment JSON |
| `GET` | [`/api/v1/verse/{book}/{chapter}/{verse}`](https://polyglotconcordance.com/api/v1/verse/mark/13/14) | Display-shape verse dict |
| `GET` | [`/api/v1/search`](https://polyglotconcordance.com/api/v1/search?q=harmonisation) | Verse-level search |
| `GET` | [`/api/v1/openapi.json`](https://polyglotconcordance.com/api/v1/openapi.json) | OpenAPI 3.0 spec |
| `GET` | [`/api/docs`](https://polyglotconcordance.com/api/docs) | Swagger UI |

---

### `GET /api/v1/manifest`

Corpus-level metadata. Hit this once to discover the scope: which books are
in the corpus, which (chapter, verse) tuples exist, which witnesses are
available, which gloss editions, the controlled vocabularies for variant
verdicts and types, and the alignment-generation provenance with the
benchmark statistics.

**Cache:** `public, max-age=86400`

**Response (abbreviated):**

```json
{
  "api_version": "v1",
  "project": "Polyglot Concordance",
  "description": "A concordance initiative with alignment to the word level — Mark across Greek NT, Syriac Peshitta, and Latin Clementine Vulgate, with AI-generated alignment and apparatus annotations on every divergence. A machine-generated alignment draft, intended as a starting point for scholar review rather than as an authoritative critical edition.",
  "license": "Code: open-source (intended). Derived alignment JSON: CC BY 4.0 + public domain mix; redistribute with attribution.",
  "schema_version": 1,
  "books": [
    {
      "id": "mark",
      "name": "Mark",
      "testament": "New Testament",
      "chapters": 16,
      "verse_count": 678,
      "verses": [[1, 1], [1, 2], "..."]
    }
  ],
  "witnesses": [
    {"id": "greek_nt", "sigil": "𝔊", "name": "Greek NT",          "script": "grc", "dir": "ltr", "source": "STEP Bible TAGNT (Tyndale House Cambridge)"},
    {"id": "peshitta", "sigil": "ℙ", "name": "Syriac Peshitta",    "script": "syr", "dir": "rtl", "source": "Aramaic Root Atlas corpus"},
    {"id": "vulgate",  "sigil": "𝔙", "name": "Clementine Vulgate", "script": "lat", "dir": "ltr", "source": "seven1m/open-bibles (USFX)"}
  ],
  "verse_glosses": [
    {"lang": "en",      "name": "English",  "edition": "World English Bible (WEB), public domain"},
    {"lang": "es",      "name": "Español",  "edition": "Reina-Valera 1909, public domain"},
    {"lang": "zh-Hans", "name": "简体中文",   "edition": "Chinese Union Version 1919 (Simplified), public domain"},
    {"lang": "zh-Hant", "name": "繁體中文",   "edition": "Chinese Union Version 1919 (Traditional), public domain"}
  ],
  "variant_verdicts": ["aligned", "minor", "major", "omitted", "added"],
  "variant_types":    ["agreement", "expansion", "omission", "substitution", "harmonisation",
                       "word-order", "construction", "idiom", "punctuation",
                       "grammar", "lexical", "gloss"],
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

---

### `GET /api/v1/alignment/{book}/{chapter}/{verse}`

The canonical on-disk alignment artifact for one verse. This is the source of
truth — the same JSON the Claude Sonnet 4.5 batch produced and the same JSON
the templates render from. Use this if you want to do textual-criticism
analysis on the variant graph itself.

**Path parameters:**
- `book` — `mark` (case-insensitive). 404 for any other value.
- `chapter` — integer (1–16 for Mark)
- `verse` — integer

**Cache:** `public, max-age=86400`

**Response 200 (abbreviated):**

```json
{
  "api_version": "v1",
  "ref": "Mark 13:14",
  "chapter": 13,
  "verse": 14,
  "traditions": {
    "greek_nt": {"tokens": ["Ὅταν", "δὲ", "ἴδητε", "..."]},
    "peshitta": {"tokens": ["..."]},
    "vulgate":  {"tokens": ["Cum", "autem", "videritis", "..."]}
  },
  "alignment": [
    {
      "id": "g1",
      "members": {"greek_nt": [0, 1], "peshitta": [0], "vulgate": [0, 1]},
      "verdict": "aligned",
      "type":    "agreement",
      "confidence": 0.95
    },
    {
      "id": "g7",
      "members": {"greek_nt": [], "peshitta": [9, 10, 11], "vulgate": []},
      "verdict": "added",
      "type":    "harmonisation",
      "note":    "The Peshitta inserts \"by Daniel the prophet\" — likely harmonisation with Matt 24:15.",
      "confidence": 0.92
    }
  ],
  "meta": {
    "generated_by":   "claude-sonnet-4-5",
    "generated_at":   "2026-04-23T...",
    "confidence":     0.91,
    "schema_version": 1
  }
}
```

**Response 404:**

```json
{ "error": { "code": "alignment_not_found", "message": "No alignment for Mark 99:99" } }
```

---

### `GET /api/v1/verse/{book}/{chapter}/{verse}`

The display-shape verse dict — the same object the rendered HTML viewer
consumes. Each witness has tokens with `align-IDs` and per-token variant
tags; variants are pulled out into a separate array; the multi-language
`gloss_map` carries the verse text in all four supported languages.

Use this when you want a single payload that gives you everything needed
to render or visualize a verse, without doing the alignment-group → witness-
column transposition yourself.

**Path parameters:** same as `alignment` endpoint.

**Cache:** `public, max-age=86400`

**Response 200 (abbreviated):**

```json
{
  "api_version": "v1",
  "ref":       "Mark 13:14",
  "book":      "Mark",
  "chapter":   13,
  "verse":     14,
  "pericope":  "The Abomination of Desolation",
  "testament": "New Testament",
  "witnesses": [
    {
      "id":       "grk",
      "sigil":    "𝔊",
      "name":     "Greek NT",
      "subtitle": "STEP TAGNT (NA28/Byzantine amalgamated)",
      "script":   "grc",
      "date":     "c. 70–90 CE",
      "dir":      "ltr",
      "tokens": [
        {"t": "Ὅταν", "a": "g1", "idx": 0},
        {"t": "δὲ",   "a": "g2", "idx": 1}
      ]
    }
    /* peshitta, vulgate witnesses follow */
  ],
  "variants": [
    {
      "id":         "v1",
      "type":       "harmonisation",
      "label":      "Peshitta + : by Daniel the prophet",
      "title":      [/* multi-witness title parts */],
      "summary":    "The Peshitta inserts \"by Daniel the prophet\"...",
      "witnesses":  ["syr"],
      "classes":    ["major"]
    }
  ],
  "gloss_map": {
    "en":      "But when you see the abomination of desolation...",
    "es":      "Pero cuando viereis la abominación de desolación...",
    "zh-Hans": "你们看见…那行毁坏可憎的...",
    "zh-Hant": "你們看見...那行毀壞可憎的..."
  },
  "prev": {"book": "mark", "chapter": 13, "verse": 13, "label": "Mk 13:13"},
  "next": {"book": "mark", "chapter": 13, "verse": 15, "label": "Mk 13:15"}
}
```

**Response 404:** `{"error": {"code": "verse_not_found", "message": "..."}}`

---

### `GET /api/v1/search`

Verse-level full-text search across all witnesses + variant types.

**Query parameters:**

| Name | Required | Default | Description |
|---|---|---|---|
| `q` | optional | `""` | Search string. Empty → empty result set. A `chapter:verse` reference (e.g. `13:14`) is treated as a jump and returns just that verse. |
| `limit` | optional | `25` | Max results (clamped to `[1, 100]`). |

**Cache:** `public, max-age=300` (shorter TTL since search results are query-keyed and may evolve as the corpus grows).

**Response 200:**

```json
{
  "api_version": "v1",
  "query": "ὄχλος",
  "count": 8,
  "items": [
    {
      "ref":        "Mark 5:21",
      "chapter":    5,
      "verse":      21,
      "snippet":    "...συνήχθη ὄχλος πολὺς...",
      "kind":       "greek",
      "matched_in": ["greek"]
    }
  ]
}
```

**Empty result:** `{"api_version": "v1", "query": "...", "count": 0, "items": []}`

**Error 400 (malformed `limit`):**

```json
{ "error": { "code": "bad_request", "message": "limit must be an integer" } }
```

---

### `GET /api/v1/openapi.json`

OpenAPI 3.0.3 spec describing the four data endpoints above. Suitable for:
- Generating typed clients (`openapi-generator`, `oapi-codegen`, etc.)
- Importing into Postman / Insomnia
- Rendering docs in any OpenAPI-aware tool

Available rendered as Swagger UI at [`/api/docs`](https://polyglotconcordance.com/api/docs).

---

## Conventions

### Versioning

- All endpoints live under `/api/v1/`. Future breaking changes will be released under `/api/v2/`.
- Every JSON response includes an `"api_version": "v1"` key for in-payload version awareness.
- The alignment artifact also carries `"meta.schema_version": 1` — that's the data-schema version, separate from the API version.

### Response envelope

- All endpoints return JSON objects (never bare arrays) so we can add metadata fields later without breaking consumers.
- List-bearing endpoints use `{"items": [...], "count": N, ...}`.

### Errors

```json
{ "error": { "code": "<machine_code>", "message": "<human-readable string>" } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `book_not_found` | 404 | The `book` path parameter isn't in the corpus |
| `verse_not_found` | 404 | The `(book, chapter, verse)` doesn't exist in the corpus |
| `alignment_not_found` | 404 | The verse exists in the corpus but the alignment file is missing |
| `bad_request` | 400 | Malformed query parameters (e.g. non-integer `limit`) |
| `internal_error` | 500 | Uncaught server error (logged; should never happen in v1) |

### CORS

`Access-Control-Allow-Origin: *` on every API response. Read-only public data;
any origin can fetch.

### Caching

| Endpoint | `Cache-Control` |
|---|---|
| `/api/v1/manifest`, `/alignment/...`, `/verse/...`, `/openapi.json` | `public, max-age=86400` |
| `/api/v1/search` | `public, max-age=300` |
| `/api/v1/` (HTML index) | `public, max-age=3600` |

Render's edge layer + Cloudflare absorb cache hits; the gunicorn origin
sees only one request per (URL, ~24 h) for the stable endpoints.

### Locale neutrality

The API is locale-neutral. There is no `/api/v1/es/...` prefix; the locale belongs to the rendered UI, not the data. The `/verse/{book}/{chapter}/{verse}` endpoint returns the multi-language `gloss_map` so callers can pick.

---

## Roadmap

What's not in v1 but is planned:

- **API v2 — per-token enrichment**
  - `GET /api/v2/strong/{number}` — Greek lemma + morphology + KJV/Berean glosses (sourced from STEP Bible TAGNT)
  - `GET /api/v2/peshitta-root/{root}` — Aramaic Root Atlas root card with sister roots + Hebrew / Arabic cognates
- **Bulk endpoints** — `GET /api/v2/alignment/mark` (the whole book in one ZIP/JSON-Lines) for downstream batch jobs
- **Sub-project 2 — Machine Annotation Engine** — `POST /api/v2/align` for live alignment of off-corpus verses (with auth + rate limits)

The roadmap also covers expanding book coverage (the rest of the NT, then the Hebrew Bible flagship) and witness coverage (English WEB as a 4th first-class column, Greek Byzantine, Coptic, the Orthodox Chinese cluster, etc.) — see [`ROADMAP.md`](../ROADMAP.md).

---

## Citing the data

If you use the alignment data in academic work, please cite:

> Fresco Benaim, J. (2026). *Polyglot Concordance — a concordance initiative with alignment to the word level: the Gospel of Mark across Greek NT, Syriac Peshitta, and Latin Clementine Vulgate.* https://polyglotconcordance.com (ORCID: 0009-0000-2026-0836)

A formal Zenodo DOI release is on the roadmap for the first stable corpus snapshot.

---

## Contact

[jossi@somosunodigital.com](mailto:jossi@somosunodigital.com) · ORCID [0009-0000-2026-0836](https://orcid.org/0009-0000-2026-0836)
