# Sonnet Consensus Corpus — Mark

Methodology audit + consensus subset of two independent Sonnet 4.5 runs.

## What this is

Two independent runs of the same prompt against the same input data, on
`claude-sonnet-4-5` via Batch API, produce alignment artifacts that often
disagree (see `docs/sonnet-vs-opus-mark13.md` for the cross-model audit).
This consensus corpus keeps only the alignment groups where **both runs
agree on the token-set partition** — i.e. both runs decided that the same
Greek tokens, Peshitta tokens, and Vulgate tokens belong together as a
single alignment group. For each kept group, we additionally record whether
the runs agree on the verdict (`aligned`/`minor`/`major`/`omitted`/`added`)
and the semantic type (`harmonisation`/`substitution`/...).

**The result is a smaller but more defensible corpus**: every group that
survives appears in two independent samples from the model. Groups that
only appeared in one run are dropped — they are exactly the unstable claims.

## Aggregate

| Metric | Value |
|---|---|
| Verses with both runs available | 660 |
| Verses that appear in only one run (dropped) | 18 |
| Run #1 (production) total groups | 6231 |
| Run #2 total groups | 6132 |
| Consensus groups (membership match) | 4067 |
| Consensus / run #1 | 65.3% |
| Consensus / run #2 | 66.3% |
| Of consensus groups: full variant agreement | 3491 (85.8%) |
| Of consensus groups: full type agreement | 2852 (70.1%) |

## How to read this

- **Consensus / run #1**: of the alignment groups in the original
  production corpus, how many survived the consensus filter. Groups
  unique to one run are unstable claims and were dropped.
- **Variant agreement**: of the groups that DID survive (both runs
  agreed on tokens), how often did they also agree on the verdict.
  Disagreement here is rare but real — a group both runs decided was
  the same alignment but disagreed on whether it's `aligned` or `minor`.
- **Type agreement**: same, for the semantic type field. Lower agreement
  (the type vocabulary has 12 categories, finer-grained than verdict).

## Distribution: variant agreement per verse

| Agreement ratio | Verses |
|---|---|
| 100% | 296 |
| 90% | 88 |
| 80% | 137 |
| 70% | 59 |
| 60% | 31 |
| 50% | 20 |
| 40% | 9 |
| 30% | 4 |
| 0% | 16 |

## Output layout

Each consensus verse JSON keeps the schema of the original alignment
artifacts but adds a `_consensus` block per group that records:
  - `runs_agree_variant`: did all runs assign the same verdict
  - `runs_agree_type`: did all runs assign the same type
  - `variants_per_run`, `types_per_run`: the per-run values

Top-level `meta` records `generated_by: 'consensus-of-N'` and the
contributing run identifiers.

## Practical use

- **For citation**: prefer the consensus subset over the single-run
  corpus. Each consensus group has been corroborated by an independent
  re-run, which is a weak but defensible reproducibility signal.
- **For review prioritization**: the groups that did NOT make consensus
  (only appearing in one run) are the natural target for human review.
  Roughly half the original corpus, focused on exactly the unstable claims.
- **For headline counts**: the production corpus reports 8,206 alignment
  groups; the consensus subset is substantially smaller. Cite both numbers
  honestly: "X consensus groups across Y verses, dropped from a single-run
  corpus of Z groups due to inter-run disagreement."
