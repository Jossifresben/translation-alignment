# Corpus changelog

This file documents every change to the published Mark alignment corpus
(`data/alignments/mark/`). Cite a specific corpus version when referencing
Polyglot Concordance data in scholarly or downstream work.

The current version is exposed via the API at:

- `GET /api/v1/manifest` → `corpus_version` field
- `data/alignments/CORPUS_VERSION` (single source of truth, read at startup)

Versioning scheme: `MAJOR.MINOR.PATCH`

- **MAJOR** — re-run of the entire corpus (new model, materially different prompt, schema migration)
- **MINOR** — partial regeneration (a chapter, a witness, an enrichment layer)
- **PATCH** — surgical edits to individual verses (typo fixes, scholar-flagged corrections,
  versification remaps, metadata adjustments)

---

## 1.0.0 — 2026-04-30 (first stable release)

First version with formal versioning. Captures the state of the corpus
after the methodology audit + scholar-flagged corrections of late April 2026.

### Provenance

- Model: `claude-sonnet-4-5` via Anthropic Messages Batch API
- Prompt: `scripts/prompts/align_3way.md` (published with the corpus)
- Generated: 2026-04-23
- Witnesses ingested: Greek NT (STEP Bible TAGNT), Syriac Peshitta (Aramaic Root Atlas), Latin Clementine Vulgate (seven1m/open-bibles USFX)
- Verse gloss editions ingested: WEB (English), RV 1909 (Spanish), CUV 1919 (Chinese Simplified + Traditional)
- Sanity check vs Berean Interlinear Bible: 67.7% Greek→English token agreement (see `docs/superpowers/specs/...` for details)
- Stability audit: 48% group-membership overlap vs Opus 4.5 (`docs/sonnet-vs-opus-mark13.md`); 65% same-model run-2 consensus (`docs/sonnet-consensus-mark.md`)

### Coverage

- 678 Mark verses
- 6,432 alignment groups
- 4,065 non-aligned divergences
- Mark 9 Vulgate versification remapped to NA28 boundaries
- CUV Simplified + Traditional Mark 7:16 and 15:28 recovered from USFX `<f>` footnote markup

### Patches applied in 1.0.0

These are scholar-flagged or self-audit-flagged corrections made between
the raw 2026-04-23 batch output and the 1.0.0 release.

#### Mark 13:14, variant `v3`

**Before**:
> "Peshitta inserts demonstrative pronoun ܐܬܐ ('sign/mark') before the construct chain..."

**Problem**: ܐܬܐ is a noun in Syriac (`'athā`, "sign"), not a demonstrative pronoun. The
gloss was right; the grammatical classification was wrong. Flagged in the
in-house methodology audit of 2026-04-30.

**After**:
> "Peshitta prepends the noun ܐܬܐ ('athā, 'sign')..."

#### Mark 1:1 — three apparatus errors caught in self-audit

Audited the demo verse for similar errors after the Mark 13:14 patch.
Three corrections, plus one out-of-scope limitation documented below.

**Group [1] (τοῦ εὐαγγελίου ↔ ܕܐܘܢܓܠܝܘܢ ↔ Evangelii)**

Original note claimed the Peshitta "uses construct state." Wrong: the
Peshitta uses the proclitic ܕ- (`d-`, the genitive/relative particle),
not construct state. Construct state in Syriac is a morphological form
of the noun itself before another noun (cf. Hebrew מַלְכוּת + Israel);
ܕ- is a different construction entirely. Rewrote the note.

**Group [3] (υἱοῦ ↔ ܒܪܗ ↔ Filii)**

Original verdict was `aligned` / type `agreement`. Wrong: the Peshitta
ܒܪܗ carries the 3ms possessive suffix -ܗ ("his son"), which the bare
Greek υἱοῦ and Latin Filii do not have. Reclassified as `minor` /
`expansion` with a new note.

**Group [4] (τοῦ θεοῦ ↔ ܕܐܠܗܐ ↔ Dei)**

Original note claimed "Syriac and Latin omit the article." Misleading:
Syriac does have a definiteness system (the emphatic state, suffix -ܐ),
and the Peshitta uses ܕ- (genitive proclitic) on ܐܠܗܐ (already in the
emphatic state). Saying the Syriac "omits the article" conflates the
Greek + Latin grammatical systems with the Syriac one. Rewrote.

### Out-of-scope limitation surfaced by the audit

**The apparatus is blind to inter-manuscript variants within a witness
tradition.** Mark 1:1 has a famous textual variant: "υἱοῦ τοῦ θεοῦ"
("Son of God") is omitted in important manuscripts (Sinaiticus,
original hand; some patristic citations). All three of our witnesses
include the phrase, so the pipeline sees no divergence and produces
no apparatus entry for it. But a human textual critic would expect
the apparatus to flag this — the absence of the variant is itself a
textual-criticism claim.

This is a structural limit of the current pipeline: it can describe
divergences *between* the three witnesses we ingest, but not
*within* any one witness's manuscript tradition. To address it
would require either ingesting multiple Greek manuscripts as
distinct witnesses (effectively turning the system into a multi-MS
collation, not a multi-translation alignment), or layering a
secondary "manuscript-variant" annotation step on top of the
alignment. Neither is in scope for v1.0.0.

This limit will be visible in the methodology section in a future patch.

### Known limitations of 1.0.0

- The apparatus is machine-generated and has not been peer-reviewed.
  Inter-run group-membership stability is ~65% (same model) / ~48% (cross-model).
- No formal error-rate measurement exists; the spot-check at Mark 13:14 found
  one classification error in 11 alignment groups (9% per-verse error rate, but
  N=1 verse so the population estimate is meaningless).
- Self-reported confidence scores are not calibrated against correctness.

---

## Format notes

Each release adds an entry above; entries are immutable once tagged.

Citation: *Polyglot Concordance Mark Corpus, version X.Y.Z. https://polyglotconcordance.com*
