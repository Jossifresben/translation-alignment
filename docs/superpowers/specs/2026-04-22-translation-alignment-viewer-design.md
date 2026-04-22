# Translation Alignment Viewer — Sub-project 1 (MVP) Design

**Date:** 2026-04-22
**Status:** Draft — pending user review
**Scope:** This spec covers Sub-project 1 only (the parallel viewer). Sub-projects 2 (machine annotation engine) and 3 (scholar review workflow) are explicitly deferred and have their own future specs.

---

## 1. Summary

A focus-verse web viewer that displays the Gospel of Mark side-by-side in three traditions — Greek NT (SBLGNT), Peshitta (Syriac), and Clementine Vulgate (Latin) — with word-level alignment and Chen-style color-coded variant highlighting. Alignment data is pre-computed once via Claude and stored as static per-verse JSON. Greek-side enrichment (Strong's, lemma, morphology) is sourced from STEP Bible's tagged NT; Peshitta-side root tooltips reuse the Aramaic Root Atlas. A Berean Interlinear preflight benchmark is run once to produce a methodology credibility number published on the About page.

The viewer is read-only, server-rendered Flask + Jinja with htmx for per-verse swaps. No auth, no DB, no runtime LLM calls.

---

## 2. Scope

### In scope (MVP)

- Focus-verse reading mode — one verse per screen, three-column layout, variant underlines, commentary slot
- Three traditions: Greek NT (SBLGNT), Peshitta NT (Syriac), Clementine Vulgate
- One book: Mark (16 chapters, ~678 verses)
- Word-level alignment as static JSON, one file per verse
- Berean preflight benchmark (Greek↔English agreement rate) published on About page
- Greek-side tooltip enrichment from STEP TAGNT (Strong's, lemma, morph, gloss)
- Peshitta-side tooltip enrichment from ARA (root, sister roots, Hebrew/Arabic cognates)
- Prev/next navigation, jump-to-verse, keyboard shortcuts
- Reuse of ARA's base template, i18n (EN/ES/HE/AR), theme, RTL handling
- Deployment to Render.com free tier

### Out of scope (parked)

- Additional books beyond Mark
- Additional traditions (Slavonic, Coptic, Armenian, Chinese, etc.)
- Cross-family root-level diff (pilot is language-agnostic alignment only)
- Live machine annotation service (Sub-project 2)
- Scholar review queue / approvals / consensus (Sub-project 3)
- User accounts, authentication, roles
- TEI XML / BibTeX / CSV gold-standard export
- In-viewer alignment editing
- Authenticated API

### Success criteria

1. Viewer loads any verse in Mark in <500ms from Render
2. All 678 alignment JSONs are produced end-to-end by one repeatable script and reviewable as git diffs
3. Berean preflight benchmark publishes a single headline agreement rate on the About page
4. At least one sample chapter passes a sanity-check read by a human — no nonsensical alignments
5. Syriac RTL and Greek/Latin LTR render correctly on desktop and mobile, light and dark theme

---

## 3. Architecture

### 3.1 Repo layout

```
translation-alignment/
  app.py                            # Flask app, routes
  translation_core/                 # Python package, parallel to aramaic_core
    __init__.py
    corpora.py                      # Load/index CSVs by book/chapter/verse
    alignment.py                    # Load alignment JSON, lookup API
    enrichment.py                   # STEP Strong's + Peshitta root lookup
    rendering.py                    # Alignment JSON → HTML with variant markup
  templates/
    base.html                       # Copied/adapted from ARA (nav, i18n, theme, RTL)
    viewer.html                     # Full-page verse view (first load)
    _verse.html                     # htmx partial: verse card only
    about.html                      # Methodology + Berean benchmark result
    _tooltip_greek.html             # Strong's/lemma/morph tooltip partial
    _tooltip_peshitta.html          # Root/sister-roots tooltip partial
  static/
    style.css                       # ARA's CSS + alignment-specific additions
    viewer.js                       # Keyboard shortcuts, tooltip wiring, htmx hooks
    fonts/                          # Self-hosted Estrangelo Edessa WOFF2 for Syriac
  data/
    corpora/
      greek_nt.csv                  # From ARA
      peshitta_nt.csv               # From ARA
      vulgate.csv                   # New, ingested from Clementine source
    alignments/
      mark/
        1/1.json, 1/2.json, …       # 678 files
    enrichment/
      greek_strong.json             # Extracted from STEP TAGNT
      peshitta_roots.json           # Snapshot from ARA
    benchmarks/
      berean_preflight.json         # Agreement-rate result
    i18n.json                       # EN/ES/HE/AR UI strings
  scripts/
    ingest_vulgate.py               # One-time
    extract_step_enrichment.py      # One-time
    snapshot_ara_roots.py           # One-time
    run_berean_benchmark.py         # One-time
    generate_alignments.py          # Claude pre-compute, idempotent
  tests/
    test_data_validation.py
    test_routes.py
    test_rendering.py
  .env.example                      # Template (real .env is gitignored)
  .gitignore
  requirements.txt
  render.yaml                       # Render deploy config
  README.md
  QA_LOG.md                         # Manual QA notes
  known-issues.md                   # Alignments with residual quality concerns
```

### 3.2 Corpus CSV format

Follows the ARA convention verbatim — any tradition can be loaded this way:

```
book_order, book, chapter, verse, reference, text
42, Mark, 1, 1, "Mark 1:1", "Ἀρχὴ τοῦ εὐαγγελίου Ἰησοῦ Χριστοῦ…"
```

Greek and Peshitta CSVs are reused unchanged from ARA. Vulgate is ingested once by `scripts/ingest_vulgate.py`.

### 3.3 Alignment JSON schema

One file per verse at `data/alignments/mark/{chapter}/{verse}.json`:

```json
{
  "ref": "Mark 1:1",
  "chapter": 1,
  "verse": 1,
  "traditions": {
    "greek_nt":  { "tokens": ["Ἀρχὴ", "τοῦ", "εὐαγγελίου", "Ἰησοῦ", "Χριστοῦ", "υἱοῦ", "θεοῦ"] },
    "peshitta":  { "tokens": ["ܪܫܐ", "ܕܐܘܢܓܠܝܘܢ", "ܕܝܫܘܥ", "ܡܫܝܚܐ", "ܒܪܗ", "ܕܐܠܗܐ"] },
    "vulgate":   { "tokens": ["Initium", "evangelii", "Iesu", "Christi", "Filii", "Dei"] }
  },
  "alignment": [
    { "greek_nt": [0],    "peshitta": [0],    "vulgate": [0],    "variant": "aligned" },
    { "greek_nt": [1, 2], "peshitta": [1],    "vulgate": [1],    "variant": "minor" },
    { "greek_nt": [3, 4], "peshitta": [2, 3], "vulgate": [2, 3], "variant": "aligned" },
    { "greek_nt": [5, 6], "peshitta": [4, 5], "vulgate": [4, 5], "variant": "major",
      "note": "Post-classical genitive construction in Vulgate; word order shift in Peshitta" }
  ],
  "meta": {
    "generated_by": "claude-sonnet-4-6",
    "generated_at": "2026-04-22T10:00:00Z",
    "confidence": 0.87,
    "schema_version": 1
  }
}
```

**Variant vocabulary** (enum, exhaustive): `aligned`, `minor`, `major`, `omitted`, `added`.

**Absent traditions:** if a verse has no counterpart in one tradition, that tradition's entry becomes `{ "absent": true }` and that tradition is omitted from the `alignment` array.

**Token indexing:** integer indices into the tradition's `tokens` array. Multi-token spans are expressed by lists of indices (not ranges).

### 3.4 Routes

| Route | Purpose |
|---|---|
| `GET /` | Landing page with project intro; single CTA "Start reading Mark 1:1" |
| `GET /mark/<int:chapter>/<int:verse>` | Full viewer page (first load) |
| `GET /partials/verse/mark/<int:chapter>/<int:verse>` | htmx partial — verse card HTML only |
| `GET /about` | Methodology description + Berean benchmark number + attributions |
| `GET /data/alignments/mark/<int:ch>/<int:v>.json` | Raw JSON (debug/dev convenience) |

### 3.5 htmx flow

1. First load hits `GET /mark/1/1` → full HTML page (nav + verse card + commentary)
2. User presses `→` → JS triggers `hx-get="/partials/verse/mark/1/2"`, swaps the verse card `<article>`, `hx-push-url` updates browser URL to `/mark/1/2`
3. Back/forward browser buttons work naturally via `hx-push-url`
4. Network failure → fallback to full-page reload to the target URL

### 3.6 Component responsibilities

- `translation_core/corpora.py` — loads CSVs into memory on first call, indexed by `(book, chapter, verse)`; pure text retrieval
- `translation_core/alignment.py` — loads alignment JSON on demand, caches in memory, validates against schema
- `translation_core/enrichment.py` — lookup Strong's metadata for Greek tokens, root metadata for Peshitta tokens
- `translation_core/rendering.py` — single Jinja macro `render_verse_card(alignment_json)` that emits the 3-column HTML with `<span class="minor|major|…">` wrappers per token group
- `app.py` — thin route layer, orchestrates the above

---

## 4. Alignment generation pipeline

All offline, one-time, idempotent. Reproducible from source data + `ANTHROPIC_API_KEY`.

### 4.1 Inputs

- Greek NT (SBLGNT) — reused from ARA
- Peshitta NT — reused from ARA
- Clementine Vulgate — ingested once from a public-domain source (e.g. `BibleGet-I-O/Clementine-Vulgate` or Perseus Latin corpus)
- STEP Bible TAGNT — cloned from `github.com/STEPBible/STEPBible-Data`, CC BY 4.0
- Berean Interlinear — Greek↔English word alignment for Mark, from BibleHub/Berean open data

### 4.2 Pipeline steps

| Step | Script | Output |
|---|---|---|
| 1 | `ingest_vulgate.py` | `data/corpora/vulgate.csv` |
| 2 | `extract_step_enrichment.py` | `data/enrichment/greek_strong.json` |
| 3 | `snapshot_ara_roots.py` | `data/enrichment/peshitta_roots.json` |
| 4 | `run_berean_benchmark.py` | `data/benchmarks/berean_preflight.json` |
| 5 | `generate_alignments.py` | `data/alignments/mark/{ch}/{v}.json` × 678 |

Each script is idempotent — re-running regenerates only missing or stale outputs unless `--force` is passed.

### 4.3 Berean preflight benchmark

Before trusting Claude on Peshitta or Vulgate pairs (which have no scholarly alignment dataset), we validate Claude's methodology on the pair that does: Greek↔English.

1. Pull Berean Interlinear Greek↔English word alignment for Mark
2. Run Claude on `(greek_text, web_english_text)` verse-by-verse, asking only for Greek↔English alignment
3. Compare against Berean's word-level alignment
4. Metric: for each Greek token, does Claude's English target match Berean's? Compute percentage agreement across all tokens in Mark
5. Publish the single number on the About page — e.g. "Alignment methodology validated against Berean Interlinear at 92% agreement on Greek↔English (Mark, Claude Sonnet 4.6, 2026-04-22)"

### 4.4 3-way alignment generation

For each of Mark's ~678 verses:

1. Assemble context: Greek text, Peshitta text, Vulgate text, plus Greek Strong's and Peshitta roots as background
2. Prompt Claude with a strict JSON schema via structured output (tool use), temperature 0.1
3. Few-shot examples: 2–3 hand-curated alignments of representative Mark verses at the top of the prompt, cached via prompt caching
4. Validate response: token indices within bounds of each tradition's token array, variant enum valid, required fields present
5. On validation failure: one retry with stricter system prompt; on second failure, quarantine to `data/alignments/_quarantine/` for manual attention
6. Save to `data/alignments/mark/{ch}/{v}.json`
7. Bounded parallelism to respect Anthropic rate limits

### 4.5 Model and cost

- **Model:** Claude Sonnet 4.6 (`claude-sonnet-4-6`) via the Batch API (50% discount) — no Opus fallback; keep the pipeline uniform
- **Prompt caching:** system prompt + schema + few-shot examples are cached; per-verse inputs bust the cache
- **Estimated cost:** ~$4–9 one-time for the full Mark run (Batch + caching). Confirm with a 10-verse pilot before the full batch.
- **API key handling:** `ANTHROPIC_API_KEY` lives in `.env` (gitignored), read only by scripts, never referenced by the running Flask app

### 4.6 Quality loop

1. Run the 10-verse pilot synchronously to verify prompt behavior and measure tokens
2. Generate all remaining ~668 verses with Sonnet in batch
3. Filter verses where `confidence < 0.7` — flag these in `known-issues.md` as "manual review recommended" rather than re-running (Sonnet re-runs won't change the answer much; real improvement would require a different prompt or human edit)
4. Eyeball 10 random verses end-to-end (distributed across Mark)
5. Document residual weak spots in `known-issues.md` — transparency beats false polish

### 4.7 Failure modes and handling

| Failure | Handling |
|---|---|
| Verse missing in one tradition (e.g., text-critical gap) | Tradition marked `"absent": true` in JSON; alignment skips that pair |
| Claude returns invalid JSON | One retry with stricter prompt; on second failure, quarantine + log |
| Token index out of bounds | Same — quarantine path |
| Versification mismatch (NA28 vs Vulgate vs Peshitta chapter/verse numbering) | Mapping table sourced from STEP's `Versification/` folder; mismatches documented in `known-issues.md` |
| Rate limit hit | Script backs off exponentially and resumes |

---

## 5. Viewer UX

### 5.1 Layout

Focus-verse mode: one verse fills the screen.

- **Top nav:** book/chapter/verse picker (dropdowns), prev/next buttons, theme toggle, language switcher (EN/ES/HE/AR)
- **Verse card (`<article>`):** three columns (Greek / Peshitta / Vulgate), each with a tradition label, the verse text tokenized and wrapped with variant spans, and a small per-tradition metadata line (script direction marker)
- **Commentary slot:** human-readable variant notes pulled from the alignment JSON's `note` fields
- **Footer:** About/Methodology link, attribution (STEP Bible, ARA, SBLGNT)

### 5.2 Color coding

- `aligned` — no underline
- `minor` — green wavy underline (`text-decoration: underline wavy #4ade80`)
- `major` — red wavy underline (`text-decoration: underline wavy #f87171`)
- `omitted` / `added` — dotted underline + inline label icon (for colorblind accessibility)

### 5.3 Keyboard shortcuts

| Key | Action |
|---|---|
| `←` / `→` | Prev / next verse (htmx swap) |
| `j` / `k` | Next / prev chapter |
| `g` | Open jump-to-verse overlay (accepts "5:12" syntax) |
| `?` | Keyboard help overlay |
| `Esc` | Close any open overlay |

### 5.4 Tooltips (click, not hover)

- Greek word → Strong's number, lemma, morphology code, English gloss (from STEP)
- Peshitta word → root transliteration, sister roots (ARA's 2-of-3 consonant overlap), Hebrew/Arabic cognates
- Vulgate word → no tooltip in MVP (no enrichment layer yet)

Click-to-open (not hover) because hover tooltips are hostile on touch devices.

### 5.5 Internationalization

UI chrome supports EN/ES/HE/AR via ARA's `t()` pattern and `data/i18n.json`. Biblical text always displays in its source language. UI direction flips for HE/AR. Syriac column is always RTL regardless of UI language.

### 5.6 Accessibility

- Semantic HTML: `<article>` per verse card, `<section>` per column, `<nav>` for navigation
- Keyboard-first: no action requires a mouse
- Screen readers: `aria-describedby` on variant spans so "Filii Dei" reads as "Filii Dei — major variant"
- Color-blind safe: variant type always indicated by underline *style* (none / wavy-green / wavy-red / dotted), not color alone; icon/label supplements color
- High-contrast mode: underlines remain visible under both themes

---

## 6. Error handling

| Failure | Viewer behavior |
|---|---|
| Verse out of range in URL | 404 page with "verse not found" + link to nearest valid verse |
| Alignment JSON missing for a valid verse | Render text-only view with an "alignment pending" badge |
| Tradition marked `absent` in alignment JSON | Column shows italic placeholder "absent in this tradition" |
| Invalid chapter/verse format in URL | Redirect to Mark 1:1 with a flash message |
| htmx network failure | Fall back to a full-page reload to the target URL |
| Syriac font load failure | Fallback chain ending in self-hosted Estrangelo Edessa WOFF2 |

No runtime Claude API dependency — all alignments are static. The viewer has zero external runtime dependencies after deployment.

---

## 7. Testing strategy

Light testing, scoped to what actually protects the MVP.

1. **Data validation (`pytest`)** — every alignment JSON validates against the JSON schema; token indices within bounds; variant enum valid; all three traditions present or explicitly `absent`
2. **Route tests (Flask test client)** — `/`, `/mark/1/1`, `/partials/verse/mark/1/1`, `/about` return 200 with expected fragments; invalid URLs 404 or redirect correctly
3. **Rendering tests** — `render_verse_card` macro produces expected HTML for a fixture alignment JSON (snapshot comparison)
4. **Benchmark reproducibility** — `run_berean_benchmark.py` runs in CI against a fixed 20-verse sample and produces an agreement rate within ±2% of the recorded baseline
5. **Manual QA** — 10 random verses across Mark, desktop + mobile viewports, light + dark theme. Findings logged in `QA_LOG.md`.

No E2E browser tests for this MVP — a read-only Flask app with static JSON doesn't warrant the infrastructure. Visual regressions will surface immediately on Render.

---

## 8. Deployment

- **Host:** Render.com free tier (matches ARA's pattern)
- **Config:** `render.yaml` defining the Flask service
- **Dependencies** (`requirements.txt`): `flask`, `jinja2`, `python-dotenv` (dev), `anthropic` (dev-only, for scripts)
- **htmx:** loaded from CDN (`unpkg.com/htmx.org`) to avoid a build step
- **Data:** all CSVs + alignment JSONs + enrichment + benchmark results committed to the repo. Data is the source of truth; scripts regenerate it. Total <1MB for Mark.
- **Secrets:** `ANTHROPIC_API_KEY` in `.env` locally (gitignored) or Render env vars (only needed if alignment generation ever runs in CI). Not referenced by the running app.
- **Domain:** default `*.onrender.com` for MVP; custom domain optional later
- **Monitoring:** Render's built-in logs are sufficient

---

## 9. Parked / future work

Explicitly deferred to Sub-projects 2, 3, or a later Sub-project 1 iteration:

- Additional books beyond Mark
- Additional traditions (Slavonic, Coptic, Armenian, Chinese, English as a 4th column, Vulgate enrichment)
- Cross-family root-level diff engine
- Live machine annotation service with on-demand alignment (Sub-project 2)
- Scholar review queue, approvals, consensus-to-gold-standard flow (Sub-project 3)
- User accounts, roles (student / scholar / editor)
- TEI XML, BibTeX, CSV export
- In-viewer alignment editing
- Authenticated API
- Full-text search across traditions
- Side-by-side diff view for the same tradition across manuscripts (Byz vs NA28 vs TR)

---

## 10. Open risks and known caveats

| Risk | Mitigation |
|---|---|
| Vulgate public-domain source quality varies between Clementine editions | Pick one canonical source (`BibleGet-I-O/Clementine-Vulgate`), document the choice, stick with it |
| STEP repo is frozen at 2021; may have stale Strong's disambiguation | Document the data snapshot date in the About page; alignments are static anyway |
| Mark versification differs between NA28 / Vulgate / Peshitta (e.g., `Mrk.12.15`, `3.19`, `13.23`, `15.47`) | Use STEP's `Versification/` mapping tables; document remaining mismatches in `known-issues.md` |
| Claude alignment quality may be weaker on Peshitta than on Greek/Vulgate (morphology is more alien to training data) | Berean preflight is only a Greek↔English check — does NOT validate Peshitta quality; the honest framing in the About page must say so |
| Syriac font rendering inconsistent across browsers/OSes | Self-host Estrangelo Edessa WOFF2; test on macOS Safari, iOS, Windows Chrome, Firefox |
| ~$10 Claude cost estimate is based on token-count heuristics, not measurement | Run a 10-verse pilot first, measure actual token use, extrapolate |

---

## 11. Attribution (to be rendered on the About page)

- **Greek NT text:** SBLGNT (Society of Biblical Literature Greek New Testament), CC BY 4.0
- **Peshitta NT text:** [source used by ARA — verify exact provenance]
- **Clementine Vulgate text:** Public domain
- **Greek-side enrichment (Strong's, lemma, morphology):** STEP Bible / Tyndale House Cambridge, CC BY 4.0, via [github.com/STEPBible/STEPBible-Data](https://github.com/STEPBible/STEPBible-Data)
- **Peshitta root data:** Aramaic Root Atlas
- **Berean Interlinear (Greek↔English alignment benchmark):** BibleHub Berean, [license to verify]
- **Alignment methodology:** Generated by Anthropic Claude (Sonnet 4.6 primary, Opus 4.7 spot-check)
- **Viewer inspiration:** Prof. Zhang Chen (UIC), bible-mt5 parallel viewer

---

## 12. Decisions locked in this spec (for reference)

1. Launch shape: Pilot (1 book, 3 traditions, 1 pair has zero scholarly alignment)
2. Book + traditions: Mark — Greek NT + Peshitta + Clementine Vulgate
3. Alignment data source: Claude pre-compute, all three pairs, static JSON
4. Validation signal: Berean Greek↔English preflight benchmark (credibility claim, not in-viewer data)
5. Cross-family root diff: **skipped** for MVP; root data repurposed as within-tradition Peshitta study tooltip
6. Viewer pattern: **focus-verse mode** (B) as primary; no classic grid or stacked cards in MVP
7. Tech stack: Flask + Jinja + htmx; no SPA; no build step
