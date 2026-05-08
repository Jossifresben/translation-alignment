# Session status — 2026-04-28

> Where to pick up tomorrow. Update or replace this file at the start of the next session.

## Live state

- **URL**: https://polyglotconcordance.com
- **Latest commit on `main`** (pushed): `cc82173` — *feat: same-model consensus corpus + correct alignment-group counts*
- **Render service**: `translation-aligner` (original; owns the custom domain). `polyglot-concordance` orphan was deleted earlier this session — only one service running, $7/mo.
- **Tests**: 138 passing. `pytest -q` from repo root, <1s.
- **Translations**: 4 languages (en/es/zh-Hans/zh-Hant), 221 keys each, full parity.

## What landed today

1. **Methodology critique** — harsh self-audit; the strongest objections were:
   - "Scholarly critical apparatus" overclaim
   - Self-confidence cited as quality signal but uncalibrated
   - 8,206-group count cited as if stable — actually run-dependent and the number itself was stale (real count: 6,432)
2. **Rhetorical fixes applied across all surfaces** (commit `c6f53c6`):
   - Replaced "scholarly critical apparatus" → "AI-generated alignment and apparatus annotations" / "machine-generated alignment draft, intended as a starting point for scholar review"
   - Disclaimed confidence in README + `/about`
   - Pedagogy bullet softened
3. **Stability audits** (data, methodology, and `docs/`):
   - Cross-model: Sonnet vs Opus on Mark 13 — `docs/sonnet-vs-opus-mark13.md`. 48% group-membership overlap, 71% verdict agreement.
   - Same-model: Sonnet × Sonnet on full Mark — `docs/sonnet-consensus-mark.md`. 65% group-membership overlap, 86% verdict agreement, 70% type agreement.
   - Conclusion: ~35% of every Sonnet run is noise; cross-model adds another ~17 pp on top of that.
4. **Consensus corpus**: 4,067 groups (vs 6,432 single-run) at `data/_compare/consensus/alignments/` — local-only, gitignored.
5. **Counts corrected** on home page + README: 8,206 → **6,432** alignment groups; ~2,600 → **4,065** non-aligned divergences.

## Local-only artifacts (gitignored)

- `data/_compare/sonnet_run2/alignments/` — full Sonnet re-run (660/678; 18 quarantined)
- `data/_compare/opus_mark13/alignments/` — Opus Mark 13 sample (36/37; Mark 13:24 quarantined)
- `data/_compare/consensus/alignments/` — consensus subset (intersection of two Sonnet runs)

If the next session needs to regenerate any of these:

```bash
# Opus Mark 13 (~$0.55)
PYTHONPATH=. python scripts/generate_alignments.py --full --model claude-opus-4-5 \
  --chapter 13 --out-root data/_compare/opus_mark13/alignments --force

# Second Sonnet run, full Mark (~$1.50)
PYTHONPATH=. python scripts/generate_alignments.py --full --model claude-sonnet-4-5 \
  --out-root data/_compare/sonnet_run2/alignments --force

# Consensus from existing two roots
PYTHONPATH=. python scripts/consensus_alignment.py \
  --root data/alignments \
  --root data/_compare/sonnet_run2/alignments \
  --book mark --out data/_compare/consensus/alignments \
  --report-md docs/sonnet-consensus-mark.md

# Sonnet vs Opus comparison report
PYTHONPATH=. python scripts/compare_sonnet_opus.py \
  --sonnet-root data/alignments \
  --opus-root data/_compare/opus_mark13/alignments \
  --chapter 13 --out docs/sonnet-vs-opus-mark13.md
```

## Cost ledger this session

- Opus Mark 13: ~$0.55
- Sonnet run #2 full Mark: ~$1.50
- **Total session API spend: ~$2**

## Open decisions / pending items

### Methodology / corpus

- **Should the consensus corpus be served via the API?** Currently local-only. Options:
  1. New endpoint `/api/v1/consensus/{book}/{ch}/{v}` (read from `data/_compare/consensus/alignments/`)
  2. Query flag `?consensus=true` on existing `/api/v1/alignment/...`
  3. Replace production corpus with consensus (loses verses where two runs disagreed entirely)
  4. Leave local-only until a third run is added (true majority-vote semantics with N≥3)

  My take: option 1 is cleanest — exposes both the full corpus and the consensus subset, lets downstream consumers pick. ~30 lines of code in `translation_core/api.py`. Defer until the user decides.

- **One-chapter human scholar review** is still the highest-leverage move per the critique. No action taken yet. Cheapest credible move: pick Mark 13, ask one textual critic to flag every error in every alignment group and apparatus note, publish the error rate. Need to identify the scholar.

- **Apparatus prose translation** to es/zh-Hans/zh-Hant (the ~2,600 non-aligned-group notes) is still deferred. Phase-2 Claude batch with field-aware prompt + scholar-reviewed sample.

### Strategic

- **Email to Chen**: draft exists in earlier session messages, ready to adapt. User hasn't sent yet. The subject paragraph used the "concordance initiative with alignment to the word level" framing borrowed from Chen.
- **Grant target**: still undefined (specific funder, amount, deadline, deliverables). High-priority gap.
- **License**: code stays private "until publicly funded." This is the policy that hurts open-data credibility most. Decision deferred.
- **Repo public flip**: GitHub repo `Jossifresben/translation-alignment` is private. The methodology audit makes a case for going public sooner — open methodology + open data is the credibility story.

### Product

- **Matthew ingestion** is the natural next book (per critique: "two books is a system; one is a demo"). Cost: ~$1.50 on Sonnet Batch via existing pipeline. Time: ~30 min wall clock. Pipeline already supports it.
- **Settings cog → Syriac font selection** is on the roadmap as next visible product polish. Tactical, not strategic.

## Files / locations to remember

| Path | What it is |
|---|---|
| `app.py` | Flask routes + WSGI locale middleware + before/after_request |
| `translation_core/api.py` | Public `/api/v1/` blueprint |
| `translation_core/openapi.py` | Hand-written OpenAPI 3.0 spec |
| `translation_core/i18n.py` | Translations class + Accept-Language parser |
| `translations/*.json` | All UI strings, 221 keys per language |
| `data/alignments/mark/` | Production corpus (Sonnet run #1, 678 verses, 6,432 groups) |
| `data/_compare/` | Local-only comparison runs (gitignored) |
| `docs/api.md` | Public API reference |
| `docs/sonnet-vs-opus-mark13.md` | Cross-model stability audit |
| `docs/sonnet-consensus-mark.md` | Same-model consensus methodology + results |
| `docs/superpowers/specs/` | Design specs (i18n, API v1) |
| `docs/superpowers/plans/` | Implementation plans |
| `scripts/generate_alignments.py` | Main alignment generator (Batch API + sync) |
| `scripts/compare_sonnet_opus.py` | Pairs two roots, emits Markdown disagreement report |
| `scripts/consensus_alignment.py` | N-way consensus filter, emits intersection corpus |
| `scripts/ingest_rv1909.py`, `ingest_cuv.py` | Verse-text gloss ingestion (eBible USFX → CSV) |

## Honest framing currently used in the product

> "A concordance initiative with alignment to the word level — the Gospel of Mark across three textual witnesses, with AI-generated alignment and apparatus annotations on every divergence. A machine-generated alignment draft, intended as a starting point for scholar review rather than as an authoritative critical edition."

(Same on `/`, `/about`, JSON-LD, llms.txt, README, manifest endpoint description, OpenAPI spec.)

## Karpathy guidelines are active

The session has been running with the Karpathy guidelines applied: think before coding, simplicity first, surgical changes, goal-driven execution with verifiable success criteria. Continue applying.

## Suggested first move tomorrow

Pick one:

1. **Send the Chen email** — costs nothing, gets the strongest external signal. Draft is in session history; can be re-rendered.
2. **Ship the consensus API endpoint** (~30 min of work) — surfaces the work already done. No new methodology risk.
3. **Ingest Matthew** — proves the pipeline scales, takes ~$1.50 + 30 min wall clock.
4. **Identify the scholar reviewer** for one-chapter human validation — highest-leverage methodology move per the critique.

If silent / no preference, default to (2) — it's the most concrete progress on already-shipped work.
